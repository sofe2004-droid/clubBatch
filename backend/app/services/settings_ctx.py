from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationSettings


async def get_or_create_settings(db: AsyncSession) -> ApplicationSettings:
    r = await db.execute(select(ApplicationSettings).where(ApplicationSettings.singleton_key == "global"))
    row = r.scalar_one_or_none()
    if row:
        return row
    row = ApplicationSettings(singleton_key="global")
    db.add(row)
    await db.flush()
    return row


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_within_application_window(
    now: datetime,
    starts: datetime | None,
    ends: datetime | None,
    globally_closed: bool,
) -> bool:
    if globally_closed:
        return False
    n = _aware(now)
    if n is None:
        n = datetime.now(timezone.utc)
    s = _aware(starts)
    e = _aware(ends)
    if s is not None and n < s:
        return False
    if e is not None and n > e:
        return False
    return True


def is_application_open_computed(now: datetime, settings: ApplicationSettings) -> bool:
    return is_within_application_window(
        now,
        settings.application_starts_at,
        settings.application_ends_at,
        settings.is_globally_closed,
    )
