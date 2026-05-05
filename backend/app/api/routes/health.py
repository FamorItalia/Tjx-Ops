from datetime import datetime, timezone
import json
from pathlib import Path

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


@router.get("/ops")
def ops_health_check() -> dict[str, object]:
    project_root = Path.cwd().parent
    heartbeat_path = project_root / "ops" / "logs" / "watchdog-heartbeat.json"
    frontend_build_id_path = project_root / "frontend" / ".next" / "BUILD_ID"

    watchdog: dict[str, object] = {
        "configured": heartbeat_path.exists(),
        "last_run_utc": None,
        "backend_ok": None,
        "frontend_ok": None,
        "is_stale": None,
    }

    if heartbeat_path.exists():
        try:
            raw = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            watchdog["last_run_utc"] = raw.get("last_run_utc")
            watchdog["backend_ok"] = raw.get("backend_ok")
            watchdog["frontend_ok"] = raw.get("frontend_ok")

            ts = raw.get("last_run_utc")
            if isinstance(ts, str) and ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
                watchdog["is_stale"] = delta.total_seconds() > 2 * 3600
        except Exception:
            pass

    frontend_build_id = None
    if frontend_build_id_path.exists():
        try:
            frontend_build_id = frontend_build_id_path.read_text(encoding="utf-8").strip()
        except Exception:
            frontend_build_id = None

    return {
        "backend": {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
            "utc_time": datetime.now(timezone.utc).isoformat(),
        },
        "frontend": {
            "build_id": frontend_build_id,
        },
        "watchdog": watchdog,
    }
