"""
Search handler for BZD Bot.
Handles route search: origin -> destination -> date -> train selection.
Also handles waitlist when no routes found.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states.booking import BookingState
from bot.keyboards.inline import (
    get_stations_keyboard, get_date_keyboard, get_trains_keyboard,
    get_waitlist_keyboard
)
from bot.services.bzd_mock import BZDMockService
from bot.database import db

logger = logging.getLogger(__name__)
router = Router()


async def start_search(message: Message, state: FSMContext) -> None:
    """Initiate ticket search flow."""
    try:
        await state.set_state(BookingState.selecting_origin)
        await message.answer(
            "🚂 Поиск билета\n\n"
            "Шаг 1/4: Выберите станцию отправления:",
            reply_markup=get_stations_keyboard(callback_prefix="origin")
        )
    except Exception as e:
        logger.error(f"Error in start_search: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.callback_query(BookingState.selecting_origin, F.data.startswith("origin_"))
async def process_origin(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle origin station selection."""
    try:
        origin = callback.data.replace("origin_", "")

        # Handle custom station input
        if origin == "custom":
            await state.set_state(BookingState.entering_custom_origin)
            await callback.message.edit_text(
                "✏️ Введите название станции отправления:\n"
                "(например: Минск-Пассажирский)"
            )
            await callback.answer()
            return

        await state.update_data(origin=origin)
        await state.set_state(BookingState.selecting_destination)
        text = "✅ Отправление: <b>" + origin + "</b>\n\nШаг 2/4: Выберите станцию назначения:"
        await callback.message.edit_text(
            text,
            reply_markup=get_stations_keyboard(
                exclude=origin,
                callback_prefix="dest"
            )
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_origin: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(BookingState.entering_custom_origin)
async def process_custom_origin(message: Message, state: FSMContext) -> None:
    """Handle custom origin station input."""
    try:
        origin = message.text.strip()
        if len(origin) < 3:
            await message.answer("❌ Название станции слишком короткое. Попробуйте ещё раз:")
            return
        await state.update_data(origin=origin)
        await state.set_state(BookingState.selecting_destination)
        await message.answer(
            "✅ Отправление: <b>" + origin + "</b>\n\n"
            "Шаг 2/4: Выберите станцию назначения:",
            reply_markup=get_stations_keyboard(
                exclude=origin,
                callback_prefix="dest"
            )
        )
    except Exception as e:
        logger.error(f"Error in process_custom_origin: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.callback_query(
    BookingState.selecting_destination,
    F.data.startswith("dest_")
)
async def process_destination(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle destination station selection."""
    try:
        destination = callback.data.replace("dest_", "")

        # Handle custom station input
        if destination == "custom":
            await state.set_state(BookingState.entering_custom_destination)
            await callback.message.edit_text(
                "✏️ Введите название станции назначения:\n"
                "(например: Брест-Центральный)"
            )
            await callback.answer()
            return

        await state.update_data(destination=destination)
        await state.set_state(BookingState.selecting_date)
        text = "✅ Маршрут: <b>" + destination + "</b>\n\nШаг 3/4: Выберите дату поездки:"
        await callback.message.edit_text(
            text,
            reply_markup=get_date_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_destination: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(BookingState.entering_custom_destination)
async def process_custom_destination(message: Message, state: FSMContext) -> None:
    """Handle custom destination station input."""
    try:
        destination = message.text.strip()
        if len(destination) < 3:
            await message.answer("❌ Название станции слишком короткое. Попробуйте ещё раз:")
            return
        data = await state.get_data()
        if destination == data.get("origin"):
            await message.answer("❌ Станция назначения не может совпадать с отправлением. Попробуйте ещё раз:")
            return
        await state.update_data(destination=destination)
        await state.set_state(BookingState.selecting_date)
        await message.answer(
            "✅ Маршрут: <b>" + destination + "</b>\n\n"
            "Шаг 3/4: Выберите дату поездки:",
            reply_markup=get_date_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in process_custom_destination: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.")


@router.callback_query(BookingState.selecting_date, F.data.startswith("date_"))
async def process_date(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle date selection and show available trains."""
    try:
        date = callback.data.replace("date_", "")
        await state.update_data(date=date)
        data = await state.get_data()
        origin = data["origin"]
        destination = data["destination"]
        routes = BZDMockService.search_routes(origin, destination, date)
        if not routes:
            # No routes found - offer waitlist
            await state.set_state(BookingState.selecting_train)
            text = (
                "😔 К сожалению, на выбранную дату рейсов не найдено.\n\n"
                "🔔 Вы можете встать в очередь ожидания — "
                "бот автоматически выкупит билет, когда он появится."
            )
            await callback.message.edit_text(
                text,
                reply_markup=get_waitlist_keyboard(0)
            )
            await callback.answer()
            return
        await state.set_state(BookingState.selecting_train)
        await state.update_data(routes=routes)
        text = "🚂 Найдено рейсов: " + str(len(routes)) + "\n\nШаг 4/4: Выберите поезд:\n\n"
        await callback.message.edit_text(
            text,
            reply_markup=get_trains_keyboard(routes)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_date: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)
