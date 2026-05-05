from pathlib import Path

from sqlalchemy.orm import Session

from app.schemas.email import EmailDraftResponse
from app.services.purchase_order_pdf_service import PurchaseOrderPdfService
from app.services.purchase_orders_service import PurchaseOrdersService


class EmailService:
    def __init__(self, db: Session):
        self.db = db
        self.purchase_orders_service = PurchaseOrdersService(db)
        self.pdf_service = PurchaseOrderPdfService(output_root=Path.cwd() / "output")

    def prepare_supplier_email(self, purchase_order_id: int) -> EmailDraftResponse:
        preview = self.purchase_orders_service.get_purchase_order(purchase_order_id)

        expected_pdf = self.pdf_service.build_output_path(preview)
        if not expected_pdf.exists():
            raise ValueError(
                "PDF ordine fornitore non trovato. Genera prima il PDF con POST /api/v1/purchase-orders/{id}/pdf."
            )

        supplier = preview.supplier_details
        emails = supplier.emails if supplier else []
        to = emails[0] if emails else ""
        cc = emails[1:] if len(emails) > 1 else []
        po_ref = preview.po or preview.po_raw or preview.po_normalized or str(preview.id)
        default_subject = f"ORDINE TJX - PO# {po_ref}"

        def fmt_date(value) -> str:
            if not value:
                return ""
            return value.strftime("%d/%m/%Y")

        variables = {
            "po": po_ref,
            "brand": preview.brand or "",
            "supplier": preview.supplier or "",
            "fornitore": preview.supplier or "",
            "start_ship_date": fmt_date(preview.start_ship_date),
            "cancel_ship_date": fmt_date(preview.cancel_ship_date),
            "contact_name": supplier.persona_di_contatto if supplier and supplier.persona_di_contatto else "",
            "supplier_company": supplier.ragione_sociale if supplier and supplier.ragione_sociale else "",
        }

        def render_template(template: str | None, fallback: str) -> str:
            text = (template or "").strip()
            base = text or fallback
            for key, value in variables.items():
                base = base.replace(f"{{{{{key}}}}}", value)
            return base

        body_lines = [
            f"Gentile {supplier.persona_di_contatto}," if supplier and supplier.persona_di_contatto else "Buongiorno,",
            "",
            "in allegato trasmettiamo l'ordine fornitore relativo a:",
            f"- Brand: {preview.brand or ''}",
            f"- PO: {po_ref}",
            f"- Fornitore: {preview.supplier or ''}",
            f"- Start Ship Date: {preview.start_ship_date or ''}",
            f"- Cancel Ship Date: {preview.cancel_ship_date or ''}",
            "",
            "Restiamo a disposizione per eventuali chiarimenti.",
            "",
            "Cordiali saluti",
        ]
        template_body = supplier.email_order_template if supplier else None
        template_subject = supplier.email_subject_template if supplier else None

        return EmailDraftResponse(
            to=to,
            cc=cc,
            subject=render_template(template_subject, default_subject),
            body=render_template(template_body, "\n".join(body_lines)),
            attachments=[str(expected_pdf.resolve())],
        )
