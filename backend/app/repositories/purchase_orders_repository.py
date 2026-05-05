import json
import math
import re

from sqlalchemy.orm import Session, selectinload

from app.core.supplier_normalization import normalize_supplier_name
from app.db.models.customer_orders import CustomerOrder
from app.db.models.master_data import Product, Supplier
from app.db.models.purchase_orders import PurchaseOrder, PurchaseOrderLine


class PurchaseOrdersRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _style_key(value: str | None) -> str | None:
        if not value:
            return None
        key = re.sub(r"[^A-Z0-9]", "", value.upper())
        return key or None

    @staticmethod
    def _normalize_supplier_name(value: str | None) -> str | None:
        return normalize_supplier_name(value)

    @staticmethod
    def _supplier_key(value: str | None) -> str | None:
        if not value:
            return None
        return re.sub(r"[^A-Z0-9]", "", value.upper()) or None

    def _find_supplier(self, supplier_name: str | None) -> Supplier | None:
        normalized = self._normalize_supplier_name(supplier_name)
        key = self._supplier_key(normalized)
        if not key:
            return None
        return self.db.query(Supplier).filter(Supplier.name_key == key).first()

    def get_customer_order(self, order_id: int) -> CustomerOrder | None:
        return (
            self.db.query(CustomerOrder)
            .options(selectinload(CustomerOrder.lines))
            .filter(CustomerOrder.id == order_id)
            .first()
        )

    def get_existing_by_customer_order_id(self, customer_order_id: int) -> PurchaseOrder | None:
        return (
            self.db.query(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .filter(PurchaseOrder.customer_order_id == customer_order_id)
            .first()
        )

    def _build_logistics(self, vendor_style: str | None) -> dict[str, int | float | str]:
        style_key = self._style_key(vendor_style)
        if not style_key:
            return {}
        product = (
            self.db.query(Product)
            .filter(Product.tjx_style_key == style_key)
            .first()
        )
        if product is None:
            return {}
        logistics: dict[str, int | float | str] = {}
        for field in [
            "pcs_per_crt",
            "layers_per_pallet",
            "cartons_per_layer",
            "cartons_per_pallet",
            "carton_width_cm",
            "carton_depth_cm",
            "carton_height_cm",
            "strat_x_pl",
            "strat_x_plt",
            "vol",
            "peso_lordo",
            "peso_netto",
            "pallet_width_cm",
            "pallet_depth_cm",
        ]:
            value = getattr(product, field)
            if value is not None:
                logistics[field] = value
        return logistics

    def _infer_supplier(self, customer_order: CustomerOrder) -> str | None:
        keys = [self._style_key(line.vendor_style) for line in customer_order.lines]
        keys = [k for k in keys if k]
        if not keys:
            return "DA_ASSOCIARE"
        names = (
            self.db.query(Product.supplier_name)
            .filter(Product.tjx_style_key.in_(keys))
            .distinct()
            .all()
        )
        values = [row[0] for row in names if row[0]]
        if not values:
            return "DA_ASSOCIARE"
        values = [self._normalize_supplier_name(v) or v for v in values]
        if len(values) == 1:
            return values[0]
        return "MULTI SUPPLIER"

    @staticmethod
    def _apply_percent(base_qty: int | None, percent: float) -> int | None:
        if base_qty is None:
            return None
        factor = 1.0 + (percent / 100.0)
        return int(math.ceil(base_qty * factor))

    def create_from_customer_order(
        self,
        customer_order: CustomerOrder,
        adjustment_percent: float,
    ) -> PurchaseOrder:
        existing = self.get_existing_by_customer_order_id(customer_order.id)
        if existing is not None:
            normalized_supplier = self._normalize_supplier_name(existing.supplier_name)
            if normalized_supplier and normalized_supplier != existing.supplier_name:
                existing.supplier_name = normalized_supplier
                self.db.commit()
            self._refresh_existing_enrichment(existing, customer_order)
            return existing

        purchase_order = PurchaseOrder(
            customer_order_id=customer_order.id,
            supplier_name=self._infer_supplier(customer_order),
            document_family=customer_order.document_family,
            brand=customer_order.brand,
            po_number=customer_order.po_normalized or customer_order.po_raw,
            po_raw=customer_order.po_raw,
            po_normalized=customer_order.po_normalized,
            start_ship_date=customer_order.start_ship_date,
            cancel_ship_date=customer_order.cancel_ship_date,
            qty_adjustment_percent=adjustment_percent,
        )
        linked_supplier = self._find_supplier(purchase_order.supplier_name)
        if linked_supplier is not None:
            purchase_order.supplier_id = linked_supplier.id
            purchase_order.supplier_name = linked_supplier.name
        self.db.add(purchase_order)
        self.db.flush()

        for line in customer_order.lines:
            base_qty = line.operational_units
            original_qty = line.original_units
            adjusted = self._apply_percent(base_qty, adjustment_percent)
            po_line = PurchaseOrderLine(
                purchase_order_id=purchase_order.id,
                customer_order_line_id=line.id,
                vendor_style=line.vendor_style,
                sku=line.vendor_style,
                item_code=line.item_code,
                description=line.description,
                nest_code=line.nest_code,
                units_per_dc_json=json.dumps(line.operational_units_per_dc) if line.operational_units_per_dc else None,
                logistics_json=json.dumps(self._build_logistics(line.vendor_style)),
                quantity_base=base_qty,
                quantity_original=original_qty,
                quantity_adjusted=adjusted,
                quantity_final=adjusted,
            )
            self.db.add(po_line)

        self.db.commit()
        self.db.refresh(purchase_order)
        return self.get_by_id(purchase_order.id) or purchase_order

    def _refresh_existing_enrichment(
        self,
        purchase_order: PurchaseOrder,
        customer_order: CustomerOrder,
    ) -> None:
        refreshed = False
        normalized_current_supplier = self._normalize_supplier_name(purchase_order.supplier_name)
        if normalized_current_supplier and normalized_current_supplier != purchase_order.supplier_name:
            purchase_order.supplier_name = normalized_current_supplier
            refreshed = True
        inferred_supplier = self._infer_supplier(customer_order)
        if (purchase_order.supplier_name in (None, "", "DA_ASSOCIARE")) and inferred_supplier:
            purchase_order.supplier_name = inferred_supplier
            refreshed = True
        linked_supplier = self._find_supplier(purchase_order.supplier_name)
        if linked_supplier is not None:
            if purchase_order.supplier_id != linked_supplier.id:
                purchase_order.supplier_id = linked_supplier.id
                refreshed = True
            if purchase_order.supplier_name != linked_supplier.name:
                purchase_order.supplier_name = linked_supplier.name
                refreshed = True

        customer_line_by_id = {line.id: line for line in customer_order.lines}
        valid_customer_line_ids = set(customer_line_by_id.keys())
        stale_lines = [
            line
            for line in purchase_order.lines
            if line.customer_order_line_id is None or line.customer_order_line_id not in valid_customer_line_ids
        ]
        if stale_lines:
            for stale in stale_lines:
                self.db.delete(stale)
            refreshed = True
            # Keep in-memory collection consistent for remaining enrichment logic.
            purchase_order.lines = [
                line for line in purchase_order.lines
                if line.customer_order_line_id is not None and line.customer_order_line_id in valid_customer_line_ids
            ]
        existing_po_line_by_customer_line_id = {
            line.customer_order_line_id: line
            for line in purchase_order.lines
            if line.customer_order_line_id is not None
        }
        for po_line in purchase_order.lines:
            style = po_line.vendor_style
            new_logistics = self._build_logistics(style)
            if new_logistics and (not po_line.logistics_json or po_line.logistics_json == "{}"):
                po_line.logistics_json = json.dumps(new_logistics)
                refreshed = True

            src = customer_line_by_id.get(po_line.customer_order_line_id)
            if src is None:
                continue
            src_units_per_dc = src.operational_units_per_dc
            if src_units_per_dc:
                src_units_per_dc_json = json.dumps(src_units_per_dc)
                if po_line.units_per_dc_json != src_units_per_dc_json:
                    po_line.units_per_dc_json = src_units_per_dc_json
                    refreshed = True
            elif po_line.units_per_dc_json:
                po_line.units_per_dc_json = None
                refreshed = True
            if po_line.nest_code != src.nest_code:
                po_line.nest_code = src.nest_code
                refreshed = True

            old_base = po_line.quantity_base
            old_adjusted = po_line.quantity_adjusted
            new_base = src.operational_units
            new_original = src.original_units
            if old_base != new_base or po_line.quantity_original != new_original:
                po_line.quantity_base = new_base
                po_line.quantity_original = new_original
                new_adjusted = self._apply_percent(new_base, purchase_order.qty_adjustment_percent)
                po_line.quantity_adjusted = new_adjusted
                # Preserve manual override only when quantity_final was changed from the previous adjusted value.
                if po_line.quantity_final is None or po_line.quantity_final == old_adjusted:
                    po_line.quantity_final = new_adjusted
                refreshed = True

        # If customer order gained new lines after a parser fix, append missing PO lines.
        for customer_line in customer_order.lines:
            if customer_line.id in existing_po_line_by_customer_line_id:
                continue
            base_qty = customer_line.operational_units
            original_qty = customer_line.original_units
            adjusted = self._apply_percent(base_qty, purchase_order.qty_adjustment_percent)
            new_po_line = PurchaseOrderLine(
                purchase_order_id=purchase_order.id,
                customer_order_line_id=customer_line.id,
                vendor_style=customer_line.vendor_style,
                sku=customer_line.vendor_style,
                item_code=customer_line.item_code,
                description=customer_line.description,
                nest_code=customer_line.nest_code,
                units_per_dc_json=(
                    json.dumps(customer_line.operational_units_per_dc)
                    if customer_line.operational_units_per_dc
                    else None
                ),
                logistics_json=json.dumps(self._build_logistics(customer_line.vendor_style)),
                quantity_base=base_qty,
                quantity_original=original_qty,
                quantity_adjusted=adjusted,
                quantity_final=adjusted,
            )
            self.db.add(new_po_line)
            refreshed = True

        if refreshed:
            self.db.commit()

    def get_by_id(self, purchase_order_id: int) -> PurchaseOrder | None:
        return (
            self.db.query(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .filter(PurchaseOrder.id == purchase_order_id)
            .first()
        )

    def get_supplier_by_id(self, supplier_id: int | None) -> Supplier | None:
        if supplier_id is None:
            return None
        return self.db.query(Supplier).filter(Supplier.id == supplier_id).first()

    def get_supplier_by_name(self, supplier_name: str | None) -> Supplier | None:
        return self._find_supplier(supplier_name)

    def update(
        self,
        purchase_order: PurchaseOrder,
        adjustment_percent: float | None,
        line_updates: dict[int, int],
    ) -> PurchaseOrder:
        if adjustment_percent is not None:
            purchase_order.qty_adjustment_percent = adjustment_percent
            for line in purchase_order.lines:
                base_qty = line.quantity_base or line.quantity_original
                adjusted = self._apply_percent(base_qty, adjustment_percent)
                line.quantity_adjusted = adjusted
                # keep manual override if present, else align to adjusted
                if line.id not in line_updates:
                    line.quantity_final = adjusted

        for line in purchase_order.lines:
            if line.id in line_updates:
                line.quantity_final = line_updates[line.id]

        self.db.commit()
        self.db.refresh(purchase_order)
        return self.get_by_id(purchase_order.id) or purchase_order
