from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.orders import (
    ActiveOrderDashboardRead,
    InventoryAlertDashboardRead,
    OrderDocumentGenerateRequest,
    OrderDocumentOptionsRead,
    OrderDetailRead,
    OrderDocumentRead,
    OrderArchiveUpdateRequest,
    OrderLineDcOriginalUpdateRequest,
    OrderLineDcOperationalUpdateRequest,
    OrderLineIdentityUpdateRequest,
    OrderLineOriginalUpdateRequest,
    OrderLineOperationalUpdateRequest,
    OrderListItemRead,
    OrderLogisticsSummaryRead,
    OrderPackingListRead,
    OrderNestedOperationalCartonsUpdateRequest,
    OrderOperationalAutoIncreaseRequest,
)
from app.services.logistics_summary_service import LogisticsSummaryService
from app.services.orders_service import OrdersService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderListItemRead])
def list_orders(db: Session = Depends(get_db)) -> list[OrderListItemRead]:
    service = OrdersService(db)
    return service.list_orders()


@router.get("/active", response_model=list[OrderListItemRead])
def list_active_orders(db: Session = Depends(get_db)) -> list[OrderListItemRead]:
    service = OrdersService(db)
    return service.list_active_orders()


@router.get("/archive", response_model=list[OrderListItemRead])
def list_archived_orders(db: Session = Depends(get_db)) -> list[OrderListItemRead]:
    service = OrdersService(db)
    return service.list_archived_orders()


@router.get("/active-dashboard", response_model=list[ActiveOrderDashboardRead])
def list_active_orders_dashboard(db: Session = Depends(get_db)) -> list[ActiveOrderDashboardRead]:
    service = OrdersService(db)
    return service.list_active_dashboard()


@router.get("/inventory-alerts", response_model=list[InventoryAlertDashboardRead])
def list_inventory_alerts_dashboard(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[InventoryAlertDashboardRead]:
    service = OrdersService(db)
    return service.list_inventory_alerts_dashboard(limit=limit)


@router.get("/{order_id}", response_model=OrderDetailRead)
def get_order(order_id: int, db: Session = Depends(get_db)) -> OrderDetailRead:
    service = OrdersService(db)
    order = service.get_order_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ordine non trovato: {order_id}",
        )
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order_id: int, db: Session = Depends(get_db)) -> None:
    service = OrdersService(db)
    service.delete_order(order_id=order_id)


@router.patch("/{order_id}/archive", response_model=OrderDetailRead)
def set_order_archive_state(
    order_id: int,
    payload: OrderArchiveUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.set_order_archived(order_id=order_id, is_archived=payload.is_archived)


@router.get("/{order_id}/documents", response_model=list[OrderDocumentRead])
def list_order_documents(order_id: int, db: Session = Depends(get_db)) -> list[OrderDocumentRead]:
    service = OrdersService(db)
    return service.list_order_documents(order_id=order_id)


@router.get("/{order_id}/documents/download-all")
def download_all_order_documents(
    order_id: int,
    format: str = Query("pdf", pattern="^(pdf|excel)$"),
    db: Session = Depends(get_db),
) -> FileResponse:
    service = OrdersService(db)
    zip_path = service.build_export_documents_zip(order_id=order_id, file_format=format)
    return FileResponse(
        path=Path(zip_path),
        filename=Path(zip_path).name,
        media_type="application/zip",
    )


@router.post("/{order_id}/documents/generate", response_model=list[OrderDocumentRead])
def generate_order_documents(order_id: int, db: Session = Depends(get_db)) -> list[OrderDocumentRead]:
    service = OrdersService(db)
    return service.generate_order_documents(order_id=order_id)


@router.get("/{order_id}/documents/options", response_model=OrderDocumentOptionsRead)
def get_order_document_options(order_id: int, db: Session = Depends(get_db)) -> OrderDocumentOptionsRead:
    service = OrdersService(db)
    return service.get_order_document_options(order_id=order_id)


@router.post("/{order_id}/documents/generate-item", response_model=list[OrderDocumentRead])
def generate_order_document_item(
    order_id: int,
    payload: OrderDocumentGenerateRequest,
    db: Session = Depends(get_db),
) -> list[OrderDocumentRead]:
    service = OrdersService(db)
    return service.generate_document(order_id=order_id, payload=payload)


@router.get("/{order_id}/packing-lists", response_model=list[OrderPackingListRead])
def list_order_packing_lists(order_id: int, db: Session = Depends(get_db)) -> list[OrderPackingListRead]:
    service = OrdersService(db)
    return service.list_order_packing_lists(order_id=order_id)


@router.post("/{order_id}/packing-lists/reset-calculated", response_model=list[OrderPackingListRead])
def reset_order_packing_list_totals(
    order_id: int,
    db: Session = Depends(get_db),
) -> list[OrderPackingListRead]:
    service = OrdersService(db)
    return service.reset_order_packing_list_totals_to_calculated(order_id=order_id)


@router.get("/{order_id}/logistics-summary", response_model=OrderLogisticsSummaryRead)
def get_order_logistics_summary(order_id: int, db: Session = Depends(get_db)) -> OrderLogisticsSummaryRead:
    repo_service = OrdersService(db)
    if repo_service.get_order_by_id(order_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ordine non trovato: {order_id}",
        )
    logistics_service = LogisticsSummaryService(repo_service.repository)
    try:
        return logistics_service.get_order_logistics_summary(order_id=order_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch("/{order_id}/lines/{line_id}/operational-units", response_model=OrderDetailRead)
def update_line_operational_units(
    order_id: int,
    line_id: int,
    payload: OrderLineOperationalUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.update_line_operational_units(
        order_id=order_id,
        line_id=line_id,
        operational_units=payload.operational_units,
    )


@router.patch("/{order_id}/lines/{line_id}/original-units", response_model=OrderDetailRead)
def update_line_original_units(
    order_id: int,
    line_id: int,
    payload: OrderLineOriginalUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.update_line_original_units(
        order_id=order_id,
        line_id=line_id,
        original_units=payload.original_units,
    )


@router.patch("/{order_id}/lines/{line_id}/dc/{dc_code}/operational-units", response_model=OrderDetailRead)
def update_line_dc_operational_units(
    order_id: int,
    line_id: int,
    dc_code: str,
    payload: OrderLineDcOperationalUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.update_line_dc_operational_units(
        order_id=order_id,
        line_id=line_id,
        dc_code=dc_code,
        operational_dc_units=payload.operational_dc_units,
    )


@router.patch("/{order_id}/lines/{line_id}/dc/{dc_code}/original-units", response_model=OrderDetailRead)
def update_line_dc_original_units(
    order_id: int,
    line_id: int,
    dc_code: str,
    payload: OrderLineDcOriginalUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.update_line_dc_original_units(
        order_id=order_id,
        line_id=line_id,
        dc_code=dc_code,
        original_dc_units=payload.original_dc_units,
    )


@router.patch("/{order_id}/lines/{line_id}/identity", response_model=OrderDetailRead)
def update_line_identity(
    order_id: int,
    line_id: int,
    payload: OrderLineIdentityUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.update_line_identity(
        order_id=order_id,
        line_id=line_id,
        vendor_style=payload.vendor_style,
        item_code=payload.item_code,
        description=payload.description,
        nest_code=payload.nest_code,
    )


@router.patch("/{order_id}/nested/{nest_code}/dc/{dc_code}/operational-cartons", response_model=OrderDetailRead)
def update_nested_operational_cartons(
    order_id: int,
    nest_code: str,
    dc_code: str,
    payload: OrderNestedOperationalCartonsUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.update_nested_operational_cartons(
        order_id=order_id,
        nest_code=nest_code,
        dc_code=dc_code,
        operational_cartons=payload.operational_cartons,
    )


@router.post("/{order_id}/operational/apply-auto-increase", response_model=OrderDetailRead)
def apply_operational_auto_increase(
    order_id: int,
    payload: OrderOperationalAutoIncreaseRequest,
    db: Session = Depends(get_db),
) -> OrderDetailRead:
    service = OrdersService(db)
    return service.apply_operational_auto_increase(order_id=order_id, percent=payload.percent)


@router.post("/{order_id}/operational/reset-to-original", response_model=OrderDetailRead)
def reset_operational_to_original(order_id: int, db: Session = Depends(get_db)) -> OrderDetailRead:
    service = OrdersService(db)
    return service.reset_operational_to_original(order_id=order_id)


@router.post("/{order_id}/received/reset-to-imported", response_model=OrderDetailRead)
def reset_received_to_imported(order_id: int, db: Session = Depends(get_db)) -> OrderDetailRead:
    service = OrdersService(db)
    return service.reset_received_to_imported(order_id=order_id)


@router.post("/{order_id}/received/normalize-quantities", response_model=OrderDetailRead)
def normalize_received_quantities(order_id: int, db: Session = Depends(get_db)) -> OrderDetailRead:
    service = OrdersService(db)
    return service.normalize_received_quantities(order_id=order_id)
