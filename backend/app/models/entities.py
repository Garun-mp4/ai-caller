from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Float, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def utcnow():
    return datetime.now(timezone.utc)

class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_status_next_call_at", "status", "next_call_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    result: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    next_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    calls: Mapped[list["Call"]] = relationship(back_populates="lead", cascade="all, delete-orphan")

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    agent_prompt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compliance_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calls: Mapped[list["Call"]] = relationship(back_populates="campaign")

class CampaignLead(Base):
    __tablename__ = "campaign_leads"
    __table_args__ = (UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_lead"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_status_started_at", "status", "started_at"),
        Index("ix_calls_lead_status", "lead_id", "status"),
        Index("ix_calls_started_at", "started_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(32))
    twilio_call_sid: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="STARTING")
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    stt_ms: Mapped[float] = mapped_column(Float, default=0)
    llm_ms: Mapped[float] = mapped_column(Float, default=0)
    tts_ms: Mapped[float] = mapped_column(Float, default=0)
    total_ms: Mapped[float] = mapped_column(Float, default=0)
    lead: Mapped["Lead"] = relationship(back_populates="calls")
    campaign: Mapped["Campaign | None"] = relationship(back_populates="calls")
    transcripts: Mapped[list["TranscriptMessage"]] = relationship(back_populates="call", cascade="all, delete-orphan", order_by="TranscriptMessage.timestamp")

class TranscriptMessage(Base):
    __tablename__ = "transcript_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    call: Mapped["Call"] = relationship(back_populates="transcripts")

class Callback(Base):
    __tablename__ = "callbacks"
    __table_args__ = (Index("ix_callbacks_status_scheduled_at", "status", "scheduled_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    call_id: Mapped[int | None] = mapped_column(ForeignKey("calls.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), default="SCHEDULED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
