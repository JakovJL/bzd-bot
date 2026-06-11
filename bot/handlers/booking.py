"""
Booking handler for BZD Bot.
Handles wagon selection, seat selection, and passenger data input.
"""
import logging
import re
from typing import Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.states.booking import BookingState
from bot.models.route import Route
from bot.keyboards.inline import (
    get_wagon_types_keyboard, get_seats_keyboard,
    get_document_types_keyboard, get_payment_keyboard,
    get_sold_out_keyboard
)
from bot.services.bzd_mock import BZDMockService
from bot.services.availability import is_seat_free
from bot.database import db

logger = logging.getLogger(__name__)
router = Router()


def _route_for(data: dict) -> Optional[Route]:
    """Resolve the selected run with date-adjusted prices and live occupancy."""
    routes = BZDMockService.search_routes(
        data.get("origin"), data.get("destination"), data.get("date")
    )
    return next((r for r in routes if r.id == data.get("route_id")), None)


@router.callback_query(BookingState.selecting_train, F.data.startswith("train_"))
async def process_train_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle train selection, show wagon types."""
    try:
        route_id = int(callback.data.replace("train_", "").split("_")[0])
        await state.update_data(route_id=route_id)
        data = await state.get_data()
        route = _route_for(data)
        if not route:
            await callback.answer("⚠️ Рейс не найден", show_alert=True)
            return
        await state.update_data(
            train_number=route.train_number,
            train_name=route.name,
            departure_time=route.departure_time,
            arrival_time=route.arrival_time,
            origin=route.origin,
            destination=route.destination,
        )
        await state.set_state(BookingState.selecting_wagon_type)
        text = (
            "🚂 <b>№ " + route.train_number + " «" + route.name + "»</b>\n"
            "📍 " + route.origin + " → " + route.destination + "\n"
            "📅 " + data["date"] + "\n"
            "⏰ " + route.departure_time + " — " + route.arrival_time +
            " (" + route.duration + ")\n\n"
            "Выберите тип вагона:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_wagon_types_keyboard(route_id, route.wagons)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_train_selection: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(BookingState.selecting_train, F.data.startswith("train_info_"))
async def show_train_info(callback: CallbackQuery, state: FSMContext) -> None:
    """Show detailed info about a train run (alert)."""
    try:
        route_id = int(callback.data.replace("train_info_", ""))
        await state.update_data(route_id=route_id)
        data = await state.get_data()
        route = _route_for(data)
        if not route:
            await callback.answer("⚠️ Рейс не найден", show_alert=True)
            return
        lines = [
            f"🚂 №{route.train_number} «{route.name}»",
            f"📍 {route.origin} → {route.destination}",
            f"⏰ {route.departure_time}—{route.arrival_time} ({route.duration})",
            "",
        ]
        for w in route.wagons:
            free = w.total_seats - len(w.occupied_seats)
            lines.append(f"{w.type}: {w.price:.2f} BYN — свободно {free}/{w.total_seats}")
        await callback.answer("\n".join(lines), show_alert=True)
    except Exception as e:
        logger.error(f"Error in show_train_info: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(
    BookingState.selecting_wagon_type,
    F.data.startswith("wagon_")
)
async def process_wagon_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle wagon type selection, show seat map."""
    try:
        parts = callback.data.split("_")
        route_id = int(parts[1])
        wagon_type = parts[2]
        wagon_number = int(parts[3])
        data = await state.get_data()
        route = _route_for(data)
        wagon = next((w for w in route.wagons if w.type == wagon_type), None) if route else None
        if not wagon:
            await callback.answer("⚠️ Вагон не найден", show_alert=True)
            return
        await state.update_data(
            wagon_type=wagon_type,
            wagon_number=wagon.number,
            price=wagon.price
        )
        await state.set_state(BookingState.selecting_seat)
        free = wagon.total_seats - len(wagon.occupied_seats)
        if free == 0:
            text = (
                "🚃 <b>" + wagon_type + "</b> (вагон " + str(wagon.number) + ")\n"
                "😔 Все " + str(wagon.total_seats) + " мест выкуплены.\n\n"
                "🔔 Встаньте в очередь — как только место освободится, "
                "бот автоматически забронирует его и пришлёт вам ссылку на оплату."
            )
            await callback.message.edit_text(
                text,
                reply_markup=get_sold_out_keyboard(route_id, wagon.number)
            )
            await callback.answer()
            return
        text = (
            "🚃 <b>" + wagon_type + "</b> (вагон " + str(wagon.number) + ")\n"
            "💵 Цена: " + f"{wagon.price:.2f}" + " BYN\n"
            "🎫 Свободно: " + str(free) + " из " + str(wagon.total_seats) + "\n\n"
            "✅ — свободно | ❌ — занято\n"
            "Выберите место:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_seats_keyboard(
                route_id, wagon_type, wagon.number,
                wagon.total_seats, wagon.occupied_seats
            )
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_wagon_type: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(BookingState.selecting_seat, F.data == "back_to_wagons")
async def back_to_wagons(callback: CallbackQuery, state: FSMContext) -> None:
    """Return from seat map to wagon type selection."""
    try:
        data = await state.get_data()
        route = _route_for(data)
        if not route:
            await callback.answer("⚠️ Рейс не найден", show_alert=True)
            return
        await state.set_state(BookingState.selecting_wagon_type)
        text = (
            "🚂 <b>№ " + route.train_number + " «" + route.name + "»</b>\n"
            "📍 " + route.origin + " → " + route.destination + "\n\n"
            "Выберите тип вагона:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_wagon_types_keyboard(route.id, route.wagons)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_wagons: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(BookingState.selecting_seat, F.data.startswith("seat_"))
async def process_seat_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle seat selection."""
    try:
        parts = callback.data.split("_")
        route_id = int(parts[1])
        wagon_type = parts[2]
        wagon_number = int(parts[3])
        seat_number = int(parts[4])
        data = await state.get_data()
        if not is_seat_free(route_id, data.get("date"), wagon_number, seat_number):
            await callback.answer(
                "❌ Место уже занято! Выберите другое.",
                show_alert=True
            )
            return
        await state.update_data(seat_number=seat_number)
        await state.set_state(BookingState.entering_name)
        await callback.message.edit_text(
            "✅ Место <b>" + str(seat_number) + "</b> выбрано!\n\n"
            "Введите ФИО пассажира (минимум 2 слова):"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_seat_selection: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(BookingState.entering_name)
async def process_passenger_name(message: Message, state: FSMContext) -> None:
    """Validate and save passenger name."""
    try:
        name = message.text.strip()
        if len(name.split()) < 2:
            await message.answer(
                "❌ Введите полное ФИО (минимум имя и фамилия)."
            )
            return
        if not re.match(r'^[А-Яа-яЁёЎўІіA-Za-z\s-]+$', name):
            await message.answer(
                "❌ ФИО должно содержать только буквы."
            )
            return
        await state.update_data(passenger_name=name)
        await state.set_state(BookingState.entering_document_type)
        await message.answer(
            "✅ ФИО: <b>" + name + "</b>\n\n"
            "Выберите тип документа:",
            reply_markup=get_document_types_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in process_passenger_name: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.callback_query(
    BookingState.entering_document_type,
    F.data.startswith("doc_")
)
async def process_document_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle document type selection."""
    try:
        doc_type = callback.data.replace("doc_", "")
        await state.update_data(document_type=doc_type)
        await state.set_state(BookingState.entering_document_number)
        await callback.message.edit_text(
            "📄 Тип документа: <b>" + doc_type + "</b>\n\n"
            "Введите номер документа:"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_document_type: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(BookingState.entering_document_number)
async def process_document_number(message: Message, state: FSMContext) -> None:
    """Validate document number and ask for email."""
    try:
        doc_number = message.text.strip()
        if len(doc_number) < 4:
            await message.answer("❌ Номер документа слишком короткий.")
            return
        await state.update_data(document_number=doc_number)
        await state.set_state(BookingState.entering_email)
        await message.answer(
            "📧 Введите email для получения электронного билета:"
        )
    except Exception as e:
        logger.error(f"Error in process_document_number: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.message(BookingState.entering_email)
async def process_email(message: Message, state: FSMContext) -> None:
    """Validate email, create order, show summary."""
    try:
        email = message.text.strip().lower()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            await message.answer(
                "❌ Некорректный email. Введите email в формате user@example.com"
            )
            return
        await state.update_data(email=email)
        data = await state.get_data()

        # Guard against a seat taken while the user was typing.
        if not is_seat_free(
            data["route_id"], data["date"],
            data["wagon_number"], data["seat_number"]
        ):
            await state.set_state(BookingState.selecting_seat)
            await message.answer(
                "❌ Увы, место уже заняли, пока вы оформляли заказ.\n"
                "Используйте 🔍 Найти билет, чтобы выбрать другое."
            )
            return

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (message.from_user.id,)
            )
            user_row = cursor.fetchone()
            user_id = user_row["id"] if user_row else None
            cursor.execute("""
                INSERT INTO orders (
                    user_id, route_id, train_number, train_name,
                    origin, destination, departure_time, arrival_time, travel_date,
                    wagon_type, wagon_number, seat_number,
                    passenger_name, document_type, document_number,
                    email, price, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, data["route_id"], data["train_number"], data["train_name"],
                data["origin"], data["destination"],
                data["departure_time"], data["arrival_time"], data["date"],
                data["wagon_type"], data["wagon_number"], data["seat_number"],
                data["passenger_name"], data["document_type"],
                data["document_number"], email, data["price"], "pending"
            ))
            order_id = cursor.lastrowid
            conn.commit()
        await state.update_data(order_id=order_id)
        await state.set_state(BookingState.confirming_payment)
        summary = (
            "🧾 <b>ПОДТВЕРЖДЕНИЕ ЗАКАЗА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚂 <b>" + data['train_number'] + "</b> «" + data['train_name'] + "»\n"
            "📍 " + data['origin'] + " → " + data['destination'] + "\n"
            "📅 " + data['date'] + "   ⏰ " + data['departure_time'] +
            " — " + data['arrival_time'] + "\n"
            "🚃 " + data['wagon_type'] + ", вагон " + str(data['wagon_number']) +
            ", место " + str(data['seat_number']) + "\n"
            "👤 " + data['passenger_name'] + "\n"
            "📄 " + data['document_type'] + " №" + data['document_number'] + "\n"
            "📧 " + email + "\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💰 <b>К оплате: " + f"{data['price']:.2f}" + " BYN</b>"
        )
        await message.answer(summary, reply_markup=get_payment_keyboard(order_id))
    except Exception as e:
        logger.error(f"Error in process_email: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")
