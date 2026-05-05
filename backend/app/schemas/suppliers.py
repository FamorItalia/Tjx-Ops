from datetime import datetime

from pydantic import BaseModel, Field


class SupplierRead(BaseModel):
    id: int
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
    is_active: bool

    model_config = {"from_attributes": True}


class SupplierUpdate(BaseModel):
    ragione_sociale: str | None = None
    indirizzo: str | None = None
    cap: str | None = None
    citta: str | None = None
    provincia: str | None = None
    paese: str | None = None
    telefono: str | None = None
    persona_di_contatto: str | None = None
    emails: list[str] | None = None
    email_subject_template: str | None = None
    email_order_template: str | None = None


class SupplierCreate(BaseModel):
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


class SupplierProductRead(BaseModel):
    id: int
    tjx_style: str | None = None
    description: str | None = None
    pcs_per_crt: int | None = None
    purchase_cost_eur: float | None = None
    sale_price_eur: float | None = None

    model_config = {"from_attributes": True}


class SupplierDocumentRead(BaseModel):
    id: int
    supplier_id: int
    file_name: str
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_at: datetime


class SupplierDocumentRename(BaseModel):
    file_name: str


class SupplierImportResponse(BaseModel):
    file_name: str
    imported_at: datetime
    total_rows_read: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    warnings: list[str]
