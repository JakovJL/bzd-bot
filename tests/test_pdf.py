"""
PDF generation tests for BZD Bot.
"""
import unittest
import os
import tempfile
from bot.services.pdf_generator import PDFGenerator


class TestPDFGenerator(unittest.TestCase):
    """Test cases for PDF generation."""

    def test_generate_ticket(self):
        """Test PDF ticket generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = PDFGenerator.generate_ticket(
                ticket_number="BZD-TEST123",
                train_number="651Б",
                train_name="Брестский экспресс",
                origin="Минск-Пассажирский",
                destination="Брест-Центральный",
                departure_time="14:30",
                arrival_time="17:45",
                date="2024-01-01",
                wagon_type="Купе",
                wagon_number=6,
                seat_number=12,
                passenger_name="Иванов Иван Иванович",
                document_type="Паспорт РБ",
                document_number="MP1234567",
                price=25.00,
                output_dir=tmpdir
            )
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 0)


if __name__ == "__main__":
    unittest.main()
