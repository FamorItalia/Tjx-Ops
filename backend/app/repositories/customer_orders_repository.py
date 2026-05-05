import json
from datetime import datetime
import re
from sqlalchemy import delete

from sqlalchemy.orm import Session, selectinload

from app.db.models.customer_orders import CustomerOrder, CustomerOrderLine
from app.db.models.inventory import ProductInventoryAlert, ProductInventoryLedger
from app.db.models.master_data import DistributionCenter, Product
from app.db.models.packing_lists import PackingList
from app.db.models.purchase_orders import PurchaseOrder
from app.schemas.sierra_parser import SierraParseResponse
from app.schemas.tjx_canada_parser import TjxCanadaParseResponse
from app.schemas.tjx_usa_parser import TjxUsaParseResponse


class CustomerOrdersRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_from_sierra(self, parsed: SierraParseResponse, source_pdf_path: str) -> CustomerOrder:
        existing_order = self.find_by_source_file_and_po_raw(
            source_file=parsed.source_file,
            po_raw=parsed.po_raw,
        )
        if existing_order is not None:
            return existing_order

        order = CustomerOrder(
            document_family=parsed.document_family,
            source_file=parsed.source_file,
            source_pdf_name=parsed.source_file,
            source_pdf_path=source_pdf_path,
            parser_family=parsed.document_family,
            po_number=parsed.po_normalized or parsed.po_raw,
            brand=parsed.document_family,
            distribution_center=parsed.distribution_center,
            po_raw=parsed.po_raw,
            po_normalized=parsed.po_normalized,
            start_ship_date=parsed.start_ship_date,
            cancel_ship_date=parsed.cancel_ship_date,
        )
        self.db.add(order)
        self.db.flush()

        for line in parsed.lines:
            db_line = CustomerOrderLine(
                customer_order_id=order.id,
                vendor_style=line.vendor_style,
                item_code=line.item_code,
                description=line.description,
                original_total_units=line.total_units,
                operational_total_units=line.total_units,
                total_units=line.total_units,
                distribution_center=parsed.distribution_center,
                original_units_per_dc_json=json.dumps(line.units_per_dc) if line.units_per_dc else None,
                operational_units_per_dc_json=json.dumps(line.units_per_dc) if line.units_per_dc else None,
                units_per_dc_json=json.dumps(line.units_per_dc) if line.units_per_dc else None,
                nest_code=None,
                carton_profile="mono",
                mixed_carton_group=None,
            )
            self.db.add(db_line)

        self.db.commit()
        self.db.refresh(order)
        self._upsert_distribution_center(
            brand=parsed.document_family,
            dc_code=parsed.distribution_center,
            dc_name=parsed.distribution_center_name,
            address=parsed.distribution_center_address,
        )
        return order

    def create_from_tjx_usa(self, parsed: TjxUsaParseResponse, source_pdf_path: str) -> CustomerOrder:
        existing_order = self.find_by_source_file_and_po_raw(
            source_file=parsed.source_file,
            po_raw=parsed.po_raw,
        )
        if existing_order is not None:
            self._refresh_existing_tjx_usa_lines(existing_order, parsed)
            return existing_order

        order = CustomerOrder(
            document_family=parsed.document_family,
            source_file=parsed.source_file,
            source_pdf_name=parsed.source_file,
            source_pdf_path=source_pdf_path,
            parser_family=parsed.document_family,
            po_number=parsed.po_normalized or parsed.po_raw,
            brand=parsed.brand,
            supplier_name=parsed.supplier_name,
            distribution_center=None,
            po_raw=parsed.po_raw,
            po_normalized=parsed.po_normalized,
            start_ship_date=parsed.start_ship_date,
            cancel_ship_date=parsed.cancel_ship_date,
        )
        self.db.add(order)
        self.db.flush()

        for line in parsed.lines:
            normalized_nest = self._normalize_nest_for_storage(line.nest_code)
            profile = "mixed" if normalized_nest else "mono"
            product = self._resolve_product_for_line(line.vendor_style, line.item_code)
            vend_pack, store_ready_pack = self._sanitize_pack_sizes_for_tjx_usa_line(
                vendor_pack_size=line.vendor_pack_size,
                store_ready_pack_size=line.store_ready_pack_size,
                total_units=line.total_units,
                nest_code=line.nest_code,
                product=product,
            )
            db_line = CustomerOrderLine(
                customer_order_id=order.id,
                vendor_style=line.vendor_style,
                item_code=line.item_code,
                description=line.description,
                original_total_units=line.total_units,
                operational_total_units=line.total_units,
                total_units=line.total_units,
                distribution_center=line.distribution_center,
                original_units_per_dc_json=json.dumps(line.units_per_dc) if line.units_per_dc else None,
                operational_units_per_dc_json=json.dumps(line.units_per_dc) if line.units_per_dc else None,
                units_per_dc_json=json.dumps(line.units_per_dc) if line.units_per_dc else None,
                vend_pack=vend_pack,
                store_ready_pack_size=store_ready_pack,
                nest_code=normalized_nest,
                carton_profile=profile,
                mixed_carton_group=normalized_nest if normalized_nest else None,
            )
            self.db.add(db_line)

        self.db.commit()
        self.db.refresh(order)
        return order

    def _refresh_existing_tjx_usa_lines(self, existing_order: CustomerOrder, parsed: TjxUsaParseResponse) -> None:
        changed = False
        by_key = {}
        for line in existing_order.lines:
            key = (line.vendor_style or "", line.item_code or "")
            by_key[key] = line
        for parsed_line in parsed.lines:
            key = (parsed_line.vendor_style or "", parsed_line.item_code or "")
            db_line = by_key.get(key)
            product = self._resolve_product_for_line(parsed_line.vendor_style, parsed_line.item_code)
            parsed_vendor_pack, parsed_store_ready = self._sanitize_pack_sizes_for_tjx_usa_line(
                vendor_pack_size=parsed_line.vendor_pack_size,
                store_ready_pack_size=parsed_line.store_ready_pack_size,
                total_units=parsed_line.total_units,
                nest_code=parsed_line.nest_code,
                product=product,
            )
            if db_line is None:
                normalized_nest = self._normalize_nest_for_storage(parsed_line.nest_code)
                profile = "mixed" if normalized_nest else "mono"
                new_line = CustomerOrderLine(
                    customer_order_id=existing_order.id,
                    vendor_style=parsed_line.vendor_style,
                    item_code=parsed_line.item_code,
                    description=parsed_line.description,
                    original_total_units=parsed_line.total_units,
                    operational_total_units=parsed_line.total_units,
                    total_units=parsed_line.total_units,
                    distribution_center=parsed_line.distribution_center,
                    original_units_per_dc_json=json.dumps(parsed_line.units_per_dc) if parsed_line.units_per_dc else None,
                    operational_units_per_dc_json=json.dumps(parsed_line.units_per_dc) if parsed_line.units_per_dc else None,
                    units_per_dc_json=json.dumps(parsed_line.units_per_dc) if parsed_line.units_per_dc else None,
                    vend_pack=parsed_vendor_pack,
                    store_ready_pack_size=parsed_store_ready,
                    nest_code=normalized_nest,
                    carton_profile=profile,
                    mixed_carton_group=normalized_nest if normalized_nest else None,
                )
                self.db.add(new_line)
                changed = True
                continue
            if parsed_vendor_pack is not None and db_line.vend_pack != parsed_vendor_pack:
                db_line.vend_pack = parsed_vendor_pack
                changed = True
            if db_line.store_ready_pack_size != parsed_store_ready:
                db_line.store_ready_pack_size = parsed_store_ready
                changed = True
            if (db_line.units_per_dc_json in (None, "")) and parsed_line.units_per_dc:
                db_line.units_per_dc_json = json.dumps(parsed_line.units_per_dc)
                if db_line.original_units_per_dc_json in (None, ""):
                    db_line.original_units_per_dc_json = json.dumps(parsed_line.units_per_dc)
                if db_line.operational_units_per_dc_json in (None, ""):
                    db_line.operational_units_per_dc_json = json.dumps(parsed_line.units_per_dc)
                changed = True
            if db_line.original_total_units is None and parsed_line.total_units is not None:
                db_line.original_total_units = parsed_line.total_units
                changed = True
            if db_line.operational_total_units is None and parsed_line.total_units is not None:
                db_line.operational_total_units = parsed_line.total_units
                changed = True
            normalized_nest = self._normalize_nest_for_storage(parsed_line.nest_code)
            if db_line.nest_code != normalized_nest:
                db_line.nest_code = normalized_nest
                db_line.carton_profile = "mixed" if normalized_nest else "mono"
                db_line.mixed_carton_group = normalized_nest if normalized_nest else None
                changed = True
        if not existing_order.supplier_name and parsed.supplier_name:
            existing_order.supplier_name = parsed.supplier_name
            changed = True
        if changed:
            self.db.commit()

    def _resolve_product_for_line(self, vendor_style: str | None, item_code: str | None) -> Product | None:
        keys = [self.style_key(vendor_style), self.style_key(item_code)]
        keys = [k for k in keys if k]
        if not keys:
            return None
        return self.db.query(Product).filter(Product.tjx_style_key.in_(keys)).first()

    def _sanitize_pack_sizes_for_tjx_usa_line(
        self,
        vendor_pack_size: int | None,
        store_ready_pack_size: int | None,
        total_units: int | None,
        nest_code: str | None,
        product: Product | None,
    ) -> tuple[int | None, int | None]:
        vend_pack = vendor_pack_size if vendor_pack_size and vendor_pack_size > 0 else None
        store_ready = store_ready_pack_size if store_ready_pack_size and store_ready_pack_size > 0 else None

        # Monoreference rows should not carry store-ready values.
        if not nest_code:
            store_ready = None

        # Reject clearly implausible pack sizes extracted from malformed PDF rows.
        if vend_pack is not None:
            if total_units is not None and vend_pack >= total_units:
                vend_pack = None
            elif vend_pack > 200:
                vend_pack = None

        fallback_pack = None
        if product is not None and getattr(product, "pcs_per_crt", None):
            try:
                candidate = int(product.pcs_per_crt)
                if candidate > 0:
                    fallback_pack = candidate
            except (TypeError, ValueError):
                fallback_pack = None

        if vend_pack is None and fallback_pack is not None:
            vend_pack = fallback_pack

        if store_ready is not None and vend_pack is not None:
            if store_ready > vend_pack:
                store_ready = None

        return vend_pack, store_ready

    def create_from_tjx_canada(self, parsed: TjxCanadaParseResponse, source_pdf_path: str) -> CustomerOrder:
        existing_order = self.find_by_source_file_and_po_raw(
            source_file=parsed.source_file,
            po_raw=parsed.po_raw,
        )
        if existing_order is not None:
            return existing_order

        order = CustomerOrder(
            document_family=parsed.document_family,
            source_file=parsed.source_file,
            source_pdf_name=parsed.source_file,
            source_pdf_path=source_pdf_path,
            parser_family=parsed.document_family,
            po_number=parsed.po_normalized or parsed.po_raw,
            brand=parsed.brand,
            distribution_center=None,
            po_raw=parsed.po_raw,
            po_normalized=parsed.po_normalized,
            import_po_number=parsed.import_po_number,
            start_ship_date=parsed.start_ship_date,
            cancel_ship_date=parsed.cancel_ship_date,
        )
        self.db.add(order)
        self.db.flush()

        for line in parsed.lines:
            db_line = CustomerOrderLine(
                customer_order_id=order.id,
                vendor_style=line.vendor_style,
                item_code=line.item_code,
                description=line.description,
                original_total_units=line.total_units,
                operational_total_units=line.total_units,
                total_units=line.total_units,
                distribution_center=None,
                original_units_per_dc_json=None,
                operational_units_per_dc_json=None,
                units_per_dc_json=None,
                nest_code=None,
                vend_pack=line.vend_pack,
                carton_profile="mono",
                mixed_carton_group=None,
            )
            self.db.add(db_line)

        self.db.commit()
        self.db.refresh(order)
        return order

    def _upsert_distribution_center(
        self,
        brand: str | None,
        dc_code: str | None,
        dc_name: str | None,
        address: str | None,
    ) -> None:
        if not brand or not dc_code:
            return
        existing = (
            self.db.query(DistributionCenter)
            .filter(DistributionCenter.brand == brand, DistributionCenter.dc_code == dc_code)
            .first()
        )
        if existing is None:
            existing = DistributionCenter(
                brand=brand,
                dc_code=dc_code,
                name=dc_name or dc_code,
                dc_name=dc_name,
                address=address,
                is_active=True,
            )
            self.db.add(existing)
        else:
            if dc_name:
                existing.dc_name = dc_name
                existing.name = dc_name
            if address:
                existing.address = address
        self.db.commit()

    def list_orders(self, archived: bool | None = None) -> list[CustomerOrder]:
        query = self.db.query(CustomerOrder)
        if archived is not None:
            query = query.filter(CustomerOrder.is_archived == archived)
        return query.order_by(CustomerOrder.id.desc()).all()

    def get_order_by_id(self, order_id: int) -> CustomerOrder | None:
        return (
            self.db.query(CustomerOrder)
            .options(selectinload(CustomerOrder.lines))
            .filter(CustomerOrder.id == order_id)
            .first()
        )

    def get_order_line(self, order_id: int, line_id: int) -> CustomerOrderLine | None:
        return (
            self.db.query(CustomerOrderLine)
            .filter(
                CustomerOrderLine.customer_order_id == order_id,
                CustomerOrderLine.id == line_id,
            )
            .first()
        )

    def set_order_archived(self, order_id: int, archived: bool) -> CustomerOrder | None:
        row = self.db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
        if row is None:
            return None
        row.is_archived = archived
        row.archived_at = datetime.utcnow() if archived else None
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_purchase_order_by_customer_order(self, customer_order_id: int) -> PurchaseOrder | None:
        return (
            self.db.query(PurchaseOrder)
            .filter(PurchaseOrder.customer_order_id == customer_order_id)
            .order_by(PurchaseOrder.id.desc())
            .first()
        )

    def get_purchase_orders_by_customer_orders(self, customer_order_ids: list[int]) -> dict[int, PurchaseOrder]:
        if not customer_order_ids:
            return {}
        rows = (
            self.db.query(PurchaseOrder)
            .filter(PurchaseOrder.customer_order_id.in_(customer_order_ids))
            .order_by(PurchaseOrder.customer_order_id.asc(), PurchaseOrder.id.desc())
            .all()
        )
        out: dict[int, PurchaseOrder] = {}
        for row in rows:
            if row.customer_order_id is None:
                continue
            out.setdefault(row.customer_order_id, row)
        return out

    def list_packing_lists_by_customer_order(self, customer_order_id: int) -> list[PackingList]:
        return (
            self.db.query(PackingList)
            .filter(PackingList.customer_order_id == customer_order_id)
            .order_by(PackingList.id.desc())
            .all()
        )

    def list_packing_lists_by_customer_orders(self, customer_order_ids: list[int]) -> list[PackingList]:
        if not customer_order_ids:
            return []
        return (
            self.db.query(PackingList)
            .filter(PackingList.customer_order_id.in_(customer_order_ids))
            .order_by(PackingList.customer_order_id.asc(), PackingList.id.desc())
            .all()
        )

    def persist(self) -> None:
        self.db.commit()

    def get_distribution_centers_by_brand_codes(
        self,
        brand: str | None,
        dc_codes: list[str],
    ) -> dict[str, DistributionCenter]:
        if not brand or not dc_codes:
            return {}
        rows = (
            self.db.query(DistributionCenter)
            .filter(
                DistributionCenter.brand == brand,
                DistributionCenter.dc_code.in_(dc_codes),
            )
            .all()
        )
        return {row.dc_code: row for row in rows}

    def find_by_source_file_and_po_raw(
        self,
        source_file: str,
        po_raw: str | None,
    ) -> CustomerOrder | None:
        query = self.db.query(CustomerOrder).filter(CustomerOrder.source_file == source_file)
        if po_raw is None:
            query = query.filter(CustomerOrder.po_raw.is_(None))
        else:
            query = query.filter(CustomerOrder.po_raw == po_raw)
        return query.first()

    @classmethod
    def po_key(cls, value: str | None) -> str | None:
        if not value:
            return None
        key = re.sub(r"[^A-Z0-9]", "", value.upper())
        return key or None

    def find_existing_by_business_po(
        self,
        *,
        brand: str | None,
        po_raw: str | None = None,
        po_normalized: str | None = None,
        import_po_number: str | None = None,
    ) -> CustomerOrder | None:
        incoming_keys = {
            k
            for k in [
                self.po_key(po_raw),
                self.po_key(po_normalized),
                self.po_key(import_po_number),
            ]
            if k
        }
        if not incoming_keys:
            return None

        query = self.db.query(CustomerOrder)
        if brand:
            query = query.filter(CustomerOrder.brand == brand)
        rows = query.order_by(CustomerOrder.id.desc()).all()
        for row in rows:
            row_keys = {
                k
                for k in [
                    self.po_key(row.po_raw),
                    self.po_key(row.po_normalized),
                    self.po_key(row.import_po_number),
                    self.po_key(row.po_number),
                ]
                if k
            }
            if row_keys.intersection(incoming_keys):
                return row
        return None

    def delete_order(self, order_id: int) -> bool:
        row = self.db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
        if row is None:
            return False

        self.db.execute(
            delete(ProductInventoryLedger).where(ProductInventoryLedger.customer_order_id == order_id)
        )
        self.db.execute(
            delete(ProductInventoryAlert).where(ProductInventoryAlert.customer_order_id == order_id)
        )
        self.db.execute(
            delete(PurchaseOrder).where(PurchaseOrder.customer_order_id == order_id)
        )
        self.db.execute(
            delete(PackingList).where(PackingList.customer_order_id == order_id)
        )
        self.db.execute(
            delete(CustomerOrderLine).where(CustomerOrderLine.customer_order_id == order_id)
        )
        self.db.execute(
            delete(CustomerOrder).where(CustomerOrder.id == order_id)
        )
        self.db.commit()
        return True

    @staticmethod
    def style_key(value: str | None) -> str | None:
        if not value:
            return None
        key = re.sub(r"[^A-Z0-9]", "", value.upper())
        return key or None

    @staticmethod
    def _normalize_nest_for_storage(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = str(value).strip().upper()
        if cleaned in {"", "0", "-", "NA", "N/A", "NONE", "MONO", "SINGLE", "NULL", "NO"}:
            return None
        if not re.fullmatch(r"[A-Z][A-Z0-9]{0,3}", cleaned):
            return None
        return cleaned

    def get_products_by_styles(self, styles: list[str | None]) -> dict[str, Product]:
        keys = [self.style_key(style) for style in styles]
        keys = [key for key in keys if key]
        if not keys:
            return {}
        rows = self.db.query(Product).filter(Product.tjx_style_key.in_(keys)).all()
        return {row.tjx_style_key: row for row in rows if row.tjx_style_key}
