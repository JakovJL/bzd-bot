"""
Reviews handler for BZD Bot.
Handles user feedback and ratings after trips.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database import db
from bot.keyboards.reply import get_main_menu_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()


class ReviewStates(StatesGroup):
    review_selecting_rating = State()
    review_entering_comment = State()


def get_rating_keyboard(route_id: int) -> InlineKeyboardBuilder:
    """Create 1-5 star rating keyboard."""
    builder = InlineKeyboardBuilder()
    stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    for i, star in enumerate(stars, 1):
        builder.row(
            InlineKeyboardButton(text=star, callback_data=f"rate_{route_id}_{i}")
        )
    return builder.as_markup()


@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle rating selection."""
    try:
        parts = callback.data.split("_")
        route_id = int(parts[1])
        rating = int(parts[2])
        await state.update_data(rating=rating, route_id=route_id)
        await state.set_state(ReviewStates.review_entering_comment)
        await callback.message.edit_text(
            "⭐" * rating + "\n\n"
            "Спасибо за оценку!\n"
            "Напишите комментарий (или отправьте '-' чтобы пропустить):"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_rating: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(F.text, ReviewStates.review_entering_comment)
async def process_comment(message: Message, state: FSMContext) -> None:
    """Handle review comment."""
    try:
        data = await state.get_data()
        rating = data["rating"]
        route_id = data["route_id"]
        comment = message.text.strip()
        if comment == "-":
            comment = None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (message.from_user.id,)
            )
            user_row = cursor.fetchone()
            user_id = user_row["id"] if user_row else None

            cursor.execute("""
                INSERT INTO reviews (user_id, route_id, rating, comment)
                VALUES (?, ?, ?, ?)
            """, (user_id, route_id, rating, comment))
            conn.commit()

        await message.answer(
            "✅ Спасибо за отзыв!\n\n"
            "Ваше мнение помогает нам становиться лучше.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error in process_comment: {e}")
        await message.answer("⚠️ Ошибка сохранения отзыва.")


@router.message(F.text == "⭐ Оставить отзыв")
async def menu_review(message: Message, state: FSMContext) -> None:
    """Handle leave review menu button."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (message.from_user.id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                await message.answer("❌ Вы не зарегистрированы. Используйте /start")
                return
            user_id = user_row["id"]
            cursor.execute("""
                SELECT o.route_id, o.train_number, o.train_name AS name,
                       o.origin, o.destination
                FROM orders o
                WHERE o.user_id = ? AND o.status = 'paid'
                AND o.route_id NOT IN (
                    SELECT route_id FROM reviews
                    WHERE user_id = ? AND route_id IS NOT NULL
                )
                GROUP BY o.route_id
                LIMIT 5
            """, (user_id, user_id))
            routes = cursor.fetchall()

        if not routes:
            await message.answer(
                "📋 У вас пока нет поездок для оценки.\n"
                "После поездки вы сможете оставить отзыв."
            )
            return

        builder = InlineKeyboardBuilder()
        for route in routes:
            text = f"🚂 №{route['train_number']} {route['origin']}→{route['destination']}"
            builder.row(
                InlineKeyboardButton(text=text, callback_data=f"review_route_{route['route_id']}")
            )

        await message.answer(
            "⭐ Выберите рейс для оценки:",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Error in menu_review: {e}")
        await message.answer("⚠️ Ошибка загрузки рейсов.")


@router.callback_query(F.data.startswith("revview_"))
async def view_route_reviews(callback: CallbackQuery) -> None:
    """Show average rating and recent comments for a run (visible to everyone)."""
    try:
        route_id = int(callback.data.replace("revview_", ""))
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as cnt, AVG(rating) as avg_rating "
                "FROM reviews WHERE route_id = ?",
                (route_id,)
            )
            agg = cursor.fetchone()
            cursor.execute(
                "SELECT rating, comment FROM reviews "
                "WHERE route_id = ? AND comment IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 3",
                (route_id,)
            )
            recent = cursor.fetchall()

        count = agg["cnt"] or 0
        if count == 0:
            await callback.answer(
                "Пока нет отзывов об этом рейсе.", show_alert=True
            )
            return

        avg = agg["avg_rating"] or 0
        full = int(round(avg))
        lines = [
            "⭐ <b>Отзывы о рейсе</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "Средняя оценка: " + ("⭐" * full) + f" {avg:.1f} / 5",
            "Всего отзывов: " + str(count),
        ]
        if recent:
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            for r in recent:
                lines.append("⭐" * r["rating"] + " — " + (r["comment"] or ""))
        await callback.message.edit_text("\n".join(lines))
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in view_route_reviews: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("review_route_"))
async def start_review(callback: CallbackQuery, state: FSMContext) -> None:
    """Start review process for selected route."""
    try:
        route_id = int(callback.data.replace("review_route_", ""))
        await state.set_state(ReviewStates.review_selecting_rating)
        await callback.message.edit_text(
            "⭐ Оцените поездку:",
            reply_markup=get_rating_keyboard(route_id)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in start_review: {e}")
        await callback.answer("⚠️ Ошибка", show_alert=True)
