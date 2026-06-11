"""
Payment handler for BZD Bot.
Multi-step card entry flow with simulated payment processing.
"""
import logging
import re
import uuid
import asyncio
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext

from bot.database import db
from bot.services.pdf_generator import PDFGenerator
from bot.services.qr_service import QRService
from bot.keyboards.reply import get_main_menu_keyboard
from bot.keyboards.inline import get_cancel_payment_keyboard
from bot.states.booking import BookingState

logger = logging.getLogger(__name__)
router = Router()


def _luhn_check(card_number: str) -> bool:
    """Validate card number using the Luhn algorithm."""
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) != 16:
        return False
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    return sum(digits) % 10 == 0


def _mask_card(number: str) -> str:
    """Return masked card number for display."""
    return "**** **** **** " + number[-4:]


@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """Start card entry flow."""
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
            await callback.answer("⚠️ Этот заказ уже обработан.", show_alert=True)
            return

        await state.update_data(order_id=order_id)
        await state.set_state(BookingState.entering_card_number)

        await callback.message.edit_text(
            "💳 <b>Оплата заказа</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💰 Сумма: <b>" + f"{order['price']:.2f}" + " BYN</b>\n\n"
            "Введите номер карты (16 цифр):",
            reply_markup=get_cancel_payment_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_payment: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(BookingState.entering_card_number)
async def process_card_number(message: Message, state: FSMContext) -> None:
    """Validate card number."""
    try:
        raw = message.text.strip().replace(" ", "")
        if not raw.isdigit() or len(raw) != 16:
            await message.answer(
                "❌ Номер карты должен содержать ровно 16 цифр.\n"
                "Введите номер карты:",
                reply_markup=get_cancel_payment_keyboard()
            )
            return
        if not _luhn_check(raw):
            await message.answer(
                "❌ Некорректный номер карты. Проверьте и введите снова:",
                reply_markup=get_cancel_payment_keyboard()
            )
            return

        await state.update_data(card_number=_mask_card(raw))
        await state.set_state(BookingState.entering_card_expiry)
        await message.answer(
            "✅ Номер карты: " + _mask_card(raw) + "\n\n"
            "Введите срок действия (MM/YY):",
            reply_markup=get_cancel_payment_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in process_card_number: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.message(BookingState.entering_card_expiry)
async def process_card_expiry(message: Message, state: FSMContext) -> None:
    """Validate card expiry date."""
    try:
        raw = message.text.strip().replace(" ", "")
        match = re.match(r'^(\d{2})/(\d{2})$', raw)
        if not match:
            await message.answer(
                "❌ Введите дату в формате MM/YY (например, 12/26):",
                reply_markup=get_cancel_payment_keyboard()
            )
            return

        month, year = int(match.group(1)), int(match.group(2))
        if month < 1 or month > 12:
            await message.answer(
                "❌ Неверный месяц. Введите MM/YY (01-12):",
                reply_markup=get_cancel_payment_keyboard()
            )
            return

        now = datetime.now()
        exp_year = 2000 + year
        if exp_year < now.year or (exp_year == now.year and month < now.month):
            await message.answer(
                "❌ Срок действия карты истёк. Введите актуальную дату MM/YY:",
                reply_markup=get_cancel_payment_keyboard()
            )
            return

        await state.update_data(card_expiry=raw)
        await state.set_state(BookingState.entering_card_cvv)
        await message.answer(
            "✅ Срок действия: " + raw + "\n\n"
            "Введите CVV (3 цифры с обратной стороны карты):",
            reply_markup=get_cancel_payment_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in process_card_expiry: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.message(BookingState.entering_card_cvv)
async def process_card_cvv(message: Message, state: FSMContext) -> None:
    """Validate CVV."""
    try:
        raw = message.text.strip()
        if not raw.isdigit() or len(raw) != 3:
            await message.answer(
                "❌ CVV должен содержать ровно 3 цифры:\n"
                "Введите CVV:",
                reply_markup=get_cancel_payment_keyboard()
            )
            return

        await state.update_data(card_cvv="***")
        await state.set_state(BookingState.entering_card_holder)
        await message.answer(
            "✅ CVV принят\n\n"
            "Введите имя держателя карты (латиница, как на карте):",
            reply_markup=get_cancel_payment_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in process_card_cvv: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.message(BookingState.entering_card_holder)
async def process_card_holder(message: Message, state: FSMContext) -> None:
    """Validate card holder name and process payment."""
    try:
        raw = message.text.strip().upper()
        if not re.match(r'^[A-Z\s.-]+$', raw) or len(raw.split()) < 2:
            await message.answer(
                "❌ Введите имя и фамилию латиницей, как на карте\n"
                "(например, IVAN IVANOV):",
                reply_markup=get_cancel_payment_keyboard()
            )
            return

        await state.update_data(card_holder=raw)
        data = await state.get_data()
        order_id = data.get("order_id")

        # Re-check order is still pending
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
        if not order or order["status"] != "pending":
            await message.answer(
                "⚠️ Заказ уже обработан или отменён.\n"
                "Используйте /start для нового поиска.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return

        await state.set_state(BookingState.processing_payment)

        # Simulated payment processing
        processing_msg = await message.answer("💳 <b>Обработка платежа...</b>")
        await asyncio.sleep(0.5)

        await processing_msg.edit_text(
            "💳 <b>Проверка карты...</b>\n"
            "🔄 Карта: " + data.get("card_number", "****") + "\n"
            "✅ CVV проверен"
        )
        await asyncio.sleep(1)

        await processing_msg.edit_text(
            "💳 <b>3D Secure...</b>\n"
            "🔄 Отправлен запрос подтверждения..."
        )
        await asyncio.sleep(2)

        await processing_msg.edit_text(
            "💳 <b>3D Secure...</b>\n"
            "✅ Подтверждение получено"
        )
        await asyncio.sleep(0.5)

        # Generate ticket
        transaction_id = str(uuid.uuid4())[:16].upper()
        ticket_number = "BZD-" + uuid.uuid4().hex[:8].upper()
        travel_date = order["travel_date"] or ""

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
            "💳 Карта: " + data.get("card_number", "****") + "\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📧 Билет отправлен на " + (order["email"] or "ваш email") + "\n"
            "📄 PDF-билет прикреплён ниже. Хорошей поездки! 🚂"
        )
        await processing_msg.edit_text(success_text)
        pdf_file = FSInputFile(pdf_path)
        await message.answer_document(
            pdf_file,
            caption="🎫 Ваш билет №" + ticket_number
        )
        await message.answer(
            "Что дальше?",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        logger.info("Payment successful for order " + str(order_id))
    except Exception as e:
        logger.error(f"Error in process_card_holder: {e}")
        await message.answer("⚠️ Ошибка оплаты. Попробуйте позже.")


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel payment during card entry."""
    try:
        await state.clear()
        await callback.message.edit_text(
            "❌ Оплата отменена.\n"
            "Используйте /start для нового поиска."
        )
        await callback.answer("Оплата отменена")
    except Exception as e:
        logger.error(f"Error in cancel_payment: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


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
