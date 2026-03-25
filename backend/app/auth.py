from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

# passlib은 bcrypt 4.x/5.x와 호환 문제가 있어 bcrypt를 직접 사용합니다.


def _password_bytes(plain: str) -> bytes:
    b = plain.encode("utf-8")
    return b[:72] if len(b) > 72 else b


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt()).decode("ascii")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_student_token(student_id: int) -> str:
    s = get_settings()
    exp = int((_now() + timedelta(minutes=s.student_token_expire_minutes)).timestamp())
    payload: dict[str, Any] = {"sub": str(student_id), "typ": "student", "exp": exp}
    return jwt.encode(payload, s.jwt_secret_student, algorithm=s.jwt_algorithm)


def create_admin_token(admin_id: int) -> str:
    s = get_settings()
    exp = int((_now() + timedelta(minutes=s.admin_token_expire_minutes)).timestamp())
    payload: dict[str, Any] = {"sub": str(admin_id), "typ": "admin", "exp": exp}
    return jwt.encode(payload, s.jwt_secret_admin, algorithm=s.jwt_algorithm)


def create_teacher_view_token() -> str:
    """동아리 배정 현황 조회 전용( DB admin_users 행 없음 )."""
    s = get_settings()
    exp = int((_now() + timedelta(minutes=s.admin_token_expire_minutes)).timestamp())
    payload: dict[str, Any] = {"sub": "teacher_view", "typ": "teacher_view", "exp": exp}
    return jwt.encode(payload, s.jwt_secret_admin, algorithm=s.jwt_algorithm)


def decode_student_token(token: str) -> int | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret_student, algorithms=[s.jwt_algorithm])
        if payload.get("typ") != "student":
            return None
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        return None


def decode_admin_token(token: str) -> int | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret_admin, algorithms=[s.jwt_algorithm])
        if payload.get("typ") != "admin":
            return None
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        return None


def parse_dashboard_access_token(
    token: str,
) -> tuple[Literal["admin", "teacher_view"], int | None] | None:
    """대시보드·동아리 배정 명단 조회용. (admin, id) 또는 (teacher_view, None)."""
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret_admin, algorithms=[s.jwt_algorithm])
    except JWTError:
        return None
    typ = payload.get("typ")
    if typ == "admin":
        try:
            return "admin", int(payload["sub"])
        except (ValueError, KeyError):
            return None
    if typ == "teacher_view":
        return "teacher_view", None
    return None
