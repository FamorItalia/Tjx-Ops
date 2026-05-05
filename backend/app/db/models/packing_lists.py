from datetime import date, datetime
import json

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PackingList(Base):
    __tablename__ = "packing_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dc_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    po_number: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_ragione_sociale: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_address_full: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dept_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    destinations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    groups_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_pieces: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cartons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_gross_weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_net_weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_cubic_meters: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_pallets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    totals_manually_overridden: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lines: Mapped[list["PackingListLine"]] = relationship(
        back_populates="packing_list",
        cascade="all, delete-orphan",
    )

    @property
    def destinations(self) -> list[dict]:
        if not self.destinations_json:
            return []
        try:
            raw = json.loads(self.destinations_json)
            if isinstance(raw, list):
                return raw
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @property
    def warnings(self) -> list[dict]:
        if not self.warnings_json:
            return []
        try:
            raw = json.loads(self.warnings_json)
            if isinstance(raw, list):
                return raw
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @property
    def groups(self) -> list[dict]:
        if not self.groups_json:
            return []
        try:
            raw = json.loads(self.groups_json)
            if isinstance(raw, list):
                return raw
        except (json.JSONDecodeError, TypeError):
            pass
        return []


class PackingListLine(Base):
    __tablename__ = "packing_list_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    packing_list_id: Mapped[int] = mapped_column(
        ForeignKey("packing_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_order_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_order_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    group_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    group_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    vendor_style: Mapped[str | None] = mapped_column(String(120), nullable=True)
    item_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vendor_pack_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    store_ready_pack_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pcs_per_crt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_per_carton: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_weight_per_carton: Mapped[float | None] = mapped_column(Float, nullable=True)
    cartons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pieces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cartons_per_layer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cartons_per_pallet: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layers_per_pallet: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carton_height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pallet_width_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pallet_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_pallets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partial_layers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_cubic_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_dc_codes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    packing_list: Mapped[PackingList] = relationship(back_populates="lines")

    @property
    def destination_dc_codes(self) -> list[str]:
        if not self.destination_dc_codes_json:
            return []
        try:
            raw = json.loads(self.destination_dc_codes_json)
            if isinstance(raw, list):
                return [str(x) for x in raw]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @property
    def warnings(self) -> list[dict]:
        if not self.warnings_json:
            return []
        try:
            raw = json.loads(self.warnings_json)
            if isinstance(raw, list):
                return raw
        except (json.JSONDecodeError, TypeError):
            pass
        return []
