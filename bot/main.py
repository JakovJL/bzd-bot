"""
Main entry point for BZD Bot.
Initializes bot, dispatcher, routers, scheduler, and starts polling.
"""
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import Config
from bot.handlers import get_all_routers
from bot.middlewares.logging_middleware import LoggingMiddleware
from bot.services.scheduler import NotificationScheduler


def setup_logging() -> None:
    """Configure logging to file and console."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(
                "logs/bot.log", 
                encoding="utf-8", 
                mode="a"
            ),
            logging.StreamHandler(sys.stdout)
        ]
    )


async def main() -> None:
    """Main async function to run the bot."""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting BZD Bot...")

    # Initialize bot and dispatcher
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middleware
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    # Register routers
    for router in get_all_routers():
        dp.include_router(router)

    logger.info(f"Registered {len(get_all_routers())} routers")

    # Publish the command menu shown in the Telegram client.
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
        BotCommand(command="admin", description="Админ-панель"),
    ])

    # Start notification scheduler
    async def send_message(user_id: int, text: str, reply_markup=None) -> None:
        await bot.send_message(user_id, text, reply_markup=reply_markup)

    scheduler = NotificationScheduler(send_message)
    scheduler.start()

    # Start polling
    logger.info("Bot is running! Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.stop()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
