from datetime import date, datetime

from pydantic import BaseModel, Field


class DistributionCenterResolvedRead(BaseModel):
    dc_code: str
    dc_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None


class OrderLineRead(BaseModel):
    id: int
    vendor_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    original_units: int | None = None
    operational_units: int | None = None
    total_units: int | None = None
    distribution_center: str | None = None
    nest_code: str | None = None
    original_units_per_dc: dict[str, int] = Field(default_factory=dict)
    operational_units_per_dc: dict[str, int] = Field(default_factory=dict)
    units_per_dc: dict[str, int] = Field(default_factory=dict)
    carton_profile: str | None = None
    mixed_carton_group: str | None = None
    vend_pack: int | None = None
    store_ready_pack_size: int | None = None
    distribution_center_detail: DistributionCenterResolvedRead | None = None
    units_per_dc_details: dict[str, DistributionCenterResolvedRead] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class OrderListItemRead(BaseModel):
    id: int
    document_family: str
    brand: str | None = None
    supplier: str | None = None
    source_file: str
    start_ship_date: date | None = None
    cancel_ship_date: date | None = None
    distribution_center: str | None = None
    po_raw: str | None = None
    po_normalized: str | None = None
    import_po_number: str | None = None
    total_cartons: int | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderDetailRead(OrderListItemRead):
    lines: list[OrderLineRead] = Field(default_factory=list)


class OrderLineOperationalUpdateRequest(BaseModel):
    operational_units: int


class OrderLineDcOperationalUpdateRequest(BaseModel):
    operational_dc_units: int


class OrderLineOriginalUpdateRequest(BaseModel):
    original_units: int


class OrderLineDcOriginalUpdateRequest(BaseModel):
    original_dc_units: int


class OrderLineIdentityUpdateRequest(BaseModel):
    vendor_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    nest_code: str | None = None


class OrderNestedOperationalCartonsUpdateRequest(BaseModel):
    operational_cartons: int


class OrderOperationalAutoIncreaseRequest(BaseModel):
    percent: float = 2.0


class OrderArchiveUpdateRequest(BaseModel):
    is_archived: bool


class OrderDocumentRead(BaseModel):
    document_type: str
    level: str  # PO | DC
    dc_code: str | None = None
    format: str
    file_name: str
    file_path: str
    generated_at: datetime | None = None


class ActiveOrderDcPreviewRead(BaseModel):
    dc_code: str
    quantity: int
    cartons: int | None = None


class ActiveOrderDashboardRead(BaseModel):
    id: int
    po: str | None = None
    customer: str | None = None
    supplier: str | None = None
    start_ship_date: date | None = None
    cancel_ship_date: date | None = None
    order_status: str
    is_late: bool = False
    total_cartons: int | None = None
    dc_preview: list[ActiveOrderDcPreviewRead] = Field(default_factory=list)


class InventoryAlertDashboardRead(BaseModel):
    id: int
    product_id: int
    product_style: str | None = None
    supplier_name: str | None = None
    stock_type: str
    threshold_value: float
    current_value: float
    below_by: float
    customer_order_id: int | None = None
    created_at: datetime


class OrderPackingListRead(BaseModel):
    id: int
    dc_code: str | None = None
    invoice_number: str | None = None
    document_date: date | None = None
    total_pieces: int | None = None
    total_cartons: int | None = None
    total_gross_weight: float | None = None
    total_net_weight: float | None = None
    total_cubic_meters: float | None = None
    total_pallets: int | None = None
    totals_manually_overridden: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class LogisticsGroupProductRead(BaseModel):
    line_id: int | None = None
    vendor_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    units: int
    cartons: int
    master_carton: int | None = None
    store_ready_pack_size: int | None = None


class LogisticsGroupRead(BaseModel):
    nest_code: str | None = None
    type: str  # mono | nested
    cartons: int
    pcs_per_carton: int
    carton_size: str | None = None
    gross_weight_per_carton: float | None = None
    net_weight_per_carton: float | None = None
    total_gross_weight: float | None = None
    total_net_weight: float | None = None
    total_volume: float | None = None
    total_pallets: int | None = None
    warnings: list[dict] = Field(default_factory=list)
    products: list[LogisticsGroupProductRead] = Field(default_factory=list)


class LogisticsDcSummaryRead(BaseModel):
    dc_code: str
    total_pieces: int
    total_cartons: int
    total_volume: float | None = None
    total_gross_weight: float | None = None
    total_net_weight: float | None = None
    total_pallets: int | None = None
    groups: list[LogisticsGroupRead] = Field(default_factory=list)


class LogisticsScopeSummaryRead(BaseModel):
    total_pieces: int
    total_cartons: int
    total_volume: float | None = None
    total_gross_weight: float | None = None
    total_net_weight: float | None = None
    total_pallets: int | None = None
    dcs: list[LogisticsDcSummaryRead] = Field(default_factory=list)


class OrderLogisticsSummaryRead(BaseModel):
    order_id: int
    received: LogisticsScopeSummaryRead
    operational: LogisticsScopeSummaryRead


class DocumentOptionRead(BaseModel):
    document_type: str
    label: str
    level: str  # ORDER | DC
    enabled: bool
    formats: list[str] = Field(default_factory=list)
    reason: str | None = None


class DocumentDcOptionsRead(BaseModel):
    dc_code: str
    options: list[DocumentOptionRead] = Field(default_factory=list)


class OrderDocumentOptionsRead(BaseModel):
    order_id: int
    has_sfarinati: bool = False
    has_p2: bool = False
    order_level_options: list[DocumentOptionRead] = Field(default_factory=list)
    dc_level_options: list[DocumentDcOptionsRead] = Field(default_factory=list)


class OrderDocumentGenerateRequest(BaseModel):
    level: str  # ORDER | DC
    document_type: str  # purchase_order | packing_list | dle | sfarinati | p2
    format: str = "pdf"  # pdf | excel
    dc_code: str | None = None
