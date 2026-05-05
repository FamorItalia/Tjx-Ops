from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings
from app.schemas.purchase_orders import PurchaseOrderPreviewResponse


@dataclass
class PdfBuildResult:
    file_name: str
    file_path: str
    generated_at: datetime
    line_count: int


class PurchaseOrderPdfService:
    def __init__(self, output_root: Path):
        self.output_root = output_root

    @staticmethod
    def _slug(value: str | None, fallback: str) -> str:
        if not value:
            return fallback
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
        return cleaned or fallback

    @staticmethod
    def _format_units_per_dc(units: dict[str, int]) -> str:
        if not units:
            return ""
        return ", ".join(f"{dc}:{qty}" for dc, qty in sorted(units.items()))

    @staticmethod
    def _format_logistics(log: dict[str, int | float | str]) -> str:
        if not log:
            return ""
        ordered_keys = [
            "pcs_per_crt",
            "layers_per_pallet",
            "cartons_per_layer",
            "cartons_per_pallet",
            "carton_width_cm",
            "carton_depth_cm",
            "carton_height_cm",
        ]
        pairs = []
        for key in ordered_keys:
            if key in log:
                pairs.append(f"{key}={log[key]}")
        for key, value in log.items():
            if key not in ordered_keys:
                pairs.append(f"{key}={value}")
        return "; ".join(pairs)

    def build_output_path(self, payload: PurchaseOrderPreviewResponse) -> Path:
        out_dir = self.output_root / "purchase_orders"
        out_dir.mkdir(parents=True, exist_ok=True)
        brand_part = self._slug(payload.brand, "BRAND")
        po_part = self._slug(payload.po or payload.po_raw or payload.po_normalized, f"ID_{payload.id}")
        file_name = f"ORDINE_FORNITORE_{brand_part}_{po_part}.pdf"
        return out_dir / file_name

    def build_pdf(self, payload: PurchaseOrderPreviewResponse) -> PdfBuildResult:
        file_path = self.build_output_path(payload)
        file_name = file_path.name

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=landscape(A4),
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=8 * mm,
            bottomMargin=8 * mm,
        )
        styles = getSampleStyleSheet()
        elements = []

        logo_path = Path(settings.document_logo_path)
        if logo_path.exists():
            logo = RLImage(str(logo_path), width=60 * mm, height=16 * mm)
            head = Table([[logo, Paragraph("<b>Ordine Fornitore</b>", styles["Title"])]], colWidths=[68 * mm, 120 * mm])
            head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            elements.append(head)
        else:
            elements.append(Paragraph("<b>Ordine Fornitore</b>", styles["Title"]))
        elements.append(Spacer(1, 4 * mm))

        header_data = [
            ["Brand", payload.brand or ""],
            ["PO", payload.po or ""],
            ["Fornitore", payload.supplier or ""],
            ["Start Ship Date", str(payload.start_ship_date or "")],
            ["Cancel Ship Date", str(payload.cancel_ship_date or "")],
            ["% Adeguamento", f"{payload.adjustment_percent:.2f}%"],
        ]
        header_table = Table(header_data, colWidths=[38 * mm, 90 * mm])
        header_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        elements.append(header_table)
        elements.append(Spacer(1, 4 * mm))

        has_units_per_dc = any(bool(line.units_per_dc) for line in payload.lines)
        has_logistics = any(bool(line.logistics) for line in payload.lines)

        columns = [
            "Vendor Style",
            "Item Code",
            "Descrizione",
            "Nest Code",
            "Qty Base",
            "%",
            "Qty Finale",
        ]
        if has_units_per_dc:
            columns.append("Units per DC")
        if has_logistics:
            columns.append("Dati logistici")

        table_rows: list[list[str]] = [columns]
        for line in payload.lines:
            row = [
                line.vendor_style or "",
                line.item_code or "",
                line.description or "",
                line.nest_code or "",
                str(line.quantity_base or ""),
                f"{(line.applied_percent or 0):.2f}%",
                str(line.quantity_final or ""),
            ]
            if has_units_per_dc:
                row.append(self._format_units_per_dc(line.units_per_dc))
            if has_logistics:
                row.append(self._format_logistics(line.logistics))
            table_rows.append(row)

        base_widths = [30 * mm, 24 * mm, 72 * mm, 16 * mm, 18 * mm, 12 * mm, 18 * mm]
        if has_units_per_dc:
            base_widths.append(36 * mm)
        if has_logistics:
            base_widths.append(46 * mm)

        lines_table = Table(table_rows, colWidths=base_widths, repeatRows=1)
        lines_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9e2f3")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(lines_table)
        elements.append(Spacer(1, 4 * mm))

        summary_data = [
            ["Totale Righe", str(payload.total_lines)],
            ["Totale Qty Base", str(payload.total_quantity_base)],
            ["Totale Qty Finale", str(payload.total_quantity_final)],
        ]
        summary_table = Table(summary_data, colWidths=[42 * mm, 24 * mm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        elements.append(summary_table)

        doc.build(elements)

        return PdfBuildResult(
            file_name=file_name,
            file_path=str(file_path.resolve()),
            generated_at=datetime.utcnow(),
            line_count=len(payload.lines),
        )
