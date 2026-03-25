from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import create_admin_token, verify_password
from app.database import get_db
from app.deps import get_current_admin_id
from app.models import (
    AdminLog,
    AdminLogAction,
    AdminUser,
    Application,
    ApplicationAttempt,
    ApplicationStatus,
    Club,
    Student,
    SyncRun,
)
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    ApplicationSettingsOut,
    ApplicationSettingsUpdate,
    AssignedStudentItem,
    ClubAdminUpdate,
    ClubAssignedStudentsOut,
    DashboardClubOut,
    DashboardOut,
    ForceAssignRequest,
    SyncSheetsResponse,
)
from app.services.admin_ops import cancel_student_application, force_assign
from app.services.export import (
    applications_to_rows,
    export_results_to_google_sheet,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
)
from app.services.settings_ctx import get_or_create_settings, is_application_open_computed
from app.services.sheets_sync import sync_from_google_sheets

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    r = await db.execute(select(AdminUser).where(AdminUser.username == body.username))
    u = r.scalar_one_or_none()
    if u is None or not verify_password(body.password, u.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_admin_token(u.id)
    return AdminLoginResponse(access_token=token)


@router.get("/settings", response_model=ApplicationSettingsOut)
async def get_settings_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
):
    s = await get_or_create_settings(db)
    return ApplicationSettingsOut(
        application_starts_at=s.application_starts_at,
        application_ends_at=s.application_ends_at,
        is_globally_closed=s.is_globally_closed,
    )


@router.patch("/settings", response_model=ApplicationSettingsOut)
async def patch_settings(
    body: ApplicationSettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_id: Annotated[int, Depends(get_current_admin_id)],
):
    s = await get_or_create_settings(db)
    now = datetime.now(timezone.utc)
    if body.application_starts_at is not None:
        s.application_starts_at = body.application_starts_at
    if body.application_ends_at is not None:
        s.application_ends_at = body.application_ends_at
    if body.is_globally_closed is not None:
        s.is_globally_closed = body.is_globally_closed
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=AdminLogAction.SETTINGS_UPDATE,
            target_student_id=None,
            target_club_id=None,
            action_time=now,
            note="settings_update",
        )
    )
    await db.flush()
    return ApplicationSettingsOut(
        application_starts_at=s.application_starts_at,
        application_ends_at=s.application_ends_at,
        is_globally_closed=s.is_globally_closed,
    )


@router.post("/sync/sheets", response_model=SyncSheetsResponse)
async def sync_sheets(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_id: Annotated[int, Depends(get_current_admin_id)],
):
    ok, msg, su, cu, pa = await sync_from_google_sheets(db)
    if ok:
        now = datetime.now(timezone.utc)
        db.add(
            AdminLog(
                admin_id=admin_id,
                action_type=AdminLogAction.SYNC_SHEETS,
                action_time=now,
                note=f"students={su}, clubs={cu}, preassign={pa}",
            )
        )
        await db.flush()
    return SyncSheetsResponse(
        ok=ok,
        message=msg,
        students_upserted=su,
        clubs_upserted=cu,
        preassignments_applied=pa,
    )


@router.get("/clubs")
async def admin_list_clubs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
):
    r = await db.execute(select(Club).order_by(Club.club_code))
    clubs = r.scalars().all()
    out = []
    for c in clubs:
        cnt = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Application)
                    .where(
                        Application.club_id == c.id,
                        Application.status.in_(
                            [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
                        ),
                    )
                )
            ).scalar_one()
        )
        out.append(
            {
                "id": c.id,
                "club_code": c.club_code,
                "club_name": c.club_name,
                "teacher_name": c.teacher_name,
                "capacity": c.capacity,
                "current_count": cnt,
                "remaining": max(0, c.capacity - cnt),
                "is_open": c.is_open,
            }
        )
    return {"items": out}


@router.get("/clubs/{club_id}/assigned-students", response_model=ClubAssignedStudentsOut)
async def club_assigned_students(
    club_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
):
    club = await db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="동아리를 찾을 수 없습니다.")
    stmt = (
        select(Student.student_number, Student.name)
        .join(Application, Application.student_id == Student.id)
        .where(
            Application.club_id == club_id,
            Application.status.in_(
                [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
            ),
        )
        .order_by(Student.student_number)
    )
    rows = (await db.execute(stmt)).all()
    students = [AssignedStudentItem(student_number=r[0], name=r[1]) for r in rows]
    return ClubAssignedStudentsOut(
        club_id=club.id, club_name=club.club_name, students=students
    )


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
):
    now = datetime.now(timezone.utc)
    settings = await get_or_create_settings(db)
    total_students = int(
        (await db.execute(select(func.count()).select_from(Student))).scalar_one()
    )
    applied_count = int(
        (
            await db.execute(
                select(func.count(func.distinct(Application.student_id)))
                .select_from(Application)
                .where(
                    Application.status.in_(
                        [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
                    )
                )
            )
        ).scalar_one()
    )
    unassigned = max(0, total_students - applied_count)
    club_rows = (await db.execute(select(Club).order_by(Club.club_code))).scalars().all()
    clubs_out: list[DashboardClubOut] = []
    for c in club_rows:
        cnt = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Application)
                    .where(
                        Application.club_id == c.id,
                        Application.status.in_(
                            [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
                        ),
                    )
                )
            ).scalar_one()
        )
        clubs_out.append(
            DashboardClubOut(
                club_id=c.id,
                club_name=c.club_name,
                capacity=c.capacity,
                applied=cnt,
                is_open=c.is_open,
                full=cnt >= c.capacity,
            )
        )
    return DashboardOut(
        total_students=total_students,
        applied_count=applied_count,
        unassigned_count=unassigned,
        is_application_open=is_application_open_computed(now, settings),
        application_starts_at=settings.application_starts_at,
        application_ends_at=settings.application_ends_at,
        is_globally_closed=settings.is_globally_closed,
        clubs=clubs_out,
    )


@router.get("/applications")
async def list_applications(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
    q: str | None = None,
    grade: int | None = None,
    class_no: int | None = None,
    club_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(200, le=500),
    offset: int = 0,
):
    """배정 완료(completed / forced_assign)만 학생당 1행으로 반환. 취소된 과거 신청은 제외."""
    active_statuses = [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
    stmt = (
        select(Application)
        .join(Student, Student.id == Application.student_id)
        .where(Application.status.in_(active_statuses))
        .options(selectinload(Application.student), selectinload(Application.club))
        .order_by(Student.student_number)
    )
    if status_filter:
        try:
            st = ApplicationStatus(status_filter)
            if st in active_statuses:
                stmt = stmt.where(Application.status == st)
        except ValueError:
            pass
    if club_id is not None:
        stmt = stmt.where(Application.club_id == club_id)
    if grade is not None:
        stmt = stmt.where(Student.grade == grade)
    if class_no is not None:
        stmt = stmt.where(Student.class_no == class_no)
    if q and q.strip():
        qq = q.strip()
        stmt = stmt.where(
            or_(
                Student.student_number.contains(qq),
                Student.name.contains(qq),
            )
        )
    r = await db.execute(stmt)
    items = r.scalars().all()
    out = []
    for a in items:
        st = a.student
        cl = a.club
        out.append(
            {
                "student_id": st.id,
                "application_id": a.id,
                "student_number": st.student_number,
                "name": st.name,
                "grade": st.grade,
                "class_no": st.class_no,
                "club_id": cl.id,
                "club_name": cl.club_name,
            }
        )
    return {"items": out[offset : offset + limit], "total": len(out)}


@router.get("/unassigned")
async def list_unassigned(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
    q: str | None = None,
    grade: int | None = None,
    class_no: int | None = None,
):
    active = [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
    # NOT IN (서브쿼리)는 NULL/드라이버 조합에서 전부 걸러지는 경우가 있어 NOT EXISTS 사용
    stmt = select(Student).where(
        ~exists(
            select(1)
            .select_from(Application)
            .where(
                Application.student_id == Student.id,
                Application.status.in_(active),
            )
        )
    )
    if grade is not None:
        stmt = stmt.where(Student.grade == grade)
    if class_no is not None:
        stmt = stmt.where(Student.class_no == class_no)
    r = await db.execute(stmt.order_by(Student.student_number))
    students = r.scalars().all()
    filtered = []
    for st in students:
        if q:
            qq = q.strip()
            if qq and qq not in st.student_number and qq not in st.name:
                continue
        filtered.append(st)

    attempt_reason: dict[int, str] = {}
    ids = [st.id for st in filtered]
    if ids:
        rn = func.row_number().over(
            partition_by=ApplicationAttempt.student_id,
            order_by=ApplicationAttempt.attempted_at.desc(),
        ).label("rn")
        subq = (
            select(ApplicationAttempt.student_id, ApplicationAttempt.failure_reason, rn).where(
                ApplicationAttempt.student_id.in_(ids)
            )
        ).subquery()
        att_r = await db.execute(
            select(subq.c.student_id, subq.c.failure_reason).where(subq.c.rn == 1)
        )
        for row in att_r.all():
            sid, fr = row[0], row[1]
            if fr == "capacity_full":
                attempt_reason[sid] = "정원 초과로 실패"
            elif fr:
                attempt_reason[sid] = fr
            else:
                attempt_reason[sid] = "미신청"

    out = []
    for st in filtered:
        reason = attempt_reason.get(st.id, "미신청")
        out.append(
            {
                "student_id": st.id,
                "student_number": st.student_number,
                "name": st.name,
                "grade": st.grade,
                "class_no": st.class_no,
                "reason": reason,
            }
        )
    return {"items": out}


@router.post("/force-assign")
async def post_force_assign(
    body: ForceAssignRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_id: Annotated[int, Depends(get_current_admin_id)],
):
    ok, msg = await force_assign(
        db,
        admin_id,
        body.student_id,
        body.club_id,
        body.reason,
        body.cancel_existing,
        body.allow_over_capacity,
    )
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, msg)
    return {"ok": True, "message": msg}


@router.post("/applications/{application_id}/cancel")
async def post_cancel_application(
    application_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_id: Annotated[int, Depends(get_current_admin_id)],
    note: str | None = None,
):
    ok, msg = await cancel_student_application(db, admin_id, application_id, note)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, msg)
    return {"ok": True, "message": msg}


@router.patch("/clubs/{club_id}")
async def patch_club(
    club_id: int,
    body: ClubAdminUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_id: Annotated[int, Depends(get_current_admin_id)],
):
    r = await db.execute(select(Club).where(Club.id == club_id))
    c = r.scalar_one_or_none()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "동아리를 찾을 수 없습니다.")
    if body.is_open is not None:
        c.is_open = body.is_open
    now = datetime.now(timezone.utc)
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=AdminLogAction.CLUB_UPDATE,
            target_club_id=club_id,
            action_time=now,
            note=f"is_open={c.is_open}",
        )
    )
    await db.flush()
    return {"ok": True, "club_id": club_id, "is_open": c.is_open}


@router.get("/export/csv")
async def export_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
):
    rows = await applications_to_rows(db)
    data = rows_to_csv_bytes(rows)
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="applications.csv"'},
    )


@router.get("/export/xlsx")
async def export_xlsx(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
):
    rows = await applications_to_rows(db)
    data = rows_to_xlsx_bytes(rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="applications.xlsx"'},
    )


@router.post("/export/sheets")
async def export_sheets(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
):
    ok, msg = await export_results_to_google_sheet(db)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, msg)
    return {"ok": True, "message": msg}


@router.get("/sync/history")
async def sync_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[int, Depends(get_current_admin_id)],
    limit: int = Query(20, le=100),
):
    r = await db.execute(
        select(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit)
    )
    rows = r.scalars().all()
    return {
        "items": [
            {
                "id": x.id,
                "started_at": x.started_at.isoformat(),
                "finished_at": x.finished_at.isoformat() if x.finished_at else None,
                "status": x.status.value,
                "message": x.message,
                "students_upserted": x.students_upserted,
                "clubs_upserted": x.clubs_upserted,
            }
            for x in rows
        ]
    }
