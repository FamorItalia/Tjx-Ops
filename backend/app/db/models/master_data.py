import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        Index("ix_suppliers_name_key", "name_key", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ragione_sociale: Mapped[str | None] = mapped_column(String(255), nullable=True)
    indirizzo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cap: Mapped[str | None] = mapped_column(String(30), nullable=True)
    citta: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    paese: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(80), nullable=True)
    persona_di_contatto: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emails_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_to: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_cc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_subject_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_order_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def emails(self) -> list[str]:
        if not self.emails_json:
            return []
        try:
            raw = json.loads(self.emails_json)
            if not isinstance(raw, list):
                return []
            return [str(x).strip() for x in raw if str(x).strip()]
        except (json.JSONDecodeError, TypeError, ValueError):
            return []


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tjx_style: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    tjx_style_key: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pcs_per_crt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strat_x_pl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strat_x_plt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layers_per_pallet: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cartons_per_layer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cartons_per_pallet: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carton_width_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    carton_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    carton_height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    peso_lordo: Mapped[float | None] = mapped_column(Float, nullable=True)
    peso_netto: Mapped[float | None] = mapped_column(Float, nullable=True)
    pallet_width_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pallet_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchase_cost_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_price_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    inventory_tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stock_product_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_packaging_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_usage_per_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    packaging_usage_per_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_alert_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    packaging_alert_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    document_dle: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    document_packing_list: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    document_sfarinati: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    document_p2: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ProductPriceHistory(Base):
    __tablename__ = "product_price_history"
    __table_args__ = (
        Index("ix_product_price_history_product_id_changed_at", "product_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_cost_eur_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchase_cost_eur_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_price_eur_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_price_eur_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_source: Mapped[str | None] = mapped_column(String(40), nullable=True)  # create | update | import
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class SupplierDocument(Base):
    __tablename__ = "supplier_documents"
    __table_args__ = (
        Index("ix_supplier_documents_supplier_id", "supplier_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ProductDocument(Base):
    __tablename__ = "product_documents"
    __table_args__ = (
        Index("ix_product_documents_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class DistributionCenter(Base):
    __tablename__ = "distribution_centers"
    __table_args__ = (
        Index("ix_distribution_centers_brand_dc_code", "brand", "dc_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    brand: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    dc_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    po_prefix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Legacy compatibility: keep `name`, add explicit `dc_name`.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dc_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    general_division_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    general_address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    general_address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    general_address_line_3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_merce_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_merce_dc_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination_merce_address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_merce_address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_merce_address_line_3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
