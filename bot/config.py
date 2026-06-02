"""
Configuration module for BZD Bot.
Loads settings from .env file and validates them.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    """Bot configuration container."""

    # Bot token from @BotFather
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Admin IDs list
    ADMIN_IDS: list[int] = [
        int(x.strip()) 
        for x in os.getenv("ADMIN_IDS", "").split(",") 
        if x.strip()
    ]

    # Database file path
    DB_PATH: str = os.getenv("DB_PATH", "data/bzd_bot.db")

    # Logging level
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration values."""
        if not cls.BOT_TOKEN or cls.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            raise ValueError(
                "BOT_TOKEN is not set!\n"
                "Create .env file from .env.example and add your token."
            )

        if not cls.ADMIN_IDS:
            logging.warning("ADMIN_IDS is empty! Admin panel will be inaccessible.")


# Ensure directories exist
Path("data").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)
Path("tickets").mkdir(exist_ok=True)
