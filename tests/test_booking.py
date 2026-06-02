"""
Booking flow tests for BZD Bot.
"""
import os
import tempfile
import unittest

from bot.services.bzd_mock import (
    BZDMockService, STATIONS, ROUTES, date_price_multiplier
)


class TestBooking(unittest.TestCase):
    """Test cases for booking functionality."""

    def test_stations_list(self):
        """Stations list is populated and includes the hub."""
        self.assertGreater(len(STATIONS), 0)
        self.assertIn("Минск-Пассажирский", STATIONS)

    def test_routes_catalogue(self):
        """Catalogue is non-trivial and route ids are unique."""
        self.assertGreater(len(ROUTES), 1)
        ids = [r.id for r in ROUTES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_routes_bidirectional(self):
        """Both directions of a line are present."""
        forward = any(
            r.origin == "Минск-Пассажирский" and r.destination == "Брест-Центральный"
            for r in ROUTES
        )
        backward = any(
            r.origin == "Брест-Центральный" and r.destination == "Минск-Пассажирский"
            for r in ROUTES
        )
        self.assertTrue(forward)
        self.assertTrue(backward)

    def test_search_routes(self):
        """Search returns runs with fully populated fields, sorted by departure."""
        routes = BZDMockService.search_routes(
            "Минск-Пассажирский", "Брест-Центральный", "2024-01-03"
        )
        self.assertGreaterEqual(len(routes), 1)
        first = routes[0]
        self.assertTrue(first.train_number)
        self.assertTrue(first.name)
        self.assertEqual(first.origin, "Минск-Пассажирский")
        self.assertEqual(first.destination, "Брест-Центральный")
        self.assertTrue(first.wagons)
        # Sorted ascending by departure time.
        times = [r.departure_time for r in routes]
        self.assertEqual(times, sorted(times))

    def test_date_price_multiplier(self):
        """Weekend and holiday dates cost more than a plain weekday."""
        # 2024-01-03 is a Wednesday -> base; 2024-01-06 Saturday -> weekend;
        # 2024-01-01 is a holiday.
        self.assertEqual(date_price_multiplier("2024-01-03"), 1.0)
        self.assertGreater(date_price_multiplier("2024-01-06"), 1.0)
        self.assertGreater(date_price_multiplier("2024-01-01"), 1.0)

    def test_search_price_reflects_date(self):
        """A weekend run is priced higher than the same run on a weekday."""
        weekday = BZDMockService.search_routes(
            "Минск-Пассажирский", "Брест-Центральный", "2024-01-03"
        )
        weekend = BZDMockService.search_routes(
            "Минск-Пассажирский", "Брест-Центральный", "2024-01-06"
        )
        self.assertGreater(
            weekend[0].wagons[0].price, weekday[0].wagons[0].price
        )


class TestSeatOccupancy(unittest.TestCase):
    """Seat occupancy is derived from real orders and persists."""

    def setUp(self):
        # Point the global db at a throwaway file so we don't touch real data.
        import bot.database as database_module
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self._orig_db = database_module.db
        database_module.db = database_module.Database(self.db_path)

    def tearDown(self):
        import bot.database as database_module
        database_module.db = self._orig_db
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_booked_seat_becomes_occupied(self):
        """After an order holds a seat, it is reported occupied."""
        from bot.services.availability import get_occupied_seats, is_seat_free
        import bot.database as database_module

        route_id, travel_date, wagon_number, seat = 1, "2024-07-15", 1, 7
        self.assertTrue(is_seat_free(route_id, travel_date, wagon_number, seat))

        with database_module.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (
                    user_id, route_id, travel_date, wagon_type, wagon_number,
                    seat_number, passenger_name, document_type, document_number,
                    price, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                1, route_id, travel_date, "Плацкарт", wagon_number, seat,
                "Тест Тестов", "Паспорт РБ", "MP000", 15.5, "pending"
            ))
            conn.commit()

        self.assertIn(seat, get_occupied_seats(route_id, travel_date, wagon_number))
        self.assertFalse(is_seat_free(route_id, travel_date, wagon_number, seat))
        # A different date for the same run/seat is unaffected.
        self.assertTrue(is_seat_free(route_id, "2024-07-16", wagon_number, seat))


if __name__ == "__main__":
    unittest.main()
