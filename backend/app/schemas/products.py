from datetime import datetime

from pydantic import BaseModel


class ProductRead(BaseModel):
    id: int
    supplier_name: str | None = None
    tjx_style: str | None = None
    tjx_style_key: str | None = None
    description: str | None = None
    pcs_per_crt: int | None = None
    strat_x_pl: int | None = None
    strat_x_plt: int | None = None
    cartons_per_layer: int | None = None
    cartons_per_pallet: int | None = None
    carton_width_cm: float | None = None
    carton_depth_cm: float | None = None
    carton_height_cm: float | None = None
    vol: float | None = None
    peso_lordo: float | None = None
    peso_netto: float | None = None
    pallet_width_cm: float | None = None
    pallet_depth_cm: float | None = None
    purchase_cost_eur: float | None = None
    sale_price_eur: float | None = None
    inventory_tracking_enabled: bool = False
    stock_product_units: float | None = None
    stock_packaging_units: float | None = None
    product_usage_per_unit: float | None = None
    packaging_usage_per_unit: float | None = None
    product_alert_threshold: float | None = None
    packaging_alert_threshold: float | None = None
    document_dle: bool = True
    document_packing_list: bool = True
    document_sfarinati: bool = False
    document_p2: bool = False

    model_config = {"from_attributes": True}


class ProductImportResponse(BaseModel):
    file_name: str
    imported_at: datetime
    total_rows_read: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    warnings: list[str]


class ProductUpdate(BaseModel):
    description: str | None = None
    pcs_per_crt: int | None = None
    strat_x_pl: int | None = None
    strat_x_plt: int | None = None
    cartons_per_layer: int | None = None
    cartons_per_pallet: int | None = None
    carton_width_cm: float | None = None
    carton_depth_cm: float | None = None
    carton_height_cm: float | None = None
    vol: float | None = None
    peso_lordo: float | None = None
    peso_netto: float | None = None
    pallet_width_cm: float | None = None
    pallet_depth_cm: float | None = None
    purchase_cost_eur: float | None = None
    sale_price_eur: float | None = None
    inventory_tracking_enabled: bool | None = None
    stock_product_units: float | None = None
    stock_packaging_units: float | None = None
    product_usage_per_unit: float | None = None
    packaging_usage_per_unit: float | None = None
    product_alert_threshold: float | None = None
    packaging_alert_threshold: float | None = None


class ProductCreate(BaseModel):
    supplier_name: str
    tjx_style: str
    description: str | None = None
    pcs_per_crt: int | None = None
    purchase_cost_eur: float | None = None
    sale_price_eur: float | None = None
    inventory_tracking_enabled: bool = False
    stock_product_units: float | None = None
    stock_packaging_units: float | None = None
    product_usage_per_unit: float | None = None
    packaging_usage_per_unit: float | None = None
    product_alert_threshold: float | None = None
    packaging_alert_threshold: float | None = None
    document_dle: bool = True
    document_packing_list: bool = True
    document_sfarinati: bool = False
    document_p2: bool = False


class ProductDocumentRead(BaseModel):
    id: int
    product_id: int
    file_name: str
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_at: datetime


class ProductInventoryMovementRead(BaseModel):
    id: int
    customer_order_id: int | None = None
    order_number: str | None = None
    movement_type: str = "order"  # order | manual
    note: str | None = None
    consumed_pieces: float
    consumed_product_stock: float
    consumed_packaging_stock: float
    stock_product_after: float | None = None
    stock_packaging_after: float | None = None
    applied_at: datetime

    model_config = {"from_attributes": True}


class ProductInventoryAlertRead(BaseModel):
    id: int
    customer_order_id: int | None = None
    stock_type: str
    threshold_value: float
    current_value: float
    email_sent: bool
    email_error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductInventoryHistoryRead(BaseModel):
    product_id: int
    inventory_tracking_enabled: bool
    stock_product_units: float | None = None
    stock_packaging_units: float | None = None
    movements: list[ProductInventoryMovementRead]
    alerts: list[ProductInventoryAlertRead]


class ProductPriceHistoryEntryRead(BaseModel):
    id: int
    product_id: int
    purchase_cost_eur_before: float | None = None
    purchase_cost_eur_after: float | None = None
    sale_price_eur_before: float | None = None
    sale_price_eur_after: float | None = None
    change_source: str | None = None
    changed_at: datetime

    model_config = {"from_attributes": True}


class ProductPricePointRead(BaseModel):
    date: datetime
    purchase_cost_eur: float | None = None
    sale_price_eur: float | None = None


class ProductPriceHistoryRead(BaseModel):
    product_id: int
    from_date: datetime | None = None
    to_date: datetime | None = None
    entries: list[ProductPriceHistoryEntryRead]
    chart_points: list[ProductPricePointRead]
