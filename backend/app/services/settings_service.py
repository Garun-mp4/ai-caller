from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
        start, end = (part.strip() for part in hours.split("-", 1))
        sh, sm = (int(part) for part in start.split(":"))
        eh, em = (int(part) for part in end.split(":"))
        if not (0 <= sh <= 23 and 0 <= eh <= 23 and 0 <= sm <= 59 and 0 <= em <= 59):
            raise ValueError("Calling hours are out of range")
        if sh * 60 + sm >= eh * 60 + em:
            raise ValueError("Calling hours must end after they start")
    except (ValueError, TypeError):
        start, end = s.calling_hours_start, s.calling_hours_end
    timezone = setting(db, "timezone", s.app_timezone)
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = s.app_timezone
    return {
        "start": start,
        "end": end,
        "timezone": timezone,
        "max_attempts": integer_setting(db, "max_attempts", s.max_attempts, 1, 50),
        "retry_delay_minutes": integer_setting(db, "delay_between_attempts", s.retry_delay_minutes, 1, 10080),
        "max_concurrent_calls": integer_setting(db, "max_concurrent_calls", s.max_concurrent_calls, 1, 25),
    }


def invalidate_runtime_providers(changed_keys: set[str]) -> None:
    """Drop provider singletons after their persisted configuration changes."""
    if changed_keys & {"llm_provider", "llm_model", "reasoning_effort"}:
        from app.llm.factory import get_llm_provider
        get_llm_provider.cache_clear()
    if "vosk_model_path" in changed_keys:
        from app.stt.factory import get_stt_provider
        get_stt_provider.cache_clear()
    if "piper_model_path" in changed_keys:
        from app.tts.factory import get_tts_provider
        get_tts_provider.cache_clear()


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
