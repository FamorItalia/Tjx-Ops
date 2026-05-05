from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.purchase_orders import (
    PurchaseOrderGenerateRequest,
    PurchaseOrderPdfResponse,
    PurchaseOrderPreviewResponse,
    PurchaseOrderUpdateRequest,
)
from app.services.purchase_order_pdf_service import PurchaseOrderPdfService
from app.services.purchase_orders_service import PurchaseOrdersService

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@router.post(
    "/preview",
    response_model=PurchaseOrderPreviewResponse,
    response_model_exclude_none=True,
)
def generate_preview(
    payload: PurchaseOrderGenerateRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderPreviewResponse:
    service = PurchaseOrdersService(db)
    try:
        return service.generate_preview(
            customer_order_id=payload.customer_order_id,
            adjustment_percent=payload.adjustment_percent,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{purchase_order_id}",
    response_model=PurchaseOrderPreviewResponse,
    response_model_exclude_none=True,
)
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
) -> PurchaseOrderPreviewResponse:
    service = PurchaseOrdersService(db)
    try:
        return service.get_purchase_order(purchase_order_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{purchase_order_id}",
    response_model=PurchaseOrderPreviewResponse,
    response_model_exclude_none=True,
)
def update_purchase_order(
    purchase_order_id: int,
    payload: PurchaseOrderUpdateRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderPreviewResponse:
    service = PurchaseOrdersService(db)
    try:
        return service.update_purchase_order(
            purchase_order_id=purchase_order_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{purchase_order_id}/pdf",
    response_model=PurchaseOrderPdfResponse,
)
def generate_purchase_order_pdf(
    purchase_order_id: int,
    db: Session = Depends(get_db),
) -> PurchaseOrderPdfResponse:
    service = PurchaseOrdersService(db)
    try:
        preview = service.get_purchase_order(purchase_order_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    output_root = Path.cwd() / "output"
    pdf_service = PurchaseOrderPdfService(output_root=output_root)
    result = pdf_service.build_pdf(preview)

    return PurchaseOrderPdfResponse(
        purchase_order_id=purchase_order_id,
        file_name=result.file_name,
        file_path=result.file_path,
        line_count=result.line_count,
        generated_at=result.generated_at,
    )
