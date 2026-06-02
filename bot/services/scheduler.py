"""
Notification scheduler for BZD Bot.
Uses APScheduler to send trip reminders and auto-purchase from waitlist.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from bot.services.bzd_mock import BZDMockService

logger = logging.getLogger(__name__)

# Reference to the running scheduler so handlers can trigger a manual check.
_active_scheduler: Optional["NotificationScheduler"] = None


def get_scheduler() -> Optional["NotificationScheduler"]:
    """Return the currently running scheduler instance, if any."""
    return _active_scheduler


class NotificationScheduler:
    """Scheduler for sending trip notifications and auto-purchasing."""

    def __init__(self, bot_send_message: Callable) -> None:
        """
        Initialize scheduler.

        Args:
            bot_send_message: Async function to send messages via bot
        """
        self.scheduler = AsyncIOScheduler()
        self.bot_send_message = bot_send_message
        self._is_running = False

    def start(self) -> None:
        """Start the scheduler."""
        global _active_scheduler
        _active_scheduler = self
        if not self._is_running:
            # Trip reminders every 10 minutes
            self.scheduler.add_job(
                self._check_upcoming_trips,
                trigger=IntervalTrigger(minutes=10),
                id="trip_reminder",
                replace_existing=True
            )
            # Waitlist auto-purchase every 5 minutes
            self.scheduler.add_job(
                self._check_waitlist,
                trigger=IntervalTrigger(minutes=5),
                id="waitlist_checker",
                replace_existing=True
            )
            self.scheduler.start()
            self._is_running = True
            logger.info("Notification scheduler started.")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._is_running:
            self.scheduler.shutdown()
            self._is_running = False
            logger.info("Notification scheduler stopped.")

    async def _check_upcoming_trips(self) -> None:
        """Send 24h and 2h departure reminders for active paid tickets."""
        from bot.database import db
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.id, t.ticket_number, t.reminded_24h, t.reminded_2h,
                           o.train_number, o.travel_date, o.departure_time,
                           u.telegram_id
                    FROM tickets t
                    JOIN orders o ON t.order_id = o.id
                    JOIN users u ON o.user_id = u.id
                    WHERE t.is_active = 1 AND o.status = 'paid'
                      AND o.travel_date IS NOT NULL
                      AND o.departure_time IS NOT NULL
                """)
                tickets = cursor.fetchall()

            now = datetime.now()
            for ticket in tickets:
                departure = self._parse_departure(
                    ticket["travel_date"], ticket["departure_time"]
                )
                if departure is None:
                    continue
                hours_left = (departure - now).total_seconds() / 3600
                if hours_left <= 0:
                    continue

                if 0 < hours_left <= 2 and not ticket["reminded_2h"]:
                    await self.send_reminder(
                        ticket["telegram_id"], ticket["train_number"] or "",
                        ticket["departure_time"], hours_before=2
                    )
                    self._mark_reminded(ticket["id"], "reminded_2h")
                elif 0 < hours_left <= 24 and not ticket["reminded_24h"]:
                    await self.send_reminder(
                        ticket["telegram_id"], ticket["train_number"] or "",
                        ticket["departure_time"], hours_before=24
                    )
                    self._mark_reminded(ticket["id"], "reminded_24h")
        except Exception as e:
            logger.error(f"Error checking upcoming trips: {e}")

    @staticmethod
    def _parse_departure(travel_date: str, departure_time: str):
        """Combine 'YYYY-MM-DD' and 'HH:MM' into a datetime, or None."""
        try:
            return datetime.strptime(
                f"{travel_date} {departure_time}", "%Y-%m-%d %H:%M"
            )
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _mark_reminded(ticket_id: int, column: str) -> None:
        """Flag a reminder as sent (column is a trusted literal, not user input)."""
        from bot.database import db
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE tickets SET {column} = 1 WHERE id = ?", (ticket_id,)
            )
            conn.commit()

    async def check_waitlist_now(self) -> int:
        """Run the waitlist check on demand; return how many seats were booked."""
        return await self._check_waitlist()

    async def _check_waitlist(self) -> int:
        """Check waitlist and auto-purchase when seats appear. Returns booked count."""
        from bot.database import db
        purchased = 0
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT w.id, w.user_id, w.route_id, w.origin, w.destination,
                           w.date, w.wagon_type, w.preferred_seat,
                           w.passenger_name, w.document_type, w.document_number,
                           u.telegram_id
                    FROM waitlist w
                    JOIN users u ON w.user_id = u.id
                    WHERE w.status = 'waiting'
                    ORDER BY w.created_at ASC
                """)
                waitlist_entries = cursor.fetchall()

            for entry in waitlist_entries:
                routes = BZDMockService.search_routes(
                    entry["origin"], entry["destination"], entry["date"]
                )
                if not routes:
                    continue
                # Honor the specific train the user queued for, if recorded.
                route = None
                if entry["route_id"]:
                    route = next(
                        (r for r in routes if r.id == entry["route_id"]), None
                    )
                if route is None:
                    route = routes[0]

                for wagon in route.wagons:
                    if entry["wagon_type"] and wagon.type != entry["wagon_type"]:
                        continue
                    free_seat = next(
                        (s for s in range(1, wagon.total_seats + 1)
                         if s not in wagon.occupied_seats),
                        None
                    )
                    if free_seat is not None:
                        await self._auto_purchase(entry, route, wagon, free_seat)
                        purchased += 1
                        break
        except Exception as e:
            logger.error(f"Error checking waitlist: {e}")
        return purchased

    async def _auto_purchase(self, entry, route, wagon, seat) -> None:
        """Auto-create a pending order for a waitlist entry and DM a pay link."""
        from bot.database import db
        from bot.keyboards.inline import get_payment_keyboard
        try:
            passenger_name = entry["passenger_name"] or "Пассажир"
            doc_type = entry["document_type"] or "Паспорт РБ"
            doc_num = entry["document_number"] or "0000000"

            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orders (
                        user_id, route_id, train_number, train_name,
                        origin, destination, departure_time, arrival_time,
                        travel_date, wagon_type, wagon_number, seat_number,
                        passenger_name, document_type, document_number, price, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry["user_id"], route.id, route.train_number, route.name,
                    route.origin, route.destination,
                    route.departure_time, route.arrival_time, entry["date"],
                    wagon.type, wagon.number, seat,
                    passenger_name, doc_type, doc_num, wagon.price, "pending"
                ))
                order_id = cursor.lastrowid
                cursor.execute("""
                    UPDATE waitlist
                    SET status = 'notified', notified_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), entry["id"]))
                conn.commit()

            text = (
                "🎉 <b>Освободилось место — билет забронирован!</b>\n\n"
                "🚂 Поезд: №" + route.train_number + " «" + route.name + "»\n"
                "📍 " + route.origin + " → " + route.destination + "\n"
                "📅 Дата: " + entry["date"] + "\n"
                "🚃 " + wagon.type + ", вагон " + str(wagon.number) +
                ", место " + str(seat) + "\n"
                "💰 Цена: " + f"{wagon.price:.2f}" + " BYN\n\n"
                "⏳ У вас есть <b>15 минут</b> для оплаты:"
            )
            await self.bot_send_message(
                entry["telegram_id"], text, get_payment_keyboard(order_id)
            )
            logger.info(f"Auto-purchased order {order_id} for waitlist {entry['id']}")

        except Exception as e:
            logger.error(f"Error auto-purchasing: {e}")

    async def send_reminder(
        self, 
        user_id: int, 
        train_number: str, 
        departure_time: str,
        hours_before: int
    ) -> None:
        """Send a reminder message to user."""
        if hours_before == 24:
            message = (
                "🔔 <b>Напоминание!</b>\n\n"
                "Ваш поезд <b>№" + train_number + "</b> завтра в " + departure_time + ".\n"
                "Не забудьте билет и документы! 🎫"
            )
        elif hours_before == 2:
            message = (
                "🚂 <b>Пора выезжать на вокзал!</b>\n\n"
                "Поезд <b>№" + train_number + "</b> отправляется в " + departure_time + ".\n"
                "Удачной поездки! ✨"
            )
        else:
            message = (
                "🔔 Напоминание о поездке\n"
                "Поезд №" + train_number + ", отправление в " + departure_time
            )

        try:
            await self.bot_send_message(user_id, message)
            logger.info(f"Reminder sent to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send reminder to {user_id}: {e}")
