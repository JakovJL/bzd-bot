"""
PDF Ticket generator for BZD Bot.

Renders an A4 boarding-pass style ticket with a scannable QR code.
A Cyrillic-capable TrueType font is registered once at import time so
Russian/Belarusian text renders correctly (reportlab's built-in Helvetica
cannot show Cyrillic).
"""
import io
import logging
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, Image, HRFlowable
)
from reportlab.lib import colors

from bot.services.qr_service import QRService

logger = logging.getLogger(__name__)

# Brand palette.
BZD_BLUE = colors.HexColor('#1a5276')
BZD_LIGHT = colors.HexColor('#d6eaf8')
BZD_GREY = colors.HexColor('#5d6d7e')

# Candidate Cyrillic-capable fonts, in order of preference.
_FONT_CANDIDATES = [
    ("Arial", "Arial-Bold",
     r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ("DejaVuSans", "DejaVuSans-Bold",
     str(Path(__file__).resolve().parent.parent / "assets" / "DejaVuSans.ttf"),
     str(Path(__file__).resolve().parent.parent / "assets" / "DejaVuSans-Bold.ttf")),
]


def _register_font() -> tuple[str, str]:
    """Register a Cyrillic font family, returning (normal, bold) face names.

    Falls back to Helvetica (no Cyrillic) only if nothing else is available,
    so generation never crashes on a machine without the expected fonts.
    """
    for normal, bold, normal_path, bold_path in _FONT_CANDIDATES:
        if not (os.path.exists(normal_path) and os.path.exists(bold_path)):
            continue
        try:
            pdfmetrics.registerFont(TTFont(normal, normal_path))
            pdfmetrics.registerFont(TTFont(bold, bold_path))
            pdfmetrics.registerFontFamily(
                normal, normal=normal, bold=bold, italic=normal, boldItalic=bold
            )
            logger.info(f"PDF font registered: {normal}")
            return normal, bold
        except Exception as e:
            logger.warning(f"Could not register font {normal}: {e}")
    logger.warning(
        "No Cyrillic TTF font found — falling back to Helvetica. "
        "Cyrillic text may not render correctly."
    )
    return "Helvetica", "Helvetica-Bold"


FONT_NORMAL, FONT_BOLD = _register_font()


class PDFGenerator:
    """Generator for PDF train tickets."""

    @staticmethod
    def generate_ticket(
        ticket_number: str,
        train_number: str,
        train_name: str,
        origin: str,
        destination: str,
        departure_time: str,
        arrival_time: str,
        date: str,
        wagon_type: str,
        wagon_number: int,
        seat_number: int,
        passenger_name: str,
        document_type: str,
        document_number: str,
        price: float,
        output_dir: str = "tickets"
    ) -> str:
        """Generate a PDF ticket and return its file path.

        `date` is the travel date. Raises on failure so the caller can keep
        the order pending rather than marking it paid without a ticket.
        """
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            filepath = os.path.join(output_dir, f"ticket_{ticket_number}.pdf")

            doc = SimpleDocTemplate(
                filepath, pagesize=A4,
                rightMargin=18 * mm, leftMargin=18 * mm,
                topMargin=16 * mm, bottomMargin=16 * mm,
                title=f"Билет {ticket_number}",
            )

            base = getSampleStyleSheet()
            banner_style = ParagraphStyle(
                'Banner', parent=base['Normal'], fontName=FONT_BOLD,
                fontSize=18, alignment=TA_CENTER, textColor=colors.white,
                leading=22,
            )
            banner_sub = ParagraphStyle(
                'BannerSub', parent=base['Normal'], fontName=FONT_NORMAL,
                fontSize=10, alignment=TA_CENTER, textColor=BZD_LIGHT,
                leading=13,
            )
            section_style = ParagraphStyle(
                'Section', parent=base['Normal'], fontName=FONT_BOLD,
                fontSize=12, textColor=BZD_BLUE, spaceBefore=4, spaceAfter=4,
            )
            small_center = ParagraphStyle(
                'SmallCenter', parent=base['Normal'], fontName=FONT_NORMAL,
                fontSize=9, alignment=TA_CENTER, textColor=BZD_GREY,
            )
            footer_style = ParagraphStyle(
                'Footer', parent=base['Normal'], fontName=FONT_NORMAL,
                fontSize=8, alignment=TA_CENTER, textColor=colors.grey,
            )

            story = []

            # --- Brand banner ---
            banner = Table(
                [[Paragraph("БЕЛОРУССКАЯ ЖЕЛЕЗНАЯ ДОРОГА", banner_style)],
                 [Paragraph("Belarusian Railway · Беларуская чыгунка", banner_sub)]],
                colWidths=[174 * mm],
            )
            banner.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), BZD_BLUE),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(banner)
            story.append(Spacer(1, 6))

            # --- Ticket number / status strip ---
            strip = Table(
                [[Paragraph(f"Билет № {ticket_number}",
                            ParagraphStyle('TN', parent=base['Normal'],
                                           fontName=FONT_BOLD, fontSize=12,
                                           textColor=BZD_BLUE)),
                  Paragraph("ОПЛАЧЕНО",
                            ParagraphStyle('ST', parent=base['Normal'],
                                           fontName=FONT_BOLD, fontSize=11,
                                           alignment=TA_CENTER,
                                           textColor=colors.white))]],
                colWidths=[124 * mm, 50 * mm],
            )
            strip.setStyle(TableStyle([
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#1e8449')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (0, 0), 0),
            ]))
            story.append(strip)
            story.append(Spacer(1, 10))

            def info_table(rows):
                t = Table(rows, colWidths=[42 * mm, 132 * mm])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), FONT_BOLD),
                    ('FONTNAME', (1, 0), (1, -1), FONT_NORMAL),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TEXTCOLOR', (0, 0), (0, -1), BZD_BLUE),
                    ('LINEBELOW', (0, 0), (-1, -2), 0.4, BZD_LIGHT),
                ]))
                return t

            # --- Train / route ---
            story.append(Paragraph("Поезд и маршрут", section_style))
            story.append(info_table([
                ["Поезд:", f"{train_number} «{train_name}»"],
                ["Маршрут:", f"{origin} → {destination}"],
                ["Дата поездки:", date],
                ["Отправление:", departure_time],
                ["Прибытие:", arrival_time],
            ]))
            story.append(Spacer(1, 10))

            # --- Seat ---
            story.append(Paragraph("Место", section_style))
            story.append(info_table([
                ["Тип вагона:", wagon_type],
                ["Вагон:", str(wagon_number)],
                ["Место:", str(seat_number)],
            ]))
            story.append(Spacer(1, 10))

            # --- Passenger ---
            story.append(Paragraph("Пассажир", section_style))
            story.append(info_table([
                ["ФИО:", passenger_name],
                ["Документ:", f"{document_type} № {document_number}"],
            ]))
            story.append(Spacer(1, 10))

            # --- Price ---
            price_tbl = Table(
                [[Paragraph("К ОПЛАТЕ",
                            ParagraphStyle('PL', parent=base['Normal'],
                                           fontName=FONT_BOLD, fontSize=11,
                                           textColor=colors.white)),
                  Paragraph(f"{price:.2f} BYN",
                            ParagraphStyle('PV', parent=base['Normal'],
                                           fontName=FONT_BOLD, fontSize=13,
                                           alignment=TA_CENTER,
                                           textColor=colors.white))]],
                colWidths=[124 * mm, 50 * mm],
            )
            price_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), BZD_BLUE),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (0, 0), 10),
            ]))
            story.append(price_tbl)
            story.append(Spacer(1, 16))

            # --- QR code (rendered in memory, no temp file) ---
            qr_data = QRService.create_ticket_qr_data(
                ticket_number, train_number, date, str(seat_number)
            )
            qr_bytes = QRService.generate_qr(qr_data, size=8)
            qr_img = Image(io.BytesIO(qr_bytes), width=46 * mm, height=46 * mm)
            qr_img.hAlign = 'CENTER'
            story.append(qr_img)
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                "Отсканируйте QR-код для проверки билета", small_center
            ))

            # --- Footer ---
            story.append(Spacer(1, 16))
            story.append(HRFlowable(width="100%", thickness=0.6, color=BZD_GREY))
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"Оформлено: {datetime.now().strftime('%d.%m.%Y %H:%M')} · "
                "Демонстрационный билет (эмуляция БЖД)", footer_style
            ))

            doc.build(story)
            return filepath
        except Exception as e:
            logger.error(f"Failed to generate PDF ticket {ticket_number}: {e}")
            raise
