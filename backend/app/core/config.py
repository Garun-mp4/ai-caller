from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "AI Call Agent"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./ai_caller.db"

    auth_mode: str = "local"
    local_admin_username: str = "admin"
    local_admin_password: str = "admin"
    openai_oauth_client_id: str = ""
    openai_oauth_client_secret: str = ""
    openai_oauth_redirect_uri: str = "http://localhost:8000/api/auth/chatgpt/callback"

    stt_provider: str = "vosk"
    vosk_model_path: str = "../models/vosk/model"
    tts_provider: str = "piper"
    piper_binary: str = "piper"
    piper_model_path: str = "../models/piper/voice.onnx"
    piper_config_path: str = "../models/piper/voice.onnx.json"

    llm_provider: str = "mock"
    codex_binary: str = "codex"
    codex_model: str = ""
    codex_reasoning_effort: str = "low"
    llm_timeout_seconds: int = 20

    telephony_provider: str = "mock"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    max_concurrent_calls: int = 1
    max_upload_bytes: int = 1024 * 1024
    calling_hours_start: str = "09:00"
    calling_hours_end: str = "18:00"
    app_timezone: str = "Europe/Helsinki"
    max_attempts: int = 3
    retry_delay_minutes: int = 60

    jwt_secret: str = "local-development-secret-change-me"

    model_config = SettingsConfigDict(env_file=str(Path(__file__).resolve().parents[3] / ".env"), env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
