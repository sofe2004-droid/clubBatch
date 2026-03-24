import os
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Application, ApplicationStatus, Club, Student, SyncRun, SyncRunStatus
from app.textnorm import (
    cell_to_str,
    normalize_club_code,
    normalize_person_name,
    normalize_student_number_input,
)

# 시트 '상태' 열이 이 값이면 학적만 반영(선정 동아리 없음). 그 외 문자열은 동아리 코드 또는 동아리명으로 매칭 시도.
_ENROLLMENT_SET = frozenset(
    normalize_person_name(x) for x in ("재학", "휴학", "졸업", "전학", "제적", "수료", "퇴학", "재적", "복학")
)


def _parse_yes(v: str | None) -> bool:
    if v is None:
        return True
    t = str(v).strip().upper()
    return t in ("Y", "YES", "TRUE", "1", "O", "예")


def _get_sheets_service():
    s = get_settings()
    path = s.google_service_account_json_path
    if not path or not os.path.isfile(path):
        return None, "GOOGLE_SERVICE_ACCOUNT_JSON_PATH가 설정되지 않았거나 파일이 없습니다."
    sid = s.google_sheets_spreadsheet_id
    if not sid:
        return None, "GOOGLE_SHEETS_SPREADSHEET_ID가 없습니다."
    creds = service_account.Credentials.from_service_account_file(
        path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return (service, sid), None


def _split_status_column(raw: str | None) -> tuple[str, str | None]:
    """(DB에 넣을 학적 상태, 선정동아리 매칭용 문자열 또는 None)."""
    if not raw or not str(raw).strip():
        return "재학", None
    t = normalize_person_name(str(raw))
    if t in _ENROLLMENT_SET:
        return t, None
    return "재학", t


def _rows_to_students(values: list[list[str]]) -> tuple[list[dict], str | None]:
    if not values:
        return [], "학생 시트가 비어 있습니다."
    header = [str(c).strip() for c in values[0]]
    idx = {h: i for i, h in enumerate(header)}
    need = ["학번", "이름"]
    for k in need:
        if k not in idx:
            return [], f"학생 시트에 '{k}' 열이 필요합니다. 헤더: {header}"
    out: list[dict] = []
    for row in values[1:]:
        def get(col: str, default: str | None = None) -> str | None:
            i = idx.get(col)
            if i is None or i >= len(row):
                return default
            return cell_to_str(row[i])

        sn_raw = get("학번")
        name_raw = get("이름")
        if not sn_raw or not name_raw:
            continue
        sn = normalize_student_number_input(sn_raw)
        name = normalize_person_name(name_raw)
        grade_s = get("학년")
        class_s = get("반")
        att_s = get("번호")
        status_raw = get("상태")
        enrollment_status, preassign_ref = _split_status_column(status_raw)
        try:
            grade = int(grade_s) if grade_s else None
        except ValueError:
            grade = None
        try:
            class_no = int(class_s) if class_s else None
        except ValueError:
            class_no = None
        try:
            attendance_no = int(att_s) if att_s else None
        except ValueError:
            attendance_no = None
        out.append(
            {
                "student_number": sn,
                "name": name,
                "grade": grade,
                "class_no": class_no,
                "attendance_no": attendance_no,
                "status": enrollment_status,
                "preassign_club_ref": preassign_ref,
            }
        )
    return out, None


def _rows_to_clubs(values: list[list[str]]) -> tuple[list[dict], str | None]:
    if not values:
        return [], "동아리 시트가 비어 있습니다."
    header = [str(c).strip() for c in values[0]]
    idx = {h: i for i, h in enumerate(header)}
    for k in ("동아리코드", "동아리명", "모집인원"):
        if k not in idx:
            return [], f"동아리 시트에 '{k}' 열이 필요합니다. 헤더: {header}"
    out: list[dict] = []
    for row in values[1:]:
        def get(col: str, default: str | None = None) -> str | None:
            i = idx.get(col)
            if i is None or i >= len(row):
                return default
            return cell_to_str(row[i])

        code_raw = get("동아리코드")
        cname_raw = get("동아리명")
        if not code_raw or not cname_raw:
            continue
        code = normalize_club_code(code_raw)
        cname = normalize_person_name(cname_raw)
        if not code or not cname:
            continue
        cap_s = get("모집인원")
        try:
            capacity = int(cap_s) if cap_s else 0
        except ValueError:
            capacity = 0
        if capacity <= 0:
            continue
        teacher = get("담당교사")
        desc = get("설명")
        open_s = get("신청가능여부")
        is_open = _parse_yes(open_s)
        out.append(
            {
                "club_code": code,
                "club_name": cname,
                "teacher_name": teacher,
                "capacity": capacity,
                "description": desc,
                "is_open": is_open,
            }
        )
    return out, None


async def _resolve_club_by_ref(db: AsyncSession, ref: str) -> Club | None:
    code_try = normalize_club_code(ref)
    r = await db.execute(select(Club).where(Club.club_code == code_try))
    c = r.scalar_one_or_none()
    if c is not None:
        return c
    name_try = normalize_person_name(ref)
    r2 = await db.execute(select(Club).where(Club.club_name == name_try))
    return r2.scalar_one_or_none()


async def _apply_sheet_preassignments(
    db: AsyncSession,
    student_rows: list[dict],
    now: datetime,
) -> tuple[int, list[str]]:
    """시트 상태열에 적힌 선정 동아리를 applications에 반영(기존 활성 신청은 취소 처리)."""
    applied = 0
    warnings: list[str] = []
    for sd in student_rows:
        ref = sd.get("preassign_club_ref")
        if not ref:
            continue
        sn = sd["student_number"]
        stu_r = await db.execute(select(Student).where(Student.student_number == sn))
        stu = stu_r.scalar_one_or_none()
        if stu is None:
            warnings.append(f"{sn}: 학생 없음")
            continue
        club = await _resolve_club_by_ref(db, ref)
        if club is None:
            warnings.append(f"{sn}: 동아리 매칭 실패 ({ref})")
            continue
        prev = await db.execute(
            select(Application).where(
                Application.student_id == stu.id,
                Application.status.in_(
                    [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
                ),
            )
        )
        for app in prev.scalars().all():
            app.status = ApplicationStatus.CANCELLED
        db.add(
            Application(
                student_id=stu.id,
                club_id=club.id,
                applied_at=now,
                status=ApplicationStatus.FORCED_ASSIGN,
                assigned_by_admin_id=None,
                assign_reason="구글시트_학생정보_상태열_선정",
            )
        )
        stu.may_self_apply = False
        applied += 1
    await db.flush()
    return applied, warnings


async def sync_from_google_sheets(db: AsyncSession) -> tuple[bool, str, int, int, int]:
    s = get_settings()
    pair, err = _get_sheets_service()
    if err:
        return False, err, 0, 0, 0
    assert pair is not None
    service, spreadsheet_id = pair

    started = datetime.now(timezone.utc)
    run = SyncRun(
        started_at=started,
        status=SyncRunStatus.FAILURE,
        message=None,
        students_upserted=0,
        clubs_upserted=0,
    )
    db.add(run)
    await db.flush()

    try:
        sh = service.spreadsheets()
        stu_range = s.google_sheets_students_range
        club_range = s.google_sheets_clubs_range
        stu_resp = (
            sh.values()
            .get(spreadsheetId=spreadsheet_id, range=stu_range)
            .execute()
        )
        club_resp = (
            sh.values()
            .get(spreadsheetId=spreadsheet_id, range=club_range)
            .execute()
        )
        stu_vals = stu_resp.get("values") or []
        club_vals = club_resp.get("values") or []

        students, e1 = _rows_to_students(stu_vals)
        if e1:
            raise ValueError(e1)
        clubs, e2 = _rows_to_clubs(club_vals)
        if e2:
            raise ValueError(e2)

        cu = 0
        for cd in clubs:
            r = await db.execute(select(Club).where(Club.club_code == cd["club_code"]))
            row = r.scalar_one_or_none()
            if row:
                row.club_name = cd["club_name"]
                row.teacher_name = cd["teacher_name"]
                row.capacity = cd["capacity"]
                row.description = cd["description"]
                row.is_open = cd["is_open"]
            else:
                db.add(
                    Club(
                        club_code=cd["club_code"],
                        club_name=cd["club_name"],
                        teacher_name=cd["teacher_name"],
                        capacity=cd["capacity"],
                        description=cd["description"],
                        is_open=cd["is_open"],
                    )
                )
            cu += 1
        await db.flush()

        su = 0
        for sd in students:
            r = await db.execute(
                select(Student).where(Student.student_number == sd["student_number"])
            )
            row = r.scalar_one_or_none()
            if row:
                row.name = sd["name"]
                row.grade = sd["grade"]
                row.class_no = sd["class_no"]
                row.attendance_no = sd["attendance_no"]
                row.status = sd["status"]
            else:
                db.add(
                    Student(
                        student_number=sd["student_number"],
                        name=sd["name"],
                        grade=sd["grade"],
                        class_no=sd["class_no"],
                        attendance_no=sd["attendance_no"],
                        status=sd["status"],
                    )
                )
            su += 1
        await db.flush()

        now = datetime.now(timezone.utc)
        pa, warns = await _apply_sheet_preassignments(db, students, now)

        extra = ""
        if warns:
            extra = " 참고: " + "; ".join(warns[:5])
            if len(warns) > 5:
                extra += f" 외 {len(warns) - 5}건"

        run.status = SyncRunStatus.SUCCESS
        run.finished_at = datetime.now(timezone.utc)
        run.students_upserted = su
        run.clubs_upserted = cu
        run.message = f"OK (시트 선정동아리 반영 {pa}명){extra}"
        await db.flush()
        return True, run.message or "동기화 완료", su, cu, pa
    except Exception as e:  # noqa: BLE001
        run.finished_at = datetime.now(timezone.utc)
        run.message = str(e)
        run.status = SyncRunStatus.FAILURE
        await db.flush()
        return False, str(e), 0, 0, 0
