from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.models.auth import AuditLog
from app.db.session import get_db
from app.schemas.auth import (
    AuditLogRead,
    LoginRequest,
    LoginResponse,
    UserCreateRequest,
    UserPasswordChangeRequest,
    UserRead,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    value = authorization.strip()
    if not value.lower().startswith("bearer "):
        return None
    return value[7:].strip()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    service = AuthService(db)
    service.ensure_seed_admin()
    token, user = service.login(payload.username, payload.password)
    return LoginResponse(token=token, user=user)


@router.post("/logout")
def logout(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token = _extract_token(authorization)
    AuthService(db).revoke_token(token)
    return {"status": "ok"}


@router.get("/me", response_model=UserRead)
def me(user=Depends(get_current_user)) -> UserRead:
    return UserRead(id=user.id, username=user.username, full_name=user.full_name, role=user.role)


@router.get("/users", response_model=list[UserRead], dependencies=[Depends(require_roles("admin"))])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    return AuthService(db).list_users()


@router.post("/users", response_model=UserRead, dependencies=[Depends(require_roles("admin"))], status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db)) -> UserRead:
    return AuthService(db).create_user(
        username=payload.username,
        full_name=payload.full_name,
        role=payload.role,
        password=payload.password,
    )


@router.patch("/users/{user_id}/password", dependencies=[Depends(require_roles("admin"))])
def change_password(user_id: int, payload: UserPasswordChangeRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    AuthService(db).change_password(user_id=user_id, password=payload.password)
    return {"status": "ok"}


@router.get("/audit", response_model=list[AuditLogRead], dependencies=[Depends(require_roles("admin"))])
def list_audit(_: Request, db: Session = Depends(get_db)) -> list[AuditLogRead]:
    rows = AuthService(db).list_audit(limit=300)
    return [
        AuditLogRead(
            id=r.id,
            user_id=r.user_id,
            username=r.username,
            method=r.method,
            path=r.path,
            payload_json=r.payload_json,
            created_at=r.created_at,
        )
        for r in rows
    ]
