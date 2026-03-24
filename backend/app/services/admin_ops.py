from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminLog,
    AdminLogAction,
    Application,
    ApplicationStatus,
    Club,
    Student,
)


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


async def force_assign(
    db: AsyncSession,
    admin_id: int,
    student_id: int,
    club_id: int,
    reason: str,
    cancel_existing: bool,
    allow_over_capacity: bool,
) -> tuple[bool, str]:
    now = datetime.now(timezone.utc)

    stu = (
        await db.execute(select(Student).where(Student.id == student_id).with_for_update())
    ).scalar_one_or_none()
    if stu is None:
        return False, "학생을 찾을 수 없습니다."

    club = (
        await db.execute(select(Club).where(Club.id == club_id).with_for_update())
    ).scalar_one_or_none()
    if club is None:
        return False, "동아리를 찾을 수 없습니다."

    res = await db.execute(
        select(Application)
        .where(
            Application.student_id == student_id,
            Application.status.in_(
                [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
            ),
        )
        .with_for_update()
    )
    existing_apps = res.scalars().all()

    if existing_apps:
        if not cancel_existing:
            return False, "이미 신청된 동아리가 있습니다. 기존 신청 취소 옵션을 사용하세요."
        for existing in existing_apps:
            existing.status = ApplicationStatus.CANCELLED
        await db.flush()

    cnt = await _count_active_for_club(db, club_id)
    if not allow_over_capacity and cnt >= club.capacity:
        return False, "정원이 찼습니다. 초과 배정을 허용하려면 allow_over_capacity를 켜세요."

    app = Application(
        student_id=student_id,
        club_id=club_id,
        applied_at=now,
        status=ApplicationStatus.FORCED_ASSIGN,
        assigned_by_admin_id=admin_id,
        assign_reason=reason,
    )
    db.add(app)
    stu.may_self_apply = False
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=AdminLogAction.FORCE_ASSIGN,
            target_student_id=student_id,
            target_club_id=club_id,
            action_time=now,
            note=reason[:2000] if reason else None,
        )
    )
    await db.flush()
    return True, "강제배정이 완료되었습니다."


async def cancel_student_application(
    db: AsyncSession,
    admin_id: int,
    application_id: int,
    note: str | None,
) -> tuple[bool, str]:
    now = datetime.now(timezone.utc)
    app = (
        await db.execute(
            select(Application).where(Application.id == application_id).with_for_update()
        )
    ).scalar_one_or_none()
    if app is None:
        return False, "신청 내역을 찾을 수 없습니다."
    if app.status == ApplicationStatus.CANCELLED:
        return False, "이미 취소된 신청입니다."
    app.status = ApplicationStatus.CANCELLED
    stu = (
        await db.execute(select(Student).where(Student.id == app.student_id).with_for_update())
    ).scalar_one_or_none()
    if stu is not None:
        stu.may_self_apply = True
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=AdminLogAction.CANCEL_APPLICATION,
            target_student_id=app.student_id,
            target_club_id=app.club_id,
            action_time=now,
            note=note,
        )
    )
    await db.flush()
    return True, "신청이 취소되었습니다."
