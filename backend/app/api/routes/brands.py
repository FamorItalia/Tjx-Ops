from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.brands import BrandOrderRowRead, BrandSummaryRead
from app.services.orders_service import OrdersService

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[BrandSummaryRead])
def list_brand_summaries(
    db: Session = Depends(get_db),
) -> list[BrandSummaryRead]:
    return OrdersService(db).list_brand_summaries()


@router.get("/{brand_key}/orders", response_model=list[BrandOrderRowRead])
def list_orders_by_brand(
    brand_key: str,
    q: str | None = Query(default=None),
    archived: bool | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> list[BrandOrderRowRead]:
    return OrdersService(db).list_orders_by_brand(
        brand_key=brand_key,
        query=q,
        archived=archived,
        month=month,
        year=year,
    )
