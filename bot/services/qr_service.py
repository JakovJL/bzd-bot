"""
QR Code generation service for BZD Bot.
Generates QR codes containing ticket information.
"""
import qrcode
import io
import base64
from typing import Optional


class QRService:
    """Service for generating QR codes."""

    @staticmethod
    def generate_qr(data: str, size: int = 10) -> bytes:
        """
        Generate QR code image from data string.

        Args:
            data: String to encode in QR
            size: Box size for QR modules

        Returns:
            PNG image bytes
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=size,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer.getvalue()

    @staticmethod
    def generate_qr_base64(data: str, size: int = 10) -> str:
        """Generate QR code as base64 string."""
        image_bytes = QRService.generate_qr(data, size)
        return base64.b64encode(image_bytes).decode('utf-8')

    @staticmethod
    def create_ticket_qr_data(
        ticket_id: str,
        train_number: str,
        date: str,
        seat: str
    ) -> str:
        """Create structured QR data for a ticket."""
        return f"BZD|TICKET|{ticket_id}|{train_number}|{date}|{seat}"
