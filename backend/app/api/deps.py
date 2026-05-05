from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_service import AuthService


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    value = authorization.strip()
    if not value.lower().startswith("bearer "):
        return None
    return value[7:].strip()


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    token = _extract_bearer_token(authorization)
    user = AuthService(db).get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione non valida. Effettua il login.")
    request.state.user_id = user.id
    request.state.username = user.username
    request.state.user_role = user.role
    return user


def require_roles(*allowed: str):
    def _inner(user=Depends(get_current_user)):
        if allowed and user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permesso negato.")
        return user

    return _inner
