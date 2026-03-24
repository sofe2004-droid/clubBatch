"""시트·입력값 정규화 (숫자 셀, 전각/유니코드, 공백)."""

import math
import unicodedata


def normalize_person_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", (s or "").strip())
    return " ".join(s.split())


def normalize_student_number_input(s: str) -> str:
    t = unicodedata.normalize("NFKC", (s or "").strip())
    t = "".join(t.split())
    if not t:
        return t
    try:
        if "." in t or "e" in t.lower() or "E" in t:
            f = float(t)
            if math.isfinite(f) and abs(f - round(f)) < 1e-9:
                return str(int(round(f)))
        if t.lstrip("-").isdigit():
            return str(int(t))
    except ValueError:
        pass
    return t


def normalize_club_code(s: str) -> str:
    """동아리코드: 숫자/숫자.0 형태는 정수 문자열로, C001 등은 NFKC만."""
    t = unicodedata.normalize("NFKC", (s or "").strip())
    if not t:
        return t
    try:
        if "." in t or "e" in t.lower():
            f = float(t)
            if math.isfinite(f) and abs(f - round(f)) < 1e-9:
                return str(int(round(f)))
        if t.isdigit():
            return str(int(t))
    except ValueError:
        pass
    return t


def cell_to_str(v: object) -> str | None:
    """Google Sheets API는 숫자 셀을 int/float로 줄 수 있음 → DB에는 깨끗한 문자열로."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            return None
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        s = str(v).rstrip("0").rstrip(".")
        return s if s else None
    s = unicodedata.normalize("NFKC", str(v)).strip()
    return s if s else None
