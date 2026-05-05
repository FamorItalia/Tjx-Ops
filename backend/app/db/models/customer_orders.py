from datetime import date, datetime
import json

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CustomerOrder(Base):
    __tablename__ = "customer_orders"
    __table_args__ = (
        Index("ix_customer_orders_source_file_po_raw", "source_file", "po_raw"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_family: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_pdf_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_pdf_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    parser_family: Mapped[str | None] = mapped_column(String(50), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    distribution_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    po_raw: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    po_normalized: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    import_po_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancel_ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lines: Mapped[list["CustomerOrderLine"]] = relationship(back_populates="order")


class CustomerOrderLine(Base):
    __tablename__ = "customer_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_order_id: Mapped[int] = mapped_column(
        ForeignKey("customer_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_style: Mapped[str | None] = mapped_column(String(120), nullable=True)
    item_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operational_total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distribution_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    original_units_per_dc_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    operational_units_per_dc_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    units_per_dc_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nest Code is row-level and brand-agnostic: empty = mono, valued = mixed.
    vend_pack: Mapped[int | None] = mapped_column(Integer, nullable=True)
    store_ready_pack_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nest_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    carton_profile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mixed_carton_group: Mapped[str | None] = mapped_column(String(120), nullable=True)

    order: Mapped[CustomerOrder] = relationship(back_populates="lines")

    @property
    def units_per_dc(self) -> dict[str, int]:
        payload = self.operational_units_per_dc_json or self.units_per_dc_json or self.original_units_per_dc_json
        if not payload:
            return {}
        try:
            raw = json.loads(payload)
            return {str(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    @property
    def original_units_per_dc(self) -> dict[str, int]:
        payload = self.original_units_per_dc_json or self.units_per_dc_json
        if not payload:
            return {}
        try:
            raw = json.loads(payload)
            return {str(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    @property
    def operational_units_per_dc(self) -> dict[str, int]:
        payload = self.operational_units_per_dc_json or self.units_per_dc_json or self.original_units_per_dc_json
        if not payload:
            return {}
        try:
            raw = json.loads(payload)
            return {str(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    @property
    def original_units(self) -> int | None:
        return self.original_total_units if self.original_total_units is not None else self.total_units

    @property
    def operational_units(self) -> int | None:
        if self.operational_total_units is not None:
            return self.operational_total_units
        if self.total_units is not None:
            return self.total_units
        return self.original_total_units
