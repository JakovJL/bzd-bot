"""
Logging middleware for BZD Bot.
Logs all user actions to file for analytics.
"""
import logging
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware that logs all user interactions."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any]
    ) -> Any:
        """Log message and pass to handler."""
        if isinstance(event, Message):
            user = event.from_user
            logger.info(
                f"[MSG] user_id={user.id} username={user.username} "
                f"text='{event.text[:50] if event.text else '[no text]'}'"
            )
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            logger.info(
                f"[CBQ] user_id={user.id} username={user.username} "
                f"data='{event.data}'"
            )

        return await handler(event, data)
