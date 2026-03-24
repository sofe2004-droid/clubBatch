import csv
import io

from googleapiclient.discovery import build
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.google_creds import load_service_account_credentials
from app.models import Application, ApplicationStatus


async def applications_to_rows(db: AsyncSession) -> list[dict]:
    r = await db.execute(
        select(Application)
        .options(selectinload(Application.student), selectinload(Application.club))
        .where(
            Application.status.in_(
                [ApplicationStatus.COMPLETED, ApplicationStatus.FORCED_ASSIGN]
            )
        )
        .order_by(Application.applied_at)
    )
    rows: list[dict] = []
    for a in r.scalars().all():
        st = a.student
        cl = a.club
        rows.append(
            {
                "student_number": st.student_number,
                "name": st.name,
                "grade": st.grade,
                "class_no": st.class_no,
                "club_code": cl.club_code,
                "club_name": cl.club_name,
                "status": a.status.value,
                "applied_at": a.applied_at.isoformat(),
            }
        )
    return rows


def rows_to_csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        header = "student_number,name,grade,class_no,club_code,club_name,status,applied_at\n"
        return ("\ufeff" + header).encode("utf-8-sig")
    buf = io.StringIO()
    fieldnames = list(rows[0].keys())
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
    return ("\ufeff" + buf.getvalue()).encode("utf-8-sig")


def rows_to_xlsx_bytes(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "applications"
    if not rows:
        ws.append(
            [
                "student_number",
                "name",
                "grade",
                "class_no",
                "club_code",
                "club_name",
                "status",
                "applied_at",
            ]
        )
    else:
        keys = list(rows[0].keys())
        ws.append(keys)
        for r in rows:
            ws.append([r.get(k) for k in keys])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def export_results_to_google_sheet(db: AsyncSession) -> tuple[bool, str]:
    s = get_settings()
    sid = s.google_sheets_spreadsheet_id
    if not sid:
        return False, "GOOGLE_SHEETS_SPREADSHEET_ID가 없습니다."

    creds, err = load_service_account_credentials(
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    if err or creds is None:
        return False, err or "Google 시트 인증에 실패했습니다."
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    rows = await applications_to_rows(db)
    values = [
        ["학번", "이름", "학년", "반", "동아리코드", "동아리명", "상태", "신청시각"],
    ]
    for r in rows:
        values.append(
            [
                r["student_number"],
                r["name"],
                r["grade"],
                r["class_no"],
                r["club_code"],
                r["club_name"],
                r["status"],
                r["applied_at"],
            ]
        )
    range_name = "결과연동!A1"
    body = {"values": values}
    sh = service.spreadsheets()
    try:
        sh.values().update(
            spreadsheetId=sid,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()
    except Exception as e:  # noqa: BLE001
        return False, f"시트 쓰기 실패: {e}. 스프레드시트에 '결과연동' 시트를 만드세요."
    return True, f"Google 시트 '결과연동'에 {len(rows)}건을 기록했습니다."
