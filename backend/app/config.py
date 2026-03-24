from functools import lru_cache

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

    google_service_account_json_path: str | None = None
    google_sheets_spreadsheet_id: str | None = None
    google_sheets_students_range: str = "학생정보!A:F"
    google_sheets_clubs_range: str = "동아리정보!A:F"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
