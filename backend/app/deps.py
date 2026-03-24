from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_admin_token, decode_student_token
from app.database import get_db
from app.models import AdminUser, Student

security = HTTPBearer(auto_error=False)


async def get_current_student_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> int:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증이 필요합니다.")
    sid = decode_student_token(creds.credentials)
    if sid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰입니다.")
    r = await db.execute(select(Student.id).where(Student.id == sid))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "학생 정보를 찾을 수 없습니다.")
    return sid


async def get_current_admin_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> int:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "관리자 로그인이 필요합니다.")
    aid = decode_admin_token(creds.credentials)
    if aid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 관리자 토큰입니다.")
    r = await db.execute(select(AdminUser.id).where(AdminUser.id == aid))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "관리자를 찾을 수 없습니다.")
    return aid
