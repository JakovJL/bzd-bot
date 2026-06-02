"""
Reply keyboards for BZD Bot.
Used for main menu and contact sharing.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Create main menu keyboard.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔍 Найти билет"),
                KeyboardButton(text="📋 Мои билеты")
            ],
            [
                KeyboardButton(text="🕐 Расписание"),
                KeyboardButton(text="📝 Мои очереди")
            ],
            [
                KeyboardButton(text="⭐ Оставить отзыв"),
                KeyboardButton(text="⚙️ Настройки")
            ],
            [
                KeyboardButton(text="❓ Помощь"),
                KeyboardButton(text="📊 Статистика")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """
    Create keyboard with contact sharing button.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard
