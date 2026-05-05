from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.packing_lists import (
    PackingListPdfBatchResponse,
    PackingListPdfResponse,
    PackingListPreviewBatchRead,
    PackingListPreviewRequest,
    PackingListRead,
    PackingListUpdateRequest,
)
from app.services.packing_list_pdf_service import PackingListPdfService
from app.services.packing_lists_service import PackingListsService

router = APIRouter(prefix="/packing-lists", tags=["packing-lists"])


@router.post("/preview", response_model=PackingListPreviewBatchRead)
def create_packing_list_preview(
    payload: PackingListPreviewRequest,
    db: Session = Depends(get_db),
) -> PackingListPreviewBatchRead:
    service = PackingListsService(db)
    try:
        return service.create_previews(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{packing_list_id}", response_model=PackingListRead)
def get_packing_list(
    packing_list_id: int,
    db: Session = Depends(get_db),
) -> PackingListRead:
    row = PackingListsService(db).get_packing_list(packing_list_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Packing list non trovata: {packing_list_id}",
        )
    return row


@router.patch("/{packing_list_id}", response_model=PackingListRead)
def update_packing_list(
    packing_list_id: int,
    payload: PackingListUpdateRequest,
    db: Session = Depends(get_db),
) -> PackingListRead:
    service = PackingListsService(db)
    try:
        return service.update_packing_list(packing_list_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{packing_list_id}/pdf", response_model=PackingListPdfResponse)
def generate_packing_list_pdf(
    packing_list_id: int,
    db: Session = Depends(get_db),
) -> PackingListPdfResponse:
    service = PackingListsService(db)
    row = service.get_packing_list(packing_list_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Packing list non trovata: {packing_list_id}",
        )
    pdf_service = PackingListPdfService(output_root=Path.cwd() / "output")
    result = pdf_service.build_pdf(row)
    return PackingListPdfResponse(
        packing_list_id=row.id,
        dc_code=row.dc_code,
        file_name=result.file_name,
        file_path=result.file_path,
        generated_at=result.generated_at,
    )


@router.post("/pdf/by-purchase-order/{purchase_order_id}", response_model=PackingListPdfBatchResponse)
def generate_packing_list_pdfs_by_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
) -> PackingListPdfBatchResponse:
    service = PackingListsService(db)
    rows = service.list_by_purchase_order_id(purchase_order_id)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Nessuna packing list trovata per purchase_order_id={purchase_order_id}. "
                "Genera prima la preview multi-DC."
            ),
        )
    pdf_service = PackingListPdfService(output_root=Path.cwd() / "output")
    files = []
    for row in rows:
        result = pdf_service.build_pdf(row)
        files.append(
            PackingListPdfResponse(
                packing_list_id=row.id,
                dc_code=row.dc_code,
                file_name=result.file_name,
                file_path=result.file_path,
                generated_at=result.generated_at,
            )
        )
    return PackingListPdfBatchResponse(
        purchase_order_id=purchase_order_id,
        files=files,
    )
