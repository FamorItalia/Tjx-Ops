import json
import calendar
from datetime import date, datetime
from pathlib import Path
import re
import math
import zipfile
import xml.etree.ElementTree as ET
import tempfile
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.supplier_normalization import normalize_supplier_name
from app.db.models.inventory import ProductInventoryAlert
from app.db.models.master_data import Product
from app.repositories.customer_orders_repository import CustomerOrdersRepository
from app.schemas.packing_lists import PackingListPreviewRequest
from app.schemas.orders import (
    ActiveOrderDashboardRead,
    ActiveOrderDcPreviewRead,
    DocumentDcOptionsRead,
    DocumentOptionRead,
    DistributionCenterResolvedRead,
    InventoryAlertDashboardRead,
    OrderDetailRead,
    OrderDocumentRead,
    OrderDocumentGenerateRequest,
    OrderDocumentOptionsRead,
    OrderLineRead,
    OrderPackingListRead,
)
from app.schemas.brands import BrandOrderRowRead, BrandSummaryRead
from app.services.packing_list_pdf_service import PackingListPdfService
from app.services.packing_list_excel_service import PackingListExcelService
from app.services.packing_lists_service import PackingListsService
from app.services.dle_pdf_service_v2 import DlePdfServiceV2
from app.services.dle_excel_service_v2 import DleExcelServiceV2
from app.services.sfarinati_pdf_service_v2 import SfarinatiPdfServiceV2
from app.services.sfarinati_excel_service_v2 import SfarinatiExcelServiceV2
from app.services.p2_pdf_service_v2 import P2PdfServiceV2, P2RenderContext
from app.services.p2_excel_service_v2 import P2ExcelServiceV2
from app.services.purchase_order_pdf_service import PurchaseOrderPdfService
from app.services.purchase_order_excel_service import PurchaseOrderExcelService
from app.services.purchase_orders_service import PurchaseOrdersService
from app.services.inventory_service import InventoryService
from app.services.logistics_summary_service import LogisticsSummaryService
from app.schemas.sierra_parser import SierraParseResponse
from app.schemas.tjx_canada_parser import TjxCanadaParseResponse
from app.schemas.tjx_usa_parser import TjxUsaParseResponse

logger = logging.getLogger(__name__)


class OrdersService:
    NO_DC_CODE = "GLOBAL"
    BRAND_CATALOG: list[tuple[str, str, set[str]]] = [
        ("SIERRA", "Sierra", {"SIERRA"}),
        ("TJMAXX", "TJ Maxx", {"TJMAXX", "TJMAXXUS", "TJXUSA"}),
        ("MARSHALLS", "Marshalls", {"MARSHALLS"}),
        ("HOMEGOODS", "HomeGoods", {"HOMEGOODS", "HOMEGOODSUS"}),
        ("HOMESENSE", "Home Sense", {"HOMESENSE", "HOMESENSECA"}),
        ("CANMARSH", "Canadian Marshalls", {"CANMARSH", "CANADIANMARSHALLS", "CM"}),
        ("WINNERS", "Winners", {"WINNERS"}),
    ]

    def __init__(self, db: Session):
        self.repository = CustomerOrdersRepository(db)

    def save_sierra_parse(self, parsed: SierraParseResponse, source_pdf_path: str) -> int:
        existing = self.repository.find_existing_by_business_po(
            brand=parsed.document_family,
            po_raw=parsed.po_raw,
            po_normalized=parsed.po_normalized,
        )
        if existing is not None:
            po_value = existing.po_normalized or existing.po_raw or existing.po_number or "-"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"PO già importato: {po_value} (ordine ID {existing.id}).",
            )
        saved_order = self.repository.create_from_sierra(parsed=parsed, source_pdf_path=source_pdf_path)
        self._apply_operational_increase_on_import(saved_order.id, percent=2.0)
        self._apply_inventory_consumption_safe(saved_order.id)
        return saved_order.id

    def save_tjx_usa_parse(self, parsed: TjxUsaParseResponse, source_pdf_path: str) -> int:
        existing = self.repository.find_existing_by_business_po(
            brand=parsed.brand,
            po_raw=parsed.po_raw,
            po_normalized=parsed.po_normalized,
        )
        if existing is not None:
            po_value = existing.po_normalized or existing.po_raw or existing.po_number or "-"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"PO già importato: {po_value} (ordine ID {existing.id}).",
            )
        saved_order = self.repository.create_from_tjx_usa(parsed=parsed, source_pdf_path=source_pdf_path)
        self._apply_operational_increase_on_import(saved_order.id, percent=2.0)
        self._apply_inventory_consumption_safe(saved_order.id)
        return saved_order.id

    def save_tjx_canada_parse(self, parsed: TjxCanadaParseResponse, source_pdf_path: str) -> int:
        existing = self.repository.find_existing_by_business_po(
            brand=parsed.brand,
            po_raw=parsed.po_raw,
            po_normalized=parsed.po_normalized,
            import_po_number=parsed.import_po_number,
        )
        if existing is not None:
            po_value = existing.po_normalized or existing.po_raw or existing.po_number or "-"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"PO già importato: {po_value} (ordine ID {existing.id}).",
            )
        saved_order = self.repository.create_from_tjx_canada(parsed=parsed, source_pdf_path=source_pdf_path)
        self._apply_operational_increase_on_import(saved_order.id, percent=2.0)
        self._apply_inventory_consumption_safe(saved_order.id)
        return saved_order.id

    def _apply_operational_increase_on_import(self, order_id: int, percent: float) -> None:
        try:
            self._apply_operational_auto_increase_or_raise(order_id=order_id, percent=percent)
            self.repository.persist()
        except HTTPException as exc:
            self.repository.db.rollback()
            logger.warning(
                "Automatic operational increase skipped for order %s: %s",
                order_id,
                exc.detail,
            )
        except Exception as exc:  # noqa: BLE001
            self.repository.db.rollback()
            logger.warning("Automatic operational increase failed for order %s: %s", order_id, exc)

    def _apply_inventory_consumption_safe(self, order_id: int) -> None:
        try:
            InventoryService(self.repository.db).apply_customer_order_consumption(order_id=order_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Inventory consumption skipped for order %s: %s", order_id, exc)

    def list_orders(self):
        return self.repository.list_orders()

    def delete_order(self, order_id: int) -> None:
        deleted = self.repository.delete_order(order_id=order_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

    def list_active_orders(self):
        return self.repository.list_orders(archived=False)

    def list_archived_orders(self):
        return self.repository.list_orders(archived=True)

    @staticmethod
    def _brand_norm(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^A-Z0-9]", "", str(value).upper())

    def _brand_key_for_order(self, brand_value: str | None) -> str | None:
        norm = self._brand_norm(brand_value)
        if not norm:
            return None
        for key, _, aliases in self.BRAND_CATALOG:
            if norm in aliases:
                return key
        return None

    @staticmethod
    def _subtract_months(input_date: date, months: int) -> date:
        if months <= 0:
            return input_date
        year = input_date.year
        month = input_date.month - months
        while month <= 0:
            month += 12
            year -= 1
        day = min(input_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    def _rolling_window_bounds(self, months: int = 12) -> tuple[date, date]:
        end_date = datetime.utcnow().date()
        start_date = self._subtract_months(end_date, months)
        return start_date, end_date

    @staticmethod
    def _order_window_reference_date(order) -> date | None:
        # Business choice: use cancel date as the primary timeline date.
        if order.cancel_ship_date:
            return order.cancel_ship_date
        if order.start_ship_date:
            return order.start_ship_date
        if order.created_at:
            return order.created_at.date()
        return None

    def _order_operational_pieces(self, order) -> int:
        total = 0
        for line in order.lines:
            if line.operational_units_per_dc:
                total += sum(int(v or 0) for v in line.operational_units_per_dc.values())
            else:
                total += int(line.operational_units or line.total_units or line.original_units or 0)
        return total

    def _order_sale_total_eur(self, order) -> float:
        products_by_key = self.repository.get_products_by_styles([line.vendor_style for line in order.lines])
        total = 0.0
        for line in order.lines:
            style_key = self.repository.style_key(line.vendor_style)
            product = products_by_key.get(style_key) if style_key else None
            unit_sale = float(product.sale_price_eur or 0.0) if product is not None else 0.0
            qty = 0
            if line.operational_units_per_dc:
                qty = sum(int(v or 0) for v in line.operational_units_per_dc.values())
            else:
                qty = int(line.operational_units or line.total_units or line.original_units or 0)
            total += unit_sale * qty
        return round(total, 2)

    def list_brand_summaries(self) -> list[BrandSummaryRead]:
        window_start, window_end = self._rolling_window_bounds(months=12)
        orders = self.repository.list_orders(archived=None)

        by_brand_key: dict[str, list] = {key: [] for key, _, _ in self.BRAND_CATALOG}
        for order in orders:
            key = self._brand_key_for_order(order.brand)
            if key is None:
                continue
            ref_date = self._order_window_reference_date(order)
            if ref_date is None or ref_date < window_start or ref_date > window_end:
                continue
            by_brand_key[key].append(order)

        rows: list[BrandSummaryRead] = []
        for key, label, _ in self.BRAND_CATALOG:
            brand_orders = by_brand_key.get(key, [])
            archived = sum(1 for o in brand_orders if bool(o.is_archived))
            to_ship = sum(1 for o in brand_orders if not bool(o.is_archived))
            revenue = round(sum(self._order_sale_total_eur(o) for o in brand_orders), 2)
            rows.append(
                BrandSummaryRead(
                    key=key,
                    label=label,
                    total_orders_year=len(brand_orders),
                    archived_orders_year=archived,
                    to_ship_orders_year=to_ship,
                    annual_revenue_eur=revenue,
                    period_start=window_start.isoformat(),
                    period_end=window_end.isoformat(),
                )
            )
        return rows

    def list_orders_by_brand(
        self,
        brand_key: str,
        *,
        query: str | None = None,
        archived: bool | None = None,
        month: int | None = None,
        year: int | None = None,
    ) -> list[BrandOrderRowRead]:
        normalized_key = (brand_key or "").strip().upper()
        if normalized_key not in {k for k, _, _ in self.BRAND_CATALOG}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insegna non supportata: {brand_key}",
            )

        orders = self.repository.list_orders(archived=archived)
        po_map = self.repository.get_purchase_orders_by_customer_orders([o.id for o in orders])
        packing_rows = self.repository.list_packing_lists_by_customer_orders([o.id for o in orders])
        packing_by_order: dict[int, list] = {}
        for row in packing_rows:
            if row.customer_order_id is not None:
                packing_by_order.setdefault(int(row.customer_order_id), []).append(row)

        needle = (query or "").strip().lower()
        today = datetime.utcnow().date()
        window_start, window_end = self._rolling_window_bounds(months=12)
        result: list[BrandOrderRowRead] = []

        for order in orders:
            if self._brand_key_for_order(order.brand) != normalized_key:
                continue
            ref_date = self._order_window_reference_date(order)
            if ref_date is None or ref_date < window_start or ref_date > window_end:
                continue
            if year is not None and ref_date.year != int(year):
                continue
            if month is not None and ref_date.month != int(month):
                continue
            po_value = order.po_normalized or order.po_raw or order.po_number
            supplier = self._resolve_supplier_name(order=order, po_row=po_map.get(order.id))
            if needle:
                hay = " ".join(
                    [
                        str(po_value or ""),
                        str(order.brand or ""),
                        str(supplier or ""),
                    ]
                ).lower()
                if needle not in hay:
                    continue
            pieces = self._order_operational_pieces(order)
            sale_total = self._order_sale_total_eur(order)
            pack_rows = packing_by_order.get(order.id, [])
            total_cartons = sum(int(r.total_cartons or 0) for r in pack_rows) if pack_rows else None
            total_volume = (
                round(sum(float(r.total_cubic_meters or 0.0) for r in pack_rows), 4)
                if pack_rows
                else None
            )

            result.append(
                BrandOrderRowRead(
                    order_id=order.id,
                    po=po_value,
                    supplier=supplier,
                    created_at=order.created_at.isoformat() if order.created_at else None,
                    start_ship_date=order.start_ship_date.isoformat() if order.start_ship_date else None,
                    cancel_ship_date=order.cancel_ship_date.isoformat() if order.cancel_ship_date else None,
                    order_status=self._calculate_order_status(today, order.start_ship_date, order.cancel_ship_date),
                    is_archived=bool(order.is_archived),
                    total_pieces=pieces,
                    total_cartons=total_cartons,
                    total_volume_cubic_meters=total_volume,
                    order_total_sale_eur=sale_total,
                )
            )

        result.sort(key=lambda x: (x.po or "", x.order_id), reverse=False)
        return result

    def list_active_dashboard(self) -> list[ActiveOrderDashboardRead]:
        orders = self.repository.list_orders(archived=False)
        if not orders:
            return []

        order_ids = [o.id for o in orders]
        po_map = self.repository.get_purchase_orders_by_customer_orders(order_ids)
        packing_rows = self.repository.list_packing_lists_by_customer_orders(order_ids)

        packing_by_order: dict[int, list] = {}
        for row in packing_rows:
            if row.customer_order_id is None:
                continue
            packing_by_order.setdefault(row.customer_order_id, []).append(row)

        today = datetime.utcnow().date()
        result: list[ActiveOrderDashboardRead] = []
        for order in orders:
            po_row = po_map.get(order.id)
            pack_rows = packing_by_order.get(order.id, [])

            fallback_total_cartons, fallback_cartons_by_dc = self._calculate_cartons_from_order_lines(order)
            total_cartons = sum((r.total_cartons or 0) for r in pack_rows) if pack_rows else fallback_total_cartons
            cartons_by_dc = (
                {
                    str(r.dc_code): int(r.total_cartons or 0)
                    for r in pack_rows
                    if r.dc_code
                }
                if pack_rows
                else fallback_cartons_by_dc
            )

            qty_by_dc: dict[str, int] = {}
            for line in order.lines:
                for dc, qty in line.operational_units_per_dc.items():
                    qty_by_dc[dc] = qty_by_dc.get(dc, 0) + int(qty or 0)

            dc_preview = [
                ActiveOrderDcPreviewRead(
                    dc_code=dc,
                    quantity=qty,
                    cartons=cartons_by_dc.get(dc),
                )
                for dc, qty in sorted(qty_by_dc.items())
            ]

            cancel_date = order.cancel_ship_date
            order_status = self._calculate_order_status(
                today=today,
                start_ship_date=order.start_ship_date,
                cancel_ship_date=order.cancel_ship_date,
            )
            is_late = order_status == "In ritardo"

            result.append(
                ActiveOrderDashboardRead(
                    id=order.id,
                    po=order.po_normalized or order.po_raw or order.po_number,
                    customer=order.brand,
                    supplier=self._resolve_supplier_name(order=order, po_row=po_row),
                    start_ship_date=order.start_ship_date,
                    cancel_ship_date=order.cancel_ship_date,
                    order_status=order_status,
                    is_late=is_late,
                    total_cartons=total_cartons,
                    dc_preview=dc_preview,
                )
            )
        return result

    def list_inventory_alerts_dashboard(self, limit: int = 20) -> list[InventoryAlertDashboardRead]:
        safe_limit = max(1, min(int(limit), 200))
        rows = (
            self.repository.db.query(ProductInventoryAlert, Product)
            .join(Product, Product.id == ProductInventoryAlert.product_id)
            .order_by(ProductInventoryAlert.created_at.desc(), ProductInventoryAlert.id.desc())
            .all()
        )
        alerts: list[InventoryAlertDashboardRead] = []
        seen_pairs: set[tuple[int, str]] = set()
        for alert, product in rows:
            pair_key = (int(alert.product_id), str(alert.stock_type or ""))
            if pair_key in seen_pairs:
                # Keep only the most recent alert per product+stock_type.
                continue
            seen_pairs.add(pair_key)

            current_value = None
            if alert.stock_type == "product":
                current_value = product.stock_product_units
            elif alert.stock_type == "packaging":
                current_value = product.stock_packaging_units
            if current_value is None:
                # No current stock value -> do not show stale historical alerts.
                continue
            current_value_f = float(current_value)
            threshold_f = float(alert.threshold_value)
            if current_value_f >= threshold_f:
                continue

            alerts.append(
                InventoryAlertDashboardRead(
                    id=alert.id,
                    product_id=alert.product_id,
                    product_style=product.tjx_style,
                    supplier_name=product.supplier_name,
                    stock_type=alert.stock_type,
                    threshold_value=threshold_f,
                    current_value=current_value_f,
                    below_by=round(threshold_f - current_value_f, 4),
                    customer_order_id=alert.customer_order_id,
                    created_at=alert.created_at,
                )
            )
            if len(alerts) >= safe_limit:
                break
        return alerts

    @staticmethod
    def _calculate_order_status(
        today: date,
        start_ship_date: date | None,
        cancel_ship_date: date | None,
    ) -> str:
        if start_ship_date and today < start_ship_date:
            return "Programmato"
        if cancel_ship_date and today > cancel_ship_date:
            return "In ritardo"
        return "Pronto al ritiro"

    def get_order_by_id(self, order_id: int):
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            return None
        sanitized_nest_changed = False
        for line in order.lines:
            normalized_nest = self._normalized_nest_code(line.nest_code)
            if line.nest_code != normalized_nest:
                line.nest_code = normalized_nest
                line.carton_profile = "mixed" if normalized_nest else "mono"
                line.mixed_carton_group = normalized_nest if normalized_nest else None
                sanitized_nest_changed = True
        if sanitized_nest_changed:
            self.repository.persist()
        po_row = self.repository.get_purchase_order_by_customer_order(order.id)
        pack_rows = self.repository.list_packing_lists_by_customer_order(order.id)
        fallback_total_cartons, _ = self._calculate_cartons_from_order_lines(order)
        total_cartons = sum((r.total_cartons or 0) for r in pack_rows) if pack_rows else fallback_total_cartons

        dc_codes: set[str] = set()
        if order.distribution_center:
            dc_codes.add(order.distribution_center)
        for line in order.lines:
            if line.distribution_center:
                dc_codes.add(line.distribution_center)
            dc_codes.update(line.units_per_dc.keys())

        dc_map = self.repository.get_distribution_centers_by_brand_codes(
            brand=order.brand,
            dc_codes=sorted(dc_codes),
        )

        lines: list[OrderLineRead] = []
        for line in order.lines:
            units_per_dc = line.units_per_dc
            original_units_per_dc = line.original_units_per_dc
            operational_units_per_dc = line.operational_units_per_dc
            units_per_dc_details: dict[str, DistributionCenterResolvedRead] = {}
            for code in units_per_dc.keys():
                dc = dc_map.get(code)
                if dc is None:
                    continue
                units_per_dc_details[code] = DistributionCenterResolvedRead(
                    dc_code=dc.dc_code,
                    dc_name=dc.dc_name,
                    address=dc.address,
                    city=dc.city,
                    state=dc.state,
                    zip_code=dc.zip_code,
                    country=dc.country,
                )

            line_dc = dc_map.get(line.distribution_center) if line.distribution_center else None
            line_dc_detail = None
            if line_dc is not None:
                line_dc_detail = DistributionCenterResolvedRead(
                    dc_code=line_dc.dc_code,
                    dc_name=line_dc.dc_name,
                    address=line_dc.address,
                    city=line_dc.city,
                    state=line_dc.state,
                    zip_code=line_dc.zip_code,
                    country=line_dc.country,
                )

            lines.append(
                OrderLineRead(
                    id=line.id,
                    vendor_style=line.vendor_style,
                    item_code=line.item_code,
                    description=line.description,
                    original_units=line.original_units,
                    operational_units=line.operational_units,
                    total_units=line.total_units,
                    distribution_center=line.distribution_center,
                    nest_code=self._normalized_nest_code(line.nest_code),
                    original_units_per_dc=original_units_per_dc,
                    operational_units_per_dc=operational_units_per_dc,
                    units_per_dc=units_per_dc,
                    carton_profile=line.carton_profile,
                    mixed_carton_group=line.mixed_carton_group,
                    vend_pack=line.vend_pack,
                    store_ready_pack_size=line.store_ready_pack_size,
                    distribution_center_detail=line_dc_detail,
                    units_per_dc_details=units_per_dc_details,
                )
            )

        return OrderDetailRead(
            id=order.id,
            document_family=order.document_family,
            brand=order.brand,
            supplier=self._resolve_supplier_name(order=order, po_row=po_row),
            source_file=order.source_file,
            start_ship_date=order.start_ship_date,
            cancel_ship_date=order.cancel_ship_date,
            distribution_center=order.distribution_center,
            po_raw=order.po_raw,
            po_normalized=order.po_normalized,
            import_po_number=order.import_po_number,
            total_cartons=total_cartons,
            is_archived=order.is_archived,
            archived_at=order.archived_at,
            created_at=order.created_at,
            lines=lines,
        )

    def _resolve_supplier_name(self, order, po_row) -> str | None:
        inferred, is_multi = self._resolve_supplier_from_order_lines(order)
        if is_multi:
            return "MULTI SUPPLIER"
        if self._is_valid_supplier_value(inferred):
            normalized = normalize_supplier_name(inferred) or inferred
            if order.supplier_name != normalized:
                order.supplier_name = normalized
                self.repository.persist()
            return normalized
        if po_row and self._is_valid_supplier_value(po_row.supplier_name):
            return po_row.supplier_name
        if self._is_valid_supplier_value(order.supplier_name):
            return order.supplier_name
        return None

    def _resolve_supplier_from_order_lines(self, order) -> tuple[str | None, bool]:
        products_by_key = self.repository.get_products_by_styles([line.vendor_style for line in order.lines])
        suppliers: set[str] = set()
        for line in order.lines:
            style_key = self.repository.style_key(line.vendor_style)
            if not style_key:
                continue
            product = products_by_key.get(style_key)
            if product is None:
                continue
            normalized = normalize_supplier_name(product.supplier_name) or product.supplier_name
            if self._is_valid_supplier_value(normalized):
                suppliers.add(normalized.strip())
        if not suppliers:
            return None, False
        if len(suppliers) > 1:
            return None, True
        return next(iter(suppliers)), False

    @staticmethod
    def _is_valid_supplier_value(value: str | None) -> bool:
        if not value:
            return False
        cleaned = value.strip().upper()
        if cleaned in {"ATTENTION", "DEAL", "CIR", "PRIMARY VENDOR", "N/A", "-", "DA_ASSOCIARE"}:
            return False
        return True

    def _calculate_cartons_from_order_lines(self, order) -> tuple[int | None, dict[str, int]]:
        products_by_key = self.repository.get_products_by_styles([line.vendor_style for line in order.lines])

        def mono_denominator(line) -> int | None:
            if line.vend_pack and line.vend_pack > 0:
                return line.vend_pack
            if line.store_ready_pack_size and line.store_ready_pack_size > 0:
                return line.store_ready_pack_size
            key = self.repository.style_key(line.vendor_style)
            product = products_by_key.get(key) if key else None
            if product and product.pcs_per_crt and product.pcs_per_crt > 0:
                return int(product.pcs_per_crt)
            return None

        def cartons_from_qty(qty: int, denominator: int) -> int:
            return int(math.ceil(qty / denominator))

        total_cartons = 0
        cartons_by_dc: dict[str, int] = {}
        has_any_value = False

        mono_lines = [line for line in order.lines if not self._normalized_nest_code(line.nest_code)]
        nested_groups: dict[str, list] = {}
        for line in order.lines:
            nest_code = self._normalized_nest_code(line.nest_code)
            if nest_code:
                nested_groups.setdefault(nest_code, []).append(line)

        for line in mono_lines:
            denom = mono_denominator(line)
            if not denom or denom <= 0:
                return None, {}
            units_map = line.operational_units_per_dc
            if units_map:
                for dc_code, qty in units_map.items():
                    if qty is None or qty < 0:
                        return None, {}
                    if qty == 0:
                        continue
                    cartons = cartons_from_qty(qty, denom)
                    total_cartons += cartons
                    cartons_by_dc[dc_code] = cartons_by_dc.get(dc_code, 0) + cartons
                    has_any_value = True
                continue

            qty = line.operational_units
            if qty is None or qty < 0:
                return None, {}
            if qty == 0:
                continue
            total_cartons += cartons_from_qty(qty, denom)
            has_any_value = True

        for nest_code, lines in nested_groups.items():
            if len(lines) < 2:
                return None, {}
            dc_codes = sorted({dc for line in lines for dc in line.operational_units_per_dc.keys()})
            if dc_codes:
                for dc_code in dc_codes:
                    dc_cartons: int | None = None
                    for line in lines:
                        sr = line.store_ready_pack_size
                        if sr is None or sr <= 0:
                            return None, {}
                        qty = line.operational_units_per_dc.get(dc_code, 0)
                        if qty == 0:
                            continue
                        line_cartons = cartons_from_qty(qty, sr)
                        if dc_cartons is None:
                            dc_cartons = line_cartons
                        elif abs(dc_cartons - line_cartons) > 1:
                            return None, {}
                    if dc_cartons is not None:
                        total_cartons += dc_cartons
                        cartons_by_dc[dc_code] = cartons_by_dc.get(dc_code, 0) + dc_cartons
                        has_any_value = True
                continue

            nested_cartons: int | None = None
            for line in lines:
                sr = line.store_ready_pack_size
                qty = line.operational_units
                if sr is None or sr <= 0 or qty is None or qty < 0:
                    return None, {}
                if qty == 0:
                    continue
                line_cartons = cartons_from_qty(qty, sr)
                if nested_cartons is None:
                    nested_cartons = line_cartons
                elif abs(nested_cartons - line_cartons) > 1:
                    return None, {}
            if nested_cartons is not None:
                total_cartons += nested_cartons
                has_any_value = True

        return (total_cartons, cartons_by_dc) if has_any_value else (None, {})

    @staticmethod
    def _slug(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")

    @staticmethod
    def _to_bool_registry(value: str | None) -> bool:
        if value is None:
            return False
        raw = str(value).strip().upper()
        return raw in {"1", "TRUE", "T", "YES", "Y", "SI", "S", "VERO", "X"}

    @staticmethod
    def _normalized_nest_code(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = str(value).strip().upper()
        if cleaned in {"", "0", "-", "NA", "N/A", "NONE", "MONO", "SINGLE", "NULL", "NO"}:
            return None
        if not re.fullmatch(r"[A-Z][A-Z0-9]{0,3}", cleaned):
            return None
        return cleaned

    def _products_registry_candidates(self) -> list[Path]:
        templates_root = Path(settings.templates_root)
        base = [
            templates_root / "ANAGRAFICHE" / "PRODOTTI.xlsx",
            Path.cwd().parent / "TEMPLATES" / "ANAGRAFICHE" / "PRODOTTI.xlsx",
            Path("C:/Progetti/TJXOPE~1/TEMPLATES/ANAGRAFICHE/PRODOTTI.xlsx"),
        ]
        dynamic: list[Path] = []
        for folder in [
            templates_root / "ANAGRAFICHE",
            Path.cwd().parent / "TEMPLATES" / "ANAGRAFICHE",
            Path("C:/Progetti/TJXOPE~1/TEMPLATES/ANAGRAFICHE"),
        ]:
            if not folder.exists() or not folder.is_dir():
                continue
            for path in folder.glob("*.xlsx"):
                if "PROD" in path.name.upper():
                    dynamic.append(path)
        unique: list[Path] = []
        seen: set[str] = set()
        for p in base + dynamic:
            key = str(p).upper()
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        return unique

    def _load_product_flags_from_registry(
        self,
        style_keys: set[str],
    ) -> dict[str, tuple[bool, bool]]:
        if not style_keys:
            return {}

        xlsx_path = next((p for p in self._products_registry_candidates() if p.exists()), None)
        if xlsx_path is None:
            return {}

        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

        try:
            with zipfile.ZipFile(xlsx_path) as z:
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in z.namelist():
                    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in root.findall(f"{ns}si"):
                        text = "".join(t.text or "" for t in si.iter(f"{ns}t"))
                        shared_strings.append(text)

                worksheet_paths = sorted(
                    [name for name in z.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")]
                )
                if not worksheet_paths:
                    return {}
                sheet_root = ET.fromstring(z.read(worksheet_paths[0]))
                rows = sheet_root.find(f"{ns}sheetData").findall(f"{ns}row")
                if not rows:
                    return {}

                def cell_value(cell) -> str:
                    t = cell.get("t")
                    if t == "inlineStr":
                        is_node = cell.find(f"{ns}is")
                        if is_node is not None:
                            return "".join(x.text or "" for x in is_node.iter(f"{ns}t"))
                        return ""
                    v = cell.find(f"{ns}v")
                    if v is None:
                        return ""
                    raw = v.text or ""
                    if t == "s":
                        try:
                            return shared_strings[int(raw)]
                        except (ValueError, IndexError):
                            return raw
                    return raw

                def col_ref(cell_ref: str | None) -> str:
                    if not cell_ref:
                        return ""
                    return re.sub(r"\d+", "", cell_ref).upper()

                header_cells = rows[0].findall(f"{ns}c")
                header_map: dict[str, str] = {}
                for c in header_cells:
                    cref = col_ref(c.get("r"))
                    hdr = re.sub(r"\s+", " ", (cell_value(c) or "").strip()).upper()
                    if cref and hdr:
                        header_map[cref] = hdr

                style_col = next((k for k, v in header_map.items() if v == "TJX STYLE"), "B")
                sf_col = next((k for k, v in header_map.items() if v in {"HAS_SFARINATI", "SFARINATI"}), "P")
                p2_col = next((k for k, v in header_map.items() if v in {"HAS_P2", "P2"}), "Q")

                out: dict[str, tuple[bool, bool]] = {}
                for row in rows[1:]:
                    row_idx = row.get("r")
                    if not row_idx:
                        continue
                    cells = row.findall(f"{ns}c")
                    data = {col_ref(c.get("r")): cell_value(c) for c in cells}
                    style_raw = (data.get(style_col) or "").strip()
                    style_key = self.repository.style_key(style_raw)
                    if not style_key or style_key not in style_keys:
                        continue
                    has_sf = self._to_bool_registry(data.get(sf_col))
                    has_p2 = self._to_bool_registry(data.get(p2_col))
                    out[style_key] = (has_sf, has_p2)
                return out
        except Exception as exc:
            logger.warning("Lettura anagrafica prodotti fallita: %s", exc)
            return {}

    def _load_nc_from_registry(self, style_keys: set[str]) -> dict[str, str]:
        if not style_keys:
            return {}
        candidates = self._products_registry_candidates() + [
            Path(settings.templates_root) / "ANAGRAFICHE" / "FORNITORI.xlsx",
            Path("C:/Progetti/TJXOPE~1/TEMPLATES/ANAGRAFICHE/FORNITORI.xlsx"),
        ]
        xlsx_path = next((p for p in candidates if p.exists()), None)
        if xlsx_path is None:
            return {}
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        try:
            with zipfile.ZipFile(xlsx_path) as z:
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in z.namelist():
                    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in root.findall(f"{ns}si"):
                        text = "".join(t.text or "" for t in si.iter(f"{ns}t"))
                        shared_strings.append(text)

                worksheet_paths = sorted(
                    [name for name in z.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")]
                )
                if not worksheet_paths:
                    return {}
                sheet_root = ET.fromstring(z.read(worksheet_paths[0]))
                rows = sheet_root.find(f"{ns}sheetData").findall(f"{ns}row")
                if not rows:
                    return {}

                def cell_value(cell) -> str:
                    t = cell.get("t")
                    if t == "inlineStr":
                        is_node = cell.find(f"{ns}is")
                        if is_node is not None:
                            return "".join(x.text or "" for x in is_node.iter(f"{ns}t"))
                        return ""
                    v = cell.find(f"{ns}v")
                    if v is None:
                        return ""
                    raw = v.text or ""
                    if t == "s":
                        try:
                            return shared_strings[int(raw)]
                        except (ValueError, IndexError):
                            return raw
                    return raw

                def col_ref(cell_ref: str | None) -> str:
                    if not cell_ref:
                        return ""
                    return re.sub(r"\d+", "", cell_ref).upper()

                header_cells = rows[0].findall(f"{ns}c")
                header_map: dict[str, str] = {}
                for c in header_cells:
                    cref = col_ref(c.get("r"))
                    hdr = re.sub(r"\s+", " ", (cell_value(c) or "").strip()).upper()
                    if cref and hdr:
                        header_map[cref] = hdr

                style_col = next((k for k, v in header_map.items() if v == "TJX STYLE"), "B")
                nc_col = next((k for k, v in header_map.items() if v == "NC"), "R")

                out: dict[str, str] = {}
                for row in rows[1:]:
                    cells = row.findall(f"{ns}c")
                    data = {col_ref(c.get("r")): cell_value(c) for c in cells}
                    style_key = self.repository.style_key((data.get(style_col) or "").strip())
                    nc_val = (data.get(nc_col) or "").strip()
                    if style_key and style_key in style_keys and nc_val:
                        out[style_key] = nc_val
                return out
        except Exception as exc:
            logger.warning("Lettura NC da anagrafica fallita: %s", exc)
            return {}

    def list_order_documents(self, order_id: int) -> list[OrderDocumentRead]:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        output_root = Path.cwd() / "output"
        po_slug = self._slug(order.po_normalized or order.po_raw or order.po_number)
        documents: list[OrderDocumentRead] = []
        seen_paths: set[str] = set()
        
        def normalized_format(file_path: Path) -> str:
            return "excel" if file_path.suffix.lower() == ".xlsx" else "pdf"

        purchase_dir = output_root / "purchase_orders"
        if purchase_dir.exists():
            for file in list(purchase_dir.glob("*.pdf")) + list(purchase_dir.glob("*.xlsx")):
                upper_name = file.name.upper()
                if po_slug and po_slug not in upper_name:
                    continue
                resolved = str(file.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                documents.append(
                    OrderDocumentRead(
                        document_type=("purchase_order_pdf" if file.suffix.lower() == ".pdf" else "purchase_order_excel"),
                        level="PO",
                        dc_code=None,
                        format=normalized_format(file),
                        file_name=file.name,
                        file_path=resolved,
                        generated_at=datetime.fromtimestamp(file.stat().st_mtime),
                    )
                )

        packing_dir = output_root / "packing_lists"
        packing_rows = self.repository.list_packing_lists_by_customer_order(order_id)
        dc_rows = {self._slug(row.dc_code): row.dc_code for row in packing_rows if row.dc_code}
        has_global_dc = any(not (row.dc_code or "").strip() for row in packing_rows)
        if packing_dir.exists():
            for file in list(packing_dir.glob("*.pdf")) + list(packing_dir.glob("*.xlsx")):
                upper_name = file.name.upper()
                if po_slug and po_slug not in upper_name:
                    continue
                dc_code: str | None = None
                for dc_slug, dc_raw in dc_rows.items():
                    if dc_slug and dc_slug in upper_name:
                        dc_code = dc_raw
                        break
                if dc_code is None and has_global_dc:
                    dc_code = self.NO_DC_CODE
                resolved = str(file.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                documents.append(
                    OrderDocumentRead(
                        document_type=("packing_list_pdf" if file.suffix.lower() == ".pdf" else "packing_list_excel"),
                        level="DC",
                        dc_code=dc_code,
                        format=normalized_format(file),
                        file_name=file.name,
                        file_path=resolved,
                        generated_at=datetime.fromtimestamp(file.stat().st_mtime),
                    )
                )

        dle_dir = output_root / "dle"
        if dle_dir.exists():
            for file in list(dle_dir.glob("*.pdf")) + list(dle_dir.glob("*.xlsx")):
                upper_name = file.name.upper()
                if po_slug and po_slug not in upper_name:
                    continue
                dc_code: str | None = None
                for dc_slug, dc_raw in dc_rows.items():
                    if dc_slug and dc_slug in upper_name:
                        dc_code = dc_raw
                        break
                if dc_code is None and has_global_dc:
                    dc_code = self.NO_DC_CODE
                resolved = str(file.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                documents.append(
                    OrderDocumentRead(
                        document_type=("dle_pdf" if file.suffix.lower() == ".pdf" else "dle_excel"),
                        level="DC",
                        dc_code=dc_code,
                        format=normalized_format(file),
                        file_name=file.name,
                        file_path=resolved,
                        generated_at=datetime.fromtimestamp(file.stat().st_mtime),
                    )
                )

        sfarinati_dir = output_root / "sfarinati"
        if sfarinati_dir.exists():
            for file in list(sfarinati_dir.glob("*.pdf")) + list(sfarinati_dir.glob("*.xlsx")):
                upper_name = file.name.upper()
                if po_slug and po_slug not in upper_name:
                    continue
                dc_code: str | None = None
                for dc_slug, dc_raw in dc_rows.items():
                    if dc_slug and dc_slug in upper_name:
                        dc_code = dc_raw
                        break
                if dc_code is None and has_global_dc:
                    dc_code = self.NO_DC_CODE
                resolved = str(file.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                documents.append(
                    OrderDocumentRead(
                        document_type=("sfarinati_pdf" if file.suffix.lower() == ".pdf" else "sfarinati_excel"),
                        level="DC",
                        dc_code=dc_code,
                        format=normalized_format(file),
                        file_name=file.name,
                        file_path=resolved,
                        generated_at=datetime.fromtimestamp(file.stat().st_mtime),
                    )
                )

        p2_dir = output_root / "p2"
        if p2_dir.exists():
            for file in list(p2_dir.glob("*.pdf")) + list(p2_dir.glob("*.xlsx")):
                upper_name = file.name.upper()
                if po_slug and po_slug not in upper_name:
                    continue
                dc_code: str | None = None
                for dc_slug, dc_raw in dc_rows.items():
                    if dc_slug and dc_slug in upper_name:
                        dc_code = dc_raw
                        break
                if dc_code is None and has_global_dc:
                    dc_code = self.NO_DC_CODE
                resolved = str(file.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                documents.append(
                    OrderDocumentRead(
                        document_type=("p2_pdf" if file.suffix.lower() == ".pdf" else "p2_excel"),
                        level="DC",
                        dc_code=dc_code,
                        format=normalized_format(file),
                        file_name=file.name,
                        file_path=resolved,
                        generated_at=datetime.fromtimestamp(file.stat().st_mtime),
                    )
                )

        documents.sort(
            key=lambda x: (
                x.generated_at or datetime.min,
                x.document_type or "",
                x.dc_code or "",
            ),
            reverse=True,
        )
        return documents

    def build_export_documents_zip(self, order_id: int, file_format: str) -> Path:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        normalized_format = (file_format or "").strip().lower()
        if normalized_format not in {"pdf", "excel"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato non valido. Usa 'pdf' o 'excel'.",
            )

        filtered_docs = self._ensure_export_documents_generated(order_id=order_id, file_format=normalized_format)

        if not filtered_docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Nessun documento export in formato {normalized_format.upper()} disponibile per questo ordine "
                    "dopo la generazione automatica."
                ),
            )

        po_value = order.po_normalized or order.po_raw or order.po_number or str(order.id)
        po_slug = self._slug(po_value) or f"ORDER_{order.id}"
        tmp_dir = Path(tempfile.gettempdir()) / "tjx_ops_hub"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = tmp_dir / f"DOCUMENTI_EXPORT_PO_{po_slug}_{normalized_format.upper()}.zip"

        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for doc in filtered_docs:
                src = Path(doc.file_path)
                if not src.exists() or not src.is_file():
                    continue
                arcname = Path(f"PO_{po_slug}") / doc.file_name
                archive.write(src, arcname=str(arcname))

        return zip_path

    def list_order_packing_lists(self, order_id: int) -> list[OrderPackingListRead]:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        rows = self.repository.list_packing_lists_by_customer_order(order_id)
        return [
            OrderPackingListRead(
                id=row.id,
                dc_code=row.dc_code or self.NO_DC_CODE,
                invoice_number=row.invoice_number,
                document_date=row.document_date,
                total_pieces=row.total_pieces,
                total_cartons=row.total_cartons,
                total_gross_weight=row.total_gross_weight,
                total_net_weight=row.total_net_weight,
                total_cubic_meters=row.total_cubic_meters,
                total_pallets=row.total_pallets,
                totals_manually_overridden=bool(getattr(row, "totals_manually_overridden", 0)),
                created_at=row.created_at,
            )
            for row in rows
        ]

    def reset_order_packing_list_totals_to_calculated(self, order_id: int) -> list[OrderPackingListRead]:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        rows = self.repository.list_packing_lists_by_customer_order(order_id)
        if not rows:
            po_preview = self._ensure_purchase_order_preview(order_id)
            PackingListsService(self.repository.db).create_previews(
                PackingListPreviewRequest(purchase_order_id=po_preview.id)
            )
            rows = self.repository.list_packing_lists_by_customer_order(order_id)
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nessuna packing list disponibile per ripristinare i totali.",
                )

        summary = LogisticsSummaryService(self.repository).get_order_logistics_summary(order_id)
        by_dc: dict[str, object] = {
            (dc.dc_code or self.NO_DC_CODE): dc
            for dc in summary.operational.dcs
        }

        for row in rows:
            dc_key = (row.dc_code or self.NO_DC_CODE)
            dc = by_dc.get(dc_key)
            if dc is None:
                continue
            row.total_gross_weight = float(dc.total_gross_weight or 0.0)
            row.total_net_weight = float(dc.total_net_weight or 0.0)
            row.total_cubic_meters = float(dc.total_volume or 0.0)
            row.total_pallets = int(dc.total_pallets or 0) if dc.total_pallets is not None else None
            row.totals_manually_overridden = 0

        self.repository.persist()
        return self.list_order_packing_lists(order_id=order_id)

    def _collect_order_dc_codes(self, order) -> list[str]:
        dc_codes: set[str] = set()
        if order.distribution_center:
            dc_codes.add(order.distribution_center)
        for line in order.lines:
            if line.distribution_center and int(line.operational_units or line.original_units or 0) > 0:
                dc_codes.add(line.distribution_center)
            for dc, qty in line.operational_units_per_dc.items():
                if int(qty or 0) > 0:
                    dc_codes.add(dc)
            for dc, qty in line.original_units_per_dc.items():
                if int(qty or 0) > 0:
                    dc_codes.add(dc)
        if dc_codes:
            return sorted(dc_codes)

        # Fallback for families/layouts without explicit DC split (e.g. some Canada orders).
        packing_rows = self.repository.list_packing_lists_by_customer_order(order.id)
        for row in packing_rows:
            if row.dc_code:
                dc_codes.add(row.dc_code)
        if dc_codes:
            return sorted(dc_codes)

        if order.lines:
            return [self.NO_DC_CODE]
        return sorted(dc_codes)

    def _resolve_order_document_flags(self, order) -> tuple[bool, bool]:
        lookup_values: list[str | None] = []
        for line in order.lines:
            lookup_values.append(line.vendor_style)
            lookup_values.append(line.item_code)
        products_by_key = self.repository.get_products_by_styles(lookup_values)
        style_keys_for_registry: set[str] = set()
        for line in order.lines:
            for k in [self.repository.style_key(line.vendor_style), self.repository.style_key(line.item_code)]:
                if k:
                    style_keys_for_registry.add(k)
        registry_flags = self._load_product_flags_from_registry(style_keys_for_registry)
        has_sfarinati = False
        has_p2 = False
        for line in order.lines:
            keys = [
                self.repository.style_key(line.vendor_style),
                self.repository.style_key(line.item_code),
            ]
            product = None
            for key in keys:
                if not key:
                    continue
                product = products_by_key.get(key)
                if product is not None:
                    break
            if product is None:
                for key in keys:
                    if key and key in registry_flags:
                        reg_sf, reg_p2 = registry_flags[key]
                        if reg_sf:
                            has_sfarinati = True
                        if reg_p2:
                            has_p2 = True
                continue

            db_sf = bool(getattr(product, "document_sfarinati", False))
            db_p2 = bool(getattr(product, "document_p2", False))
            reg_sf = False
            reg_p2 = False
            for key in keys:
                if key and key in registry_flags:
                    r_sf, r_p2 = registry_flags[key]
                    reg_sf = reg_sf or r_sf
                    reg_p2 = reg_p2 or r_p2

            if db_sf or reg_sf:
                has_sfarinati = True
            if db_p2 or reg_p2:
                has_p2 = True
        return has_sfarinati, has_p2

    def get_order_document_options(self, order_id: int) -> OrderDocumentOptionsRead:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        has_sfarinati, has_p2 = self._resolve_order_document_flags(order)
        dc_codes = self._collect_order_dc_codes(order)

        order_level = [
            DocumentOptionRead(
                document_type="purchase_order",
                label="Ordine fornitore",
                level="ORDER",
                enabled=True,
                formats=["pdf", "excel"],
            )
        ]

        def dc_option(
            doc_type: str,
            label: str,
            enabled: bool,
            reason: str | None = None,
            formats: list[str] | None = None,
        ) -> DocumentOptionRead:
            return DocumentOptionRead(
                document_type=doc_type,
                label=label,
                level="DC",
                enabled=enabled,
                formats=(formats or ["pdf"]) if enabled else [],
                reason=reason,
            )

        dc_options: list[DocumentDcOptionsRead] = []
        for dc in dc_codes:
            options = [
                dc_option("packing_list", "Packing List", enabled=True, formats=["pdf", "excel"]),
                dc_option(
                    "dle",
                    "DLE",
                    enabled=True,
                    formats=["pdf", "excel"],
                ),
            ]
            if has_sfarinati:
                options.append(
                    dc_option(
                        "sfarinati",
                        "Sfarinati",
                        enabled=True,
                        formats=["pdf", "excel"],
                    )
                )
            if has_p2:
                options.append(
                    dc_option(
                        "p2",
                        "P2",
                        enabled=True,
                        formats=["pdf", "excel"],
                    )
                )
            dc_options.append(DocumentDcOptionsRead(dc_code=dc, options=options))

        return OrderDocumentOptionsRead(
            order_id=order_id,
            has_sfarinati=has_sfarinati,
            has_p2=has_p2,
            order_level_options=order_level,
            dc_level_options=dc_options,
        )

    def _ensure_purchase_order_preview(self, order_id: int):
        db = self.repository.db
        po_service = PurchaseOrdersService(db)
        existing_po = self.repository.get_purchase_order_by_customer_order(order_id)
        if existing_po is None:
            return po_service.generate_preview(customer_order_id=order_id, adjustment_percent=2.0)
        return po_service.get_purchase_order(existing_po.id)

    def _generate_purchase_order_pdf(self, order_id: int) -> None:
        po_preview = self._ensure_purchase_order_preview(order_id)
        po_pdf_service = PurchaseOrderPdfService(output_root=Path.cwd() / "output")
        po_pdf_service.build_pdf(po_preview)

    def _generate_purchase_order_excel(self, order_id: int) -> None:
        po_preview = self._ensure_purchase_order_preview(order_id)
        po_excel_service = PurchaseOrderExcelService(output_root=Path.cwd() / "output")
        po_excel_service.build_excel(po_preview)

    def _resolve_packing_row_for_dc(self, order_id: int, dc_code: str):
        db = self.repository.db
        packing_service = PackingListsService(db)
        po_preview = self._ensure_purchase_order_preview(order_id)
        packing_rows = packing_service.list_by_purchase_order_id(po_preview.id)
        if not packing_rows:
            packing_service.create_previews(
                PackingListPreviewRequest(
                    purchase_order_id=po_preview.id,
                )
            )
            packing_rows = packing_service.list_by_purchase_order_id(po_preview.id)
        requested = (dc_code or "").strip().upper()
        if requested in {"N/A", "NA", "NO_DC", self.NO_DC_CODE}:
            row = next((x for x in packing_rows if not (x.dc_code or "").strip()), None)
        else:
            row = next((x for x in packing_rows if (x.dc_code or "") == dc_code), None)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Packing list non trovata per DC {dc_code}.",
            )
        return row

    def _generate_packing_list_pdf_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        packing_pdf_service = PackingListPdfService(output_root=Path.cwd() / "output")
        packing_pdf_service.build_pdf(row)

    def _generate_packing_list_excel_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        packing_excel_service = PackingListExcelService(output_root=Path.cwd() / "output")
        packing_excel_service.build_excel(row)

    def _generate_dle_pdf_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        dle_service = DlePdfServiceV2(output_root=Path.cwd() / "output")
        dle_service.build_pdf(row)

    def _generate_dle_excel_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        dle_service = DleExcelServiceV2(output_root=Path.cwd() / "output")
        dle_service.build_excel(row)

    def _generate_sfarinati_pdf_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        sfarinati_service = SfarinatiPdfServiceV2(output_root=Path.cwd() / "output")
        sfarinati_service.build_pdf(row)

    def _generate_sfarinati_excel_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        sfarinati_service = SfarinatiExcelServiceV2(output_root=Path.cwd() / "output")
        sfarinati_service.build_excel(row)

    def _build_p2_context_for_row(self, row) -> P2RenderContext:
        styles: list[str | None] = []
        style_keys: set[str] = set()
        for line in row.lines:
            styles.extend([line.vendor_style, line.item_code])
            for raw in [line.vendor_style, line.item_code]:
                key = self.repository.style_key(raw)
                if key:
                    style_keys.add(key)

        products_map = self.repository.get_products_by_styles(styles)
        nc_map = self._load_nc_from_registry(style_keys)
        nc_values: list[str] = []
        for key in style_keys:
            val = (nc_map.get(key) or "").strip()
            if val and val not in nc_values:
                nc_values.append(val)
        customs_nc = ", ".join(nc_values) if nc_values else "-"

        valore_merce = 0.0
        has_value = False
        for line in row.lines:
            pieces = float(line.pieces or 0)
            if pieces <= 0:
                continue
            prod = None
            for raw in [line.vendor_style, line.item_code]:
                key = self.repository.style_key(raw)
                if key and key in products_map:
                    prod = products_map[key]
                    break
            if prod is None:
                continue
            sale_price = float(getattr(prod, "sale_price_eur", 0) or 0)
            if sale_price <= 0:
                continue
            has_value = True
            valore_merce += pieces * sale_price

        po_prefix = None
        if row.destinations:
            po_prefix = row.destinations[0].po_prefix

        return P2RenderContext(
            po_prefix=po_prefix,
            customs_nc=customs_nc,
            valore_merce=(round(valore_merce, 2) if has_value else None),
        )

    def _generate_p2_pdf_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        ctx = self._build_p2_context_for_row(row)
        p2_service = P2PdfServiceV2(output_root=Path.cwd() / "output")
        p2_service.build_pdf(row, ctx)

    def _generate_p2_excel_for_dc(self, order_id: int, dc_code: str) -> None:
        row = self._resolve_packing_row_for_dc(order_id=order_id, dc_code=dc_code)
        ctx = self._build_p2_context_for_row(row)
        p2_service = P2ExcelServiceV2(output_root=Path.cwd() / "output")
        p2_service.build_excel(row, ctx)

    def _ensure_export_documents_generated(self, order_id: int, file_format: str) -> list[OrderDocumentRead]:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        normalized_format = (file_format or "").strip().lower()
        if normalized_format not in {"pdf", "excel"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato non valido. Usa 'pdf' o 'excel'.",
            )

        has_sfarinati, has_p2 = self._resolve_order_document_flags(order)
        dc_codes = self._collect_order_dc_codes(order)

        expected_keys: set[tuple[str, str]] = set()

        for dc_code in dc_codes:
            dc_key = self.NO_DC_CODE if dc_code == self.NO_DC_CODE else dc_code
            if normalized_format == "pdf":
                self._generate_packing_list_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                expected_keys.add(("packing_list_pdf", dc_key))
                self._generate_dle_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                expected_keys.add(("dle_pdf", dc_key))
                if has_sfarinati:
                    self._generate_sfarinati_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                    expected_keys.add(("sfarinati_pdf", dc_key))
                if has_p2:
                    self._generate_p2_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                    expected_keys.add(("p2_pdf", dc_key))
            else:
                self._generate_packing_list_excel_for_dc(order_id=order_id, dc_code=dc_code)
                expected_keys.add(("packing_list_excel", dc_key))
                self._generate_dle_excel_for_dc(order_id=order_id, dc_code=dc_code)
                expected_keys.add(("dle_excel", dc_key))
                if has_sfarinati:
                    self._generate_sfarinati_excel_for_dc(order_id=order_id, dc_code=dc_code)
                    expected_keys.add(("sfarinati_excel", dc_key))
                if has_p2:
                    self._generate_p2_excel_for_dc(order_id=order_id, dc_code=dc_code)
                    expected_keys.add(("p2_excel", dc_key))

        docs = self.list_order_documents(order_id=order_id)
        latest_by_key: dict[tuple[str, str], OrderDocumentRead] = {}
        for doc in docs:
            if doc.level != "DC":
                continue
            if doc.format.lower() != normalized_format:
                continue
            key = (doc.document_type, doc.dc_code or self.NO_DC_CODE)
            if key not in expected_keys:
                continue
            current = latest_by_key.get(key)
            if current is None or (doc.generated_at or datetime.min) > (current.generated_at or datetime.min):
                latest_by_key[key] = doc

        return list(latest_by_key.values())

    def generate_document(self, order_id: int, payload: OrderDocumentGenerateRequest) -> list[OrderDocumentRead]:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        level = payload.level.strip().upper()
        doc_type = payload.document_type.strip().lower()
        doc_format = payload.format.strip().lower()

        if doc_format not in {"pdf", "excel"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato '{payload.format}' non supportato. Usa PDF o Excel.",
            )

        if level == "ORDER":
            if doc_type != "purchase_order":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Documento livello ordine non supportato: {payload.document_type}",
                )
            if doc_format == "pdf":
                self._generate_purchase_order_pdf(order_id)
            else:
                self._generate_purchase_order_excel(order_id)
            return self.list_order_documents(order_id)

        if level == "DC":
            if not payload.dc_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="dc_code obbligatorio per documenti livello DC.",
                )
            dc_code = payload.dc_code.strip()
            if doc_type == "packing_list":
                if doc_format == "pdf":
                    self._generate_packing_list_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                else:
                    self._generate_packing_list_excel_for_dc(order_id=order_id, dc_code=dc_code)
                return self.list_order_documents(order_id)
            if doc_type == "dle":
                if doc_format == "pdf":
                    self._generate_dle_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                else:
                    self._generate_dle_excel_for_dc(order_id=order_id, dc_code=dc_code)
                return self.list_order_documents(order_id)
            if doc_type == "sfarinati":
                if doc_format == "pdf":
                    self._generate_sfarinati_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                else:
                    self._generate_sfarinati_excel_for_dc(order_id=order_id, dc_code=dc_code)
                return self.list_order_documents(order_id)
            if doc_type == "p2":
                if doc_format == "pdf":
                    self._generate_p2_pdf_for_dc(order_id=order_id, dc_code=dc_code)
                else:
                    self._generate_p2_excel_for_dc(order_id=order_id, dc_code=dc_code)
                return self.list_order_documents(order_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo documento DC non supportato: {payload.document_type}",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Livello documento non valido: {payload.level}. Usa ORDER o DC.",
        )

    def generate_order_documents(self, order_id: int) -> list[OrderDocumentRead]:
        self._generate_purchase_order_pdf(order_id)
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        for dc_code in self._collect_order_dc_codes(order):
            self._generate_packing_list_pdf_for_dc(order_id=order_id, dc_code=dc_code)
        return self.list_order_documents(order_id)

    def set_order_archived(self, order_id: int, is_archived: bool) -> OrderDetailRead:
        row = self.repository.set_order_archived(order_id=order_id, archived=is_archived)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        detail = self.get_order_by_id(order_id)
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        return detail

    def apply_operational_auto_increase(self, order_id: int, percent: float = 2.0) -> OrderDetailRead:
        self._apply_operational_auto_increase_or_raise(order_id=order_id, percent=percent)
        self.repository.persist()
        detail = self.get_order_by_id(order_id)
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        return detail

    def reset_operational_to_original(self, order_id: int) -> OrderDetailRead:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        for line in order.lines:
            original_map = dict(line.original_units_per_dc)
            if original_map:
                line.operational_units_per_dc_json = json.dumps(original_map)
                line.operational_total_units = sum(int(v or 0) for v in original_map.values())
            else:
                line.operational_total_units = int(line.original_units or 0)

        self._validate_nested_operational_or_raise(order_id)
        self.repository.persist()

        detail = self.get_order_by_id(order_id)
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        return detail

    def reset_received_to_imported(self, order_id: int) -> OrderDetailRead:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        for line in order.lines:
            snapshot_map: dict[str, int] = {}
            payload = (line.units_per_dc_json or "").strip()
            if payload:
                try:
                    raw = json.loads(payload)
                    if isinstance(raw, dict):
                        snapshot_map = {str(k): int(v or 0) for k, v in raw.items()}
                except (json.JSONDecodeError, TypeError, ValueError):
                    snapshot_map = {}

            if snapshot_map:
                line.original_units_per_dc_json = json.dumps(snapshot_map)
                line.original_total_units = sum(int(v or 0) for v in snapshot_map.values())
                line.total_units = line.original_total_units
            elif line.original_total_units is None and line.total_units is not None:
                # Fallback scalar-only rows: keep existing imported scalar when available.
                line.original_total_units = int(line.total_units or 0)

        self.repository.persist()
        detail = self.get_order_by_id(order_id)
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        return detail

    def normalize_received_quantities(self, order_id: int) -> OrderDetailRead:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        def nearest_multiple(value: int, divisor: int) -> int:
            if divisor <= 0:
                return value
            if value <= 0:
                return 0
            low = (value // divisor) * divisor
            high = low + divisor
            # tie-break verso il basso per non aumentare in modo inatteso
            if abs(value - low) <= abs(high - value):
                return low
            return high

        # Group lines by normalized nest code.
        nested_groups: dict[str, list] = {}
        mono_lines: list = []
        for line in order.lines:
            n = self._normalized_nest_code(line.nest_code)
            if n:
                nested_groups.setdefault(n, []).append(line)
            else:
                mono_lines.append(line)

        # Mono lines: normalize per master carton.
        for line in mono_lines:
            master = self._line_master_pack_for_nest_validation(line)
            if master is None or master <= 0:
                continue
            original_map = dict(line.original_units_per_dc)
            if original_map:
                for dc in list(original_map.keys()):
                    original_map[dc] = nearest_multiple(int(original_map.get(dc) or 0), int(master))
                line.original_units_per_dc_json = json.dumps(original_map)
                line.original_total_units = sum(int(v or 0) for v in original_map.values())
                line.total_units = line.original_total_units
            else:
                qty = int(line.original_units or 0)
                line.original_total_units = nearest_multiple(qty, int(master))
                line.total_units = line.original_total_units

        # Nested lines: infer uniform store_ready from shared master/sku_count.
        for nest_code, lines in nested_groups.items():
            if len(lines) < 2:
                # single-line nest is treated as mono fallback
                line = lines[0]
                master = self._line_master_pack_for_nest_validation(line)
                if master is None or master <= 0:
                    continue
                original_map = dict(line.original_units_per_dc)
                if original_map:
                    for dc in list(original_map.keys()):
                        original_map[dc] = nearest_multiple(int(original_map.get(dc) or 0), int(master))
                    line.original_units_per_dc_json = json.dumps(original_map)
                    line.original_total_units = sum(int(v or 0) for v in original_map.values())
                    line.total_units = line.original_total_units
                else:
                    qty = int(line.original_units or 0)
                    line.original_total_units = nearest_multiple(qty, int(master))
                    line.total_units = line.original_total_units
                continue

            packs: list[int] = []
            for line in lines:
                pack = self._line_master_pack_for_nest_validation(line)
                if pack is None or pack <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Nested group {nest_code}: master carton mancante/non valido su {line.vendor_style}.",
                    )
                packs.append(int(pack))
            if len(set(packs)) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group {nest_code}: master carton non uniforme {packs}.",
                )
            master = packs[0]
            if master % len(lines) != 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nested group {nest_code}: master carton {master} non divisibile "
                        f"per numero SKU {len(lines)}."
                    ),
                )
            sr = master // len(lines)

            for line in lines:
                original_map = dict(line.original_units_per_dc)
                if original_map:
                    for dc in list(original_map.keys()):
                        original_map[dc] = nearest_multiple(int(original_map.get(dc) or 0), int(sr))
                    line.original_units_per_dc_json = json.dumps(original_map)
                    line.original_total_units = sum(int(v or 0) for v in original_map.values())
                    line.total_units = line.original_total_units
                else:
                    qty = int(line.original_units or 0)
                    line.original_total_units = nearest_multiple(qty, int(sr))
                    line.total_units = line.original_total_units
                line.store_ready_pack_size = int(sr)

        self.repository.persist()

        detail = self.get_order_by_id(order_id)
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        return detail

    def _apply_operational_auto_increase_or_raise(self, order_id: int, percent: float) -> None:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )
        if percent < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="percent deve essere >= 0",
            )

        factor = 1.0 + (float(percent) / 100.0)
        products_by_key = self.repository.get_products_by_styles([line.vendor_style for line in order.lines])

        def line_label(line) -> str:
            return line.vendor_style or line.item_code or f"line#{line.id}"

        def resolve_nested_store_ready_for_dc(lines: list, dc_code: str) -> dict[int, int]:
            """Resolve nested store_ready with business-safe rule:
            - master carton must be uniform across lines
            - master carton must be divisible by sku count
            - effective store_ready is uniform split (master/sku_count)
            """
            if len(lines) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group non valido su DC {dc_code}: meno di 2 righe.",
                )
            pack_values: set[int] = set()
            details: list[dict] = []
            for line in lines:
                pack = self._line_master_pack_for_nest_validation(line)
                details.append({"vendor_style": line_label(line), "master_carton": pack})
                if pack is None or pack <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Nested group incoerente su DC {dc_code}: master carton mancante ({details}).",
                    )
                pack_values.add(int(pack))

            if len(pack_values) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group incoerente su DC {dc_code}: master carton non uniforme ({details}).",
                )

            master = next(iter(pack_values))
            if master % len(lines) != 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nested group incoerente su DC {dc_code}: master carton {master} "
                        f"non divisibile per numero SKU {len(lines)}."
                    ),
                )

            sr = master // len(lines)
            for line in lines:
                qty = int(line.original_units_per_dc.get(dc_code) or 0)
                if qty % sr != 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Nested group incoerente su DC {dc_code}: dc_units {qty} non divisibili "
                            f"per store_ready uniforme {sr} su SKU {line_label(line)}."
                        ),
                    )

            return {line.id: sr for line in lines}

        def mono_master_carton(line) -> int:
            candidates = []
            if line.vend_pack:
                candidates.append(int(line.vend_pack))
            style = self.repository.style_key(line.vendor_style)
            if style and style in products_by_key:
                p = products_by_key[style]
                if p and p.pcs_per_crt:
                    candidates.append(int(p.pcs_per_crt))
            if line.store_ready_pack_size:
                candidates.append(int(line.store_ready_pack_size))
            for value in candidates:
                if value > 0:
                    return value
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Master carton non disponibile per SKU {line_label(line)}.",
            )

        # Reset operational data from original as base, then apply increase.
        for line in order.lines:
            original_map = dict(line.original_units_per_dc)
            if original_map:
                line.operational_units_per_dc_json = json.dumps(original_map)
                line.operational_total_units = sum(int(v or 0) for v in original_map.values())
            else:
                line.operational_total_units = int(line.original_units or 0)

        nested_groups: dict[str, list] = {}
        mono_lines = []
        for line in order.lines:
            nest = self._normalized_nest_code(line.nest_code)
            if not nest:
                mono_lines.append(line)
            else:
                nested_groups.setdefault(nest, []).append(line)

        # MONO: per SKU per DC
        for line in mono_lines:
            master = mono_master_carton(line)
            original_map = dict(line.original_units_per_dc)
            if original_map:
                next_map: dict[str, int] = {}
                for dc_code, qty_raw in original_map.items():
                    units_cliente_dc = int(qty_raw or 0)
                    if units_cliente_dc < 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Quantità cliente negativa per SKU {line_label(line)} su DC {dc_code}.",
                        )
                    if units_cliente_dc % master != 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Quantità cliente non divisibile per cartone su SKU {line_label(line)} "
                                f"DC {dc_code}: units={units_cliente_dc}, master_carton={master}."
                            ),
                        )
                    max_units_fornitore = math.floor(units_cliente_dc * factor)
                    cartoni_operativi = math.floor(max_units_fornitore / master)
                    units_operativi = int(cartoni_operativi * master)
                    if units_operativi > max_units_fornitore:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Aumento oltre limite +{percent}% per SKU {line_label(line)} DC {dc_code}: "
                                f"operativi={units_operativi}, max={max_units_fornitore}."
                            ),
                        )
                    next_map[dc_code] = units_operativi
                line.operational_units_per_dc_json = json.dumps(next_map)
                line.operational_total_units = sum(next_map.values())
            else:
                units_cliente = int(line.original_units or 0)
                if units_cliente % master != 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Quantità cliente non divisibile per cartone su SKU {line_label(line)}: "
                            f"units={units_cliente}, master_carton={master}."
                        ),
                    )
                max_units_fornitore = math.floor(units_cliente * factor)
                cartoni_operativi = math.floor(max_units_fornitore / master)
                line.operational_total_units = int(cartoni_operativi * master)

        # NESTED: per gruppo per DC
        for nest_code, lines in nested_groups.items():
            if len(lines) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group {nest_code} non valido: meno di 2 righe.",
                )

            dc_codes = sorted({dc for line in lines for dc in line.original_units_per_dc.keys()})
            for dc_code in dc_codes:
                sr_map = resolve_nested_store_ready_for_dc(lines=lines, dc_code=dc_code)
                pcs_per_carton_group = sum(sr_map.values())
                cartons_by_sku: dict[str, int] = {}
                for line in lines:
                    sr = int(sr_map.get(line.id) or 0)
                    original_map = dict(line.original_units_per_dc)
                    if dc_code not in original_map:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Nested group {nest_code} incoerente su DC {dc_code}: "
                                f"dc_units mancanti per SKU {line_label(line)}."
                            ),
                        )
                    units_cliente_dc = int(original_map.get(dc_code) or 0)
                    if units_cliente_dc < 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Nested group {nest_code} incoerente su DC {dc_code}: "
                                f"dc_units negativi per SKU {line_label(line)}."
                            ),
                        )
                    if units_cliente_dc % sr != 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Nested group {nest_code} incoerente su DC {dc_code}: "
                                f"SKU {line_label(line)} units={units_cliente_dc} non divisibili per "
                                f"store_ready_pack_size={sr}."
                            ),
                        )
                    cartons_by_sku[line_label(line)] = int(units_cliente_dc // sr)

                cartons_values = list(cartons_by_sku.values())
                if len(set(cartons_values)) != 1:
                    detail = ", ".join(f"SKU {sku} produce {cartons} cartons" for sku, cartons in cartons_by_sku.items())
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Nested group {nest_code} incoerente su DC {dc_code}: {detail}",
                    )

                cartoni_gruppo_cliente = cartons_values[0]
                units_gruppo_cliente = cartoni_gruppo_cliente * pcs_per_carton_group
                max_units_gruppo_fornitore = math.floor(units_gruppo_cliente * factor)
                cartoni_gruppo_operativi = math.floor(max_units_gruppo_fornitore / pcs_per_carton_group)

                for line in lines:
                    sr = int(sr_map.get(line.id) or 0)
                    units_operativi_dc = int(cartoni_gruppo_operativi * sr)
                    ops_map = dict(line.operational_units_per_dc)
                    ops_map[dc_code] = units_operativi_dc
                    line.operational_units_per_dc_json = json.dumps(ops_map)
                    line.operational_total_units = sum(int(v or 0) for v in ops_map.values())

        self._validate_nested_operational_or_raise(order_id)

    def _validate_nested_operational_or_raise(self, order_id: int) -> None:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        nested_lines = [l for l in order.lines if self._normalized_nest_code(l.nest_code)]
        by_nest: dict[str, list] = {}
        for line in nested_lines:
            nest_code = self._normalized_nest_code(line.nest_code)
            if nest_code:
                by_nest.setdefault(nest_code, []).append(line)

        def line_label(line) -> str:
            return line.vendor_style or line.item_code or f"line#{line.id}"

        def resolve_effective_sr(lines: list, dc: str) -> dict[int, int]:
            pack_values: set[int] = set()
            details: list[dict] = []
            for line in lines:
                pack = self._line_master_pack_for_nest_validation(line)
                details.append({"vendor_style": line_label(line), "master_carton": pack})
                if pack is None or pack <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Nested group incoerente su DC {dc}: master carton mancante ({details}).",
                    )
                pack_values.add(int(pack))

            if len(pack_values) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group incoerente su DC {dc}: master carton non uniforme ({details}).",
                )

            master = next(iter(pack_values))
            if master % len(lines) != 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nested group incoerente su DC {dc}: master carton {master} "
                        f"non divisibile per numero SKU {len(lines)}."
                    ),
                )

            sr = master // len(lines)
            for line in lines:
                qty = int(line.operational_units_per_dc.get(dc) or 0)
                if qty % sr != 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Nested group incoerente su DC {dc}: dc_units {qty} non divisibili "
                            f"per store_ready uniforme {sr} su SKU {line_label(line)}."
                        ),
                    )

            return {line.id: sr for line in lines}

        for nest_code, lines in by_nest.items():
            if len(lines) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group {nest_code} non valido: meno di 2 righe.",
                )

            dc_codes: set[str] = set()
            for line in lines:
                dc_codes.update(line.operational_units_per_dc.keys())
            for dc in sorted(dc_codes):
                sr_map = resolve_effective_sr(lines=lines, dc=dc)
                for line in lines:
                    units_map = line.operational_units_per_dc
                    if dc not in units_map:
                        continue
                    qty = units_map.get(dc)
                    sr = int(sr_map.get(line.id) or 0)
                    if qty is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Nested group {nest_code} incoerente su DC {dc}: "
                                f"dc_units mancanti per SKU {line.vendor_style}."
                            ),
                        )
                    if sr is None or sr <= 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Nested group {nest_code} incoerente su DC {dc}: "
                                f"store_ready_pack_size non valido per SKU {line.vendor_style} (valore={sr})."
                            ),
                        )

    def update_line_identity(
        self,
        order_id: int,
        line_id: int,
        vendor_style: str | None = None,
        item_code: str | None = None,
        description: str | None = None,
        nest_code: str | None = None,
    ) -> OrderDetailRead:
        line = self.repository.get_order_line(order_id, line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Riga ordine non trovata: order_id={order_id}, line_id={line_id}",
            )

        changed = False
        if vendor_style is not None:
            normalized_vendor_style = vendor_style.strip()
            if not normalized_vendor_style:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="vendor_style non puÃ² essere vuoto.",
                )
            if line.vendor_style != normalized_vendor_style:
                line.vendor_style = normalized_vendor_style
                changed = True
                self._refresh_line_pack_sizes_from_product(line)

        if item_code is not None and line.item_code != item_code.strip():
            line.item_code = item_code.strip() or None
            changed = True
        if description is not None and line.description != description.strip():
            line.description = description.strip() or None
            changed = True

        if nest_code is not None:
            normalized_nest = self._normalized_nest_code(nest_code)
            if line.nest_code != normalized_nest:
                line.nest_code = normalized_nest
                line.carton_profile = "mixed" if normalized_nest else "mono"
                line.mixed_carton_group = normalized_nest if normalized_nest else None
                changed = True

        if not changed:
            return self.get_order_by_id(order_id)

        self._validate_nest_master_pack_consistency(order_id=order_id)

        inventory_applied = InventoryService(self.repository.db).apply_customer_order_consumption(
            order_id=order_id,
            force_reapply=True,
        )
        if not inventory_applied:
            self.repository.persist()
        return self.get_order_by_id(order_id)

    def _line_master_pack_for_nest_validation(self, line) -> int | None:
        pack_candidates: list[int] = []
        try:
            if line.vend_pack is not None:
                p = int(line.vend_pack)
                if p > 0:
                    pack_candidates.append(p)
        except (TypeError, ValueError):
            pass

        style = self.repository.style_key(line.vendor_style)
        if style:
            products = self.repository.get_products_by_styles([line.vendor_style])
            product = products.get(style)
            if product is not None and getattr(product, "pcs_per_crt", None) is not None:
                try:
                    p = int(product.pcs_per_crt)
                    if p > 0:
                        pack_candidates.append(p)
                except (TypeError, ValueError):
                    pass

        for candidate in pack_candidates:
            if candidate > 0:
                return candidate
        return None

    def _validate_nest_master_pack_consistency(self, order_id: int) -> None:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            return

        by_nest: dict[str, list] = {}
        for line in order.lines:
            nest = self._normalized_nest_code(line.nest_code)
            if not nest:
                continue
            by_nest.setdefault(nest, []).append(line)

        for nest, lines in by_nest.items():
            if len(lines) < 2:
                # Consenti fase di editing intermedia (utente sta ancora assegnando i nest).
                continue
            packs: dict[int, list[str]] = {}
            unknown_styles: list[str] = []
            for line in lines:
                pack = self._line_master_pack_for_nest_validation(line)
                style = line.vendor_style or line.item_code or f"line#{line.id}"
                if pack is None:
                    unknown_styles.append(style)
                    continue
                packs.setdefault(pack, []).append(style)

            if len(packs) > 1:
                detail_parts = [f"{pack}: {styles}" for pack, styles in sorted(packs.items(), key=lambda x: x[0])]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nest manuale {nest} non valido: master pack diversi tra referenze "
                        f"({'; '.join(detail_parts)})."
                    ),
                )

            if unknown_styles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nest manuale {nest} non valido: master pack non disponibile per "
                        f"{unknown_styles}. Completa anagrafica/pack prima di assegnare il gruppo."
                    ),
                )

    def _refresh_line_pack_sizes_from_product(self, line) -> None:
        style_key = self.repository.style_key(line.vendor_style)
        if not style_key:
            return
        products = self.repository.get_products_by_styles([line.vendor_style])
        product = products.get(style_key)
        if product is None:
            return

        try:
            product_pack = int(product.pcs_per_crt) if product.pcs_per_crt is not None else None
        except (TypeError, ValueError):
            product_pack = None
        if not product_pack or product_pack <= 0:
            return

        current_pack = int(line.vend_pack or 0)
        current_total = int(line.original_units or line.total_units or 0)
        if current_pack <= 0 or current_pack > 500 or (current_total > 0 and current_pack >= current_total):
            line.vend_pack = product_pack

    def update_line_operational_units(self, order_id: int, line_id: int, operational_units: int) -> OrderDetailRead:
        if operational_units < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="operational_units deve essere >= 0",
            )
        line = self.repository.get_order_line(order_id, line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Riga ordine non trovata: order_id={order_id}, line_id={line_id}",
            )
        if line.operational_units_per_dc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La riga ha quantità per DC. Usa l'endpoint di aggiornamento per DC "
                    "(/orders/{order_id}/lines/{line_id}/dc/{dc_code}/operational-units)."
                ),
            )

        line.operational_total_units = operational_units
        line.total_units = line.original_units if line.original_units is not None else line.total_units
        try:
            self._validate_nested_operational_or_raise(order_id)
            self.repository.persist()
        except HTTPException:
            self.repository.db.rollback()
            raise
        return self.get_order_by_id(order_id)

    def update_line_original_units(self, order_id: int, line_id: int, original_units: int) -> OrderDetailRead:
        if original_units < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="original_units deve essere >= 0",
            )
        line = self.repository.get_order_line(order_id, line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Riga ordine non trovata: order_id={order_id}, line_id={line_id}",
            )
        if line.original_units_per_dc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La riga ha quantità cliente per DC. Usa l'endpoint originale per DC "
                    "(/orders/{order_id}/lines/{line_id}/dc/{dc_code}/original-units)."
                ),
            )

        line.original_total_units = original_units
        line.total_units = original_units
        self.repository.persist()
        return self.get_order_by_id(order_id)

    def update_line_dc_operational_units(
        self,
        order_id: int,
        line_id: int,
        dc_code: str,
        operational_dc_units: int,
    ) -> OrderDetailRead:
        if operational_dc_units < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="operational_dc_units deve essere >= 0",
            )
        line = self.repository.get_order_line(order_id, line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Riga ordine non trovata: order_id={order_id}, line_id={line_id}",
            )
        ops_map = dict(line.operational_units_per_dc)
        if dc_code not in ops_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DC {dc_code} non presente nella riga {line_id}.",
            )

        ops_map[dc_code] = operational_dc_units
        line.operational_units_per_dc_json = json.dumps(ops_map)
        line.operational_total_units = sum(ops_map.values())
        try:
            self._validate_nested_operational_or_raise(order_id)
            self.repository.persist()
        except HTTPException:
            self.repository.db.rollback()
            raise

        return self.get_order_by_id(order_id)

    def update_line_dc_original_units(
        self,
        order_id: int,
        line_id: int,
        dc_code: str,
        original_dc_units: int,
    ) -> OrderDetailRead:
        if original_dc_units < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="original_dc_units deve essere >= 0",
            )
        line = self.repository.get_order_line(order_id, line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Riga ordine non trovata: order_id={order_id}, line_id={line_id}",
            )
        original_map = dict(line.original_units_per_dc)
        if dc_code not in original_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DC {dc_code} non presente nella riga {line_id}.",
            )

        original_map[dc_code] = original_dc_units
        line.original_units_per_dc_json = json.dumps(original_map)
        line.original_total_units = sum(original_map.values())
        line.total_units = line.original_total_units
        self.repository.persist()
        return self.get_order_by_id(order_id)

    def update_nested_operational_cartons(
        self,
        order_id: int,
        nest_code: str,
        dc_code: str,
        operational_cartons: int,
    ) -> OrderDetailRead:
        if operational_cartons < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="operational_cartons deve essere >= 0",
            )
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ordine non trovato: {order_id}",
            )

        normalized_target_nest = self._normalized_nest_code(nest_code)
        lines = [
            l
            for l in order.lines
            if self._normalized_nest_code(l.nest_code) == normalized_target_nest
        ]
        if len(lines) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nested group {nest_code} non trovato o con meno di 2 righe.",
            )

        for line in lines:
            sr = line.store_ready_pack_size
            if sr is None or sr <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nested group {nest_code}: store_ready_pack_size non valido "
                        f"per SKU {line.vendor_style} (valore={sr})."
                    ),
                )
            ops_map = dict(line.operational_units_per_dc)
            if dc_code not in ops_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group {nest_code}: DC {dc_code} non presente per SKU {line.vendor_style}.",
                )
            ops_map[dc_code] = operational_cartons * sr
            line.operational_units_per_dc_json = json.dumps(ops_map)
            line.operational_total_units = sum(ops_map.values())

        try:
            self._validate_nested_operational_or_raise(order_id)
            self.repository.persist()
        except HTTPException:
            self.repository.db.rollback()
            raise
        return self.get_order_by_id(order_id)
