from datetime import datetime, timezone, timedelta
import time
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import Lead, Campaign, Call, TranscriptMessage, Callback
from app.llm.factory import get_llm_provider
from app.agent.prompt import build_sales_prompt
from app.agent.parser import parse_agent_decision
from app.telephony.factory import get_telephony_provider
from app.services.events import emit_hot_lead
from app.core.config import get_settings
from app.services.settings_service import call_preferences

ACTIVE_CALL_STATUSES = ("STARTING", "QUEUED", "INITIATED", "RINGING", "ANSWERED", "IN_PROGRESS")


class CallNotEligibleError(ValueError):
    pass

async def initiate_call(db: Session, lead: Lead, campaign: Campaign | None) -> Call:
    if lead.status == "DO_NOT_CALL":
        raise CallNotEligibleError("Lead is DO_NOT_CALL")
    active_for_lead = db.scalar(
        select(Call.id).where(Call.lead_id == lead.id, Call.status.in_(ACTIVE_CALL_STATUSES)).limit(1)
    )
    if active_for_lead is not None:
        raise CallNotEligibleError("Lead already has an active call")
    active_calls = db.scalar(
        select(func.count()).select_from(Call).where(Call.status.in_(ACTIVE_CALL_STATUSES))
    ) or 0
    if active_calls >= call_preferences(db)["max_concurrent_calls"]:
        raise CallNotEligibleError("Maximum concurrent calls reached")

    started=datetime.now(timezone.utc)
    call=Call(lead_id=lead.id,campaign_id=campaign.id if campaign else None,phone=lead.phone,status="STARTING",started_at=started)
    db.add(call)
    lead.status="CALLING"
    lead.attempts += 1
    lead.last_call_at=started
    # Persist the reservation before any provider I/O so another tick or manual
    # request sees both the active call and the lead's CALLING state.
    db.commit()
    db.refresh(call)
    call_id=call.id
    lead_id=lead.id
    try:
        tel=await get_telephony_provider().create_call(lead.phone,call_id)
        call.twilio_call_sid=tel.get("sid")
        if get_settings().telephony_provider == "mock":
            await _finish_mock_call(db, lead, campaign, call)
        else:
            call.status=(tel.get("status") or "QUEUED").upper().replace("-", "_")
            db.commit(); db.refresh(call)
    except Exception:
        # A failed create/generation must not leave a permanent STARTING call.
        # Do not retry automatically: a remote provider may have accepted a call
        # even if its response was lost.
        db.rollback()
        failed_call=db.get(Call,call_id)
        failed_lead=db.get(Lead,lead_id)
        if failed_call and failed_lead:
            failed_call.status="FAILED"
            failed_call.result="provider_error"
            failed_call.summary="Не удалось подтвердить запуск звонка. Проверьте журнал провайдера."
            failed_call.ended_at=datetime.now(timezone.utc)
            failed_lead.status="FAILED"
            failed_lead.result="Call provider error"
            db.commit()
        raise
    return call

async def _finish_mock_call(db: Session, lead: Lead, campaign: Campaign | None, call: Call) -> None:
    call.status="IN_PROGRESS"; call.answered_at=datetime.now(timezone.utc)
    scenario = "не интересно"
    last=int(''.join(c for c in lead.phone if c.isdigit())[-1])
    if last in (1,6): scenario="Нам интересен редизайн сайта"
    elif last in (2,7): scenario="Перезвоните завтра, пожалуйста"
    elif last in (3,8): scenario="Больше мне не звоните"
    elif last in (4,9): scenario="Да, интересно, нужен новый сайт"
    db.add(TranscriptMessage(call_id=call.id,role="user",content=scenario))
    t=time.perf_counter(); raw=await get_llm_provider().generate(build_sales_prompt(db, campaign.agent_prompt if campaign else ""),[],scenario); llm_ms=(time.perf_counter()-t)*1000
    d=parse_agent_decision(raw); db.add(TranscriptMessage(call_id=call.id,role="assistant",content=d.speech))
    call.llm_ms=llm_ms; call.total_ms=llm_ms; call.status="COMPLETED"; call.ended_at=datetime.now(timezone.utc)
    started_at=call.started_at if call.started_at.tzinfo else call.started_at.replace(tzinfo=timezone.utc)
    call.duration=max(1,int((call.ended_at-started_at).total_seconds()))
    action_summaries={"continue":"Разговор продолжается","end_call":"Разговор завершён","callback":"Нужен обратный звонок","interested":"Клиент проявил интерес","hot_lead":"Клиент готов к следующему шагу","do_not_call":"Клиент попросил больше не звонить"}
    call.result=d.action; call.summary=f"Тестовый звонок. {d.reason or action_summaries.get(d.action, 'Результат сохранён')}. Клиент: {scenario}"
    apply_decision(db, lead, call, d)
    db.commit(); db.refresh(call)

def apply_decision(db: Session, lead: Lead, call: Call, d) -> None:
    if d.action=="do_not_call":
        lead.status="DO_NOT_CALL"; lead.result="Do not call"; lead.next_call_at=None
    elif d.action=="callback":
        when=d.callback_at or datetime.now(timezone.utc)+timedelta(days=1)
        if when.tzinfo is None: when=when.replace(tzinfo=timezone.utc)
        lead.status="CALLBACK"; lead.next_call_at=when; lead.result="Callback requested"
        db.add(Callback(lead_id=lead.id,call_id=call.id,reason=d.reason or "Callback requested",scheduled_at=when))
    elif d.action in ("interested","hot_lead"):
        lead.status="HOT_LEAD" if d.action=="hot_lead" else "INTERESTED"; lead.result=d.action
        if d.action=="hot_lead": emit_hot_lead(db,lead.id,lead.company,lead.phone,call.summary)
    elif d.action=="end_call":
        lead.status="NOT_INTERESTED"; lead.result=d.action
    else:
        lead.status="DONE"; lead.result=d.action

# Backward-compatible alias used by tests/older code.
execute_mock_call = initiate_call
