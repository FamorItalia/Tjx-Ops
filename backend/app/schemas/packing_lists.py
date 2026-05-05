from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class PackingListPreviewRequest(BaseModel):
    purchase_order_id: int | None = None
    customer_order_id: int | None = None
    invoice_number: str | None = None
    document_date: date | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if self.purchase_order_id is None and self.customer_order_id is None:
            raise ValueError("Specificare purchase_order_id oppure customer_order_id.")
        return self


class PackingListDestinationRead(BaseModel):
    dc_code: str
    dc_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    po_prefix: str | None = None
    general_division_name: str | None = None
    general_address_line_1: str | None = None
    general_address_line_2: str | None = None
    general_address_line_3: str | None = None
    destination_merce_name: str | None = None
    destination_merce_dc_number: str | None = None
    destination_merce_address_line_1: str | None = None
    destination_merce_address_line_2: str | None = None
    destination_merce_address_line_3: str | None = None


class PackingListLineRead(BaseModel):
    id: int
    group_key: str | None = None
    group_type: str | None = None
    line_no: int
    vendor_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    pcs_per_crt: int | None = None
    gross_weight_per_carton: float | None = None
    net_weight_per_carton: float | None = None
    cartons: int | None = None
    pieces: int | None = None
    cartons_per_layer: int | None = None
    cartons_per_pallet: int | None = None
    layers_per_pallet: int | None = None
    carton_height_cm: float | None = None
    pallet_width_cm: float | None = None
    pallet_depth_cm: float | None = None
    full_pallets: int | None = None
    partial_layers: int | None = None
    line_cubic_meters: float | None = None
    vendor_pack_size: int | None = None
    store_ready_pack_size: int | None = None
    destination_dc_codes: list[str] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)


class PackingListGroupProductRead(BaseModel):
    line_no: int
    vendor_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    pieces: int | None = None
    pcs_x_crt: int | None = None
    vendor_pack_size: int | None = None
    store_ready_pack_size: int | None = None


class PackingListGroupRead(BaseModel):
    group_key: str
    group_type: str  # mono | nested
    nest_code: str | None = None
    vendor_pack_size: int | None = None
    total_cartons: int | None = None
    carton_size: str | None = None
    gross_weight_per_carton: float | None = None
    net_weight_per_carton: float | None = None
    total_gross_weight: float | None = None
    total_net_weight: float | None = None
    total_cubic_meters: float | None = None
    products: list[PackingListGroupProductRead] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)


class PackingListRead(BaseModel):
    id: int
    purchase_order_id: int | None = None
    customer_order_id: int | None = None
    invoice_number: str | None = None
    document_date: date | None = None
    dc_code: str | None = None
    po_number: str | None = None
    brand: str | None = None
    supplier_name: str | None = None
    supplier_ragione_sociale: str | None = None
    supplier_address_full: str | None = None
    dept_no: str | None = None
    recipient_name: str | None = None
    recipient_address: str | None = None
    destinations: list[PackingListDestinationRead] = Field(default_factory=list)
    total_pieces: int
    total_cartons: int
    total_gross_weight: float
    total_net_weight: float
    total_cubic_meters: float
    total_pallets: int | None = None
    totals_manually_overridden: bool = False
    groups: list[PackingListGroupRead] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
    lines: list[PackingListLineRead] = Field(default_factory=list)
    created_at: datetime


class PackingListPreviewBatchRead(BaseModel):
    purchase_order_id: int
    customer_order_id: int | None = None
    po_number: str | None = None
    brand: str | None = None
    packing_lists: list[PackingListRead] = Field(default_factory=list)


class PackingListUpdateRequest(BaseModel):
    invoice_number: str | None = None
    document_date: date | None = None
    total_gross_weight: float | None = None
    total_net_weight: float | None = None
    total_cubic_meters: float | None = None
    total_pallets: int | None = None
    totals_manually_overridden: bool | None = None


class PackingListPdfResponse(BaseModel):
    packing_list_id: int
    dc_code: str | None = None
    file_name: str
    file_path: str
    generated_at: datetime


class PackingListPdfBatchResponse(BaseModel):
    purchase_order_id: int
    files: list[PackingListPdfResponse] = Field(default_factory=list)
