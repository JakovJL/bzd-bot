"""Handlers package for BZD Bot."""
from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.search import router as search_router
from bot.handlers.booking import router as booking_router
from bot.handlers.payment import router as payment_router
from bot.handlers.tickets import router as tickets_router
from bot.handlers.admin import router as admin_router
from bot.handlers.notifications import router as notifications_router
from bot.handlers.help import router as help_router
from bot.handlers.waitlist import router as waitlist_router
from bot.handlers.reviews import router as reviews_router


def get_all_routers() -> list[Router]:
    """Return list of all routers to register."""
    return [
        start_router,
        search_router,
        booking_router,
        payment_router,
        tickets_router,
        admin_router,
        help_router,
        waitlist_router,
        reviews_router,
        # Registered LAST: its catch-all @router.message() fallback must only
        # fire after every other router has had a chance to match.
        notifications_router,
    ]


__all__ = ["get_all_routers"]
