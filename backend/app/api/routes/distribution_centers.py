from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.distribution_centers import DistributionCenterImportResponse, DistributionCenterRead
from app.services.distribution_centers_service import DistributionCentersService

router = APIRouter(prefix="/distribution-centers", tags=["distribution-centers"])


@router.post("/import", response_model=DistributionCenterImportResponse)
async def import_distribution_centers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DistributionCenterImportResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome file mancante.")
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato non supportato. Carica un file Excel .xlsx/.xlsm.",
        )
    content = await file.read()
    service = DistributionCentersService(db)
    try:
        return service.import_distribution_centers_excel(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[DistributionCenterRead])
def list_distribution_centers(db: Session = Depends(get_db)) -> list[DistributionCenterRead]:
    service = DistributionCentersService(db)
    return service.list_distribution_centers()


@router.get("/export/excel")
def export_distribution_centers_excel(db: Session = Depends(get_db)) -> Response:
    service = DistributionCentersService(db)
    excel_bytes = service.export_distribution_centers_excel()
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"ANAGRAFICA_DC_{now}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/{dc_id}", response_model=DistributionCenterRead)
def get_distribution_center(dc_id: int, db: Session = Depends(get_db)) -> DistributionCenterRead:
    service = DistributionCentersService(db)
    row = service.get_distribution_center(dc_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Distribution center non trovato: {dc_id}",
        )
    return row
