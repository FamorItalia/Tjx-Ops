from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import black, red, blue, green
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.schemas.packing_lists import PackingListRead


@dataclass
class DlePdfBuildResult:
    file_name: str
    file_path: str
    generated_at: datetime


class DlePdfService:
    # Fixed positions for the current DLE template (A4 portrait, points).
    # These are the only dynamic overlay slots required by business rules.
    INVOICE_NUMBER_BOX = (112.0, 685.0, 235.0, 24.0)  # x, y, w, h
    INVOICE_DATE_BOX = (392.0, 685.0, 215.0, 24.0)
    TODAY_DATE_BOX = (42.0, 52.0, 220.0, 22.0)
    LOGO_BOX = (212.0, 705.0, 188.0, 54.0)

    def __init__(self, output_root: Path):
        self.output_root = output_root

    @staticmethod
    def _slug(value: str | None, fallback: str) -> str:
        if not value:
            return fallback
        return re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_") or fallback

    def _template_candidates(self) -> list[Path]:
        export_root = Path(settings.templates_root) / settings.documenti_export_dir
        fallback_root = Path("C:/Progetti/TJXOPE~1/TEMPLATES/DOCUMENTI EXPORT")
        exact_name = "HG LIKING 90 - DLE.pdf"
        return [
            Path(settings.document_dle_template_path),
            export_root / exact_name,
            fallback_root / exact_name,
        ]

    def _resolve_template_path(self) -> Path:
        template = next((p for p in self._template_candidates() if p.exists()), None)
        if template is None:
            raise FileNotFoundError("Template DLE non trovato.")
        return template

    def build_output_path(self, payload: PackingListRead) -> Path:
        out_dir = self.output_root / "dle"
        out_dir.mkdir(parents=True, exist_ok=True)
        brand = self._slug(payload.brand, "BRAND")
        po = self._slug(payload.po_number, f"PO_{payload.id}")
        dc = self._slug(payload.dc_code, "GLOBAL")
        return out_dir / f"DLE_{brand}_{po}_{dc}.pdf"

    def build_debug_output_path(self) -> Path:
        out_dir = self.output_root / "dle"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / "DLE_DEBUG_BOXES.pdf"

    @staticmethod
    def _fmt_date(value: date | None) -> str:
        if value is None:
            return ""
        return value.strftime("%d/%m/%Y")

    @staticmethod
    def _draw_text_fit_box(
        can: canvas.Canvas,
        text: str,
        box: tuple[float, float, float, float],
        max_font_size: float = 11.0,
        min_font_size: float = 8.5,
        padding_x: float = 6.0,
    ) -> None:
        if not text:
            return
        x, y, w, h = box
        usable = max(10.0, w - (padding_x * 2))
        font_name = "Helvetica-Bold"
        font_size = max_font_size
        while font_size > min_font_size and can.stringWidth(text, font_name, font_size) > usable:
            font_size -= 0.2
        baseline = y + ((h - font_size) / 2.0) + 1.5
        can.setFillColor(black)
        can.setFont(font_name, font_size)
        can.drawString(x + padding_x, baseline, text)

    def _build_overlay(
        self,
        width: float,
        height: float,
        invoice_number: str,
        invoice_date: str,
    ) -> bytes:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(width, height))

        # 1) Add Famor logo in template header area.
        logo_path = Path(settings.document_logo_path)
        if logo_path.exists():
            can.drawImage(
                str(logo_path),
                self.LOGO_BOX[0],
                self.LOGO_BOX[1],
                width=self.LOGO_BOX[2],
                height=self.LOGO_BOX[3],
                preserveAspectRatio=True,
                mask="auto",
            )

        # 2) Fill only requested fields in the gray slots.
        self._draw_text_fit_box(
            can=can,
            text=invoice_number,
            box=self.INVOICE_NUMBER_BOX,
            max_font_size=11.0,
            min_font_size=8.5,
        )
        self._draw_text_fit_box(
            can=can,
            text=invoice_date,
            box=self.INVOICE_DATE_BOX,
            max_font_size=11.0,
            min_font_size=8.5,
        )
        today_text = datetime.now().strftime("%d/%m/%Y")
        self._draw_text_fit_box(
            can=can,
            text=today_text,
            box=self.TODAY_DATE_BOX,
            max_font_size=10.5,
            min_font_size=8.5,
        )

        can.save()
        packet.seek(0)
        return packet.getvalue()

    def build_pdf(self, payload: PackingListRead) -> DlePdfBuildResult:
        template_path = self._resolve_template_path()
        output_path = self.build_output_path(payload)
        invoice_number = (payload.invoice_number or "").strip()
        invoice_date = self._fmt_date(payload.document_date)

        template_reader = PdfReader(str(template_path))
        if not template_reader.pages:
            raise ValueError("Template DLE senza pagine.")
        first_page = template_reader.pages[0]
        width = float(first_page.mediabox.width)
        height = float(first_page.mediabox.height)

        overlay_pdf = PdfReader(BytesIO(self._build_overlay(width, height, invoice_number, invoice_date)))
        first_page.merge_page(overlay_pdf.pages[0])

        writer = PdfWriter()
        for page in template_reader.pages:
            writer.add_page(page)
        with output_path.open("wb") as stream:
            writer.write(stream)

        return DlePdfBuildResult(
            file_name=output_path.name,
            file_path=str(output_path.resolve()),
            generated_at=datetime.fromtimestamp(output_path.stat().st_mtime),
        )

    def build_debug_boxes_pdf(self) -> DlePdfBuildResult:
        template_path = self._resolve_template_path()
        output_path = self.build_debug_output_path()

        template_reader = PdfReader(str(template_path))
        if not template_reader.pages:
            raise ValueError("Template DLE senza pagine.")
        first_page = template_reader.pages[0]
        width = float(first_page.mediabox.width)
        height = float(first_page.mediabox.height)

        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(width, height))
        can.setLineWidth(0.9)

        # Red: invoice number box (after "con ns. fattura n°")
        can.setStrokeColor(red)
        can.rect(*self.INVOICE_NUMBER_BOX, fill=0, stroke=1)

        # Blue: invoice date box (after "del")
        can.setStrokeColor(blue)
        can.rect(*self.INVOICE_DATE_BOX, fill=0, stroke=1)

        # Green: today's date box (next to "Data:")
        can.setStrokeColor(green)
        can.rect(*self.TODAY_DATE_BOX, fill=0, stroke=1)

        can.save()
        packet.seek(0)

        overlay_pdf = PdfReader(packet)
        first_page.merge_page(overlay_pdf.pages[0])

        writer = PdfWriter()
        for page in template_reader.pages:
            writer.add_page(page)
        with output_path.open("wb") as stream:
            writer.write(stream)

        return DlePdfBuildResult(
            file_name=output_path.name,
            file_path=str(output_path.resolve()),
            generated_at=datetime.fromtimestamp(output_path.stat().st_mtime),
        )
