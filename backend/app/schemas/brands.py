from pydantic import BaseModel


class BrandSummaryRead(BaseModel):
    key: str
    label: str
    total_orders_year: int
    archived_orders_year: int
    to_ship_orders_year: int
    annual_revenue_eur: float
    period_start: str
    period_end: str


class BrandOrderRowRead(BaseModel):
    order_id: int
    po: str | None = None
    supplier: str | None = None
    created_at: str | None = None
    start_ship_date: str | None = None
    cancel_ship_date: str | None = None
    order_status: str
    is_archived: bool
    total_pieces: int
    total_cartons: int | None = None
    total_volume_cubic_meters: float | None = None
    order_total_sale_eur: float
