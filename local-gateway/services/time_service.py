from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SYSTEM_TIMEZONE_NAME = "Asia/Shanghai"
SYSTEM_TIMEZONE = ZoneInfo(SYSTEM_TIMEZONE_NAME)


def system_now() -> datetime:
    return datetime.now(SYSTEM_TIMEZONE)


def system_now_iso() -> str:
    return system_now().isoformat()


def system_today_iso() -> str:
    return system_now().date().isoformat()


def parse_system_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        if len(normalized) == 10:
            parsed = datetime.fromisoformat(f"{normalized}T23:59:59")
        else:
            parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SYSTEM_TIMEZONE)
    return parsed.astimezone(SYSTEM_TIMEZONE)


def extract_system_date(value: str | None) -> str | None:
    parsed = parse_system_datetime(value)
    return parsed.date().isoformat() if parsed else None


def is_overdue(value: str | None, reference: datetime | None = None) -> bool:
    parsed = parse_system_datetime(value)
    if not parsed:
        return False
    return parsed < (reference or system_now())


def build_system_time_payload() -> dict:
    now = system_now()
    return {
        "now": now.isoformat(),
        "today": now.date().isoformat(),
        "timezone": SYSTEM_TIMEZONE_NAME,
        "timestamp_ms": int(now.timestamp() * 1000),
    }
