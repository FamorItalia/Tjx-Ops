from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.core.config import settings
from app.schemas.packing_lists import PackingListRead


@dataclass
class P2PdfV2BuildResult:
    file_name: str
    file_path: str
    generated_at: datetime


@dataclass
class P2RenderContext:
    po_prefix: str | None = None
    customs_nc: str | None = None
    valore_merce: float | None = None


class P2PdfServiceV2:
    def __init__(self, output_root: Path):
        self.output_root = output_root

    @staticmethod
    def _slug(value: str | None, fallback: str) -> str:
        if not value:
            return fallback
        return re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_") or fallback

    def build_output_path(self, payload: PackingListRead) -> Path:
        out_dir = self.output_root / "p2"
        out_dir.mkdir(parents=True, exist_ok=True)
        brand = self._slug(payload.brand, "BRAND")
        po = self._slug(payload.po_number, f"PO_{payload.id}")
        dc = self._slug(payload.dc_code, "GLOBAL")
        return out_dir / f"P2_{brand}_{po}_{dc}.pdf"

    @staticmethod
    def _fmt_num(value: float | int | None, decimals: int = 2) -> str:
        if value is None:
            return "-"
        return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def build_pdf(self, payload: PackingListRead, ctx: P2RenderContext) -> P2PdfV2BuildResult:
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
        body = ParagraphStyle(
            "p2_body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10.0,
            leading=12.2,
        )
        bold = ParagraphStyle(
            "p2_bold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.0,
            leading=12.2,
        )
        title = ParagraphStyle(
            "p2_title",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12.8,
        )

        invoice_number = (payload.invoice_number or "").strip() or "-"
        invoice_date = payload.document_date.strftime("%d/%m/%Y") if payload.document_date else "-"
        generation_date = datetime.now().strftime("%d/%m/%Y")
        po_number = (payload.po_number or "").strip() or "-"
        po_prefix = (ctx.po_prefix or "").strip()
        po_line = f"{po_prefix} {po_number}".strip() if po_prefix else po_number
        nc_value = (ctx.customs_nc or "-").strip() or "-"
        styles_seen: set[str] = set()
        styles_ordered: list[str] = []
        for line in payload.lines:
            style = (line.vendor_style or "").strip()
            if not style:
                continue
            key = style.upper()
            if key in styles_seen:
                continue
            styles_seen.add(key)
            styles_ordered.append(style)
        styles_text = ", ".join(styles_ordered) if styles_ordered else "-"

        elements = []

        logo_path = Path(settings.document_logo_path)
        if logo_path.exists():
            logo = RLImage(str(logo_path), width=68.4 * mm, height=18 * mm)
            logo.hAlign = "CENTER"
            elements.append(logo)
            elements.append(Spacer(1, 6 * mm))

        elements.append(Paragraph("Spett.", body))
        elements.append(Paragraph("EXPEDITORS INTERNATIONAL ITALIA SRL", body))
        elements.append(Paragraph("VIA SANDRO PERTINI, 56", body))
        elements.append(Spacer(1, 5 * mm))

        elements.append(Paragraph("Oggetto:", title))
        elements.append(
            Paragraph(
                "Conferimento mandato operazione di esportazione con dest. USA con richiesta cert. P2 per paste alimentari non cotte né farcite né altrimenti preparate.",
                body,
            )
        )
        elements.append(Spacer(1, 5 * mm))

        elements.append(
            Paragraph(
                f"Numero fattura: <b>{invoice_number}</b> - Data fattura: <b>{invoice_date}</b>",
                bold,
            )
        )
        elements.append(Spacer(1, 4 * mm))

        elements.append(Paragraph(f"PREFIX/PO {po_line}", body))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph("STYLE", body))
        elements.append(Paragraph(styles_text, body))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(f"NC. {nc_value}", body))
        elements.append(Paragraph(f"COLLI {self._fmt_num(payload.total_cartons, 0)}", body))
        elements.append(Paragraph(f"LORDO KG {self._fmt_num(payload.total_gross_weight, 2)}", body))
        elements.append(Paragraph(f"NETTO KG {self._fmt_num(payload.total_net_weight, 2)}", body))
        elements.append(Paragraph(f"VALORE MERCE {self._fmt_num(ctx.valore_merce, 2)}", body))
        elements.append(Spacer(1, 4 * mm))

        elements.append(
            Paragraph(
                "Con la presente diamo l’incarico a codesta società ad effettuare a nome e per nostro conto, o sdoganamento della spedizione citata in oggetto con richiesta P2, e allo stesso tempo si attribuisce il potere di rappresentarci dinanzi alle autorità doganali, ai fini dell’espletamento del presente incarico.",
                body,
            )
        )
        elements.append(Paragraph("Con l’occasione si porgono cordiali saluti.", body))
        elements.append(Spacer(1, 8 * mm))

        elements.append(Paragraph(f"Livorno, {generation_date}", body))
        elements.append(Paragraph("Timbro e Firma", bold))
        elements.append(Spacer(1, 2 * mm))

        stamp_path = Path(settings.document_stamp_signature_path)
        if stamp_path.exists():
            stamp = RLImage(str(stamp_path), width=68 * mm, height=27 * mm)
            stamp.hAlign = "LEFT"
            elements.append(stamp)

        doc.build(elements)
        return P2PdfV2BuildResult(
            file_name=output_path.name,
            file_path=str(output_path.resolve()),
            generated_at=datetime.fromtimestamp(output_path.stat().st_mtime),
        )
