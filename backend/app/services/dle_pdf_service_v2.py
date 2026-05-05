from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings
from app.schemas.packing_lists import PackingListRead


@dataclass
class DlePdfV2BuildResult:
    file_name: str
    file_path: str
    generated_at: datetime


class DlePdfServiceV2:
    def __init__(self, output_root: Path):
        self.output_root = output_root

    @staticmethod
    def _slug(value: str | None, fallback: str) -> str:
        if not value:
            return fallback
        return re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_") or fallback

    def build_output_path(self, payload: PackingListRead) -> Path:
        out_dir = self.output_root / "dle"
        out_dir.mkdir(parents=True, exist_ok=True)
        brand = self._slug(payload.brand, "BRAND")
        po = self._slug(payload.po_number, f"PO_{payload.id}")
        dc = self._slug(payload.dc_code, "GLOBAL")
        return out_dir / f"DLE_{brand}_{po}_{dc}.pdf"

    @staticmethod
    def _fmt_date(value: date | None) -> str:
        if value is None:
            return ""
        return value.strftime("%d/%m/%Y")

    def build_pdf(self, payload: PackingListRead) -> DlePdfV2BuildResult:
        output_path = self.build_output_path(payload)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "dle_title",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=15,
            alignment=1,
        )
        section_style = ParagraphStyle(
            "dle_section",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11.0,
        )
        body_style = ParagraphStyle(
            "dle_body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.6,
            leading=10.0,
        )
        bullet_style = ParagraphStyle(
            "dle_bullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=9.5,
            leftIndent=10,
            firstLineIndent=-8,
            spaceAfter=1.4,
        )
        footer_style = ParagraphStyle(
            "dle_footer",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.0,
            leading=10.5,
        )

        invoice_number = (payload.invoice_number or "").strip()
        invoice_date = self._fmt_date(payload.document_date)
        generation_date = datetime.now().strftime("%d/%m/%Y")

        elements = []

        logo_path = Path(settings.document_logo_path)
        if logo_path.exists():
            logo = RLImage(str(logo_path), width=61.2 * mm, height=15.75 * mm)
            logo.hAlign = "CENTER"
            elements.append(logo)
            elements.append(Spacer(1, 3 * mm))

        elements.append(Paragraph("OGGETTO: DICHIARAZIONE DI LIBERA ESPORTAZIONE", title_style))
        elements.append(Spacer(1, 3.5 * mm))

        elements.append(Paragraph("RIFERIMENTO:", section_style))
        ref_text = (
            f'Numero fattura: <b>{invoice_number or "-"}</b>'
            f"  -  Data fattura: <b>{invoice_date or '-'}</b>"
        )
        elements.append(Paragraph(ref_text, body_style))
        elements.append(Spacer(1, 3.0 * mm))

        elements.append(
            Paragraph(
                "Consapevoli di assumere ogni conseguente responsabilità, siamo a dichiararvi che tutto il materiale esportato:",
                body_style,
            )
        )
        elements.append(Spacer(1, 1.8 * mm))

        bullets = [
            "- non rientra nell’elenco dei beni come da regolamento (CE) n. 428/2009 del Consiglio e successive modifiche, che istituisce un regime comunitario di controllo delle esportazioni, del trasferimento, dell'intermediazione e del transito di prodotti a duplice uso. (Y901)",
            "- non rientra nell’elenco dei beni come da Reg.to (CE) n° 338/97 del Consiglio del 9 dicembre 1997 e succ. modifiche, relativo alla protezione di specie della flora e della fauna selvatiche mediante il controllo del loro commercio (CONVENZIONE DI WASHINGTON – CITES) (Y900)",
            "- non rientra nell’elenco dei beni come da Reg.to (CE) n°1523/2007, pertanto non contiene pelliccia di cane o di gatto (Y922)",
            "- non rientra nell’elenco dei beni come da Reg.to (CE) n° 116/2009 del Consiglio del 18 dicembre 2008, relativo all’esportazione dei beni culturali (Y903-Y905)",
            "- non rientra nell’elenco dei beni come da Reg.to (CE) n° 1236/2005 del Consiglio del 27 giugno 2005, relativo al commercio di determinate merci che potrebbero essere utilizzate per la pena di morte, per la tortura o per altri trattamenti o pene crudeli, inumani o degradanti (Y904-Y906-Y907-Y908)",
            "- non rientra nell’elenco dei beni come da Reg.to (CE) n° 267/12 del Consiglio del 23 marzo 2012 modificato dai regolamenti 1861/1862 del 2015 per i prodotti e tecnologie ad uso militare concernenti le misure restrittive nei confronti dell’Iran (Y920)",
            "- non è soggetto alle disposizioni del Reg.to (CE) n° 689/2008 del Consiglio del 17 giugno 2008 sull’esportazione di sostanze chimiche (all. I e V) (Y916-Y917).",
            "- Prodotto non soggetto alle disposizioni del regolamento (UE) n. 649/2012 sull'esportazione e importazione di sostanze chimiche, allegato I (Y916)",
            "- non è soggetta a licenza di esportazione per sostanze che riducono lo strato di ozono (sostanze controllate, sostanze nuove, prodotti e apparecchiature che dipendono da tali sostanze) come da Reg.to CE 1005/2009 del Consiglio del 16/09/2009 (Y902).",
            "- non rientra nell’elenco dei prodotti e apparecchiature che contengono gas fluorurati ad effetto serra, o il cui funzionamento dipende da tali gas, elencati nell'allegato II del Reg.to (CE) n. 842/2006 del Consiglio del 17 Maggio 2006. (Y926)",
            "- merce non soggetta a sorveglianza, come definita dalla direttiva 2001/83/CE del Parlamento Europeo e del Consiglio (Y903)",
            "- prodotti diversi da quelli derivati dalla foca in conformità del Reg.to UEn.737/2010 (Y032).",
            "- merce che non rientra negli allegati del Reg.to UE n.1332/2013 (restr. Siria) (Y935).",
            "- Le merci dichiarate non rientrano nel campo di applicazione del Reg.to (CE) n. 1984/2003 e/o del Regolamento (UE) n. 640/2010 (cattura tonno rosso) (Y909).",
            "- Le merci dichiarate non sono contemplate dal Reg.to(CE) n. 1005/2008 del Consiglio (Pesca illegale) (Y927).",
            "- Prodotti  e  miscugli  non  contenenti  efedrina,  pseudo  efedrina,  safrolo:  LPS/SPX  (codice addizionale 3201).",
            "- Prodotto non soggetto alle disposizioni del Reg.to (UE) n. 258/2012 per l’esportazione delle armi da fuoco, loro parti e componenti e munizioni (Y934)",
            "- Prodotto non soggetto alle disposizioni del Reg.to (CE) n.1013/2006 (rifiuti) (Y923)",
            "- Merci diverse dal mercurio metallico di cui al regolamento (CE) n. 1102/2008 (Y924)",
            "- Merci diverse da quelle che rientrano nelle disposizioni applicabili del regolamento (UE) 2024/573 sui gas fluorurati a effetto serra (Y160)",
        ]

        for item in bullets:
            elements.append(Paragraph(item, bullet_style))

        elements.append(Spacer(1, 3.2 * mm))
        elements.append(Paragraph(f"Livorno, {generation_date}", footer_style))
        elements.append(Spacer(1, 3.2 * mm))
        elements.append(Paragraph("Timbro e Firma", section_style))
        elements.append(Spacer(1, 1.3 * mm))

        stamp_path = Path(settings.document_stamp_signature_path)
        if stamp_path.exists():
            stamp = RLImage(str(stamp_path), width=68 * mm, height=27 * mm)
            stamp.hAlign = "LEFT"
            elements.append(stamp)

        doc.build(elements)
        return DlePdfV2BuildResult(
            file_name=output_path.name,
            file_path=str(output_path.resolve()),
            generated_at=datetime.fromtimestamp(output_path.stat().st_mtime),
        )
