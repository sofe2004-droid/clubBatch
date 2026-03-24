import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.auth import hash_password
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.google_creds import SHEETS_AUTH_IMPL
from app.models import AdminUser, ApplicationSettings
from app.routers import admin, student


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with AsyncSessionLocal() as session:
        cnt = (
            await session.execute(select(func.count()).select_from(AdminUser))
        ).scalar_one()
        if int(cnt) == 0:
            s = get_settings()
            session.add(
                AdminUser(
                    username=s.admin_username,
                    password_hash=hash_password(s.admin_password),
                )
            )
        r2 = await session.execute(
            select(ApplicationSettings).where(ApplicationSettings.singleton_key == "global")
        )
        if r2.scalar_one_or_none() is None:
            session.add(ApplicationSettings(singleton_key="global"))
        await session.commit()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="동아리 신청 API", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(student.router)
    app.include_router(admin.router)

    @app.get("/health")
    async def health():
        raw = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
        google_keys = sorted(k for k in os.environ if "GOOGLE" in k.upper())
        return {
            "status": "ok",
            "sheets_auth_code": SHEETS_AUTH_IMPL,
            "google_service_account_json_set": bool(raw),
            "google_env_keys_present": google_keys,
        }

    _mount_frontend_static(app)

    return app


def _mount_frontend_static(app: FastAPI) -> None:
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if not static_dir.is_dir():
        return

    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="vite_assets",
        )

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path in (
            "docs",
            "redoc",
            "openapi.json",
        ):
            raise HTTPException(status_code=404)
        if full_path.startswith("docs/") or full_path.startswith("redoc/"):
            raise HTTPException(status_code=404)
        if ".." in full_path:
            raise HTTPException(status_code=404)

        candidate = (static_dir / full_path).resolve()
        try:
            candidate.relative_to(static_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=404) from None

        if candidate.is_file():
            return FileResponse(candidate)
        index = static_dir / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404)


app = create_app()
