from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, Request

from app.api.router import api_router
from app.core.config import settings
from app.core.paths import template_paths
from app.db.models.auth import AuditLog, UserAccount, UserSession
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.auth_service import AuthService


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        AuthService(db).ensure_seed_admin()
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    payload_text: str | None = None
    if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
        try:
            body = await request.body()
            if body:
                payload_text = body.decode("utf-8", errors="ignore")
                if len(payload_text) > 4000:
                    payload_text = payload_text[:4000]
        except Exception:
            payload_text = None

    response = await call_next(request)

    if request.url.path.startswith("/api/v1/auth"):
        return response
    if request.method not in {"POST", "PATCH", "DELETE", "PUT"}:
        return response
    if response.status_code >= 400:
        return response

    auth = request.headers.get("authorization") or ""
    token = None
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()

    if not token:
        return response

    db = SessionLocal()
    try:
        session = db.query(UserSession).filter(UserSession.token == token, UserSession.revoked_at.is_(None)).first()
        user = db.get(UserAccount, session.user_id) if session else None
        db.add(
            AuditLog(
                user_id=user.id if user else None,
                username=user.username if user else None,
                method=request.method,
                path=request.url.path,
                payload_json=payload_text if payload_text and payload_text.strip() else None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return response


app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, object]:
    return {
        "message": "TJX Operativita API",
        "templates_root": str(template_paths.root),
        "available_routes": [
            "/api/v1/health",
            "/api/v1/files/pdfs",
            "/api/v1/files/upload-pdf",
            "/api/v1/parser/test",
            "/api/v1/parser/sierra/test",
            "/api/v1/parser/tjx_usa/test",
            "/api/v1/parser/tjx_canada/test",
            "/api/v1/orders",
            "/api/v1/orders/active",
            "/api/v1/orders/active-dashboard",
            "/api/v1/orders/archive",
            "/api/v1/brands",
            "/api/v1/brands/{brand_key}/orders",
            "/api/v1/orders/{id}",
            "/api/v1/orders/{id}/documents",
            "/api/v1/purchase-orders/preview",
            "/api/v1/purchase-orders/{id}",
            "/api/v1/purchase-orders/{id}/pdf",
            "/api/v1/distribution-centers/import",
            "/api/v1/distribution-centers",
            "/api/v1/distribution-centers/{id}",
            "/api/v1/suppliers/import",
            "/api/v1/suppliers",
            "/api/v1/suppliers/{id}",
            "/api/v1/email/prepare/{purchase_order_id}",
            "/api/v1/packing-lists/preview",
            "/api/v1/packing-lists/{id}",
            "/api/v1/packing-lists/{id}/pdf",
            "/api/v1/packing-lists/pdf/by-purchase-order/{purchase_order_id}",
        ],
    }
