"""
Tickets handler for BZD Bot.
Shows user tickets, history, and handles returns.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile

from bot.database import db
from bot.keyboards.inline import get_ticket_actions_keyboard
from bot.keyboards.reply import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


async def show_user_tickets(message: Message) -> None:
    """Show active tickets for the user."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (message.from_user.id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                await message.answer(
                    "❌ Вы не зарегистрированы. Используйте /start"
                )
                return
            user_id = user_row["id"]
            cursor.execute("""
                SELECT t.id, t.ticket_number, t.pdf_path, t.is_active,
                       o.train_number, o.train_name, o.origin, o.destination,
                       o.travel_date, o.departure_time, o.arrival_time,
                       o.wagon_type, o.wagon_number,
                       o.seat_number, o.passenger_name, o.price, o.status
                FROM tickets t
                JOIN orders o ON t.order_id = o.id
                WHERE o.user_id = ? AND t.is_active = 1
                ORDER BY t.created_at DESC
            """, (user_id,))
            tickets = cursor.fetchall()
        if not tickets:
            await message.answer(
                "📋 У вас нет активных билетов.\n"
                "Используйте 🔍 Найти билет для покупки."
            )
            return
        await message.answer("📋 Ваши билеты (" + str(len(tickets)) + "):")
        for ticket in tickets:
            status_emoji = "✅" if ticket["status"] == "paid" else "⏳"
            route_line = ""
            if ticket["origin"] and ticket["destination"]:
                route_line = "📍 " + ticket["origin"] + " → " + ticket["destination"] + "\n"
            when_line = ""
            if ticket["travel_date"]:
                when_line = "📅 " + ticket["travel_date"]
                if ticket["departure_time"]:
                    when_line += "   ⏰ " + ticket["departure_time"]
                when_line += "\n"
            text = (
                status_emoji + " <b>Билет №" + ticket['ticket_number'] + "</b>\n"
                "🚂 №" + (ticket['train_number'] or "—") +
                (" «" + ticket['train_name'] + "»" if ticket['train_name'] else "") + "\n"
                + route_line + when_line +
                "🚃 " + ticket['wagon_type'] + ", вагон " + str(ticket['wagon_number']) + ", "
                "место " + str(ticket['seat_number']) + "\n"
                "👤 " + ticket['passenger_name'] + "\n"
                "💰 " + f"{ticket['price']:.2f}" + " BYN"
            )
            await message.answer(
                text,
                reply_markup=get_ticket_actions_keyboard(ticket["id"])
            )
    except Exception as e:
        logger.error(f"Error in show_user_tickets: {e}")
        await message.answer("⚠️ Ошибка загрузки билетов.")


@router.callback_query(F.data.startswith("pdf_"))
async def show_pdf(callback: CallbackQuery) -> None:
    """Send PDF ticket file."""
    try:
        ticket_id = int(callback.data.replace("pdf_", ""))
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pdf_path, ticket_number FROM tickets WHERE id = ?",
                (ticket_id,)
            )
            ticket = cursor.fetchone()
        if not ticket or not ticket["pdf_path"]:
            await callback.answer("⚠️ PDF не найден", show_alert=True)
            return
        pdf_file = FSInputFile(ticket["pdf_path"])
        await callback.message.answer_document(
            pdf_file,
            caption="🎫 Билет №" + ticket['ticket_number']
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_pdf: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("return_"))
async def return_ticket(callback: CallbackQuery) -> None:
    """Handle ticket return."""
    try:
        ticket_id = int(callback.data.replace("return_", ""))
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.order_id, t.ticket_number, o.price
                FROM tickets t
                JOIN orders o ON t.order_id = o.id
                WHERE t.id = ?
            """, (ticket_id,))
            ticket = cursor.fetchone()
            if not ticket:
                await callback.answer("⚠️ Билет не найден", show_alert=True)
                return
            cursor.execute(
                "UPDATE tickets SET is_active = 0 WHERE id = ?",
                (ticket_id,)
            )
            cursor.execute(
                "UPDATE orders SET status = 'refunded' WHERE id = ?",
                (ticket["order_id"],)
            )
            conn.commit()
        await callback.message.edit_text(
            "✅ Билет №" + ticket['ticket_number'] + " возвращён.\n"
            "💰 Возврат: " + f"{ticket['price']:.2f}" + " BYN\n"
            "(Эмуляция — в реальности требуется API БЖД)"
        )
        await callback.answer("Билет возвращён")
    except Exception as e:
        logger.error(f"Error in return_ticket: {e}")
        await callback.answer("⚠️ Ошибка возврата", show_alert=True)
