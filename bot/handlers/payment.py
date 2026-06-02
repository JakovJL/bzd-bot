"""
Payment handler for BZD Bot.
Emulates payment processing and generates tickets.
"""
import logging
import uuid
import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from bot.database import db
from bot.services.pdf_generator import PDFGenerator
from bot.services.qr_service import QRService
from bot.keyboards.reply import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """Emulate payment processing."""
    try:
        order_id = int(callback.data.replace("pay_", ""))
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
        if not order:
            await callback.answer("⚠️ Заказ не найден", show_alert=True)
            return
        if order["status"] != "pending":
            await callback.answer(
                "⚠️ Этот заказ уже обработан.", show_alert=True
            )
            return

        await callback.message.edit_text(
            "💳 <b>Обработка платежа...</b>\n"
            "⏳ Пожалуйста, подождите..."
        )
        await asyncio.sleep(3)

        transaction_id = str(uuid.uuid4())[:16].upper()
        ticket_number = "BZD-" + uuid.uuid4().hex[:8].upper()
        travel_date = order["travel_date"] or ""

        # Generate ticket artefacts BEFORE committing payment, so a PDF
        # failure leaves the order 'pending' rather than 'paid without ticket'.
        qr_data = QRService.create_ticket_qr_data(
            ticket_number,
            order["train_number"] or "",
            travel_date,
            str(order["seat_number"])
        )
        pdf_path = PDFGenerator.generate_ticket(
            ticket_number=ticket_number,
            train_number=order["train_number"] or "",
            train_name=order["train_name"] or "",
            origin=order["origin"] or "",
            destination=order["destination"] or "",
            departure_time=order["departure_time"] or "",
            arrival_time=order["arrival_time"] or "",
            date=travel_date,
            wagon_type=order["wagon_type"],
            wagon_number=order["wagon_number"],
            seat_number=order["seat_number"],
            passenger_name=order["passenger_name"],
            document_type=order["document_type"],
            document_number=order["document_number"],
            price=order["price"]
        )

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders
                SET status = 'paid', transaction_id = ?
                WHERE id = ?
            """, (transaction_id, order_id))
            cursor.execute("""
                INSERT INTO tickets (order_id, ticket_number, pdf_path, qr_data)
                VALUES (?, ?, ?, ?)
            """, (order_id, ticket_number, pdf_path, qr_data))
            conn.commit()

        success_text = (
            "✅ <b>Оплата прошла успешно!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎫 Билет: <b>" + ticket_number + "</b>\n"
            "🚂 " + (order["train_number"] or "") + " «" + (order["train_name"] or "") + "»\n"
            "📍 " + (order["origin"] or "") + " → " + (order["destination"] or "") + "\n"
            "📅 " + travel_date + "   ⏰ " + (order["departure_time"] or "") + "\n"
            "🚃 " + order["wagon_type"] + ", вагон " + str(order["wagon_number"]) +
            ", место " + str(order["seat_number"]) + "\n"
            "💳 Транзакция: " + transaction_id + "\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📄 PDF-билет прикреплён ниже. Хорошей поездки! 🚂"
        )
        await callback.message.edit_text(success_text)
        pdf_file = FSInputFile(pdf_path)
        await callback.message.answer_document(
            pdf_file,
            caption="🎫 Ваш билет №" + ticket_number
        )
        await callback.message.answer(
            "Что дальше?",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        logger.info("Payment successful for order " + str(order_id))
    except Exception as e:
        logger.error(f"Error in process_payment: {e}")
        await callback.answer("⚠️ Ошибка оплаты", show_alert=True)


@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel pending order."""
    try:
        order_id = int(callback.data.replace("cancel_order_", ""))
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = 'cancelled' WHERE id = ?",
                (order_id,)
            )
            conn.commit()
        await callback.message.edit_text(
            "❌ Заказ отменён.\n"
            "Используйте /start для нового поиска."
        )
        await state.clear()
        await callback.answer("Заказ отменён")
    except Exception as e:
        logger.error(f"Error in cancel_order: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)
