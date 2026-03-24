"""
구글 스프레드시트 → PostgreSQL 동기화 (관리자 화면「시트 동기화」와 동일 로직).

사전 조건
  - alembic upgrade head 로 DB 스키마 최신
  - backend/.env 에 DATABASE_URL, GOOGLE_SERVICE_ACCOUNT_JSON_PATH,
    GOOGLE_SHEETS_SPREADSHEET_ID, (선택) 범위 변수 설정

실행 (backend 디렉터리에서):
  python -m scripts.sync_sheets_to_db

시트 형식은 app.services.sheets_sync 주석·코드와 동일
(학생: 학번, 이름, 학년, 반, 번호, 상태 / 동아리: 동아리코드, 동아리명, 모집인원 등).
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _main() -> int:
    from app.database import AsyncSessionLocal
    from app.services.sheets_sync import sync_from_google_sheets

    async with AsyncSessionLocal() as session:
        ok, msg, su, cu, pa = await sync_from_google_sheets(session)
        if ok:
            await session.commit()
            print(msg)
            print(f"학생 upsert: {su}명, 동아리 upsert: {cu}개, 시트 선정 반영: {pa}명")
            return 0
        await session.rollback()
        print(msg, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
