from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _resolve_brand_logo(brand: str | None) -> Path | None:
        if not brand:
            return None
        brand_key = re.sub(r"[^A-Z0-9]+", "", str(brand).upper())
        logo_dir = Path(settings.templates_root) / "LOGHI INSEGNE"
        candidates: list[str] = []
        if "HOMEGOODS" in brand_key:
            candidates = ["homegoods.png"]
        elif "HOMESENSE" in brand_key:
            candidates = ["HomeSense.png", "homesense.png"]
        elif "TJMAXX" in brand_key or "TJMAX" in brand_key:
            candidates = ["TJ_Maxx.png", "tj-maxx.png"]
        elif "CANADIANMARSHALLS" in brand_key or ("CAN" in brand_key and "MARSH" in brand_key):
            candidates = ["Canadian Marshalls.png", "canadian-marshalls.png"]
        elif "MARSHALLS" in brand_key:
            candidates = ["Marshalls.png", "marshalls.png"]
        elif "WINNERS" in brand_key:
            candidates = ["Winners.png", "winners.png"]
        elif "SIERRA" in brand_key:
            candidates = ["Sierra.jpg", "sierra.jpg", "sierra.png"]
        for name in candidates:
            p = logo_dir / name
            if p.exists():
                return p
        # Fallback: loose match in template logos and frontend public logos
        search_dirs = [logo_dir, Path("C:/Progetti/TJXOPE~1/frontend/public/brands")]
        tokens = [t for t in re.split(r"[^A-Z0-9]+", str(brand).upper()) if t]
        for d in search_dirs:
            if not d.exists():
                continue
            for p in d.glob("*"):
                name_up = p.name.upper()
                if all(tok in name_up for tok in tokens[:2]) or any(tok in name_up for tok in tokens):
                    return p
        return None

    @staticmethod
    def _truncate_text(value: str | None, max_len: int) -> str:
        if not value:
            return ""
        text = str(value).strip()
        if len(text) <= max_len:
            return text
        return f"{text[: max_len - 3].rstrip()}..."

    @staticmethod
    def _fmt_cancel_date(value) -> str:
        if value is None:
            return ""
        return str(value)

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
            ["PO", payload.po or ""],
            ["Fornitore", payload.supplier or ""],
            ["Start Ship Date", str(payload.start_ship_date or "")],
            ["Cancel Ship Date", str(payload.cancel_ship_date or "")],
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
        brand_logo_path = self._resolve_brand_logo(payload.brand)
        if brand_logo_path and brand_logo_path.exists():
            try:
                iw, ih = ImageReader(str(brand_logo_path)).getSize()
                max_w = 40 * mm
                max_h = 20 * mm
                scale = min(max_w / max(iw, 1), max_h / max(ih, 1))
                brand_logo = RLImage(str(brand_logo_path), width=iw * scale, height=ih * scale)
                block = Table([[brand_logo, header_table]], colWidths=[45 * mm, 128 * mm])
                block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
                elements.append(block)
            except Exception:
                elements.append(header_table)
        else:
            elements.append(header_table)
        elements.append(Spacer(1, 4 * mm))

        dc_codes = sorted({dc for line in payload.lines for dc in line.units_per_dc.keys()})

        columns = [
            "Vendor Style",
            "Item Code",
            "Descrizione",
            "Nest Code",
        ]
        for dc in dc_codes:
            columns.append(f"{dc} Units")
        columns.append("Total Units")

        table_rows: list[list[str]] = [columns]
        for line in payload.lines:
            row = [
                line.vendor_style or "",
                line.item_code or "",
                self._truncate_text(line.description, 36),
                line.nest_code or "",
            ]
            total_units = 0
            for dc in dc_codes:
                qty = line.units_per_dc.get(dc)
                total_units += int(qty or 0)
                row.append(str(qty) if qty is not None else "")
            if total_units == 0:
                if line.quantity_final:
                    total_units = int(line.quantity_final)
                elif line.quantity_base:
                    total_units = int(line.quantity_base)
            row.append(str(total_units))
            table_rows.append(row)

        fixed_widths = [24 * mm, 20 * mm, 66 * mm, 16 * mm, 16 * mm]
        remaining = (277 * mm) - sum(fixed_widths)
        dc_w = remaining / max(len(dc_codes), 1) if dc_codes else 20 * mm
        dc_w = max(12 * mm, min(20 * mm, dc_w))
        base_widths = fixed_widths[:4] + ([dc_w] * len(dc_codes)) + [fixed_widths[4]]

        lines_table = Table(table_rows, colWidths=base_widths, repeatRows=1)
        lines_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9e2f3")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (4, 1), (-1, -1), "CENTER"),
                ]
            )
        )
        elements.append(lines_table)
        elements.append(Spacer(1, 4 * mm))

        # Compact logistics by DC (no invoice/date)
        dc_totals: dict[str, dict[str, float]] = {}
        for dc in dc_codes:
            dc_totals[dc] = {
                "pieces": 0.0,
                "cartons": 0.0,
                "volume": 0.0,
                "gross": 0.0,
                "net": 0.0,
            }

        for line in payload.lines:
            pcs_per_crt = int(self._to_float(line.logistics.get("pcs_per_crt"))) if line.logistics else 0
            c_per_pallet = int(self._to_float(line.logistics.get("cartons_per_pallet"))) if line.logistics else 0
            cw = self._to_float(line.logistics.get("carton_width_cm")) if line.logistics else 0.0
            cd = self._to_float(line.logistics.get("carton_depth_cm")) if line.logistics else 0.0
            ch = self._to_float(line.logistics.get("carton_height_cm")) if line.logistics else 0.0
            gross_per_carton = self._to_float(line.logistics.get("peso_lordo")) if line.logistics else 0.0
            net_per_carton = self._to_float(line.logistics.get("peso_netto")) if line.logistics else 0.0
            vol_per_carton_m3 = (cw * cd * ch) / 1_000_000 if cw > 0 and cd > 0 and ch > 0 else 0.0

            for dc, qty in line.units_per_dc.items():
                if dc not in dc_totals:
                    continue
                q = float(qty or 0)
                cartons = math.ceil(q / pcs_per_crt) if pcs_per_crt > 0 and q > 0 else 0
                dc_totals[dc]["pieces"] += q
                dc_totals[dc]["cartons"] += cartons
                dc_totals[dc]["volume"] += cartons * vol_per_carton_m3
                dc_totals[dc]["gross"] += cartons * gross_per_carton
                dc_totals[dc]["net"] += cartons * net_per_carton

        log_rows: list[list[str]] = [[
            "DC",
            "Totale pezzi",
            "Totale cartoni",
            "Volume (m3)",
            "Peso lordo (kg)",
            "Peso netto (kg)",
        ]]
        for dc in dc_codes:
            row = dc_totals[dc]
            log_rows.append(
                [
                    dc,
                    str(int(row["pieces"])),
                    str(int(row["cartons"])),
                    f"{row['volume']:.3f}",
                    f"{row['gross']:.2f}",
                    f"{row['net']:.2f}",
                ]
            )
        if len(log_rows) > 1:
            elements.append(Paragraph("<b>Riepilogo logistico per DC</b>", styles["Heading3"]))
            log_table = Table(log_rows, colWidths=[24 * mm, 32 * mm, 32 * mm, 28 * mm, 36 * mm, 36 * mm], repeatRows=1)
            log_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ]
                )
            )
            elements.append(log_table)
            elements.append(Spacer(1, 4 * mm))

        # Second page: operational general info
        elements.append(PageBreak())
        cancel_date = self._fmt_cancel_date(payload.cancel_ship_date)

        title_style = ParagraphStyle(
            "GTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=14,
            textColor=colors.HexColor("#1f2f46"),
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "GBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=11.0,
            textColor=colors.HexColor("#1d1d1d"),
            spaceAfter=2.0,
        )
        item_style = ParagraphStyle(
            "GItem",
            parent=body_style,
            leftIndent=3,
            spaceAfter=1.8,
        )
        minor_title_style = ParagraphStyle(
            "GMinorTitle",
            parent=body_style,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1f2f46"),
            spaceAfter=1.0,
        )

        elements.append(Paragraph("GENERAL INFO", title_style))
        intro_table = Table(
            [[
                Paragraph(
                    "Le attivita richieste per il completamento di questo ordine includono: creazione e stampa della doppia etichetta cartone, applicazione delle etichette cartone, applicazione delle etichette pre-price, inscatolamento, preparazione dei pallet, nonche creazione, stampa e applicazione delle etichette pallet.<br/><br/>"
                    "In allegato alla presente e disponibile una e-mail con istruzioni dettagliate, comprensive di immagini e documentazione descrittiva, relative all'intero processo di preparazione dell'ordine.<br/><br/>"
                    "<b>I pallet dovranno essere tassativamente fumigati oppure in plastica.</b>",
                    body_style,
                )
            ]],
            colWidths=[277 * mm],
        )
        intro_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd8e3")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fbff")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(intro_table)
        elements.append(Spacer(1, 1.2 * mm))

        left_block = [
            Paragraph("Riepilogo operativo", minor_title_style),
            Paragraph("<b>Etichette prodotto pre-price:</b> saranno consegnate direttamente presso la vostra sede (non sono a vostro carico). Tali etichette saranno previste per alcuni ordini specifici (Preticket: YES), mentre altri ne saranno privi (Preticket: NO).", item_style),
            Paragraph("<b>Etichette cartone:</b> dovranno essere stampate e applicate a vostra cura. Ogni cartone dovra riportare due etichette: una applicata sul lato corto e una sul lato lungo. Una delle due etichette dovra essere sempre visibile sul pallet.", item_style),
            Paragraph("<b>Quantitativi:</b> fare riferimento esclusivamente ai quantitativi indicati in questo documento.", item_style),
            Paragraph("<b>Etichette pallet:</b> dovranno essere stampate e applicate a cura vostra. E richiesta una sola etichetta per ciascun pallet.", item_style),
            Paragraph(f"<b>Prontezza ordine:</b> la merce dovra essere pronta entro e non oltre il <b>{cancel_date}</b>.", item_style),
        ]
        right_block = [
            Paragraph("Ulteriori istruzioni", minor_title_style),
            Paragraph(
                "Preparazione pallet: dovra essere predisposta una pedana per ciascun ordine (identificato dal relativo prefisso PO/DC), anche nel caso di un numero esiguo di cartoni. Non e consentito creare pallet misti contenenti merce destinata a diversi centri di distribuzione. Qualora il numero di cartoni ecceda la capacita di una pedana, dovranno essere preparate pedane aggiuntive e sul foglio pallet dovra essere indicato il numero della pedana ed il totale pedane di quel determinato PO/DC, esempio: se ci sono 3 pedane di un PO/DC, dovranno essere indicate 1/3 , 2/3 , 3/3.",
                item_style,
            ),
            Paragraph("Formato Best Before Date", minor_title_style),
            Paragraph("<b>USA</b>: MESE/GIORNO/ANNO (Es.: 07/23/2041)", item_style),
            Paragraph("<b>CANADA</b>: ANNO/MESE/GIORNO (Es.: 2041/JL/23)", item_style),
            Paragraph("JA=January, FE=February, MR=March, AL=April, MA=May, JN=June, JL=July, AU=August, SE=September, OC=October, NO=November, DE=December.", item_style),
        ]

        content_table = Table(
            [[left_block, right_block]],
            colWidths=[138.5 * mm, 138.5 * mm],
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd8e3")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#d9e1ec")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        )
        elements.append(content_table)

        doc.build(elements)

        return PdfBuildResult(
            file_name=file_name,
            file_path=str(file_path.resolve()),
            generated_at=datetime.utcnow(),
            line_count=len(payload.lines),
        )
