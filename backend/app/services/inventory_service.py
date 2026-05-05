from __future__ import annotations

from collections import defaultdict
from email.message import EmailMessage
import logging
import re
import smtplib

from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models.customer_orders import CustomerOrder
from app.db.models.inventory import ProductInventoryAlert, ProductInventoryLedger, ProductInventoryManualAdjustment
from app.db.models.master_data import Product

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _style_key(value: str | None) -> str | None:
        if not value:
            return None
        key = re.sub(r"[^A-Z0-9]", "", value.upper())
        return key or None

    def _rollback_customer_order_consumption(self, order_id: int) -> None:
        ledgers = (
            self.db.query(ProductInventoryLedger)
            .filter(ProductInventoryLedger.customer_order_id == order_id)
            .all()
        )
        if not ledgers:
            return

        product_ids = sorted({int(l.product_id) for l in ledgers})
        products = self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        by_product_id = {p.id: p for p in products}

        for ledger in ledgers:
            product = by_product_id.get(int(ledger.product_id))
            if product is None:
                continue
            if product.stock_product_units is not None and float(ledger.consumed_product_stock or 0.0) > 0:
                product.stock_product_units = round(
                    float(product.stock_product_units) + float(ledger.consumed_product_stock),
                    4,
                )
            if product.stock_packaging_units is not None and float(ledger.consumed_packaging_stock or 0.0) > 0:
                product.stock_packaging_units = round(
                    float(product.stock_packaging_units) + float(ledger.consumed_packaging_stock),
                    4,
                )

        (
            self.db.query(ProductInventoryLedger)
            .filter(ProductInventoryLedger.customer_order_id == order_id)
            .delete(synchronize_session=False)
        )
        (
            self.db.query(ProductInventoryAlert)
            .filter(ProductInventoryAlert.customer_order_id == order_id)
            .delete(synchronize_session=False)
        )
        self.db.flush()

    def apply_customer_order_consumption(self, order_id: int, *, force_reapply: bool = False) -> bool:
        if force_reapply:
            self._rollback_customer_order_consumption(order_id)
        # Idempotency guard: if ledger rows already exist for this order, skip.
        already_applied = (
            self.db.query(ProductInventoryLedger.id)
            .filter(ProductInventoryLedger.customer_order_id == order_id)
            .first()
        )
        if already_applied is not None and not force_reapply:
            return False

        order = (
            self.db.query(CustomerOrder)
            .options(selectinload(CustomerOrder.lines))
            .filter(CustomerOrder.id == order_id)
            .first()
        )
        if order is None:
            return False

        style_keys: set[str] = set()
        for line in order.lines:
            for raw in [line.vendor_style, line.item_code]:
                key = self._style_key(raw)
                if key:
                    style_keys.add(key)

        if not style_keys:
            if force_reapply:
                self.db.commit()
            return False

        products = self.db.query(Product).filter(Product.tjx_style_key.in_(sorted(style_keys))).all()
        by_style = {p.tjx_style_key: p for p in products if p.tjx_style_key}

        pieces_by_product_id: dict[int, float] = defaultdict(float)

        for line in order.lines:
            pieces = 0.0
            if line.operational_units_per_dc:
                pieces = float(sum(line.operational_units_per_dc.values()))
            elif line.operational_units is not None:
                pieces = float(line.operational_units)
            elif line.original_units is not None:
                pieces = float(line.original_units)
            elif line.total_units is not None:
                pieces = float(line.total_units)

            if pieces <= 0:
                continue

            product = None
            for raw in [line.vendor_style, line.item_code]:
                key = self._style_key(raw)
                if key and key in by_style:
                    product = by_style[key]
                    break

            if product is None or not product.inventory_tracking_enabled:
                continue

            pieces_by_product_id[product.id] += pieces

        if not pieces_by_product_id:
            if force_reapply:
                self.db.commit()
            return False

        products_by_id = {p.id: p for p in products}

        for product_id, pieces in pieces_by_product_id.items():
            product = products_by_id.get(product_id)
            if product is None:
                continue

            product_coeff = max(float(product.product_usage_per_unit or 0.0), 0.0)
            packaging_coeff = max(float(product.packaging_usage_per_unit or 0.0), 0.0)

            consumed_product = pieces * product_coeff
            consumed_packaging = pieces * packaging_coeff

            prev_product_stock = product.stock_product_units
            prev_packaging_stock = product.stock_packaging_units

            new_product_stock = prev_product_stock
            new_packaging_stock = prev_packaging_stock

            if prev_product_stock is not None and consumed_product > 0:
                new_product_stock = round(float(prev_product_stock) - consumed_product, 4)
                product.stock_product_units = new_product_stock

            if prev_packaging_stock is not None and consumed_packaging > 0:
                new_packaging_stock = round(float(prev_packaging_stock) - consumed_packaging, 4)
                product.stock_packaging_units = new_packaging_stock

            self.db.add(
                ProductInventoryLedger(
                    product_id=product.id,
                    customer_order_id=order_id,
                    consumed_pieces=round(pieces, 4),
                    consumed_product_stock=round(consumed_product, 4),
                    consumed_packaging_stock=round(consumed_packaging, 4),
                    stock_product_after=new_product_stock,
                    stock_packaging_after=new_packaging_stock,
                )
            )

            self._maybe_alert(
                product=product,
                order_id=order_id,
                stock_type="product",
                previous_value=prev_product_stock,
                current_value=new_product_stock,
                threshold=product.product_alert_threshold,
            )
            self._maybe_alert(
                product=product,
                order_id=order_id,
                stock_type="packaging",
                previous_value=prev_packaging_stock,
                current_value=new_packaging_stock,
                threshold=product.packaging_alert_threshold,
            )

        self.db.commit()
        return True

    def _maybe_alert(
        self,
        product: Product,
        order_id: int,
        stock_type: str,
        previous_value: float | None,
        current_value: float | None,
        threshold: float | None,
    ) -> None:
        if threshold is None or current_value is None:
            return
        if float(current_value) > float(threshold):
            return

        alert = ProductInventoryAlert(
            product_id=product.id,
            customer_order_id=order_id,
            stock_type=stock_type,
            threshold_value=float(threshold),
            current_value=float(current_value),
            email_sent=False,
            email_error=None,
        )
        self.db.add(alert)
        self.db.flush()

        try:
            self._send_alert_email(product=product, alert=alert)
            alert.email_sent = True
            alert.email_error = None
        except Exception as exc:  # noqa: BLE001
            alert.email_sent = False
            alert.email_error = str(exc)[:500]
            logger.warning("Inventory alert email failed: %s", exc)

    def _send_alert_email(self, product: Product, alert: ProductInventoryAlert) -> None:
        recipients = settings.inventory_alert_recipients
        if not recipients:
            raise RuntimeError("INVENTORY_ALERT_EMAIL_TO non configurato.")
        if not settings.smtp_host:
            raise RuntimeError("SMTP_HOST non configurato.")

        style = product.tjx_style or f"ID {product.id}"
        subject = f"ALERT GIACENZA {alert.stock_type.upper()} - {style}"
        below_by = round(float(alert.threshold_value) - float(alert.current_value), 4)
        stock_label = "Giacenza prodotto" if alert.stock_type == "product" else "Giacenza packaging"
        body = (
            "Segnalazione automatica TJX Ops Hub\n\n"
            "La giacenza è scesa sotto la soglia configurata.\n\n"
            f"Prodotto: {style}\n"
            f"Fornitore: {product.supplier_name or '-'}\n"
            f"Tipo: {stock_label}\n"
            f"Soglia impostata: {alert.threshold_value}\n"
            f"Valore attuale: {alert.current_value}\n"
            f"Sotto soglia di: {below_by}\n"
            f"Order ID che ha generato l'alert: {alert.customer_order_id}\n\n"
            "Verificare approvvigionamento e aggiornare la pianificazione."
        )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.inventory_alert_email_from
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)

    def get_product_inventory_history(
        self,
        product_id: int,
        *,
        limit_movements: int = 200,
        limit_alerts: int = 200,
    ) -> dict[str, object] | None:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if product is None:
            return None

        movements = (
            self.db.query(ProductInventoryLedger)
            .filter(ProductInventoryLedger.product_id == product_id)
            .order_by(ProductInventoryLedger.applied_at.desc(), ProductInventoryLedger.id.desc())
            .limit(max(1, min(limit_movements, 1000)))
            .all()
        )
        manual_adjustments = (
            self.db.query(ProductInventoryManualAdjustment)
            .filter(ProductInventoryManualAdjustment.product_id == product_id)
            .order_by(ProductInventoryManualAdjustment.created_at.desc(), ProductInventoryManualAdjustment.id.desc())
            .limit(max(1, min(limit_movements, 1000)))
            .all()
        )
        order_ids = sorted({int(m.customer_order_id) for m in movements if m.customer_order_id is not None})
        orders_by_id: dict[int, CustomerOrder] = {}
        if order_ids:
            orders = self.db.query(CustomerOrder).filter(CustomerOrder.id.in_(order_ids)).all()
            orders_by_id = {int(o.id): o for o in orders}

        movement_rows: list[dict[str, object]] = []
        for m in movements:
            order = orders_by_id.get(int(m.customer_order_id))
            order_number = None
            if order is not None:
                order_number = order.po_normalized or order.po_raw or order.po_number or str(order.id)
            movement_rows.append(
                {
                    "id": m.id,
                    "customer_order_id": m.customer_order_id,
                    "order_number": order_number,
                    "movement_type": "order",
                    "note": None,
                    "consumed_pieces": m.consumed_pieces,
                    "consumed_product_stock": m.consumed_product_stock,
                    "consumed_packaging_stock": m.consumed_packaging_stock,
                    "stock_product_after": m.stock_product_after,
                    "stock_packaging_after": m.stock_packaging_after,
                    "applied_at": m.applied_at,
                }
            )
        for adj in manual_adjustments:
            delta_product = (
                round(float(adj.stock_product_after) - float(adj.stock_product_before), 4)
                if adj.stock_product_after is not None and adj.stock_product_before is not None
                else 0.0
            )
            delta_packaging = (
                round(float(adj.stock_packaging_after) - float(adj.stock_packaging_before), 4)
                if adj.stock_packaging_after is not None and adj.stock_packaging_before is not None
                else 0.0
            )
            movement_rows.append(
                {
                    "id": int(adj.id) + 1_000_000_000,
                    "customer_order_id": None,
                    "order_number": "MODIFICA MANUALE",
                    "movement_type": "manual",
                    "note": adj.note,
                    "consumed_pieces": 0.0,
                    "consumed_product_stock": delta_product,
                    "consumed_packaging_stock": delta_packaging,
                    "stock_product_after": adj.stock_product_after,
                    "stock_packaging_after": adj.stock_packaging_after,
                    "applied_at": adj.created_at,
                }
            )
        movement_rows.sort(key=lambda x: x["applied_at"], reverse=True)
        alerts = (
            self.db.query(ProductInventoryAlert)
            .filter(ProductInventoryAlert.product_id == product_id)
            .order_by(ProductInventoryAlert.created_at.desc(), ProductInventoryAlert.id.desc())
            .limit(max(1, min(limit_alerts, 1000)))
            .all()
        )

        return {
            "product_id": product.id,
            "inventory_tracking_enabled": bool(product.inventory_tracking_enabled),
            "stock_product_units": product.stock_product_units,
            "stock_packaging_units": product.stock_packaging_units,
            "movements": movement_rows,
            "alerts": alerts,
        }
