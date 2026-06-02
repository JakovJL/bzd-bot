"""
Help handler for BZD Bot.
Provides FAQ, support contacts, and command list.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline import get_help_keyboard
from bot.config import Config

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    try:
        help_text = (
            "❓ <b>Помощь</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Как купить билет?</b>\n"
            "1. Нажмите 🔍 Найти билет\n"
            "2. Выберите станции и дату\n"
            "3. Выберите поезд, вагон и место\n"
            "4. Введите данные пассажира\n"
            "5. Оплатите и получите PDF\n\n"
            "<b>Как вернуть билет?</b>\n"
            "В разделе 📋 Мои билеты нажмите ❌ Вернуть билет.\n"
            "Возврат возможен до отправления поезда.\n\n"
            "<b>Что делать, если оплата не прошла?</b>\n"
            "Попробуйте ещё раз или обратитесь в поддержку."
        )
        await message.answer(help_text, reply_markup=get_help_keyboard())
    except Exception as e:
        logger.error(f"Error in cmd_help: {e}")
        await message.answer("⚠️ Ошибка.")


@router.callback_query(F.data == "faq")
async def show_faq(callback: CallbackQuery) -> None:
    """Show FAQ."""
    try:
        faq_text = (
            "📖 <b>Частые вопросы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Q: Сколько стоит билет?</b>\n"
            "A: От 13.90 BYN (плацкарт) до 48 BYN (СВ).\n\n"
            "<b>Q: Можно ли выбрать место?</b>\n"
            "A: Да, при бронировании вы видите схему вагона.\n\n"
            "<b>Q: Нужна ли регистрация?</b>\n"
            "A: Да, при первом запуске бот запросит телефон.\n\n"
            "<b>Q: Какие документы нужны?</b>\n"
            "A: Паспорт РБ, загранпаспорт или свидетельство о рождении."
        )
        await callback.message.edit_text(faq_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_faq: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "commands")
async def show_commands(callback: CallbackQuery) -> None:
    """Show available commands."""
    try:
        commands_text = (
            "📋 <b>Команды бота</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "/start — Главное меню\n"
            "/help — Помощь\n"
            "/admin — Админ-панель (только админы)\n"
            "/cancel — Отменить текущее действие\n\n"
            "Также используйте кнопки меню для навигации."
        )
        await callback.message.edit_text(commands_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_commands: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data == "support")
async def support_request(callback: CallbackQuery) -> None:
    """Handle support request."""
    try:
        await callback.message.edit_text(
            "📝 <b>Связь с поддержкой</b>\n\n"
            "Опишите вашу проблему одним сообщением.\n"
            "Оно будет переслано администратору.\n\n"
            "(Функция в разработке — требует настройки пересылки)"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in support_request: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command — reset any active FSM flow."""
    from bot.keyboards.reply import get_main_menu_keyboard
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_main_menu_keyboard()
    )
