from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ProductInventoryLedger(Base):
    __tablename__ = "product_inventory_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customer_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consumed_pieces: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consumed_product_stock: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consumed_packaging_stock: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stock_product_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_packaging_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ProductInventoryAlert(Base):
    __tablename__ = "product_inventory_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customer_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stock_type: Mapped[str] = mapped_column(String(40), nullable=False)  # product | packaging
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ProductInventoryManualAdjustment(Base):
    __tablename__ = "product_inventory_manual_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stock_product_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_product_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_packaging_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_packaging_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
