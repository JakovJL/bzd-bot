"""
Inline keyboards for BZD Bot.
Used for selections, confirmations, and actions.
"""
from typing import List
from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.bzd_mock import STATIONS, BZDMockService
from bot.models.route import Route


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for language selection."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇧🇾 Белорусский", callback_data="lang_by")
    )
    return builder.as_markup()


def get_stations_keyboard(
    exclude: str = None,
    callback_prefix: str = "origin"
) -> InlineKeyboardMarkup:
    """
    Create station selection keyboard with custom input option.
    """
    builder = InlineKeyboardBuilder()
    stations = [s for s in STATIONS if s != exclude]

    for station in stations:
        builder.row(
            InlineKeyboardButton(
                text=station,
                callback_data=f"{callback_prefix}_{station}"
            )
        )

    # Add custom input button
    builder.row(
        InlineKeyboardButton(
            text="✏️ Ввести свою станцию",
            callback_data=f"{callback_prefix}_custom"
        )
    )
    return builder.as_markup()


def get_date_keyboard() -> InlineKeyboardMarkup:
    """Create date selection keyboard (next 7 days)."""
    builder = InlineKeyboardBuilder()
    today = datetime.now()

    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        display = date.strftime("%d.%m.%Y (%a)")
        builder.row(
            InlineKeyboardButton(text=display, callback_data=f"date_{date_str}")
        )
    return builder.as_markup()


def get_trains_keyboard(routes: List[Route]) -> InlineKeyboardMarkup:
    """Create train selection keyboard."""
    builder = InlineKeyboardBuilder()

    for route in routes:
        free_seats = sum(
            w.total_seats - len(w.occupied_seats)
            for w in route.wagons
        )
        text = f"🚂 {route.train_number} | {route.origin}->{route.destination}"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"train_{route.id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=f"💵 от {min(w.price for w in route.wagons):.2f} BYN | "
                     f"🎫 {free_seats} мест",
                callback_data=f"train_info_{route.id}"
            )
        )
    return builder.as_markup()


def get_wagon_types_keyboard(route_id: int, wagons: List) -> InlineKeyboardMarkup:
    """Create wagon type selection keyboard."""
    builder = InlineKeyboardBuilder()

    for wagon in wagons:
        free = wagon.total_seats - len(wagon.occupied_seats)
        text = f"{wagon.type} (вагон {wagon.number}) — {wagon.price:.2f} BYN"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"wagon_{route_id}_{wagon.type}_{wagon.number}"
            )
        )
    return builder.as_markup()


def get_seats_keyboard(
    route_id: int,
    wagon_type: str,
    wagon_number: int,
    total_seats: int,
    occupied: List[int],
    per_row: int = 6,
) -> InlineKeyboardMarkup:
    """Create a full seat map: every seat, free (✅) or taken (❌)."""
    builder = InlineKeyboardBuilder()
    occupied_set = set(occupied)

    row: list = []
    for seat in range(1, total_seats + 1):
        icon = "❌" if seat in occupied_set else "✅"
        row.append(
            InlineKeyboardButton(
                text=f"{icon}{seat:02d}",
                callback_data=f"seat_{route_id}_{wagon_type}_{wagon_number}_{seat}"
            )
        )
        if len(row) == per_row:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_wagons")
    )
    return builder.as_markup()


def get_document_types_keyboard() -> InlineKeyboardMarkup:
    """Create document type selection keyboard."""
    builder = InlineKeyboardBuilder()
    types = ["Паспорт РБ", "Загранпаспорт", "Свидетельство о рождении"]
    for doc_type in types:
        builder.row(
            InlineKeyboardButton(text=doc_type, callback_data=f"doc_{doc_type}")
        )
    return builder.as_markup()


def get_payment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Create payment confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="💳 Оплатить",
            callback_data=f"pay_{order_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"cancel_order_{order_id}"
        )
    )
    return builder.as_markup()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Create admin panel keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="🚂 Рейсы", callback_data="admin_routes")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="📋 Логи", callback_data="admin_logs")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Очереди ожидания", callback_data="admin_waitlist")
    )
    builder.row(
        InlineKeyboardButton(text="🎬 Демо: очередь", callback_data="admin_demo")
    )
    return builder.as_markup()


def get_demo_keyboard() -> InlineKeyboardMarkup:
    """Demo control panel: make a wagon sold out, free a seat, reset."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔴 Распродать вагон", callback_data="demo_fill")
    )
    builder.row(
        InlineKeyboardButton(text="🟢 Освободить 1 место", callback_data="demo_free")
    )
    builder.row(
        InlineKeyboardButton(text="🧹 Очистить демо-данные", callback_data="demo_clear")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")
    )
    return builder.as_markup()


def get_ticket_actions_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Create ticket action keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📄 Показать PDF",
            callback_data=f"pdf_{ticket_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Вернуть билет",
            callback_data=f"return_{ticket_id}"
        )
    )
    return builder.as_markup()


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Create help/support keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📝 Написать в поддержку",
            callback_data="support"
        )
    )
    builder.row(
        InlineKeyboardButton(text="📖 FAQ", callback_data="faq"),
        InlineKeyboardButton(text="📋 Команды", callback_data="commands")
    )
    return builder.as_markup()


def get_settings_keyboard(
    language: str, notifications_enabled: bool
) -> InlineKeyboardMarkup:
    """Settings screen keyboard with live toggle labels."""
    builder = InlineKeyboardBuilder()
    lang_label = "🇷🇺 Русский" if language == "ru" else "🇧🇾 Беларуская"
    notif_label = "🔔 Напоминания: вкл" if notifications_enabled else "🔕 Напоминания: выкл"
    builder.row(
        InlineKeyboardButton(text="🌐 Язык: " + lang_label, callback_data="settings_lang")
    )
    builder.row(
        InlineKeyboardButton(text=notif_label, callback_data="settings_notify")
    )
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="settings_profile")
    )
    return builder.as_markup()


def get_waitlist_keyboard(route_id: int) -> InlineKeyboardMarkup:
    """Create waitlist join keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📝 Встать в очередь ожидания",
            callback_data=f"waitlist_{route_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔍 Искать другой рейс",
            callback_data="search_again"
        )
    )
    return builder.as_markup()


def get_sold_out_keyboard(route_id: int, wagon_number: int) -> InlineKeyboardMarkup:
    """Keyboard shown when a wagon is fully booked: join queue or go back."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📝 Встать в очередь на этот вагон",
            callback_data=f"waitqueue_{route_id}_{wagon_number}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_wagons")
    )
    return builder.as_markup()


def get_check_now_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with a manual 'check the queue now' trigger (demo helper)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить очередь сейчас",
            callback_data="waitlist_check_now"
        )
    )
    return builder.as_markup()


def get_waitlist_cancel_keyboard(waitlist_id: int) -> InlineKeyboardMarkup:
    """Create waitlist cancel keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="❌ Покинуть очередь",
            callback_data=f"waitlist_cancel_{waitlist_id}"
        )
    )
    return builder.as_markup()
