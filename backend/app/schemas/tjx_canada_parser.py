from datetime import date

from pydantic import BaseModel, Field

from app.schemas.sierra_parser import ParserWarning


class TjxCanadaParseRequest(BaseModel):
    file_name: str


class TjxCanadaOrderLine(BaseModel):
    pg_ln: str | None = None
    vendor_style: str | None = None
    item_code: str | None = None
    detailed_description: str | None = None
    description: str | None = None
    units: int | None = None
    total_units: int | None = None
    vend_pack: int | None = None


class TjxCanadaParseResponse(BaseModel):
    document_family: str
    brand: str | None = None
    source_file: str
    po_raw: str | None = None
    po_normalized: str | None = None
    import_po_number: str | None = None
    start_ship_date: date | None = None
    cancel_ship_date: date | None = None
    total_units: int | None = None
    lines: list[TjxCanadaOrderLine] = Field(default_factory=list)
    warnings: list[ParserWarning] = Field(default_factory=list)
    saved_order_id: int | None = None

