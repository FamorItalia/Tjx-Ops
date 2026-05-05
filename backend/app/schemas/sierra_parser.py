from datetime import date

from pydantic import BaseModel, Field


class ParserWarning(BaseModel):
    code: str
    message: str
    page: int | None = None
    context: dict[str, str] = Field(default_factory=dict)


class SierraOrderLine(BaseModel):
    vendor_style: str | None = None
    item_code: str | None = None
    description: str | None = None
    total_units: int | None = None
    units_per_dc: dict[str, int] = Field(default_factory=dict)


class SierraParseRequest(BaseModel):
    file_name: str


class SierraParseResponse(BaseModel):
    document_family: str
    source_file: str
    start_ship_date: date | None = None
    cancel_ship_date: date | None = None
    distribution_center: str | None = None
    distribution_center_name: str | None = None
    distribution_center_address: str | None = None
    po_raw: str | None = None
    po_normalized: str | None = None
    lines: list[SierraOrderLine] = Field(default_factory=list)
    warnings: list[ParserWarning] = Field(default_factory=list)
    saved_order_id: int | None = None
