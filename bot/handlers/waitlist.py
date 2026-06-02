"""
Waitlist handler for BZD Bot.
Handles queue when tickets are not available - auto-purchase when tickets appear.
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.database import db
from bot.states.booking import WaitlistState
from bot.services.bzd_mock import BZDMockService
from bot.keyboards.reply import get_main_menu_keyboard
from bot.keyboards.inline import get_waitlist_cancel_keyboard, get_check_now_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("waitqueue_"))
async def join_train_waitlist(callback: CallbackQuery, state: FSMContext) -> None:
    """Join the queue for a specific sold-out train + wagon."""
    try:
        parts = callback.data.split("_")
        route_id = int(parts[1])
        wagon_number = int(parts[2])
        data = await state.get_data()
        date = data.get("date")
        routes = BZDMockService.search_routes(
            data.get("origin"), data.get("destination"), date
        )
        route = next((r for r in routes if r.id == route_id), None)
        wagon = next(
            (w for w in route.wagons if w.number == wagon_number), None
        ) if route else None
        if not route or not wagon or not date:
            await callback.answer("⚠️ Рейс не найден", show_alert=True)
            return

        await state.update_data(
            wl_route_id=route_id,
            wl_origin=route.origin,
            wl_destination=route.destination,
            wl_date=date,
            wl_wagon_type=wagon.type,
            wl_train_number=route.train_number,
        )
        await state.set_state(WaitlistState.entering_waitlist_name)
        await callback.message.edit_text(
            "📝 <b>Очередь на поезд №" + route.train_number + "</b>\n"
            "📍 " + route.origin + " → " + route.destination + "\n"
            "📅 " + date + "   🚃 " + wagon.type + "\n\n"
            "Введите ФИО пассажира (минимум 2 слова):"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in join_train_waitlist: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(WaitlistState.entering_waitlist_name)
async def waitlist_enter_name(message: Message, state: FSMContext) -> None:
    """Save passenger name and create the train-specific waitlist entry."""
    try:
        name = message.text.strip()
        if len(name.split()) < 2:
            await message.answer("❌ Введите полное ФИО (минимум имя и фамилия).")
            return
        data = await state.get_data()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (message.from_user.id,)
            )
            user_row = cursor.fetchone()
            user_id = user_row["id"] if user_row else None
            cursor.execute("""
                INSERT INTO waitlist (
                    user_id, route_id, origin, destination, date,
                    wagon_type, passenger_name, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting')
            """, (
                user_id, data["wl_route_id"], data["wl_origin"],
                data["wl_destination"], data["wl_date"],
                data["wl_wagon_type"], name
            ))
            waitlist_id = cursor.lastrowid
            conn.commit()
        await state.clear()
        await message.answer(
            "✅ <b>Вы в очереди!</b> (#" + str(waitlist_id) + ")\n\n"
            "🚂 №" + data["wl_train_number"] + "\n"
            "📍 " + data["wl_origin"] + " → " + data["wl_destination"] + "\n"
            "📅 " + data["wl_date"] + "   🚃 " + data["wl_wagon_type"] + "\n\n"
            "🔔 Как только место освободится, бот забронирует его и пришлёт "
            "ссылку на оплату. Для демонстрации можно проверить очередь вручную:",
            reply_markup=get_check_now_keyboard()
        )
        await message.answer(
            "Меню:", reply_markup=get_main_menu_keyboard()
        )
        logger.info(f"User {message.from_user.id} joined train waitlist #{waitlist_id}")
    except Exception as e:
        logger.error(f"Error in waitlist_enter_name: {e}")
        await message.answer("⚠️ Ошибка оформления очереди.")


@router.callback_query(F.data == "waitlist_check_now")
async def check_waitlist_now(callback: CallbackQuery) -> None:
    """Manually trigger the waitlist auto-purchase check (demo helper)."""
    try:
        from bot.services.scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler is None:
            await callback.answer("⚠️ Планировщик недоступен", show_alert=True)
            return
        purchased = await scheduler.check_waitlist_now()
        if purchased:
            await callback.answer(
                f"✅ Найдено мест: {purchased}! Проверьте уведомления.",
                show_alert=True
            )
        else:
            await callback.answer(
                "Пока свободных мест нет. Попробуйте позже.",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Error in check_waitlist_now: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data.regexp(r"^waitlist_\d+$"))
async def join_waitlist(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle joining waitlist when no tickets available."""
    try:
        data = await state.get_data()
        origin = data.get("origin")
        destination = data.get("destination")
        date = data.get("date")

        if not all([origin, destination, date]):
            await callback.answer("⚠️ Ошибка данных", show_alert=True)
            return

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (callback.from_user.id,)
            )
            user_row = cursor.fetchone()
            user_id = user_row["id"] if user_row else None

            cursor.execute("""
                INSERT INTO waitlist (user_id, origin, destination, date, status)
                VALUES (?, ?, ?, ?, 'waiting')
            """, (user_id, origin, destination, date))
            waitlist_id = cursor.lastrowid
            conn.commit()

        text = (
            "📝 <b>Вы встали в очередь ожидания!</b>\n\n"
            "📍 Маршрут: " + origin + " → " + destination + "\n"
            "📅 Дата: " + date + "\n\n"
            "🔔 Как только появится билет, бот автоматически:\n"
            "1. Забронирует место\n"
            "2. Отправит вам уведомление\n"
            "3. Вы сможете оплатить в течение 15 минут\n\n"
            "Место в очереди: #" + str(waitlist_id)
        )
        await callback.message.edit_text(text)
        await callback.message.answer(
            "Очередь оформлена!",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        logger.info(f"User {callback.from_user.id} joined waitlist #{waitlist_id}")

    except Exception as e:
        logger.error(f"Error in join_waitlist: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "search_again")
async def search_again(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to search from waitlist offer."""
    try:
        await state.clear()
        from bot.handlers.search import start_search
        await start_search(callback.message, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in search_again: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(F.text == "📝 Мои очереди")
async def show_user_waitlists(message: Message) -> None:
    """Show active waitlists for user."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (message.from_user.id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                await message.answer("❌ Вы не зарегистрированы. Используйте /start")
                return
            user_id = user_row["id"]
            cursor.execute("""
                SELECT id, origin, destination, date, status, created_at
                FROM waitlist
                WHERE user_id = ? AND status = 'waiting'
                ORDER BY created_at DESC
            """, (user_id,))
            waitlists = cursor.fetchall()

        if not waitlists:
            await message.answer(
                "📋 У вас нет активных очередей ожидания.\n"
                "Они создаются автоматически, когда билетов нет в наличии."
            )
            return

        await message.answer("📝 Ваши очереди ожидания:")
        for wl in waitlists:
            status_emoji = "⏳" if wl["status"] == "waiting" else "✅"
            text = (
                status_emoji + " <b>Очередь #" + str(wl["id"]) + "</b>\n"
                "📍 " + wl["origin"] + " → " + wl["destination"] + "\n"
                "📅 " + wl["date"] + "\n"
                "🕐 Создана: " + wl["created_at"][:10]
            )
            await message.answer(
                text,
                reply_markup=get_waitlist_cancel_keyboard(wl["id"])
            )
        await message.answer(
            "Проверить наличие мест прямо сейчас:",
            reply_markup=get_check_now_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in show_user_waitlists: {e}")
        await message.answer("⚠️ Ошибка загрузки очередей.")


@router.callback_query(F.data.startswith("waitlist_cancel_"))
async def cancel_waitlist(callback: CallbackQuery) -> None:
    """Cancel waitlist entry."""
    try:
        waitlist_id = int(callback.data.replace("waitlist_cancel_", ""))
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE waitlist SET status = 'cancelled' WHERE id = ?",
                (waitlist_id,)
            )
            conn.commit()
        await callback.message.edit_text(
            "❌ Очередь ожидания #" + str(waitlist_id) + " отменена."
        )
        await callback.answer("Очередь отменена")
    except Exception as e:
        logger.error(f"Error in cancel_waitlist: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)
