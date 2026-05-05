from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.products import (
    ProductCreate,
    ProductDocumentRead,
    ProductImportResponse,
    ProductInventoryHistoryRead,
    ProductRead,
    ProductUpdate,
)
from app.services.inventory_service import InventoryService
from app.services.products_service import ProductsService

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/import", response_model=ProductImportResponse)
async def import_products_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ProductImportResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome file mancante.",
        )
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato non supportato. Carica un file Excel .xlsx/.xlsm.",
        )
    content = await file.read()
    service = ProductsService(db)
    try:
        return service.import_products_excel(file.filename, content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)) -> list[ProductRead]:
    service = ProductsService(db)
    return service.list_products()


@router.post("", response_model=ProductRead)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> ProductRead:
    service = ProductsService(db)
    try:
        return service.create_product(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/export/excel")
def export_products_excel(db: Session = Depends(get_db)) -> Response:
    service = ProductsService(db)
    excel_bytes = service.export_products_excel()
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"ANAGRAFICA_PRODOTTI_{now}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductRead:
    service = ProductsService(db)
    product = service.get_product(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prodotto non trovato: {product_id}",
        )
    return product


@router.get("/{product_id}/inventory-history", response_model=ProductInventoryHistoryRead)
def get_product_inventory_history(product_id: int, db: Session = Depends(get_db)) -> ProductInventoryHistoryRead:
    inventory_service = InventoryService(db)
    history = inventory_service.get_product_inventory_history(product_id=product_id)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prodotto non trovato: {product_id}",
        )
    return ProductInventoryHistoryRead.model_validate(history)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
) -> ProductRead:
    service = ProductsService(db)
    product = service.update_product(product_id=product_id, payload=payload)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prodotto non trovato: {product_id}",
        )
    return product


@router.get("/{product_id}/documents", response_model=list[ProductDocumentRead])
def list_product_documents(product_id: int, db: Session = Depends(get_db)) -> list[ProductDocumentRead]:
    service = ProductsService(db)
    product = service.get_product(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prodotto non trovato: {product_id}",
        )
    return service.list_product_documents(product_id=product_id)


@router.post("/{product_id}/documents/upload", response_model=ProductDocumentRead)
async def upload_product_document(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ProductDocumentRead:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome file mancante.")
    service = ProductsService(db)
    try:
        content = await file.read()
        return service.upload_product_document(
            product_id=product_id,
            file_name=file.filename,
            content=content,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{product_id}/documents/{document_id}/download")
def download_product_document(
    product_id: int,
    document_id: int,
    inline: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    service = ProductsService(db)
    row = service.get_product_document(product_id=product_id, document_id=document_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento prodotto non trovato: {document_id}",
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


@router.delete("/{product_id}/documents/{document_id}")
def delete_product_document(
    product_id: int,
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    service = ProductsService(db)
    deleted = service.delete_product_document(product_id=product_id, document_id=document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento prodotto non trovato: {document_id}",
        )
    return {"ok": True, "deleted_id": document_id}
