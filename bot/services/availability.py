"""
Seat availability service for BZD Bot.
Seat occupancy is derived from real orders in the database, so a booked
seat stays booked across searches (unlike the old random.sample approach).
"""
import logging
from typing import Set

logger = logging.getLogger(__name__)

# Orders in these statuses hold a seat.
HOLDING_STATUSES = ("pending", "paid")


def get_occupied_seats(
    route_id: int,
    travel_date: str,
    wagon_number: int
) -> Set[int]:
    """Return the set of seat numbers already taken for a given run/wagon."""
    from bot.database import db
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(HOLDING_STATUSES))
            cursor.execute(
                f"""
                SELECT seat_number FROM orders
                WHERE route_id = ? AND travel_date = ? AND wagon_number = ?
                  AND status IN ({placeholders})
                """,
                (route_id, travel_date, wagon_number, *HOLDING_STATUSES)
            )
            return {row["seat_number"] for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"Error reading occupied seats: {e}")
        return set()


def is_seat_free(
    route_id: int,
    travel_date: str,
    wagon_number: int,
    seat_number: int
) -> bool:
    """Check seat availability against real orders."""
    return seat_number not in get_occupied_seats(
        route_id, travel_date, wagon_number
    )
