"""서비스 계정: 로컬은 JSON 파일, 클라우드는 env 본문(GOOGLE_SERVICE_ACCOUNT_JSON) 권장."""

from __future__ import annotations

import json
import os

from google.oauth2 import service_account

from app.config import get_settings


SHEETS_AUTH_IMPL = 3
"""배포가 최신 google_creds인지 /health 등에서 확인용 (올리면 숫자만 증가)."""


def load_service_account_credentials(
    scopes: list[str],
) -> tuple[service_account.Credentials | None, str | None]:
    """
    1) GOOGLE_SERVICE_ACCOUNT_JSON: 키 파일 전체 JSON 문자열 (환경 변수 직접 읽기 → Settings 순)
    2) GOOGLE_SERVICE_ACCOUNT_JSON_PATH: 파일 경로
    """
    s = get_settings()
    # Railway: pydantic/멀티라인 이슈를 피하려면 OS env를 우선
    raw = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
    if not raw:
        raw = (s.google_service_account_json or "").strip()
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            return None, "GOOGLE_SERVICE_ACCOUNT_JSON이 올바른 JSON이 아닙니다."
        if not isinstance(info, dict):
            return None, "GOOGLE_SERVICE_ACCOUNT_JSON은 JSON 객체여야 합니다."
        return service_account.Credentials.from_service_account_info(info, scopes=scopes), None

    path = (s.google_service_account_json_path or "").strip()
    if not path:
        path = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH") or "").strip()
    if path and os.path.isfile(path):
        return (
            service_account.Credentials.from_service_account_file(path, scopes=scopes),
            None,
        )

    return (
        None,
        "Google 서비스 계정 키가 없습니다. Railway에서는 GOOGLE_SERVICE_ACCOUNT_JSON에 "
        "JSON 본문을 넣거나, Secret File 경로를 GOOGLE_SERVICE_ACCOUNT_JSON_PATH에 지정하세요.",
    )
