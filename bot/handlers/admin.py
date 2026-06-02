"""
Admin handler for BZD Bot.
Provides admin panel with statistics, broadcasts, and logs.
"""
import logging
import os
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from bot.config import Config
from bot.database import db
from bot.keyboards.inline import (
    get_admin_keyboard, get_check_now_keyboard, get_demo_keyboard
)
from bot.services.bzd_mock import BZDMockService

logger = logging.getLogger(__name__)
router = Router()

# Demo target: a specific run + wagon used to stage the sold-out scenario.
# Filler orders are tagged by document_number so they can be cleaned up.
DEMO_ROUTE_ID = 1
DEMO_WAGON_TYPE = "СВ"
DEMO_DOC_TAG = "DEMO-FILL"


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in Config.ADMIN_IDS


def _demo_dates() -> list:
    """Dates shown in the search keyboard (today + next 6 days)."""
    today = datetime.now()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def _ensure_user(cursor, telegram_id: int) -> int:
    """Return the users.id for a telegram id, creating the row if needed."""
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    if row:
        return row["id"]
    cursor.execute(
        "INSERT INTO users (telegram_id, username) VALUES (?, ?)",
        (telegram_id, "demo")
    )
    return cursor.lastrowid


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Handle /admin command."""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("⛔ У вас нет доступа к админ-панели.")
            return
        await message.answer(
            "🔧 <b>Админ-панель</b>\n\n"
            "Выберите действие:",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in cmd_admin: {e}")
        await message.answer("⚠️ Ошибка.")


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery) -> None:
    """Show bot statistics."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            users_count = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM orders")
            orders_count = cursor.fetchone()["count"]
            cursor.execute("""
                SELECT COUNT(*) as count FROM orders WHERE status = 'paid'
            """)
            paid_orders = cursor.fetchone()["count"]
            cursor.execute("""
                SELECT SUM(price) as total FROM orders WHERE status = 'paid'
            """)
            revenue = cursor.fetchone()["total"] or 0
        stats_text = (
            "📊 <b>Статистика бота</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👥 Пользователей: " + str(users_count) + "\n"
            "📦 Всего заказов: " + str(orders_count) + "\n"
            "✅ Оплачено: " + str(paid_orders) + "\n"
            "💰 Выручка: " + f"{revenue:.2f}" + " BYN\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await callback.message.edit_text(stats_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_stats: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin_routes")
async def manage_routes(callback: CallbackQuery) -> None:
    """Show route management info."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        await callback.message.edit_text(
            "🚂 <b>Управление рейсами</b>\n\n"
            "Рейсы управляются через mock-сервис (bzd_mock.py).\n"
            "Для изменения — отредактируйте файл и перезапустите бота."
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in manage_routes: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin_broadcast")
async def broadcast_message(callback: CallbackQuery) -> None:
    """Show broadcast instructions."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        await callback.message.edit_text(
            "📢 <b>Рассылка</b>\n\n"
            "Отправьте сообщение, которое нужно разослать всем пользователям.\n"
            "(Функция в разработке — требует интеграции с рассылочным модулем)"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in broadcast_message: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin_waitlist")
async def show_waitlist(callback: CallbackQuery) -> None:
    """Show a summary of the current waiting queue."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT origin, destination, date, wagon_type,
                       passenger_name, created_at
                FROM waitlist
                WHERE status = 'waiting'
                ORDER BY created_at ASC
            """)
            rows = cursor.fetchall()
        if not rows:
            await callback.message.edit_text(
                "📋 <b>Очереди ожидания</b>\n\nОчередь пуста."
            )
            await callback.answer()
            return
        lines = [
            "📋 <b>Очереди ожидания</b> (" + str(len(rows)) + ")",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, r in enumerate(rows[:25], start=1):
            wagon = (" / " + r["wagon_type"]) if r["wagon_type"] else ""
            who = r["passenger_name"] or "—"
            lines.append(
                str(i) + ". " + r["origin"] + " → " + r["destination"] +
                " (" + r["date"] + wagon + ") — " + who
            )
        if len(rows) > 25:
            lines.append("… и ещё " + str(len(rows) - 25))
        await callback.message.edit_text(
            "\n".join(lines), reply_markup=get_check_now_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_waitlist: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery) -> None:
    """Return to the admin panel."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        await callback.message.edit_text(
            "🔧 <b>Админ-панель</b>\n\nВыберите действие:",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_back: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin_demo")
async def demo_menu(callback: CallbackQuery) -> None:
    """Show the demo control panel for the waitlist scenario."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        route = BZDMockService.get_route_by_id(DEMO_ROUTE_ID)
        await callback.message.edit_text(
            "🎬 <b>Демо: очередь на распроданный поезд</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Поезд №" + route.train_number + " «" + route.name + "»\n"
            "📍 " + route.origin + " → " + route.destination + "\n"
            "🚃 Вагон: " + DEMO_WAGON_TYPE + "\n\n"
            "<b>Порядок показа:</b>\n"
            "1. 🔴 Распродать вагон\n"
            "2. Найти этот рейс → вагон " + DEMO_WAGON_TYPE +
            " → «Встать в очередь» (ввести ФИО)\n"
            "3. 🟢 Освободить 1 место\n"
            "4. «🔄 Проверить очередь сейчас» — бот выкупит место",
            reply_markup=get_demo_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in demo_menu: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "demo_fill")
async def demo_fill(callback: CallbackQuery) -> None:
    """Mark the demo wagon as fully sold out across the bookable dates."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        route = BZDMockService.get_route_by_id(DEMO_ROUTE_ID)
        wagon = next(w for w in route.wagons if w.type == DEMO_WAGON_TYPE)
        dates = _demo_dates()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            user_id = _ensure_user(cursor, callback.from_user.id)
            # Reset previous filler so the wagon ends up exactly sold out.
            cursor.execute(
                "DELETE FROM orders WHERE document_number = ?", (DEMO_DOC_TAG,)
            )
            for date in dates:
                for seat in range(1, wagon.total_seats + 1):
                    cursor.execute("""
                        INSERT INTO orders (
                            user_id, route_id, train_number, train_name,
                            origin, destination, departure_time, arrival_time,
                            travel_date, wagon_type, wagon_number, seat_number,
                            passenger_name, document_type, document_number,
                            price, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid')
                    """, (
                        user_id, route.id, route.train_number, route.name,
                        route.origin, route.destination,
                        route.departure_time, route.arrival_time, date,
                        wagon.type, wagon.number, seat,
                        "Демо-бронь", "Паспорт РБ", DEMO_DOC_TAG, wagon.price
                    ))
            conn.commit()
        await callback.message.edit_text(
            "🔴 <b>Вагон распродан.</b>\n"
            "Поезд №" + route.train_number + ", вагон " + DEMO_WAGON_TYPE +
            " — все " + str(wagon.total_seats) + " мест заняты на " +
            str(len(dates)) + " дней.\n\n"
            "Теперь найдите рейс " + route.origin + " → " + route.destination +
            " и встаньте в очередь.",
            reply_markup=get_demo_keyboard()
        )
        await callback.answer("Готово")
    except Exception as e:
        logger.error(f"Error in demo_fill: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "demo_free")
async def demo_free(callback: CallbackQuery) -> None:
    """Free one filler seat so the queue can auto-purchase it."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders SET status = 'refunded'
                WHERE document_number = ? AND status = 'paid'
                  AND seat_number = (
                      SELECT MIN(seat_number) FROM orders o2
                      WHERE o2.document_number = ?
                        AND o2.status = 'paid'
                        AND o2.travel_date = orders.travel_date
                  )
            """, (DEMO_DOC_TAG, DEMO_DOC_TAG))
            freed = cursor.rowcount
            conn.commit()
        if freed:
            await callback.message.edit_text(
                "🟢 <b>Освобождено мест: " + str(freed) + "</b> "
                "(по одному на каждую дату).\n\n"
                "Теперь нажмите «🔄 Проверить очередь сейчас» — "
                "бот выкупит освободившееся место для очередника.",
                reply_markup=get_check_now_keyboard()
            )
            await callback.answer("Место освобождено")
        else:
            await callback.message.edit_text(
                "ℹ️ Нет занятых демо-мест. Сначала нажмите «🔴 Распродать вагон».",
                reply_markup=get_demo_keyboard()
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in demo_free: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "demo_clear")
async def demo_clear(callback: CallbackQuery) -> None:
    """Remove all demo filler orders."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM orders WHERE document_number = ?", (DEMO_DOC_TAG,)
            )
            removed = cursor.rowcount
            conn.commit()
        await callback.message.edit_text(
            "🧹 <b>Демо-данные очищены.</b>\nУдалено броней: " + str(removed) + ".",
            reply_markup=get_demo_keyboard()
        )
        await callback.answer("Очищено")
    except Exception as e:
        logger.error(f"Error in demo_clear: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery) -> None:
    """Show last 50 lines of log file."""
    try:
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        log_path = "logs/bot.log"
        if not os.path.exists(log_path):
            await callback.message.edit_text("📋 Лог-файл не найден.")
            await callback.answer()
            return
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        last_lines = lines[-50:] if len(lines) > 50 else lines
        log_text = "".join(last_lines)
        if len(log_text) > 4000:
            log_text = log_text[-4000:]
        await callback.message.edit_text(
            "📋 <b>Последние логи:</b>\n\n"
            "<pre>" + log_text + "</pre>"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_logs: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)
