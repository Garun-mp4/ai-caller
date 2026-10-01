from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    status: str | None = None

class CallbackCreate(BaseModel):
    scheduled_at: datetime
    reason: str = "Manual callback"

class LoginRequest(BaseModel):
    username: str
    password: str

class AgentDecision(BaseModel):
    speech: str
    action: str
    stage: str
    callback_at: datetime | None = None
    reason: str | None = None
