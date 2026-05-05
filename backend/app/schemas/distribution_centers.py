from datetime import datetime

from pydantic import BaseModel


class DistributionCenterRead(BaseModel):
    id: int
    brand: str
    dc_code: str
    po_prefix: str | None = None
    dc_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    general_division_name: str | None = None
    general_address_line_1: str | None = None
    general_address_line_2: str | None = None
    general_address_line_3: str | None = None
    destination_merce_name: str | None = None
    destination_merce_dc_number: str | None = None
    destination_merce_address_line_1: str | None = None
    destination_merce_address_line_2: str | None = None
    destination_merce_address_line_3: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class DistributionCenterImportResponse(BaseModel):
    file_name: str
    imported_at: datetime
    total_columns_read: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    warnings: list[str]
