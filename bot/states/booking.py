"""
FSM states for ticket booking flow.
Uses aiogram FSM (Finite State Machine).
"""
from aiogram.fsm.state import State, StatesGroup


class BookingState(StatesGroup):
    """States for the ticket booking process."""

    # Step 1: Select origin station
    selecting_origin = State()
    entering_custom_origin = State()

    # Step 2: Select destination station
    selecting_destination = State()
    entering_custom_destination = State()

    # Step 3: Select travel date
    selecting_date = State()

    # Step 4: Select train/route
    selecting_train = State()

    # Step 5: Select wagon type
    selecting_wagon_type = State()

    # Step 6: Select specific seat
    selecting_seat = State()

    # Step 7: Enter passenger data
    entering_name = State()
    entering_document_type = State()
    entering_document_number = State()

    # Step 8: Enter email for e-ticket
    entering_email = State()

    # Step 9: Confirm and pay
    confirming_payment = State()

    # Step 10: Card entry (after clicking "Оплатить")
    entering_card_number = State()
    entering_card_expiry = State()
    entering_card_cvv = State()
    entering_card_holder = State()
    processing_payment = State()


class WaitlistState(StatesGroup):
    """States for waitlist/queue process."""
    entering_waitlist_origin = State()
    entering_waitlist_destination = State()
    entering_waitlist_date = State()
    entering_waitlist_wagon = State()
    entering_waitlist_name = State()
    entering_waitlist_phone = State()


class ReviewState(StatesGroup):
    """States for leaving a review."""
    selecting_route_for_review = State()
    entering_rating = State()
    entering_comment = State()
