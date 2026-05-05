import hashlib
import secrets
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.auth import AuditLog, UserAccount, UserSession
from app.schemas.auth import UserRead


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def build_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}${_hash_password(password, salt)}"


def verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    return _hash_password(password, salt) == digest


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_seed_admin(self) -> None:
        admin_exists = self.db.query(UserAccount.id).filter(UserAccount.username == "admin").first()
        if admin_exists:
            return
        admin = UserAccount(
            username="admin",
            full_name="Amministratore",
            role="admin",
            password_hash=build_password_hash("admin123"),
        )
        self.db.add(admin)
        self.db.commit()

    def login(self, username: str, password: str) -> tuple[str, UserRead]:
        user = (
            self.db.query(UserAccount)
            .filter(UserAccount.username == (username or "").strip())
            .first()
        )
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenziali non valide.")
        token = secrets.token_urlsafe(48)
        self.db.add(UserSession(user_id=user.id, token=token))
        self.db.commit()
        return token, UserRead(id=user.id, username=user.username, full_name=user.full_name, role=user.role)

    def get_user_by_token(self, token: str | None) -> UserAccount | None:
        if not token:
            return None
        session = (
            self.db.query(UserSession)
            .filter(UserSession.token == token, UserSession.revoked_at.is_(None))
            .first()
        )
        if session is None:
            return None
        return self.db.get(UserAccount, session.user_id)

    def revoke_token(self, token: str | None) -> None:
        if not token:
            return
        session = (
            self.db.query(UserSession)
            .filter(UserSession.token == token, UserSession.revoked_at.is_(None))
            .first()
        )
        if session is None:
            return
        session.revoked_at = datetime.utcnow()
        self.db.commit()

    def list_users(self) -> list[UserRead]:
        rows = self.db.query(UserAccount).order_by(UserAccount.username.asc()).all()
        return [UserRead(id=r.id, username=r.username, full_name=r.full_name, role=r.role) for r in rows]

    def create_user(self, username: str, full_name: str, role: str, password: str) -> UserRead:
        key = (username or "").strip()
        if not key:
            raise HTTPException(status_code=400, detail="Username obbligatorio.")
        exists = self.db.query(UserAccount.id).filter(UserAccount.username == key).first()
        if exists:
            raise HTTPException(status_code=409, detail="Username già esistente.")
        if role not in {"admin", "operatore", "viewer"}:
            raise HTTPException(status_code=400, detail="Ruolo non valido.")
        row = UserAccount(
            username=key,
            full_name=(full_name or key).strip(),
            role=role,
            password_hash=build_password_hash(password),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return UserRead(id=row.id, username=row.username, full_name=row.full_name, role=row.role)

    def change_password(self, user_id: int, password: str) -> None:
        row = self.db.get(UserAccount, user_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Utente non trovato.")
        row.password_hash = build_password_hash(password)
        self.db.commit()

    def list_audit(self, limit: int = 200) -> list[AuditLog]:
        return self.db.query(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 1000))).all()
