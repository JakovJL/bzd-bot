"""
Database tests for BZD Bot.
"""
import unittest
import os
import tempfile
from bot.database import Database


class TestDatabase(unittest.TestCase):
    """Test cases for database operations."""

    def setUp(self):
        """Create temporary database for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_tables_created(self):
        """Test that all tables are created."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN 
                ('users', 'routes', 'orders', 'tickets')
            """)
            tables = [row["name"] for row in cursor.fetchall()]
            self.assertEqual(len(tables), 4)

    def test_user_insert(self):
        """Test user insertion."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (telegram_id, username, phone, language)
                VALUES (?, ?, ?, ?)
            """, (123456, "testuser", "+375291234567", "ru"))
            conn.commit()

            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (123456,))
            user = cursor.fetchone()
            self.assertIsNotNone(user)
            self.assertEqual(user["username"], "testuser")


if __name__ == "__main__":
    unittest.main()
