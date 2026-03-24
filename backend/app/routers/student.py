from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_student_token
from app.database import get_db
from app.deps import get_current_student_id
from app.models import Application, ApplicationStatus, Club, Student
from app.schemas import ApplyRequest, ApplyResponse, ClubListItem, StudentVerifyRequest, StudentVerifyResponse
from app.textnorm import normalize_person_name, normalize_student_number_input
from app.services.apply import student_apply
from app.services.settings_ctx import get_or_create_settings, is_application_open_computed

router = APIRouter(prefix="/api/student", tags=["student"])


@router.get("/me")
async def student_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    student_id: Annotated[int, Depends(get_current_student_id)],
):
    r = await db.execute(select(Student).where(Student.id == student_id))
    stu = r.scalar_one_or_none()
    if stu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "학생을 찾을 수 없습니다.")
    return {
        "id": stu.id,
        "student_number": stu.student_number,
        "name": stu.name,
        "grade": stu.grade,
        "class_no": stu.class_no,
    }


@router.post("/verify", response_model=StudentVerifyResponse)
async def verify_student(body: StudentVerifyRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    sn = normalize_student_number_input(body.student_number)
    name = normalize_person_name(body.name)
    r = await db.execute(select(Student).where(Student.student_number == sn))
    stu = r.scalar_one_or_none()
    if stu is None and sn.isdigit():
        bad = f"{int(sn)}.0"
        r2 = await db.execute(select(Student).where(Student.student_number == bad))
        stu = r2.scalar_one_or_none()
    if stu is None or normalize_person_name(stu.name) != name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "학번과 이름이 일치하지 않습니다.")
    token = create_student_token(stu.id)
    return StudentVerifyResponse(
        access_token=token,
        student_id=stu.id,
        name=stu.name,
        student_number=stu.student_number,
    )


@router.get("/my-assignment")
async def my_assignment(
    db: Annotated[AsyncSession, Depends(get_db)],
    student_id: Annotated[int, Depends(get_current_student_id)],
):
    """활성 배정이 있으면 동아리명을 반환 (없으면 null)."""
    r = await db.execute(
        select(Club.club_name)
        .join(Application, Application.club_id == Club.id)
        .where(
            Application.student_id == student_id,
            Application.status.in_(
                [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
            ),
        )
        .limit(1)
    )
    row = r.first()
    return {"club_name": row[0] if row else None}


@router.get("/clubs", response_model=list[ClubListItem])
async def list_clubs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_student_id)],
):
    now = datetime.now(timezone.utc)
    settings = await get_or_create_settings(db)
    window_open = is_application_open_computed(now, settings)

    r = await db.execute(select(Club).order_by(Club.club_code))
    clubs = r.scalars().all()
    out: list[ClubListItem] = []
    for c in clubs:
        cnt_r = await db.execute(
            select(func.count())
            .select_from(Application)
            .where(
                Application.club_id == c.id,
                Application.status.in_(
                    [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
                ),
            )
        )
        current = int(cnt_r.scalar_one())
        remaining = max(0, c.capacity - current)
        effective_open = c.is_open and window_open and remaining > 0
        out.append(
            ClubListItem(
                id=c.id,
                club_code=c.club_code,
                club_name=c.club_name,
                teacher_name=c.teacher_name,
                capacity=c.capacity,
                current_count=current,
                remaining=remaining,
                description=c.description,
                is_open=effective_open,
            )
        )
    return out


@router.post("/apply", response_model=ApplyResponse)
async def apply_club(
    body: ApplyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    student_id: Annotated[int, Depends(get_current_student_id)],
):
    ok, msg, cname, at = await student_apply(db, student_id, body.club_id)
    return ApplyResponse(ok=ok, message=msg, club_name=cname, applied_at=at)
