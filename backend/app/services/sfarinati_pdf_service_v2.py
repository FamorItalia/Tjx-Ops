from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.core.config import settings
from app.schemas.packing_lists import PackingListRead


@dataclass
class SfarinatiPdfV2BuildResult:
    file_name: str
    file_path: str
    generated_at: datetime


class SfarinatiPdfServiceV2:
    MANDATORY_PARAGRAPH_LINES = (
        "non rientrano nelle disposizioni previste dal Decreto del Ministero delle Politiche Agricole Alimentari e Forestali del 17 dicembre 2013, concernente l'obbligo di \"comunicazione\" prevista",
        "dall'art.12, comma 1, del Decreto del Presidente della Repubblica 9 febbraio 2001, n.187",
        "(cod.09YY - prodotto non sottoposto a comunicazione).",
    )

    def __init__(self, output_root: Path):
        self.output_root = output_root

    @staticmethod
    def _slug(value: str | None, fallback: str) -> str:
        if not value:
            return fallback
        return re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_") or fallback

    def build_output_path(self, payload: PackingListRead) -> Path:
        out_dir = self.output_root / "sfarinati"
        out_dir.mkdir(parents=True, exist_ok=True)
        brand = self._slug(payload.brand, "BRAND")
        po = self._slug(payload.po_number, f"PO_{payload.id}")
        dc = self._slug(payload.dc_code, "GLOBAL")
        return out_dir / f"SFARINATI_{brand}_{po}_{dc}.pdf"

    @staticmethod
    def _fmt_date(value: date | None) -> str:
        if value is None:
            return ""
        return value.strftime("%d/%m/%Y")

    @classmethod
    def _validate_output_contains_mandatory_paragraph(cls, pdf_path: Path) -> None:
        reader = PdfReader(str(pdf_path))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        probe = "cod.09YY - prodotto non sottoposto a comunicazione"
        if probe not in extracted:
            raise RuntimeError(
                f"SFARINATI PDF non valido: paragrafo obbligatorio assente nel file generato ({pdf_path})."
            )

    def build_pdf(self, payload: PackingListRead) -> SfarinatiPdfV2BuildResult:
        output_path = self.build_output_path(payload)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=12 * mm,
            bottomMargin=14 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "sf_title",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=14.5,
            alignment=1,
        )
        body_style = ParagraphStyle(
            "sf_body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10.0,
            leading=12.2,
        )
        section_style = ParagraphStyle(
            "sf_section",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.0,
            leading=12.0,
        )

        invoice_number = (payload.invoice_number or "").strip() or "-"
        invoice_date = self._fmt_date(payload.document_date) or "-"
        generation_date = datetime.now().strftime("%d/%m/%Y")

        elements = []

        logo_path = Path(settings.document_logo_path)
        if logo_path.exists():
            logo = RLImage(str(logo_path), width=68.4 * mm, height=18 * mm)
            logo.hAlign = "CENTER"
            elements.append(logo)
            elements.append(Spacer(1, 4 * mm))

        elements.append(Paragraph("OGGETTO: DICHIARAZIONE DI LIBERA ESPORTAZIONE", title_style))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph("OGGETTO: SFARINATI E PASTE ALIMENTARI", title_style))
        elements.append(Spacer(1, 6 * mm))

        elements.append(
            Paragraph(
                "Consapevoli di assumere ogni conseguente responsabilità, siamo a dichiararvi che le merci (NC.1902) esportate con",
                body_style,
            )
        )
        elements.append(Spacer(1, 4 * mm))

        elements.append(
            Paragraph(
                f"Numero fattura: <b>{invoice_number}</b> - Data fattura: <b>{invoice_date}</b>",
                section_style,
            )
        )
        elements.append(Spacer(1, 4 * mm))
        for line in self.MANDATORY_PARAGRAPH_LINES:
            elements.append(Paragraph(line, body_style))
        elements.append(Spacer(1, 4 * mm))

        elements.append(Paragraph(f"Livorno, {generation_date}", body_style))
        elements.append(Spacer(1, 5 * mm))
        elements.append(Paragraph("Timbro e Firma", section_style))
        elements.append(Spacer(1, 2 * mm))

        stamp_path = Path(settings.document_stamp_signature_path)
        if stamp_path.exists():
            stamp = RLImage(str(stamp_path), width=68 * mm, height=27 * mm)
            stamp.hAlign = "LEFT"
            elements.append(stamp)

        doc.build(elements)
        self._validate_output_contains_mandatory_paragraph(output_path)
        return SfarinatiPdfV2BuildResult(
            file_name=output_path.name,
            file_path=str(output_path.resolve()),
            generated_at=datetime.fromtimestamp(output_path.stat().st_mtime),
        )
