from datetime import date

from pydantic import BaseModel, Field

from app.schemas.sierra_parser import ParserWarning


class TjxUsaParseRequest(BaseModel):
    file_name: str


class TjxUsaOrderLine(BaseModel):
    pg_ln: str | None = None
    vendor_style: str | None = None
    tjx_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    total_units: int | None = None
    vendor_pack_size: int | None = None
    store_ready_pack_size: int | None = None
    nest_code: str | None = None
    distribution_center: str | None = None
    units_per_dc: dict[str, int] = Field(default_factory=dict)


class TjxUsaParseResponse(BaseModel):
    document_family: str
    brand: str | None = None
    supplier_name: str | None = None
    source_file: str
    po_raw: str | None = None
    po_normalized: str | None = None
    start_ship_date: date | None = None
    cancel_ship_date: date | None = None
    distribution_centers: list[str] = Field(default_factory=list)
    lines: list[TjxUsaOrderLine] = Field(default_factory=list)
    warnings: list[ParserWarning] = Field(default_factory=list)
    saved_order_id: int | None = None
