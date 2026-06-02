"""Keyboards package for BZD Bot."""
from bot.keyboards.reply import get_main_menu_keyboard, get_contact_keyboard
from bot.keyboards.inline import (
    get_language_keyboard, get_stations_keyboard, get_date_keyboard,
    get_trains_keyboard, get_wagon_types_keyboard, get_seats_keyboard,
    get_document_types_keyboard, get_payment_keyboard, get_admin_keyboard,
    get_ticket_actions_keyboard, get_help_keyboard
)

__all__ = [
    "get_main_menu_keyboard", "get_contact_keyboard",
    "get_language_keyboard", "get_stations_keyboard", "get_date_keyboard",
    "get_trains_keyboard", "get_wagon_types_keyboard", "get_seats_keyboard",
    "get_document_types_keyboard", "get_payment_keyboard", "get_admin_keyboard",
    "get_ticket_actions_keyboard", "get_help_keyboard"
]
