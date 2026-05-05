from sqlalchemy.orm import Session

from app.db.models.purchase_orders import PurchaseOrder
from app.repositories.purchase_orders_repository import PurchaseOrdersRepository
from app.schemas.purchase_orders import (
    PurchaseOrderLinePreview,
    PurchaseOrderPreviewResponse,
    SupplierDetailsRead,
    PurchaseOrderUpdateRequest,
)


class PurchaseOrdersService:
    def __init__(self, db: Session):
        self.repository = PurchaseOrdersRepository(db)

    def _to_response(self, purchase_order: PurchaseOrder) -> PurchaseOrderPreviewResponse:
        supplier_row = self.repository.get_supplier_by_id(purchase_order.supplier_id)
        if supplier_row is None and purchase_order.supplier_name:
            supplier_row = self.repository.get_supplier_by_name(purchase_order.supplier_name)
        supplier_details = None
        if supplier_row is not None:
            address_parts = [
                supplier_row.indirizzo,
                " ".join(
                    p for p in [supplier_row.cap, supplier_row.citta, supplier_row.provincia] if p
                ).strip()
                or None,
                supplier_row.paese,
            ]
            supplier_details = SupplierDetailsRead(
                fornitore=supplier_row.name,
                ragione_sociale=supplier_row.ragione_sociale,
                indirizzo=supplier_row.indirizzo,
                cap=supplier_row.cap,
                citta=supplier_row.citta,
                provincia=supplier_row.provincia,
                paese=supplier_row.paese,
                telefono=supplier_row.telefono,
                persona_di_contatto=supplier_row.persona_di_contatto,
                emails=supplier_row.emails,
                email_subject_template=supplier_row.email_subject_template,
                email_order_template=supplier_row.email_order_template,
                indirizzo_completo=", ".join(x for x in address_parts if x),
            )

        sorted_db_lines = sorted(
            purchase_order.lines,
            key=lambda x: (
                x.customer_order_line_id if x.customer_order_line_id is not None else 10**9,
                x.id if x.id is not None else 10**9,
            ),
        )

        lines = [
            PurchaseOrderLinePreview(
                id=line.id,
                customer_order_line_id=line.customer_order_line_id,
                vendor_style=line.vendor_style,
                item_code=line.item_code,
                description=line.description,
                nest_code=line.nest_code,
                units_per_dc=line.units_per_dc,
                logistics=line.logistics,
                quantity_base=line.quantity_base or line.quantity_original,
                applied_percent=purchase_order.qty_adjustment_percent,
                quantity_final=line.quantity_final,
            )
            for line in sorted_db_lines
        ]

        total_quantity_base = sum((line.quantity_base or 0) for line in lines)
        total_quantity_final = sum((line.quantity_final or 0) for line in lines)

        pdf_payload = {
            "header": {
                "brand": purchase_order.brand,
                "document_family": purchase_order.document_family,
                "supplier": purchase_order.supplier_name,
                "supplier_company": supplier_details.ragione_sociale if supplier_details else None,
                "po": purchase_order.po_normalized or purchase_order.po_raw or purchase_order.po_number,
                "start_ship_date": str(purchase_order.start_ship_date) if purchase_order.start_ship_date else None,
                "cancel_ship_date": str(purchase_order.cancel_ship_date) if purchase_order.cancel_ship_date else None,
                "adjustment_percent": purchase_order.qty_adjustment_percent,
            },
            "lines": [
                {
                    "vendor_style": line.vendor_style,
                    "item_code": line.item_code,
                    "description": line.description,
                    "nest_code": line.nest_code,
                    "units_per_dc": line.units_per_dc,
                    "quantity_base": line.quantity_base,
                    "quantity_final": line.quantity_final,
                    "logistics": line.logistics,
                }
                for line in lines
            ],
            "summary": {
                "total_lines": len(lines),
                "total_quantity_base": total_quantity_base,
                "total_quantity_final": total_quantity_final,
            },
        }

        return PurchaseOrderPreviewResponse(
            id=purchase_order.id,
            customer_order_id=purchase_order.customer_order_id,
            document_family=purchase_order.document_family,
            brand=purchase_order.brand,
            supplier=purchase_order.supplier_name,
            po=purchase_order.po_normalized or purchase_order.po_raw or purchase_order.po_number,
            po_raw=purchase_order.po_raw,
            po_normalized=purchase_order.po_normalized,
            start_ship_date=purchase_order.start_ship_date,
            cancel_ship_date=purchase_order.cancel_ship_date,
            adjustment_percent=purchase_order.qty_adjustment_percent,
            created_at=purchase_order.created_at,
            supplier_details=supplier_details,
            total_lines=len(lines),
            total_quantity_base=total_quantity_base,
            total_quantity_final=total_quantity_final,
            lines=lines,
            pdf_payload=pdf_payload,
        )

    def generate_preview(self, customer_order_id: int, adjustment_percent: float) -> PurchaseOrderPreviewResponse:
        customer_order = self.repository.get_customer_order(customer_order_id)
        if customer_order is None:
            raise ValueError(f"Ordine cliente non trovato: {customer_order_id}")

        purchase_order = self.repository.create_from_customer_order(
            customer_order=customer_order,
            adjustment_percent=adjustment_percent,
        )
        return self._to_response(purchase_order)

    def get_purchase_order(self, purchase_order_id: int) -> PurchaseOrderPreviewResponse:
        purchase_order = self.repository.get_by_id(purchase_order_id)
        if purchase_order is None:
            raise ValueError(f"Ordine fornitore non trovato: {purchase_order_id}")
        return self._to_response(purchase_order)

    def update_purchase_order(
        self,
        purchase_order_id: int,
        payload: PurchaseOrderUpdateRequest,
    ) -> PurchaseOrderPreviewResponse:
        purchase_order = self.repository.get_by_id(purchase_order_id)
        if purchase_order is None:
            raise ValueError(f"Ordine fornitore non trovato: {purchase_order_id}")

        line_updates = {line.line_id: line.quantity_final for line in payload.line_updates}
        updated = self.repository.update(
            purchase_order=purchase_order,
            adjustment_percent=payload.adjustment_percent,
            line_updates=line_updates,
        )
        return self._to_response(updated)
