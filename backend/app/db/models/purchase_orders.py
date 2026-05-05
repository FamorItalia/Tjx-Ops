from datetime import date, datetime
import json

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_family: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    po_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    po_normalized: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancel_ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qty_adjustment_percent: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_order_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_order_lines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    vendor_style: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(120), nullable=True)
    item_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nest_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    units_per_dc_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    logistics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity_base: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_original: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_adjusted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_final: Mapped[int | None] = mapped_column(Integer, nullable=True)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")

    @property
    def units_per_dc(self) -> dict[str, int]:
        if not self.units_per_dc_json:
            return {}
        try:
            raw = json.loads(self.units_per_dc_json)
            return {str(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    @property
    def logistics(self) -> dict[str, int | float | str]:
        if not self.logistics_json:
            return {}
        try:
            raw = json.loads(self.logistics_json)
            if isinstance(raw, dict):
                return raw
        except (json.JSONDecodeError, TypeError):
            pass
        return {}
