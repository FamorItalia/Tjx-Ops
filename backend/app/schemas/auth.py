from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: int
    username: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: UserRead


class UserCreateRequest(BaseModel):
    username: str
    full_name: str
    role: str = "operatore"
    password: str


class UserPasswordChangeRequest(BaseModel):
    password: str


class AuditLogRead(BaseModel):
    id: int
    user_id: int | None
    username: str | None
    method: str
    path: str
    payload_json: str | None
    created_at: datetime
