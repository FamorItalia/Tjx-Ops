from datetime import date, datetime

from pydantic import BaseModel, Field


class PurchaseOrderGenerateRequest(BaseModel):
    customer_order_id: int
    adjustment_percent: float = 2.0


class PurchaseOrderLinePreview(BaseModel):
    id: int | None = None
    customer_order_line_id: int | None = None
    vendor_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    nest_code: str | None = None
    units_per_dc: dict[str, int] = Field(default_factory=dict)
    logistics: dict[str, int | float | str] = Field(default_factory=dict)
    quantity_base: int | None = None
    applied_percent: float | None = None
    quantity_final: int | None = None


class SupplierDetailsRead(BaseModel):
    fornitore: str
    ragione_sociale: str | None = None
    indirizzo: str | None = None
    cap: str | None = None
    citta: str | None = None
    provincia: str | None = None
    paese: str | None = None
    telefono: str | None = None
    persona_di_contatto: str | None = None
    emails: list[str] = Field(default_factory=list)
    email_subject_template: str | None = None
    email_order_template: str | None = None
    indirizzo_completo: str | None = None


class PurchaseOrderPreviewResponse(BaseModel):
    id: int
    customer_order_id: int | None = None
    document_family: str | None = None
    brand: str | None = None
    supplier: str | None = None
    po: str | None = None
    po_raw: str | None = None
    po_normalized: str | None = None
    start_ship_date: date | None = None
    cancel_ship_date: date | None = None
    adjustment_percent: float
    created_at: datetime
    total_lines: int
    total_quantity_base: int
    total_quantity_final: int
    supplier_details: SupplierDetailsRead | None = None
    lines: list[PurchaseOrderLinePreview] = Field(default_factory=list)
    pdf_payload: dict[str, object] = Field(default_factory=dict)


class PurchaseOrderLineUpdate(BaseModel):
    line_id: int
    quantity_final: int


class PurchaseOrderUpdateRequest(BaseModel):
    adjustment_percent: float | None = None
    line_updates: list[PurchaseOrderLineUpdate] = Field(default_factory=list)


class PurchaseOrderPdfResponse(BaseModel):
    purchase_order_id: int
    file_name: str
    file_path: str
    line_count: int
    generated_at: datetime
