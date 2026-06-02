"""
Start handler for BZD Bot.
Handles /start, language selection, registration, and main menu.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.database import db
from bot.keyboards.reply import get_main_menu_keyboard, get_contact_keyboard
from bot.keyboards.inline import get_language_keyboard, get_settings_keyboard

logger = logging.getLogger(__name__)
router = Router()


BZD_LOGO = """
╔═══════════════════════════════════════╗
║     БЕЛОРУССКАЯ ЖЕЛЕЗНАЯ ДОРОГА      ║
║         Belarusian Railway            ║
║          Беларуская чыгунка           ║
╚═══════════════════════════════════════╝
"""


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Handle /start command.
    Check if user exists, if not — start registration.
    """
    try:
        await state.clear()
        user_id = message.from_user.id
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (user_id,)
            )
            user = cursor.fetchone()
        if user:
            text = (
                BZD_LOGO + "\n"
                "👋 С возвращением, " + message.from_user.first_name + "!\n"
                "Выберите действие в меню ниже:"
            )
            await message.answer(
                text,
                reply_markup=get_main_menu_keyboard()
            )
        else:
            text = (
                BZD_LOGO + "\n"
                "👋 Добро пожаловать в билетный бот БЖД!\n\n"
                "🌍 Выберите язык / Абярыце мову:"
            )
            await message.answer(
                text,
                reply_markup=get_language_keyboard()
            )
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("lang_"))
async def process_language(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle language selection."""
    try:
        lang = callback.data.split("_")[1]
        await state.update_data(language=lang)
        greeting = (
            "Отлично! Теперь поделитесь номером телефона "
            "для завершения регистрации."
            if lang == "ru" else
            "Выдатна! Цяпер падзяліцеся нумарам тэлефона "
            "для завяршэння рэгістрацыі."
        )
        await callback.message.edit_text(greeting)
        await callback.message.answer(
            "📱 Нажмите кнопку ниже:",
            reply_markup=get_contact_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_language: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(F.contact)
async def process_contact(message: Message, state: FSMContext) -> None:
    """Handle contact sharing — complete registration."""
    try:
        data = await state.get_data()
        language = data.get("language", "ru")
        phone = message.contact.phone_number
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (telegram_id, username, phone, language)
                VALUES (?, ?, ?, ?)
            """, (
                message.from_user.id,
                message.from_user.username,
                phone,
                language
            ))
            conn.commit()
        welcome_text = (
            "✅ Регистрация завершена!\n"
            "Телефон: " + phone + "\n\n"
            "Теперь вы можете покупать билеты на поезда БЖД."
        )
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())
        await state.clear()
        logger.info("New user registered: " + str(message.from_user.id))
    except Exception as e:
        logger.error(f"Error in process_contact: {e}")
        await message.answer("⚠️ Ошибка регистрации. Попробуйте /start")


@router.message(F.text == "🔍 Найти билет")
async def menu_search(message: Message, state: FSMContext) -> None:
    """Handle 'Find ticket' menu button."""
    from bot.handlers.search import start_search
    await start_search(message, state)


@router.message(F.text == "📋 Мои билеты")
async def menu_tickets(message: Message) -> None:
    """Handle 'My tickets' menu button."""
    from bot.handlers.tickets import show_user_tickets
    await show_user_tickets(message)


@router.message(F.text == "📝 Мои очереди")
async def menu_waitlists(message: Message) -> None:
    """Handle 'My waitlists' menu button."""
    from bot.handlers.waitlist import show_user_waitlists
    await show_user_waitlists(message)


@router.message(F.text == "⭐ Оставить отзыв")
async def menu_review(message: Message, state: FSMContext) -> None:
    """Handle 'Leave review' menu button."""
    from bot.handlers.reviews import menu_review as review_handler
    await review_handler(message, state)


@router.message(F.text == "📊 Статистика")
async def menu_stats(message: Message) -> None:
    """Handle 'Statistics' menu button."""
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

            cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(price), 0) as total "
                "FROM orders WHERE user_id = ? AND status = 'paid'",
                (user_id,)
            )
            paid_row = cursor.fetchone()
            trips = paid_row["count"]
            spent = paid_row["total"] or 0

            cursor.execute(
                "SELECT COUNT(*) as count FROM tickets t "
                "JOIN orders o ON t.order_id = o.id "
                "WHERE o.user_id = ? AND t.is_active = 1",
                (user_id,)
            )
            active_tickets = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM waitlist "
                "WHERE user_id = ? AND status = 'waiting'",
                (user_id,)
            )
            queues = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM reviews WHERE user_id = ?",
                (user_id,)
            )
            reviews_count = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT origin, destination, COUNT(*) as cnt "
                "FROM orders WHERE user_id = ? AND status = 'paid' "
                "AND origin IS NOT NULL AND destination IS NOT NULL "
                "GROUP BY origin, destination ORDER BY cnt DESC LIMIT 1",
                (user_id,)
            )
            fav_row = cursor.fetchone()

            cursor.execute(
                "SELECT train_number, origin, destination, travel_date, departure_time "
                "FROM orders WHERE user_id = ? AND status = 'paid' "
                "AND travel_date >= date('now') "
                "ORDER BY travel_date ASC, departure_time ASC LIMIT 1",
                (user_id,)
            )
            next_row = cursor.fetchone()

        lines = [
            "📊 <b>Ваша статистика</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "🚂 Поездок (оплачено): " + str(trips),
            "🎫 Активных билетов: " + str(active_tickets),
            "💰 Потрачено: " + f"{spent:.2f}" + " BYN",
            "📝 В очередях: " + str(queues),
            "⭐ Оставлено отзывов: " + str(reviews_count),
        ]
        if fav_row and fav_row["cnt"] > 0:
            lines.append(
                "❤️ Любимое направление: " + fav_row["origin"] +
                " → " + fav_row["destination"] + " (" + str(fav_row["cnt"]) + ")"
            )
        if next_row:
            when = next_row["travel_date"] or ""
            if next_row["departure_time"]:
                when += " " + next_row["departure_time"]
            lines.append(
                "🗓 Ближайшая поездка: " + (next_row["train_number"] or "") +
                " " + (next_row["origin"] or "") + "→" + (next_row["destination"] or "") +
                " (" + when + ")"
            )
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        await message.answer("\n".join(lines))
    except Exception as e:
        logger.error(f"Error in menu_stats: {e}")
        await message.answer("⚠️ Ошибка загрузки статистики.")


@router.message(F.text == "❓ Помощь")
async def menu_help(message: Message) -> None:
    """Handle 'Help' menu button."""
    from bot.handlers.help import cmd_help
    await cmd_help(message)


def _render_settings(user_row) -> str:
    """Build the settings screen text from a users row."""
    lang = "Русский" if user_row["language"] == "ru" else "Беларуская"
    notif = "включены" if user_row["notifications_enabled"] else "выключены"
    return (
        "⚙️ <b>Настройки</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 Язык: <b>" + lang + "</b>\n"
        "🔔 Напоминания: <b>" + notif + "</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Нажмите на пункт, чтобы изменить."
    )


def _get_user_row(telegram_id: int):
    """Fetch a users row by telegram id (or None)."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        return cursor.fetchone()


@router.message(F.text == "⚙️ Настройки")
async def menu_settings(message: Message) -> None:
    """Handle 'Settings' menu button."""
    try:
        user_row = _get_user_row(message.from_user.id)
        if not user_row:
            await message.answer("❌ Вы не зарегистрированы. Используйте /start")
            return
        await message.answer(
            _render_settings(user_row),
            reply_markup=get_settings_keyboard(
                user_row["language"], bool(user_row["notifications_enabled"])
            )
        )
    except Exception as e:
        logger.error(f"Error in menu_settings: {e}")
        await message.answer("⚠️ Ошибка загрузки настроек.")


@router.callback_query(F.data == "settings_lang")
async def settings_toggle_language(callback: CallbackQuery) -> None:
    """Toggle UI language between RU and BY."""
    try:
        user_row = _get_user_row(callback.from_user.id)
        if not user_row:
            await callback.answer("⚠️ Не зарегистрированы", show_alert=True)
            return
        new_lang = "by" if user_row["language"] == "ru" else "ru"
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET language = ? WHERE telegram_id = ?",
                (new_lang, callback.from_user.id)
            )
            conn.commit()
        user_row = _get_user_row(callback.from_user.id)
        await callback.message.edit_text(
            _render_settings(user_row),
            reply_markup=get_settings_keyboard(
                user_row["language"], bool(user_row["notifications_enabled"])
            )
        )
        await callback.answer("Язык изменён")
    except Exception as e:
        logger.error(f"Error in settings_toggle_language: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "settings_notify")
async def settings_toggle_notify(callback: CallbackQuery) -> None:
    """Toggle trip reminders on/off."""
    try:
        user_row = _get_user_row(callback.from_user.id)
        if not user_row:
            await callback.answer("⚠️ Не зарегистрированы", show_alert=True)
            return
        new_value = 0 if user_row["notifications_enabled"] else 1
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET notifications_enabled = ? WHERE telegram_id = ?",
                (new_value, callback.from_user.id)
            )
            conn.commit()
        user_row = _get_user_row(callback.from_user.id)
        await callback.message.edit_text(
            _render_settings(user_row),
            reply_markup=get_settings_keyboard(
                user_row["language"], bool(user_row["notifications_enabled"])
            )
        )
        await callback.answer("Сохранено")
    except Exception as e:
        logger.error(f"Error in settings_toggle_notify: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "settings_profile")
async def settings_profile(callback: CallbackQuery) -> None:
    """Show the user's profile details."""
    try:
        user_row = _get_user_row(callback.from_user.id)
        if not user_row:
            await callback.answer("⚠️ Не зарегистрированы", show_alert=True)
            return
        username = user_row["username"] or "—"
        text = (
            "👤 <b>Профиль</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🆔 Telegram ID: " + str(user_row["telegram_id"]) + "\n"
            "🔖 Username: @" + username + "\n"
            "📱 Телефон: " + (user_row["phone"] or "—") + "\n"
            "📅 Регистрация: " + str(user_row["created_at"])[:10]
        )
        await callback.message.edit_text(text)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in settings_profile: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(F.text == "🕐 Расписание")
async def menu_schedule(message: Message) -> None:
    """Handle 'Schedule' menu button — pick origin station."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from bot.services.bzd_mock import STATIONS

    builder = InlineKeyboardBuilder()
    for idx, station in enumerate(STATIONS):
        builder.row(
            InlineKeyboardButton(text=station, callback_data=f"schedfrom_{idx}")
        )
    await message.answer(
        "🕐 <b>Расписание поездов</b>\n\nВыберите станцию отправления:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("schedfrom_"))
async def schedule_pick_destination(callback: CallbackQuery) -> None:
    """Schedule: choose destination after origin."""
    try:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        from bot.services.bzd_mock import STATIONS

        origin_idx = int(callback.data.replace("schedfrom_", ""))
        builder = InlineKeyboardBuilder()
        for idx, station in enumerate(STATIONS):
            if idx == origin_idx:
                continue
            builder.row(
                InlineKeyboardButton(
                    text=station, callback_data=f"schedto_{origin_idx}_{idx}"
                )
            )
        await callback.message.edit_text(
            "🕐 Отправление: <b>" + STATIONS[origin_idx] + "</b>\n\n"
            "Выберите станцию назначения:",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in schedule_pick_destination: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("schedto_"))
async def schedule_pick_date(callback: CallbackQuery) -> None:
    """Schedule: choose date after the direction is set."""
    try:
        from datetime import datetime, timedelta
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        from bot.services.bzd_mock import STATIONS

        _, origin_idx, dest_idx = callback.data.split("_")
        builder = InlineKeyboardBuilder()
        today = datetime.now()
        for d in range(7):
            day = today + timedelta(days=d)
            builder.row(
                InlineKeyboardButton(
                    text=day.strftime("%d.%m.%Y (%a)"),
                    callback_data=f"scheddate_{origin_idx}_{dest_idx}_{d}"
                )
            )
        await callback.message.edit_text(
            "🕐 " + STATIONS[int(origin_idx)] + " → " + STATIONS[int(dest_idx)] +
            "\n\nВыберите дату:",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in schedule_pick_date: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("scheddate_"))
async def schedule_show(callback: CallbackQuery) -> None:
    """Schedule: list all runs for the chosen direction and date."""
    try:
        from datetime import datetime, timedelta
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        from bot.services.bzd_mock import STATIONS, BZDMockService

        _, origin_idx, dest_idx, day_off = callback.data.split("_")
        origin = STATIONS[int(origin_idx)]
        destination = STATIONS[int(dest_idx)]
        date = (datetime.now() + timedelta(days=int(day_off))).strftime("%Y-%m-%d")

        routes = BZDMockService.search_routes(origin, destination, date)
        if not routes:
            await callback.message.edit_text(
                "🕐 " + origin + " → " + destination + "\n📅 " + date + "\n\n"
                "😔 На эту дату прямых рейсов нет."
            )
            await callback.answer()
            return

        lines = [
            "🕐 <b>Расписание</b>",
            "📍 " + origin + " → " + destination,
            "📅 " + date,
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for r in routes:
            free = sum(w.total_seats - len(w.occupied_seats) for w in r.wagons)
            price_from = min(w.price for w in r.wagons)
            lines.append(
                "🚂 <b>№" + r.train_number + "</b> «" + r.name + "»\n"
                "⏰ " + r.departure_time + " — " + r.arrival_time +
                " (" + r.duration + ")\n"
                "💵 от " + f"{price_from:.2f}" + " BYN · 🎫 свободно " + str(free)
            )
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("Чтобы купить билет — нажмите 🔍 Найти билет.")

        builder = InlineKeyboardBuilder()
        for r in routes:
            builder.row(
                InlineKeyboardButton(
                    text="⭐ Отзывы: №" + r.train_number,
                    callback_data=f"revview_{r.id}"
                )
            )
        await callback.message.edit_text(
            "\n\n".join(lines), reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in schedule_show: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)
