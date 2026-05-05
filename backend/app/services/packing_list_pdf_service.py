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
from app.schemas.packing_lists import PackingListRead


@dataclass
class PackingListPdfBuildResult:
    file_name: str
    file_path: str
    generated_at: datetime


class PackingListPdfService:
    def __init__(self, output_root: Path):
        self.output_root = output_root

    @staticmethod
    def _slug(value: str | None, fallback: str) -> str:
        if not value:
            return fallback
        return re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_") or fallback

    @staticmethod
    def _normalize_po_prefix(prefix: str | None) -> str | None:
        if not prefix:
            return None
        text = re.sub(r"\s+", " ", str(prefix).strip())
        match = re.search(r"(\d+)", text)
        if match:
            return f"PO # {match.group(1)}"
        text = text.replace("PO#", "PO #").replace("PO #", "PO #")
        return text

    def _format_po_display(self, po_number: str | None, po_prefix: str | None) -> str:
        po = (po_number or "").strip()
        if not po:
            return ""
        normalized_prefix = self._normalize_po_prefix(po_prefix)
        if normalized_prefix:
            return f"{normalized_prefix} {po}"
        return f"PO # {po}"

    @staticmethod
    def _fmt_weight(value: float | int | None) -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _fmt_cbm(value: float | int | None) -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):.4f}"
        except (TypeError, ValueError):
            return ""

    def build_output_path(self, payload: PackingListRead) -> Path:
        out_dir = self.output_root / "packing_lists"
        out_dir.mkdir(parents=True, exist_ok=True)
        brand = self._slug(payload.brand, "BRAND")
        po = self._slug(payload.po_number, f"PL_{payload.id}")
        dc = self._slug(payload.dc_code, "NA")
        file_name = f"PACKING_LIST_{brand}_{po}_{dc}.pdf"
        return out_dir / file_name

    def build_pdf(self, payload: PackingListRead) -> PackingListPdfBuildResult:
        file_path = self.build_output_path(payload)
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
        usable_width = doc.width

        logo_path = Path(settings.document_logo_path)
        if logo_path.exists():
            logo = RLImage(str(logo_path), width=60 * mm, height=16 * mm)
            header_logo = Table(
                [[logo, Paragraph("<b>Packing List</b>", styles["Title"]), ""]],
                colWidths=[60 * mm, usable_width - (120 * mm), 60 * mm],
            )
            header_logo.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (0, 0), "LEFT"),
                        ("ALIGN", (1, 0), (1, 0), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            elements.append(header_logo)
        else:
            elements.append(Paragraph("<b>Packing List</b>", styles["Title"]))
        elements.append(Spacer(1, 4 * mm))

        destination = payload.destinations[0] if payload.destinations else None
        destination_name = destination.dc_name if destination else (payload.recipient_name or "")
        destination_address_parts = []
        if destination:
            if destination.address:
                destination_address_parts.append(destination.address)
            city_line = " ".join(
                x for x in [destination.zip_code, destination.city, destination.state] if x
            ).strip()
            if city_line:
                destination_address_parts.append(city_line)
            if destination.country:
                destination_address_parts.append(destination.country)
        destination_address = ", ".join(destination_address_parts) if destination_address_parts else (payload.recipient_address or "")
        po_display = self._format_po_display(
            po_number=payload.po_number,
            po_prefix=(destination.po_prefix if destination else None),
        )

        cell_style = styles["BodyText"].clone("cell")
        cell_style.fontName = "Helvetica"
        cell_style.fontSize = 8
        cell_style.leading = 9

        top_row_headers = ["N. FT", "DATA FT", "PO", "DEPT"]
        top_row_values = [
            Paragraph(payload.invoice_number or "", cell_style),
            Paragraph(str(payload.document_date or ""), cell_style),
            Paragraph(po_display, cell_style),
            Paragraph(payload.dept_no or "-", cell_style),
        ]
        top_row_table = Table([top_row_headers, top_row_values], colWidths=[32 * mm, 32 * mm, 96 * mm, 22 * mm])
        top_row_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        summary_data = [
            ["Total Pieces", str(payload.total_pieces)],
            ["Total Cartons", str(payload.total_cartons)],
            ["Total Gross Weight", self._fmt_weight(payload.total_gross_weight)],
            ["Total Net Weight", self._fmt_weight(payload.total_net_weight)],
            ["Total Cubic Meters", self._fmt_cbm(payload.total_cubic_meters)],
        ]
        summary_table = Table(summary_data, colWidths=[42 * mm, 28 * mm])
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

        manufacturer_data = [
            ["RAGIONE SOCIALE FABBRICANTE", Paragraph(payload.supplier_ragione_sociale or payload.supplier_name or "", cell_style)],
            ["", Paragraph(payload.supplier_address_full or "", cell_style)],
        ]
        manufacturer_table = Table(manufacturer_data, colWidths=[62 * mm, 120 * mm])
        manufacturer_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f0f0f0")),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        left_column_blocks: list = [top_row_table, Spacer(1, 3 * mm), manufacturer_table, Spacer(1, 2 * mm)]

        if destination and (
            destination.general_division_name
            or destination.general_address_line_1
            or destination.general_address_line_2
            or destination.general_address_line_3
            or destination.destination_merce_name
            or destination.destination_merce_address_line_1
            or destination.destination_merce_address_line_2
            or destination.destination_merce_address_line_3
        ):
            general_block = [
                ["INDIRIZZO GENERALE", Paragraph(destination.general_division_name or "", cell_style)],
                ["", Paragraph(destination.general_address_line_1 or "", cell_style)],
                ["", Paragraph(destination.general_address_line_2 or "", cell_style)],
                ["", Paragraph(destination.general_address_line_3 or "", cell_style)],
            ]
            destination_dc_display = destination.destination_merce_dc_number or destination.dc_code or ""
            destination_block = [
                ["LUOGO DI DESTINAZIONE DELLA MERCE", Paragraph(destination.destination_merce_name or destination.dc_name or "", cell_style)],
                ["", Paragraph(f"DC# {destination_dc_display}".strip(), cell_style)],
                ["", Paragraph(destination.destination_merce_address_line_1 or destination.address or "", cell_style)],
                ["", Paragraph(destination.destination_merce_address_line_2 or "", cell_style)],
                ["", Paragraph(destination.destination_merce_address_line_3 or "", cell_style)],
            ]
            extra_table = Table(general_block + destination_block, colWidths=[62 * mm, 120 * mm])
            extra_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
                        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f0f0f0")),
                        ("BACKGROUND", (0, 4), (0, 4), colors.HexColor("#f0f0f0")),
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                        ("FONTNAME", (0, 4), (0, 4), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            left_column_blocks.extend([extra_table, Spacer(1, 4 * mm)])

        header_layout = Table(
            [[left_column_blocks, summary_table]],
            colWidths=[192 * mm, 70 * mm],
        )
        header_layout.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(header_layout)
        elements.append(Spacer(1, 4 * mm))

        rows = [[
            "Vendor Style / Rif",
            "Description",
            "PCS x CRT",
            "Pieces",
            "Tot Cartons",
            "Carton Size",
            "Gross /Crt",
            "Net /Crt",
            "Tot Gross",
            "Tot Net",
            "CBM",
        ]]
        span_cmds: list[tuple] = []
        current_row = 1

        groups = payload.groups
        if not groups and payload.lines:
            pseudo: dict[str, dict] = {}
            for line in payload.lines:
                key = line.group_key or f"legacy:{line.id}"
                if key not in pseudo:
                    pseudo[key] = {
                        "group_key": key,
                        "total_cartons": line.cartons,
                        "carton_size": None,
                        "gross_weight_per_carton": line.gross_weight_per_carton,
                        "net_weight_per_carton": line.net_weight_per_carton,
                        "total_gross_weight": None,
                        "total_net_weight": None,
                        "total_cubic_meters": line.line_cubic_meters,
                        "products": [],
                    }
                pseudo[key]["products"].append(
                    {
                        "vendor_style": line.vendor_style,
                        "description": line.description,
                        "pcs_x_crt": line.pcs_per_crt,
                        "pieces": line.pieces,
                    }
                )
            groups = list(pseudo.values())

        for group in groups:
            g_products = group.products if hasattr(group, "products") else group.get("products", [])
            g_key = group.group_key if hasattr(group, "group_key") else group.get("group_key")
            g_cartons = group.total_cartons if hasattr(group, "total_cartons") else group.get("total_cartons")
            g_size = group.carton_size if hasattr(group, "carton_size") else group.get("carton_size")
            g_gross = group.gross_weight_per_carton if hasattr(group, "gross_weight_per_carton") else group.get("gross_weight_per_carton")
            g_net = group.net_weight_per_carton if hasattr(group, "net_weight_per_carton") else group.get("net_weight_per_carton")
            g_tot_gross = group.total_gross_weight if hasattr(group, "total_gross_weight") else group.get("total_gross_weight")
            g_tot_net = group.total_net_weight if hasattr(group, "total_net_weight") else group.get("total_net_weight")
            g_cbm = group.total_cubic_meters if hasattr(group, "total_cubic_meters") else group.get("total_cubic_meters")
            start_row = current_row
            if not g_products:
                rows.append(
                    [
                        "",
                        Paragraph(f"[{g_key}] gruppo vuoto", cell_style),
                        "",
                        "",
                        str(g_cartons or ""),
                        Paragraph(g_size or "", cell_style),
                        self._fmt_weight(g_gross),
                        self._fmt_weight(g_net),
                        self._fmt_weight(g_tot_gross),
                        self._fmt_weight(g_tot_net),
                        self._fmt_cbm(g_cbm),
                    ]
                )
                current_row += 1
                continue

            for p in g_products:
                p_vendor = p.vendor_style if hasattr(p, "vendor_style") else p.get("vendor_style")
                p_desc = p.description if hasattr(p, "description") else p.get("description")
                p_pcs = p.pcs_x_crt if hasattr(p, "pcs_x_crt") else p.get("pcs_x_crt")
                p_qty = p.pieces if hasattr(p, "pieces") else p.get("pieces")
                rows.append(
                    [
                        Paragraph(p_vendor or "", cell_style),
                        Paragraph(p_desc or "", cell_style),
                        str(p_pcs or ""),
                        str(p_qty or ""),
                        str(g_cartons or ""),
                        Paragraph(g_size or "", cell_style),
                        self._fmt_weight(g_gross),
                        self._fmt_weight(g_net),
                        self._fmt_weight(g_tot_gross),
                        self._fmt_weight(g_tot_net),
                        self._fmt_cbm(g_cbm),
                    ]
                )
                current_row += 1

            end_row = current_row - 1
            if end_row > start_row:
                for col in [4, 5, 6, 7, 8, 9, 10]:
                    span_cmds.append(("SPAN", (col, start_row), (col, end_row)))
                span_cmds.append(("VALIGN", (4, start_row), (10, end_row), "MIDDLE"))

        lines_table = Table(
            rows,
            colWidths=[30 * mm, 78 * mm, 14 * mm, 14 * mm, 16 * mm, 32 * mm, 14 * mm, 14 * mm, 16 * mm, 16 * mm, 14 * mm],
            repeatRows=1,
        )
        style_cmds = [
            ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9e2f3")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (3, -1), "TOP"),
            ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (0, 1), (1, -1), "LEFT"),
            ("ALIGN", (2, 1), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        style_cmds.extend(span_cmds)
        lines_table.setStyle(TableStyle(style_cmds))
        elements.append(lines_table)
        elements.append(Spacer(1, 4 * mm))

        elements.append(Paragraph("<font size='9'><b>Made In Italy</b></font>", styles["Normal"]))
        elements.append(Spacer(1, 2 * mm))
        elements.append(
            Paragraph(
                "<font size='8'><i>Wood packaging materials have been used in the shipment and have been treated and marked in compliance with the ISPM 15 standards</i></font>",
                styles["Normal"],
            )
        )

        try:
            doc.build(elements)
        except PermissionError:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            alt = file_path.with_name(f"{file_path.stem}_{ts}{file_path.suffix}")
            doc = SimpleDocTemplate(
                str(alt),
                pagesize=landscape(A4),
                leftMargin=10 * mm,
                rightMargin=10 * mm,
                topMargin=8 * mm,
                bottomMargin=8 * mm,
            )
            doc.build(elements)
            file_path = alt
        return PackingListPdfBuildResult(
            file_name=file_path.name,
            file_path=str(file_path.resolve()),
            generated_at=datetime.utcnow(),
        )
