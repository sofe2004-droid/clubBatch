from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Application,
    ApplicationAttempt,
    ApplicationStatus,
    Club,
    Student,
)
from app.services.settings_ctx import get_or_create_settings, is_application_open_computed


def _student_eligible(status: str) -> bool:
    s = (status or "").strip()
    if not s:
        return True
    blocked = ("휴학", "졸업", "전학", "제적")
    return not any(b in s for b in blocked)


async def _count_active_for_club(db: AsyncSession, club_id: int) -> int:
    r = await db.execute(
        select(func.count())
        .select_from(Application)
        .where(
            Application.club_id == club_id,
            Application.status.in_(
                [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
            ),
        )
    )
    return int(r.scalar_one())


async def student_apply(
    db: AsyncSession,
    student_id: int,
    club_id: int,
) -> tuple[bool, str, str | None, datetime | None]:
    now = datetime.now(timezone.utc)
    settings = await get_or_create_settings(db)
    if not is_application_open_computed(now, settings):
        return False, "신청 기간이 아니거나 신청이 마감되었습니다.", None, None

    stu = (
        await db.execute(select(Student).where(Student.id == student_id).with_for_update())
    ).scalar_one_or_none()
    if stu is None:
        return False, "학생을 찾을 수 없습니다.", None, None
    if not _student_eligible(stu.status):
        return False, "현재 상태로는 신청할 수 없습니다.", None, None

    existing = (
        await db.execute(
            select(Application).where(
                Application.student_id == student_id,
                Application.status.in_(
                    [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
                ),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False, "이미 동아리에 신청하셨습니다.", None, None
    if not stu.may_self_apply:
        return (
            False,
            "관리자가 동아리 배정을 삭제한 경우에만 다시 신청할 수 있습니다. 행정실에 문의해 주세요.",
            None,
            None,
        )

    club = (
        await db.execute(select(Club).where(Club.id == club_id).with_for_update())
    ).scalar_one_or_none()
    if club is None:
        return False, "동아리를 찾을 수 없습니다.", None, None
    if not club.is_open:
        return False, "해당 동아리는 신청을 받지 않습니다.", None, None

    cnt = await _count_active_for_club(db, club_id)
    if cnt >= club.capacity:
        db.add(
            ApplicationAttempt(
                student_id=student_id,
                club_id=club_id,
                attempted_at=now,
                failure_reason="capacity_full",
            )
        )
        await db.flush()
        return False, "정원이 마감되었습니다.", None, None

    app = Application(
        student_id=student_id,
        club_id=club_id,
        applied_at=now,
        status=ApplicationStatus.COMPLETED,
        assigned_by_admin_id=None,
        assign_reason=None,
    )
    db.add(app)
    stu.may_self_apply = False
    await db.flush()
    return True, f"{club.club_name}동아리에 배정 완료되었습니다.", club.club_name, now
