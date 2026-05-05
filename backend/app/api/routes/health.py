from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.services.sfarinati_pdf_service_v2 import SfarinatiPdfServiceV2

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "utc_time": datetime.now(timezone.utc).isoformat(),
        "sfarinati_marker": SfarinatiPdfServiceV2.MANDATORY_PARAGRAPH_LINES[-1],
        "sfarinati_builder": SfarinatiPdfServiceV2.__name__,
    }
