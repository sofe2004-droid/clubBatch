from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg_async://clubapp:clubapp@localhost:5432/clubapp"
    jwt_secret_student: str = "dev-student-secret"
    jwt_secret_admin: str = "dev-admin-secret"
    jwt_algorithm: str = "HS256"
    student_token_expire_minutes: int = 120
    admin_token_expire_minutes: int = 480

    admin_username: str = "admin"
    admin_password: str = "changeme"

    teacher_view_username: str = "teacher"
    teacher_view_password: str = "club2026"

    google_service_account_json_path: str | None = None  # 로컬 JSON 파일
    google_service_account_json: str | None = None  # Railway 등: 키 JSON 전체 문자열(우선)
    google_sheets_spreadsheet_id: str | None = None
    google_sheets_students_range: str = "학생정보!A:F"
    google_sheets_clubs_range: str = "동아리정보!A:F"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> object:
        """Railway 등에서 주는 postgres:// / postgresql:// 를 async 드라이버 URL로 맞춤."""
        if not isinstance(v, str):
            return v
        u = v.strip()
        if u.startswith("postgres://"):
            u = "postgresql://" + u[len("postgres://") :]
        scheme = u.split("://", 1)[0] if "://" in u else ""
        if scheme == "postgresql":
            return "postgresql+psycopg_async://" + u[len("postgresql://") :]
        return u


@lru_cache
def get_settings() -> Settings:
    return Settings()
