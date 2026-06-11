"""
Database module for BZD Bot.
Provides SQLite connection, session management, and table creation.
"""
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from bot.config import Config

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str = None) -> None:
        self.db_path = db_path or Config.DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _init_tables(self) -> None:
        """Create tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    phone TEXT,
                    language TEXT DEFAULT 'ru',
                    notifications_enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Stations reference table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

            # Routes table (reference catalogue of train runs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS routes (
                    id INTEGER PRIMARY KEY,
                    train_number TEXT NOT NULL,
                    name TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_time TEXT NOT NULL,
                    arrival_time TEXT NOT NULL,
                    duration TEXT NOT NULL
                )
            """)

            # Orders table — route fields are denormalized so a ticket keeps
            # its train data even though routes are reference/static.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    route_id INTEGER NOT NULL,
                    train_number TEXT,
                    train_name TEXT,
                    origin TEXT,
                    destination TEXT,
                    departure_time TEXT,
                    arrival_time TEXT,
                    travel_date TEXT,
                    wagon_type TEXT NOT NULL,
                    wagon_number INTEGER NOT NULL,
                    seat_number INTEGER NOT NULL,
                    passenger_name TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    document_number TEXT NOT NULL,
                    price REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    transaction_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (route_id) REFERENCES routes (id)
                )
            """)

            # Tickets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    ticket_number TEXT UNIQUE NOT NULL,
                    pdf_path TEXT,
                    qr_data TEXT,
                    is_active INTEGER DEFAULT 1,
                    reminded_24h INTEGER DEFAULT 0,
                    reminded_2h INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (id)
                )
            """)

            # Waitlist table - for queue when tickets are not available
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS waitlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    date TEXT NOT NULL,
                    wagon_type TEXT,
                    preferred_seat INTEGER,
                    passenger_name TEXT,
                    document_type TEXT,
                    document_number TEXT,
                    status TEXT DEFAULT 'waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Reviews table - for user feedback
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    route_id INTEGER,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            conn.commit()

            self._migrate(cursor)
            conn.commit()

            logger.info("Database tables initialized.")

        self._seed_reference_data()

    @staticmethod
    def _migrate(cursor: sqlite3.Cursor) -> None:
        """Add columns introduced after the initial schema (idempotent)."""
        migrations = {
            "users": [("notifications_enabled", "INTEGER DEFAULT 1")],
            "orders": [
                ("train_number", "TEXT"), ("train_name", "TEXT"),
                ("origin", "TEXT"), ("destination", "TEXT"),
                ("departure_time", "TEXT"), ("arrival_time", "TEXT"),
                ("travel_date", "TEXT"),
                ("email", "TEXT"),
            ],
            "tickets": [
                ("reminded_24h", "INTEGER DEFAULT 0"),
                ("reminded_2h", "INTEGER DEFAULT 0"),
            ],
            "waitlist": [("route_id", "INTEGER")],
        }
        for table, columns in migrations.items():
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row["name"] for row in cursor.fetchall()}
            for name, ddl in columns:
                if name not in existing:
                    cursor.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"
                    )
                    logger.info(f"Migrated: added {table}.{name}")

    def _seed_reference_data(self) -> None:
        """Seed stations and route catalogue from the mock service."""
        from bot.services.bzd_mock import STATIONS, ROUTES

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for name in STATIONS:
                cursor.execute(
                    "INSERT OR IGNORE INTO stations (name) VALUES (?)", (name,)
                )
            for r in ROUTES:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO routes
                        (id, train_number, name, origin, destination,
                         departure_time, arrival_time, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (r.id, r.train_number, r.name, r.origin, r.destination,
                     r.departure_time, r.arrival_time, r.duration)
                )
            conn.commit()
            logger.info(
                f"Seeded {len(STATIONS)} stations and {len(ROUTES)} routes."
            )

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


# Global database instance
db = Database()
