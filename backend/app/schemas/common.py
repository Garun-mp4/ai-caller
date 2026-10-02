from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_sqlite_datetimes(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class LeadOut(ORMModel):
    id: int
    phone: str
    name: str | None
    company: str | None
    notes: str
    status: str
    result: str | None
    attempts: int
    created_at: datetime
    updated_at: datetime
    next_call_at: datetime | None
    last_call_at: datetime | None

class LeadPageOut(BaseModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int
    page_count: int

class CampaignOut(ORMModel):
    id: int
    name: str
    description: str
    agent_prompt: str
    status: str
    created_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None
    compliance_confirmed_at: datetime | None

class TranscriptOut(ORMModel):
    id: int
    role: str
    content: str
    timestamp: datetime

class CallOut(ORMModel):
    id: int
    lead_id: int
    campaign_id: int | None
    phone: str
    twilio_call_sid: str | None
    started_at: datetime
    answered_at: datetime | None
    ended_at: datetime | None
    duration: int
    status: str
    result: str | None
    summary: str
    stt_ms: float
    llm_ms: float
    tts_ms: float
    total_ms: float
    transcripts: list[TranscriptOut] = []

class CallStatsOut(BaseModel):
    total: int
    answered: int
    average_duration: float
    with_transcript: int

class CallPageOut(BaseModel):
    items: list[CallOut]
    total: int
    page: int
    page_size: int
    page_count: int
    stats: CallStatsOut

class CallbackOut(ORMModel):
    id: int
    lead_id: int
    call_id: int | None
    reason: str
    scheduled_at: datetime
    status: str
    created_at: datetime

class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    agent_prompt: str = ""

class CampaignStart(BaseModel):
    confirm_compliance: bool

class LeadUpdate(BaseModel):
    notes: str | None = None
    status: Literal["NEW", "QUEUED", "CALLBACK", "INTERESTED", "HOT_LEAD", "NO_ANSWER", "BUSY", "NOT_INTERESTED", "DONE", "FAILED", "DO_NOT_CALL"] | None = None

class CallbackCreate(BaseModel):
    scheduled_at: datetime
    reason: str = Field(default="Manual callback", max_length=2000)

    @field_validator("scheduled_at")
    @classmethod
    def callback_must_be_future(cls, value: datetime) -> datetime:
        comparable = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if comparable <= datetime.now(timezone.utc):
            raise ValueError("Callback must be scheduled in the future")
        return value

class CallbackUpdate(BaseModel):
    scheduled_at: datetime | None = None
    status: Literal["SCHEDULED", "COMPLETED", "CANCELED"] | None = None
    reason: str | None = Field(default=None, max_length=2000)

class LoginRequest(BaseModel):
    username: str
    password: str

class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str | None = Field(default=None, min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=300)
    what_we_sell: str | None = Field(default=None, max_length=2000)
    introduction: str | None = Field(default=None, max_length=4000)
    offer: str | None = Field(default=None, max_length=4000)
    allowed_claims: str | None = Field(default=None, max_length=4000)
    forbidden_claims: str | None = Field(default=None, max_length=4000)
    call_objective: str | None = Field(default=None, max_length=4000)
    max_response_length: int | None = Field(default=None, ge=1, le=8)
    calling_hours: str | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    max_attempts: int | None = Field(default=None, ge=1, le=50)
    delay_between_attempts: int | None = Field(default=None, ge=1, le=10080)
    max_concurrent_calls: int | None = Field(default=None, ge=1, le=25)
    vosk_model_path: str | None = Field(default=None, max_length=1024)
    piper_model_path: str | None = Field(default=None, max_length=1024)
    llm_provider: Literal["mock", "codex"] | None = None
    llm_model: str | None = Field(default=None, max_length=200)
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] | None = None

    @field_validator("max_response_length", "max_attempts", "delay_between_attempts", "max_concurrent_calls", mode="before")
    @classmethod
    def parse_integer_setting(cls, value):
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("Expected an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdecimal():
            return int(value.strip())
        raise ValueError("Expected an integer")

    @field_validator("calling_hours")
    @classmethod
    def validate_calling_hours(cls, value: str | None) -> str | None:
        if value is None:
            return value
        import re
        match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)", value.strip())
        if not match:
            raise ValueError("Use the HH:MM-HH:MM format")
        start = int(match.group(1)) * 60 + int(match.group(2))
        end = int(match.group(3)) * 60 + int(match.group(4))
        if start >= end:
            raise ValueError("The end of the calling window must be after its start")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Use a valid IANA time zone") from error
        return value

class AgentDecision(BaseModel):
    speech: str
    action: str
    stage: str
    callback_at: datetime | None = None
    reason: str | None = None
