"""
User model for BZD Bot.
Represents a registered Telegram user.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User data model."""
    id: int
    telegram_id: int
    username: Optional[str]
    phone: Optional[str]
    language: str = "ru"
    created_at: Optional[datetime] = None
