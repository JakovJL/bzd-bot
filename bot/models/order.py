"""
Order model for BZD Bot.
Represents a booking order.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Order:
    """Order data model."""
    id: int
    user_id: int
    route_id: int
    wagon_type: str
    wagon_number: int
    seat_number: int
    passenger_name: str
    document_type: str
    document_number: str
    price: float
    status: str = "pending"  # pending, paid, cancelled, refunded
    transaction_id: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None
