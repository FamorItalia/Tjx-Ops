from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.suppliers import (
    SupplierCreate,
    SupplierDocumentRename,
    SupplierDocumentRead,
    SupplierImportResponse,
    SupplierProductRead,
    SupplierRead,
    SupplierUpdate,
)
from app.services.suppliers_service import SuppliersService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.post("/import", response_model=SupplierImportResponse)
async def import_suppliers_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SupplierImportResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome file mancante.")
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato non supportato. Carica un file Excel .xlsx/.xlsm.",
        )

    content = await file.read()
    service = SuppliersService(db)
    try:
        return service.import_suppliers_excel(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[SupplierRead])
def list_suppliers(db: Session = Depends(get_db)) -> list[SupplierRead]:
    return SuppliersService(db).list_suppliers()


@router.post("", response_model=SupplierRead)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)) -> SupplierRead:
    try:
        return SuppliersService(db).create_supplier(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/export/excel")
def export_suppliers_excel(db: Session = Depends(get_db)) -> Response:
    excel_bytes = SuppliersService(db).export_suppliers_excel()
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"ANAGRAFICA_FORNITORI_{now}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, db: Session = Depends(get_db)) -> SupplierRead:
    row = SuppliersService(db).get_supplier(supplier_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fornitore non trovato: {supplier_id}",
        )
    return row


@router.patch("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
) -> SupplierRead:
    row = SuppliersService(db).update_supplier(supplier_id=supplier_id, payload=payload)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fornitore non trovato: {supplier_id}",
        )
    return row


@router.get("/{supplier_id}/products", response_model=list[SupplierProductRead])
def list_supplier_products(
    supplier_id: int,
    db: Session = Depends(get_db),
) -> list[SupplierProductRead]:
    supplier = SuppliersService(db).get_supplier(supplier_id)
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fornitore non trovato: {supplier_id}",
        )
    return SuppliersService(db).list_supplier_products(supplier_id=supplier_id)


@router.get("/{supplier_id}/documents", response_model=list[SupplierDocumentRead])
def list_supplier_documents(
    supplier_id: int,
    db: Session = Depends(get_db),
) -> list[SupplierDocumentRead]:
    supplier = SuppliersService(db).get_supplier(supplier_id)
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fornitore non trovato: {supplier_id}",
        )
    return SuppliersService(db).list_supplier_documents(supplier_id=supplier_id)


@router.post("/{supplier_id}/documents/upload", response_model=SupplierDocumentRead)
async def upload_supplier_document(
    supplier_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SupplierDocumentRead:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome file mancante.")
    service = SuppliersService(db)
    try:
        content = await file.read()
        return service.upload_supplier_document(
            supplier_id=supplier_id,
            file_name=file.filename,
            content=content,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{supplier_id}/documents/{document_id}", response_model=SupplierDocumentRead)
def rename_supplier_document(
    supplier_id: int,
    document_id: int,
    payload: SupplierDocumentRename,
    db: Session = Depends(get_db),
) -> SupplierDocumentRead:
    service = SuppliersService(db)
    try:
        row = service.rename_supplier_document(
            supplier_id=supplier_id,
            document_id=document_id,
            file_name=payload.file_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento fornitore non trovato: {document_id}",
        )
    return row


@router.get("/{supplier_id}/documents/{document_id}/download")
def download_supplier_document(
    supplier_id: int,
    document_id: int,
    inline: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    service = SuppliersService(db)
    row = service.get_supplier_document(supplier_id=supplier_id, document_id=document_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento fornitore non trovato: {document_id}",
        )
    file_path = Path(row.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File documento non trovato su disco: {row.file_name}",
        )

    disposition = "inline" if inline else "attachment"
    headers = {"Content-Disposition": f'{disposition}; filename="{row.file_name}"'}
    return FileResponse(
        path=file_path,
        media_type=row.content_type or "application/octet-stream",
        filename=row.file_name,
        headers=headers,
    )


@router.delete("/{supplier_id}/documents/{document_id}")
def delete_supplier_document(
    supplier_id: int,
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    service = SuppliersService(db)
    deleted = service.delete_supplier_document(supplier_id=supplier_id, document_id=document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento fornitore non trovato: {document_id}",
        )
    return {"ok": True, "deleted_id": document_id}
