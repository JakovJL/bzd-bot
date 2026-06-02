"""
Mock BZD (Belarusian Railway) API service.

Provides a realistic catalogue of train runs (both directions, several
departures per day on popular routes) with date-dependent pricing.
Seat availability comes from real orders via bot.services.availability,
so booked seats stay booked between searches.
"""
from typing import List, Optional
from datetime import datetime

from bot.models.route import Route, Wagon


# List of all stations
STATIONS: List[str] = [
    "Минск-Пассажирский", "Брест-Центральный", "Гродно", "Витебск",
    "Гомель", "Могилев", "Барановичи", "Лида", "Пинск", "Полоцк",
    "Орша", "Слуцк", "Новогрудок"
]


# Belarusian public holidays (MM-DD) — peak pricing days.
_HOLIDAYS_MMDD = {
    "01-01", "01-02", "01-07", "03-08", "05-01",
    "05-09", "07-03", "11-07", "12-25",
}

# Price multipliers
_HOLIDAY_MULTIPLIER = 1.25
_WEEKEND_MULTIPLIER = 1.15


def _duration(departure: str, arrival: str) -> str:
    """Compute human-readable duration between two HH:MM times (same/next day)."""
    fmt = "%H:%M"
    dep = datetime.strptime(departure, fmt)
    arr = datetime.strptime(arrival, fmt)
    minutes = int((arr - dep).total_seconds() // 60)
    if minutes < 0:
        minutes += 24 * 60
    return f"{minutes // 60}ч {minutes % 60:02d}мин"


def date_price_multiplier(date_str: str) -> float:
    """Return a price multiplier for a travel date (weekend/holiday surcharge)."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return 1.0
    if d.strftime("%m-%d") in _HOLIDAYS_MMDD:
        return _HOLIDAY_MULTIPLIER
    if d.weekday() >= 5:  # Saturday/Sunday
        return _WEEKEND_MULTIPLIER
    return 1.0


def _wagons(base: float) -> List[Wagon]:
    """Build a standard 3-wagon set from a Плацкарт base price."""
    return [
        Wagon(type="Плацкарт", number=1, total_seats=54, price=round(base, 2)),
        Wagon(type="Купе", number=2, total_seats=36, price=round(base * 1.65, 2)),
        Wagon(type="СВ", number=3, total_seats=18, price=round(base * 2.9, 2)),
    ]


# Each entry: (origin, destination, base_price, [(train_number, name, dep, arr), ...])
_LINES = [
    ("Минск-Пассажирский", "Брест-Центральный", 15.50, [
        ("651Б", "Брестский экспресс", "08:10", "11:25"),
        ("653Б", "Брестский экспресс", "14:30", "17:45"),
        ("655Б", "Брестский ночной", "22:40", "02:05"),
    ]),
    ("Минск-Пассажирский", "Гродно", 14.20, [
        ("607Б", "Гродненский", "08:15", "12:30"),
        ("609Б", "Гродненский", "17:40", "21:55"),
    ]),
    ("Минск-Пассажирский", "Витебск", 14.80, [
        ("709Б", "Витебский", "07:25", "11:35"),
        ("711Б", "Витебский", "16:00", "20:10"),
    ]),
    ("Минск-Пассажирский", "Гомель", 17.30, [
        ("801Б", "Гомельский", "07:00", "10:45"),
        ("803Б", "Гомельский", "13:20", "17:05"),
        ("805Б", "Сож", "19:15", "23:00"),
    ]),
    ("Минск-Пассажирский", "Могилев", 13.90, [
        ("503Б", "Могилевский", "11:20", "14:50"),
        ("505Б", "Днепр", "18:30", "22:00"),
    ]),
    ("Минск-Пассажирский", "Полоцк", 16.00, [
        ("621Б", "Полоцкий", "09:05", "13:40"),
    ]),
    ("Минск-Пассажирский", "Барановичи", 9.50, [
        ("615Б", "Региональный", "10:30", "12:25"),
        ("617Б", "Региональный", "18:05", "20:00"),
    ]),
    ("Гомель", "Брест-Центральный", 19.00, [
        ("095Б", "Полесье", "06:40", "12:55"),
    ]),
    ("Витебск", "Гомель", 21.00, [
        ("083Б", "Двина", "07:50", "14:20"),
    ]),
]


def _build_routes() -> List[Route]:
    """Expand the line catalogue into directional Route objects with unique ids."""
    routes: List[Route] = []
    rid = 1
    for origin, destination, base, departures in _LINES:
        for direction_origin, direction_dest in (
            (origin, destination),
            (destination, origin),
        ):
            for train_number, name, dep, arr in departures:
                routes.append(Route(
                    id=rid,
                    train_number=train_number,
                    name=name,
                    origin=direction_origin,
                    destination=direction_dest,
                    departure_time=dep,
                    arrival_time=arr,
                    duration=_duration(dep, arr),
                    wagons=_wagons(base),
                ))
                rid += 1
    return routes


# Full catalogue of train runs (both directions).
ROUTES: List[Route] = _build_routes()


class BZDMockService:
    """Mock service for Belarusian Railway API."""

    @staticmethod
    def get_stations() -> List[str]:
        """Return list of available stations."""
        return STATIONS.copy()

    @staticmethod
    def search_routes(
        origin: str,
        destination: str,
        date: str
    ) -> List[Route]:
        """
        Search runs between two stations on a date.

        Prices are adjusted for the travel date and seat occupancy is read
        from real orders, so results reflect actual availability.
        """
        from bot.services.availability import get_occupied_seats

        multiplier = date_price_multiplier(date)
        results: List[Route] = []
        for route in ROUTES:
            if route.origin != origin or route.destination != destination:
                continue
            wagons = []
            for wagon in route.wagons:
                occupied = sorted(get_occupied_seats(route.id, date, wagon.number))
                wagons.append(Wagon(
                    type=wagon.type,
                    number=wagon.number,
                    total_seats=wagon.total_seats,
                    price=round(wagon.price * multiplier, 2),
                    occupied_seats=occupied,
                ))
            results.append(Route(
                id=route.id,
                train_number=route.train_number,
                name=route.name,
                origin=route.origin,
                destination=route.destination,
                departure_time=route.departure_time,
                arrival_time=route.arrival_time,
                duration=route.duration,
                wagons=wagons,
            ))
        results.sort(key=lambda r: r.departure_time)
        return results

    @staticmethod
    def get_route_by_id(route_id: int) -> Optional[Route]:
        """Get a route run by its id."""
        for route in ROUTES:
            if route.id == route_id:
                return route
        return None

    @staticmethod
    def get_wagon_price(route_id: int, wagon_type: str, date: str) -> Optional[float]:
        """Date-adjusted price for a wagon type on a run."""
        route = BZDMockService.get_route_by_id(route_id)
        if not route:
            return None
        multiplier = date_price_multiplier(date)
        for wagon in route.wagons:
            if wagon.type == wagon_type:
                return round(wagon.price * multiplier, 2)
        return None

    @staticmethod
    def is_seat_available(
        route_id: int,
        wagon_type: str,
        seat_number: int,
        date: str
    ) -> bool:
        """Check seat availability against real orders for a given date."""
        from bot.services.availability import get_occupied_seats

        route = BZDMockService.get_route_by_id(route_id)
        if not route:
            return False
        for wagon in route.wagons:
            if wagon.type == wagon_type:
                return seat_number not in get_occupied_seats(
                    route_id, date, wagon.number
                )
        return False
