"""
Route model for BZD Bot.
Represents a train route between stations.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class Wagon:
    """Wagon information."""
    type: str          # e.g., 'Плацкарт', 'Купе', 'СВ'
    number: int
    total_seats: int
    price: float
    occupied_seats: List[int] = None

    def __post_init__(self):
        if self.occupied_seats is None:
            self.occupied_seats = []


@dataclass
class Route:
    """Train route data model."""
    id: int
    train_number: str
    name: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration: str
    wagons: List[Wagon] = None

    def __post_init__(self):
        if self.wagons is None:
            self.wagons = []
