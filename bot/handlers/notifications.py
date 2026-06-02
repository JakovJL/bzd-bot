"""
Notifications handler for BZD Bot.
Handles notification settings and manual checks.
"""
import logging
from aiogram import Router
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router()


@router.message()
async def unmatched_message(message: Message) -> None:
    """Friendly fallback for messages not matched by any other handler.

    This router is registered last, so FSM-state handlers in earlier routers
    have already had their chance — anything reaching here is off-flow.
    """
    from bot.keyboards.reply import get_main_menu_keyboard
    await message.answer(
        "🤔 Не понял команду.\n"
        "Воспользуйтесь кнопками меню ниже или отправьте /start.",
        reply_markup=get_main_menu_keyboard()
    )
