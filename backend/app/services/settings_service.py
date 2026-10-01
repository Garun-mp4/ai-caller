from sqlalchemy.orm import Session
from app.models import AppSetting
from app.core.config import get_settings

def setting(db: Session, key: str, default: str) -> str:
    row = db.get(AppSetting, key)
    return row.value if row is not None else default

def integer_setting(db: Session, key: str, default: int, minimum: int = 0, maximum: int = 100000) -> int:
    try:
        value = int(setting(db, key, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))

def call_preferences(db: Session) -> dict:
    s = get_settings()
    hours = setting(db, "calling_hours", f"{s.calling_hours_start}-{s.calling_hours_end}")
    try:
        start, end = [x.strip() for x in hours.split("-", 1)]
        # validates HH:MM enough for scheduler usage
        sh, sm = map(int, start.split(":")); eh, em = map(int, end.split(":"))
        assert 0 <= sh <= 23 and 0 <= eh <= 23 and 0 <= sm <= 59 and 0 <= em <= 59
    except Exception:
        start, end = s.calling_hours_start, s.calling_hours_end
    return {
        "start": start,
        "end": end,
        "timezone": setting(db, "timezone", s.app_timezone),
        "max_attempts": integer_setting(db, "max_attempts", s.max_attempts, 1, 50),
        "retry_delay_minutes": integer_setting(db, "delay_between_attempts", s.retry_delay_minutes, 1, 10080),
        "max_concurrent_calls": integer_setting(db, "max_concurrent_calls", s.max_concurrent_calls, 1, 25),
    }


def runtime_setting(key: str, default: str) -> str:
    """Read a non-secret setting for provider construction; fall back safely before migrations."""
    try:
        from app.db.session import SessionLocal
        db=SessionLocal()
        try:
            row=db.get(AppSetting,key)
            return row.value if row is not None else default
        finally: db.close()
    except Exception:
        return default
