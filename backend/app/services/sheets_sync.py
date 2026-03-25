import asyncio
from datetime import datetime, timezone

from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.google_creds import load_service_account_credentials
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
    creds, err = load_service_account_credentials(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    if err or creds is None:
        return None, err or "Google 인증 정보를 불러오지 못했습니다."
    sid = s.google_sheets_spreadsheet_id
    if not sid:
        return None, "GOOGLE_SHEETS_SPREADSHEET_ID가 없습니다."
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
    if not out:
        if len(values) <= 1:
            return [], "학생 시트에 데이터 행이 없습니다(헤더만 있거나 시트 범위가 비었습니다)."
        return (
            [],
            "학생 시트에 데이터 행은 있으나 '학번'·'이름'이 채워진 행이 없습니다. "
            "첫 행에 정확히 '학번','이름' 헤더가 있는지, GOOGLE_SHEETS_STUDENTS_RANGE가 "
            "해당 열을 모두 포함하는지 확인하세요.",
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
    if not out:
        if len(values) <= 1:
            return [], "동아리 시트에 데이터 행이 없습니다(헤더만 있거나 범위가 비었습니다)."
        return (
            [],
            "동아리 시트에 데이터 행은 있으나 반영 가능한 행이 없습니다. "
            "동아리코드·동아리명·모집인원(1 이상)과 첫 행 헤더 이름을 확인하세요.",
        )
    return out, None


def _club_from_ref(
    ref: str,
    clubs_by_code: dict[str, Club],
    clubs_by_name: dict[str, Club],
) -> Club | None:
    code_try = normalize_club_code(ref)
    c = clubs_by_code.get(code_try)
    if c is not None:
        return c
    name_try = normalize_person_name(ref)
    return clubs_by_name.get(name_try)


def _blocking_fetch_sheet_ranges(
    service: object,
    spreadsheet_id: str,
    stu_range: str,
    club_range: str,
) -> tuple[dict, dict]:
    sh = service.spreadsheets()
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
    return stu_resp, club_resp


async def _apply_sheet_preassignments(
    db: AsyncSession,
    student_rows: list[dict],
    now: datetime,
    students_by_sn: dict[str, Student],
    clubs_by_code: dict[str, Club],
    clubs_by_name: dict[str, Club],
) -> tuple[int, list[str]]:
    """시트 상태열에 적힌 선정 동아리를 applications에 반영(기존 활성 신청은 취소 처리)."""
    applied = 0
    warnings: list[str] = []
    rows_with_ref = [sd for sd in student_rows if sd.get("preassign_club_ref")]
    if not rows_with_ref:
        return 0, []

    cancel_ids: list[int] = []
    for sd in rows_with_ref:
        stu = students_by_sn.get(sd["student_number"])
        if stu is not None:
            cancel_ids.append(stu.id)

    if cancel_ids:
        prev = await db.execute(
            select(Application).where(
                Application.student_id.in_(cancel_ids),
                Application.status.in_(
                    [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
                ),
            )
        )
        for app in prev.scalars().all():
            app.status = ApplicationStatus.CANCELLED

    for sd in rows_with_ref:
        sn = sd["student_number"]
        ref = sd["preassign_club_ref"]
        stu = students_by_sn.get(sn)
        if stu is None:
            warnings.append(f"{sn}: 학생 없음")
            continue
        club = _club_from_ref(ref, clubs_by_code, clubs_by_name)
        if club is None:
            warnings.append(f"{sn}: 동아리 매칭 실패 ({ref})")
            continue
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
        stu_range = s.google_sheets_students_range
        club_range = s.google_sheets_clubs_range
        stu_resp, club_resp = await asyncio.to_thread(
            _blocking_fetch_sheet_ranges,
            service,
            spreadsheet_id,
            stu_range,
            club_range,
        )
        stu_vals = stu_resp.get("values") or []
        club_vals = club_resp.get("values") or []

        students, e1 = _rows_to_students(stu_vals)
        if e1:
            raise ValueError(e1)
        clubs, e2 = _rows_to_clubs(club_vals)
        if e2:
            raise ValueError(e2)

        codes = [cd["club_code"] for cd in clubs]
        clubs_existing: dict[str, Club] = {}
        if codes:
            r_clubs = await db.execute(select(Club).where(Club.club_code.in_(codes)))
            clubs_existing = {c.club_code: c for c in r_clubs.scalars().all()}

        cu = 0
        for cd in clubs:
            row = clubs_existing.get(cd["club_code"])
            if row:
                row.club_name = cd["club_name"]
                row.teacher_name = cd["teacher_name"]
                row.capacity = cd["capacity"]
                row.description = cd["description"]
                row.is_open = cd["is_open"]
            else:
                neu = Club(
                    club_code=cd["club_code"],
                    club_name=cd["club_name"],
                    teacher_name=cd["teacher_name"],
                    capacity=cd["capacity"],
                    description=cd["description"],
                    is_open=cd["is_open"],
                )
                db.add(neu)
                clubs_existing[cd["club_code"]] = neu
            cu += 1
        await db.flush()

        r_all_clubs = await db.execute(select(Club))
        club_rows = list(r_all_clubs.scalars().all())
        clubs_by_code = {c.club_code: c for c in club_rows}
        clubs_by_name = {c.club_name: c for c in club_rows}

        sns = [sd["student_number"] for sd in students]
        by_sn: dict[str, Student] = {}
        if sns:
            r_stu = await db.execute(
                select(Student).where(Student.student_number.in_(sns))
            )
            by_sn = {s.student_number: s for s in r_stu.scalars().all()}

        su = 0
        for sd in students:
            row = by_sn.get(sd["student_number"])
            if row:
                row.name = sd["name"]
                row.grade = sd["grade"]
                row.class_no = sd["class_no"]
                row.attendance_no = sd["attendance_no"]
                row.status = sd["status"]
            else:
                neu = Student(
                    student_number=sd["student_number"],
                    name=sd["name"],
                    grade=sd["grade"],
                    class_no=sd["class_no"],
                    attendance_no=sd["attendance_no"],
                    status=sd["status"],
                )
                db.add(neu)
                by_sn[sd["student_number"]] = neu
            su += 1
        await db.flush()

        now = datetime.now(timezone.utc)
        pa, warns = await _apply_sheet_preassignments(
            db, students, now, by_sn, clubs_by_code, clubs_by_name
        )

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
