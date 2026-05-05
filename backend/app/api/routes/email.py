from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.email import EmailDraftResponse
from app.services.email_service import EmailService

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/prepare/{purchase_order_id}", response_model=EmailDraftResponse)
def prepare_email_draft(
    purchase_order_id: int,
    db: Session = Depends(get_db),
) -> EmailDraftResponse:
    service = EmailService(db)
    try:
        return service.prepare_supplier_email(purchase_order_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
