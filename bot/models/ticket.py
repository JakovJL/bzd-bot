"""
Ticket model for BZD Bot.
Represents a generated ticket after payment.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Ticket:
    """Ticket data model."""
    id: int
    order_id: int
    ticket_number: str
    pdf_path: Optional[str]
    qr_data: str
    is_active: bool = True
    created_at: Optional[datetime] = None
