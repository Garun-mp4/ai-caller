from datetime import datetime, timezone, timedelta
import logging
import shutil
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, WebSocket, Form, Query
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, or_, text, update, literal, case
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_settings
from app.core.security import create_token, require_user
from app.core.chatgpt_auth import begin_chatgpt_login, finish_chatgpt_login
from app.db.session import get_db, SessionLocal
from app.models import Lead, Campaign, CampaignLead, Call, TranscriptMessage, Callback, AppSetting
from app.schemas.common import *
from app.crm.importer import import_txt
from app.scheduler.call_scheduler import scheduler
from app.llm.factory import get_llm_provider
from app.telephony.factory import get_telephony_provider
from app.stt.factory import get_stt_provider
from app.tts.factory import get_tts_provider
from app.services.call_service import initiate_call, apply_decision, CallNotEligibleError
from app.agent.prompt import build_sales_prompt, configured_introduction
from app.services.settings_service import call_preferences, runtime_setting, invalidate_runtime_providers
from app.telephony.media_stream import handle_twilio_media
from app.telephony.request_validation import validate_twilio_request, validate_twilio_websocket

router=APIRouter(prefix="/api")
log=logging.getLogger(__name__)
S=get_settings()

@router.get("/health")
def health(): return {"ok":True,"app":S.app_name,"env":S.app_env}

@router.get("/health/ready")
def readiness(db:Session=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503,detail="Database is not ready")
    return {"ok":True,"database":"ready"}

@router.post("/auth/login")
def login(req: LoginRequest):
    if S.auth_mode!="local": raise HTTPException(400,"Local login disabled")
    if req.username!=S.local_admin_username or req.password!=S.local_admin_password: raise HTTPException(401,"Invalid credentials")
    return {"access_token":create_token(req.username),"token_type":"bearer","user":req.username}

@router.get("/auth/config")
def auth_config():
    return {"mode":S.auth_mode,"chatgpt_oauth_available":bool(S.openai_oauth_client_id),"note":"Site auth and Codex CLI auth are separate."}

@router.get("/auth/chatgpt/start")
def chatgpt_start():
    if S.auth_mode != "chatgpt":
        raise HTTPException(400, "AUTH_MODE is not chatgpt")
    return RedirectResponse(begin_chatgpt_login(), status_code=302)

@router.get("/auth/chatgpt/callback")
async def chatgpt_callback(code: str, state: str):
    if S.auth_mode != "chatgpt":
        raise HTTPException(400, "AUTH_MODE is not chatgpt")
    identity = await finish_chatgpt_login(code, state)
    app_token = create_token("chatgpt:" + identity["sub"])
    target = S.frontend_url.rstrip("/") + "/login?" + __import__("urllib.parse", fromlist=["urlencode"]).urlencode({"token": app_token, "user": identity["name"]})
    return RedirectResponse(target, status_code=302)

@router.get("/dashboard", dependencies=[Depends(require_user)])
def dashboard(db: Session=Depends(get_db)):
    pref=call_preferences(db)
    local_now=datetime.now(ZoneInfo(pref["timezone"]))
    local_start=local_now.replace(hour=0,minute=0,second=0,microsecond=0)
    day_start=local_start.astimezone(timezone.utc)
    day_end=(local_start+timedelta(days=1)).astimezone(timezone.utc)
    leads=db.scalar(select(func.count()).select_from(Lead)) or 0
    calls=db.scalars(select(Call).options(selectinload(Call.transcripts)).order_by(Call.id.desc()).limit(6)).all()
    callbacks=db.scalars(select(Callback).where(Callback.status.in_(["SCHEDULED","DUE"])).order_by(Callback.scheduled_at).limit(6)).all()
    statuses=dict(db.execute(select(Lead.status,func.count()).group_by(Lead.status)).all())
    calls_today=db.scalar(select(func.count()).select_from(Call).where(Call.started_at>=day_start,Call.started_at<day_end)) or 0
    return {"stats":{"total_leads":leads,"calls_today":calls_today,"answered":db.scalar(select(func.count()).select_from(Call).where(Call.answered_at.is_not(None))) or 0,"interested":statuses.get("INTERESTED",0),"hot_leads":statuses.get("HOT_LEAD",0),"callbacks":statuses.get("CALLBACK",0),"no_answer":statuses.get("NO_ANSWER",0)},"recent_calls":[CallOut.model_validate(c) for c in calls],"callbacks":[CallbackOut.model_validate(c) for c in callbacks]}

@router.post("/leads/import", dependencies=[Depends(require_user)])
async def import_leads(file: UploadFile=File(...), db: Session=Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith('.txt'): raise HTTPException(400,"Only TXT files are allowed")
    data=await file.read(S.max_upload_bytes+1)
    if len(data)>S.max_upload_bytes: raise HTTPException(413,"TXT file is too large")
    try: text=data.decode('utf-8-sig')
    except UnicodeDecodeError:
        try: text=data.decode('cp1251')
        except UnicodeDecodeError: raise HTTPException(400,"File must be UTF-8 or CP1251 text")
    return import_txt(db,text)

@router.get("/leads", response_model=LeadPageOut, dependencies=[Depends(require_user)])
def leads(
    status: str|None=None,
    campaign: int|None=None,
    search: str|None=Query(default=None,max_length=120),
    page: int=Query(default=1,ge=1),
    page_size: int=Query(default=25,ge=1,le=100),
    sort_by: Literal["id","name","company","phone","status","attempts","next_call_at","last_call_at","created_at"]="id",
    sort_order: Literal["asc","desc"]="desc",
    db: Session=Depends(get_db),
):
    filters=[]
    if status: filters.append(Lead.status==status)
    if campaign:
        campaign_membership=select(CampaignLead.id).where(CampaignLead.campaign_id==campaign,CampaignLead.lead_id==Lead.id).exists()
        filters.append(campaign_membership)
    query=(search or "").strip()
    if query:
        if S.database_url.startswith("sqlite"):
            normalized=query.casefold()
            filters.append(or_(func.app_casefold(Lead.phone).contains(normalized,autoescape=True),func.app_casefold(Lead.company).contains(normalized,autoescape=True),func.app_casefold(Lead.name).contains(normalized,autoescape=True)))
        else:
            escaped=query.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
            pattern=f"%{escaped}%"
            filters.append(or_(Lead.phone.ilike(pattern,escape="\\"),Lead.company.ilike(pattern,escape="\\"),Lead.name.ilike(pattern,escape="\\")))
    total=db.scalar(select(func.count()).select_from(Lead).where(*filters)) or 0
    sort_column=getattr(Lead,sort_by)
    ordering=sort_column.asc().nulls_last() if sort_order=="asc" else sort_column.desc().nulls_last()
    statement=select(Lead).where(*filters).order_by(ordering)
    if sort_by!="id": statement=statement.order_by(Lead.id.desc())
    items=db.scalars(statement.offset((page-1)*page_size).limit(page_size)).all()
    page_count=max(1,(total+page_size-1)//page_size)
    return {"items":items,"total":total,"page":page,"page_size":page_size,"page_count":page_count}

@router.get("/leads/{lead_id}", dependencies=[Depends(require_user)])
def lead_details(lead_id:int,db: Session=Depends(get_db)):
    lead=db.get(Lead,lead_id)
    if not lead: raise HTTPException(404,"Lead not found")
    calls=db.scalars(select(Call).where(Call.lead_id==lead_id).options(selectinload(Call.transcripts)).order_by(Call.id.desc())).all()
    callbacks=db.scalars(select(Callback).where(Callback.lead_id==lead_id).order_by(Callback.scheduled_at.desc())).all()
    return {"lead":LeadOut.model_validate(lead),"calls":[CallOut.model_validate(c) for c in calls],"callbacks":[CallbackOut.model_validate(c) for c in callbacks]}

@router.patch("/leads/{lead_id}", response_model=LeadOut, dependencies=[Depends(require_user)])
def update_lead(lead_id:int,req:LeadUpdate,db:Session=Depends(get_db)):
    lead=db.get(Lead,lead_id)
    if not lead: raise HTTPException(404,"Lead not found")
    if req.notes is not None: lead.notes=req.notes
    if req.status is not None:
        lead.status=req.status
        if req.status=="DO_NOT_CALL":
            lead.next_call_at=None
            for callback in db.scalars(select(Callback).where(Callback.lead_id==lead_id,Callback.status.in_(["SCHEDULED","DUE"]))).all():
                callback.status="CANCELED"
    db.commit(); db.refresh(lead); return lead

@router.post("/leads/{lead_id}/callback", response_model=CallbackOut, dependencies=[Depends(require_user)])
def schedule_callback(lead_id:int,req:CallbackCreate,db:Session=Depends(get_db)):
    lead=db.get(Lead,lead_id)
    if not lead: raise HTTPException(404,"Lead not found")
    if lead.status=="DO_NOT_CALL": raise HTTPException(409,"Lead is DO_NOT_CALL")
    cb=Callback(lead_id=lead_id,reason=req.reason,scheduled_at=req.scheduled_at,status="SCHEDULED"); db.add(cb); lead.status="CALLBACK"; lead.next_call_at=req.scheduled_at; db.commit(); db.refresh(cb); return cb

@router.post("/leads/{lead_id}/call-now", response_model=CallOut, dependencies=[Depends(require_user)])
async def call_now(lead_id:int,db:Session=Depends(get_db)):
    lead=db.get(Lead,lead_id)
    if not lead: raise HTTPException(404,"Lead not found")
    try:
        c=await initiate_call(db,lead,None)
    except CallNotEligibleError as error:
        raise HTTPException(409,str(error)) from error
    db.refresh(c); return c

@router.get("/campaigns", dependencies=[Depends(require_user)])
def campaigns(db:Session=Depends(get_db)):
    campaign_rows=db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()
    status_rows=db.execute(select(CampaignLead.campaign_id,Lead.status,func.count()).join(Lead,Lead.id==CampaignLead.lead_id).group_by(CampaignLead.campaign_id,Lead.status)).all()
    answered_rows=db.execute(select(Call.campaign_id,func.count()).where(Call.campaign_id.is_not(None),Call.answered_at.is_not(None)).group_by(Call.campaign_id)).all()
    stats_by_campaign={}
    for campaign_id,status,count in status_rows:
        stats_by_campaign.setdefault(campaign_id,{})[status]=count
    answered_by_campaign=dict(answered_rows)
    out=[]
    for campaign in campaign_rows:
        stats=stats_by_campaign.get(campaign.id,{})
        total=sum(stats.values())
        out.append({**CampaignOut.model_validate(campaign).model_dump(),"metrics":{"total":total,"queued":stats.get("QUEUED",0)+stats.get("NEW",0),"calling":stats.get("CALLING",0),"answered":answered_by_campaign.get(campaign.id,0),"no_answer":stats.get("NO_ANSWER",0),"interested":stats.get("INTERESTED",0),"hot_leads":stats.get("HOT_LEAD",0),"callbacks":stats.get("CALLBACK",0)}})
    return out

@router.post("/campaigns", response_model=CampaignOut, dependencies=[Depends(require_user)])
def create_campaign(req:CampaignCreate,db:Session=Depends(get_db)):
    c=Campaign(**req.model_dump()); db.add(c); db.commit(); db.refresh(c); return c

@router.post("/campaigns/{campaign_id}/attach-all", dependencies=[Depends(require_user)])
def attach_all(campaign_id:int,db:Session=Depends(get_db)):
    if not db.get(Campaign,campaign_id): raise HTTPException(404,"Campaign not found")
    existing=select(CampaignLead.id).where(CampaignLead.campaign_id==campaign_id,CampaignLead.lead_id==Lead.id).exists()
    source=select(literal(campaign_id),Lead.id).where(Lead.status.in_(["NEW","QUEUED","CALLBACK"]),~existing)
    result=db.execute(sqlite_insert(CampaignLead).from_select(["campaign_id","lead_id"],source).on_conflict_do_nothing(index_elements=["campaign_id","lead_id"]))
    db.execute(update(Lead).where(Lead.status=="NEW",Lead.id.in_(select(CampaignLead.lead_id).where(CampaignLead.campaign_id==campaign_id))).values(status="QUEUED"))
    added=max(result.rowcount or 0,0)
    db.commit(); return {"attached":added}

@router.get("/campaigns/{campaign_id}/audience", dependencies=[Depends(require_user)])
def campaign_audience(campaign_id:int,db:Session=Depends(get_db)):
    if not db.get(Campaign,campaign_id): raise HTTPException(404,"Campaign not found")
    existing=select(CampaignLead.id).where(CampaignLead.campaign_id==campaign_id,CampaignLead.lead_id==Lead.id).exists()
    by_status=dict(db.execute(select(Lead.status,func.count()).where(Lead.status.in_(["NEW","QUEUED","CALLBACK"]),~existing).group_by(Lead.status)).all())
    attached=db.scalar(select(func.count()).select_from(CampaignLead).where(CampaignLead.campaign_id==campaign_id)) or 0
    attached_eligible=db.scalar(select(func.count()).select_from(CampaignLead).join(Lead,Lead.id==CampaignLead.lead_id).where(CampaignLead.campaign_id==campaign_id,Lead.status.in_(["NEW","QUEUED","CALLBACK"]))) or 0
    return {"to_attach":sum(by_status.values()),"already_attached":attached,"attached_eligible":attached_eligible,"by_status":by_status}

@router.post("/campaigns/{campaign_id}/start", response_model=CampaignOut, dependencies=[Depends(require_user)])
def start_campaign(campaign_id:int,req:CampaignStart,db:Session=Depends(get_db)):
    c=db.get(Campaign,campaign_id)
    if not c: raise HTTPException(404,"Campaign not found")
    if not req.confirm_compliance: raise HTTPException(400,"Compliance confirmation is required")
    c.status="RUNNING"; c.started_at=datetime.now(timezone.utc); c.compliance_confirmed_at=datetime.now(timezone.utc); c.stopped_at=None; db.commit(); db.refresh(c); return c

@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignOut, dependencies=[Depends(require_user)])
def pause_campaign(campaign_id:int,db:Session=Depends(get_db)):
    c=db.get(Campaign,campaign_id)
    if not c: raise HTTPException(404,"Campaign not found")
    c.status="PAUSED"; db.commit(); db.refresh(c); return c

@router.post("/campaigns/{campaign_id}/stop", response_model=CampaignOut, dependencies=[Depends(require_user)])
def stop_campaign(campaign_id:int,db:Session=Depends(get_db)):
    c=db.get(Campaign,campaign_id)
    if not c: raise HTTPException(404,"Campaign not found")
    c.status="STOPPED"; c.stopped_at=datetime.now(timezone.utc); db.commit(); db.refresh(c); return c

@router.post("/scheduler/tick", dependencies=[Depends(require_user)])
async def scheduler_tick():
    if S.app_env.casefold() in {"production", "prod"}:
        raise HTTPException(status_code=403, detail="Manual scheduler tick is available only in development")
    return {"processed":await scheduler.tick(ignore_hours=True)}

@router.get("/calls", response_model=CallPageOut, dependencies=[Depends(require_user)])
def calls(
    search: str|None=Query(default=None,max_length=120),
    status: Literal["ANSWERED","NO_ANSWER","BUSY","FAILED","IN_PROGRESS"]|None=None,
    page: int=Query(default=1,ge=1),
    page_size: int=Query(default=25,ge=1,le=100),
    db:Session=Depends(get_db),
):
    filters=[]
    answered_call=or_(Call.answered_at.is_not(None),Call.status=="ANSWERED")
    if status=="ANSWERED":
        filters.append(answered_call)
    elif status in ("NO_ANSWER","BUSY"):
        filters.append(or_(func.upper(Call.status)==status,func.upper(Call.result)==status))
    elif status=="FAILED":
        filters.append(or_(func.upper(Call.status).in_(["FAILED","PROVIDER_ERROR"]),func.upper(Call.result).in_(["FAILED","PROVIDER_ERROR"])))
    elif status=="IN_PROGRESS":
        filters.append(Call.status.in_(["STARTING","QUEUED","INITIATED","RINGING","ANSWERED","IN_PROGRESS"]))

    query=(search or "").strip()
    if query:
        escaped=query.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
        filters.append(Call.phone.ilike(f"%{escaped}%",escape="\\"))

    total=db.scalar(select(func.count()).select_from(Call).where(*filters)) or 0
    rows=db.scalars(
        select(Call)
        .where(*filters)
        .options(selectinload(Call.transcripts))
        .order_by(Call.started_at.desc(),Call.id.desc())
        .offset((page-1)*page_size)
        .limit(page_size)
    ).all()
    page_count=max(1,(total+page_size-1)//page_size)
    stats={
        "total":db.scalar(select(func.count()).select_from(Call)) or 0,
        "answered":db.scalar(select(func.count()).select_from(Call).where(answered_call)) or 0,
        "average_duration":db.scalar(select(func.avg(Call.duration))) or 0,
        "with_transcript":db.scalar(select(func.count(func.distinct(TranscriptMessage.call_id)))) or 0,
    }
    return {"items":rows,"total":total,"page":page,"page_size":page_size,"page_count":page_count,"stats":stats}

@router.get("/callbacks", response_model=CallbackPageOut, dependencies=[Depends(require_user)])
def callbacks(
    status: Literal["ACTIVE","COMPLETED","CANCELED"]|None=None,
    search: str|None=Query(default=None,max_length=120),
    page: int=Query(default=1,ge=1),
    page_size: int=Query(default=25,ge=1,le=100),
    db:Session=Depends(get_db),
):
    active_statuses=["SCHEDULED","DUE"]
    filters=[]
    if status=="ACTIVE":
        filters.append(Callback.status.in_(active_statuses))
    elif status:
        filters.append(Callback.status==status)

    query=(search or "").strip()
    if query:
        if S.database_url.startswith("sqlite"):
            normalized=query.casefold()
            filters.append(or_(
                func.app_casefold(Callback.reason).contains(normalized,autoescape=True),
                func.app_casefold(Lead.phone).contains(normalized,autoescape=True),
                func.app_casefold(Lead.company).contains(normalized,autoescape=True),
                func.app_casefold(Lead.name).contains(normalized,autoescape=True),
            ))
        else:
            escaped=query.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
            pattern=f"%{escaped}%"
            filters.append(or_(
                Callback.reason.ilike(pattern,escape="\\"),
                Lead.phone.ilike(pattern,escape="\\"),
                Lead.company.ilike(pattern,escape="\\"),
                Lead.name.ilike(pattern,escape="\\"),
            ))

    total=db.scalar(select(func.count()).select_from(Callback).join(Lead,Lead.id==Callback.lead_id).where(*filters)) or 0
    active=Callback.status.in_(active_statuses)
    ordered=(
        select(Callback,Lead.phone,Lead.company)
        .join(Lead,Lead.id==Callback.lead_id)
        .where(*filters)
        .order_by(
            case((active,0),else_=1),
            case((active,Callback.scheduled_at),else_=None).asc().nulls_last(),
            case((Callback.status.in_(["COMPLETED","CANCELED"]),Callback.created_at),else_=None).desc().nulls_last(),
            Callback.id.desc(),
        )
        .offset((page-1)*page_size)
        .limit(page_size)
    )
    rows=db.execute(ordered).all()
    page_count=max(1,(total+page_size-1)//page_size)

    now_utc=datetime.now(timezone.utc)
    local_now=now_utc.astimezone(ZoneInfo(call_preferences(db)["timezone"]))
    local_start=local_now.replace(hour=0,minute=0,second=0,microsecond=0)
    day_start_utc=local_start.astimezone(timezone.utc)
    day_end_utc=(local_start+timedelta(days=1)).astimezone(timezone.utc)
    active_count=db.scalar(select(func.count()).select_from(Callback).where(active)) or 0
    overdue_count=db.scalar(select(func.count()).select_from(Callback).where(
        active,
        or_(Callback.status=="DUE",Callback.scheduled_at<=now_utc),
    )) or 0
    today_count=db.scalar(select(func.count()).select_from(Callback).where(
        Callback.status=="SCHEDULED",
        Callback.scheduled_at>now_utc,
        Callback.scheduled_at>=day_start_utc,
        Callback.scheduled_at<day_end_utc,
    )) or 0
    completed_count=db.scalar(select(func.count()).select_from(Callback).where(Callback.status=="COMPLETED")) or 0
    items=[{**CallbackOut.model_validate(callback).model_dump(),"phone":phone,"company":company} for callback,phone,company in rows]
    return {
        "items":items,
        "total":total,
        "page":page,
        "page_size":page_size,
        "page_count":page_count,
        "stats":{
            "total":db.scalar(select(func.count()).select_from(Callback)) or 0,
            "active":active_count,
            "overdue":overdue_count,
            "today":today_count,
            "upcoming":max(0,active_count-overdue_count-today_count),
            "completed":completed_count,
        },
    }

@router.patch("/callbacks/{callback_id}", response_model=CallbackOut, dependencies=[Depends(require_user)])
def update_callback(callback_id:int,req:CallbackUpdate,db:Session=Depends(get_db)):
    callback=db.get(Callback,callback_id)
    if not callback: raise HTTPException(404,"Callback not found")
    lead=db.get(Lead,callback.lead_id)
    if not lead: raise HTTPException(404,"Lead not found")
    target_status=req.status or callback.status
    scheduled_at=req.scheduled_at
    if scheduled_at is not None and scheduled_at.tzinfo is None:
        scheduled_at=scheduled_at.replace(tzinfo=timezone.utc)
    if callback.status in ("COMPLETED","CANCELED") and (req.scheduled_at is not None or req.reason is not None or req.status not in (None,callback.status)):
        raise HTTPException(409,"Callback is already closed")
    if target_status in ("SCHEDULED","DUE"):
        if lead.status=="DO_NOT_CALL": raise HTTPException(409,"Lead is DO_NOT_CALL")
        target_time=scheduled_at or callback.scheduled_at
        if target_time.tzinfo is None: target_time=target_time.replace(tzinfo=timezone.utc)
        if target_time<=datetime.now(timezone.utc): raise HTTPException(422,"Callback must be scheduled in the future")
        callback.scheduled_at=target_time
        if scheduled_at is not None: callback.status="SCHEDULED"
    elif scheduled_at is not None:
        raise HTTPException(422,"Only scheduled callbacks can be rescheduled")
    if req.reason is not None: callback.reason=req.reason.strip()
    if req.status is not None: callback.status=req.status
    if callback.status in ("COMPLETED","CANCELED"):
        active=db.scalars(select(Callback).where(Callback.lead_id==lead.id,Callback.id!=callback.id,Callback.status.in_(["SCHEDULED","DUE"])).order_by(Callback.scheduled_at)).all()
        if active and lead.status!="DO_NOT_CALL":
            lead.status="CALLBACK"; lead.next_call_at=active[0].scheduled_at
        else:
            lead.next_call_at=None
            if lead.status=="CALLBACK": lead.status="DONE" if callback.status=="COMPLETED" else "NEW"
    db.commit(); db.refresh(callback); return callback

@router.get("/settings", dependencies=[Depends(require_user)])
def settings(db:Session=Depends(get_db)):
    llm_provider=runtime_setting("llm_provider",S.llm_provider)
    llm_model=runtime_setting("llm_model",S.codex_model)
    reasoning_effort=runtime_setting("reasoning_effort",S.codex_reasoning_effort)
    vosk_model_path=runtime_setting("vosk_model_path",S.vosk_model_path)
    piper_model_path=runtime_setting("piper_model_path",S.piper_model_path)
    preferences=call_preferences(db)
    defaults={"agent_name":"Алекс","company_name":"Веб-студия","what_we_sell":"Разработка сайтов, редизайн и автоматизация для бизнеса","introduction":"Добрый день! Можно задать короткий вопрос о вашем сайте?","offer":"Разработка и улучшение сайтов для бизнеса","allowed_claims":"Мы разрабатываем сайты и автоматизируем процессы.","forbidden_claims":"Не придумывать цены, кейсы, гарантии и сроки.","call_objective":"Понять интерес и договориться о следующем шаге.","max_response_length":"3","calling_hours":f"{preferences['start']}-{preferences['end']}","timezone":preferences['timezone'],"max_attempts":str(preferences['max_attempts']),"delay_between_attempts":str(preferences['retry_delay_minutes']),"max_concurrent_calls":str(preferences['max_concurrent_calls']),"vosk_model_path":vosk_model_path,"piper_model_path":piper_model_path,"llm_provider":llm_provider,"llm_model":llm_model,"reasoning_effort":reasoning_effort}
    allowed=set(SettingsUpdate.model_fields)
    stored={x.key:x.value for x in db.scalars(select(AppSetting).where(AppSetting.key.in_(allowed))).all()}; defaults.update(stored)
    defaults.update({"calling_hours":f"{preferences['start']}-{preferences['end']}","timezone":preferences['timezone'],"max_attempts":str(preferences['max_attempts']),"delay_between_attempts":str(preferences['retry_delay_minutes']),"max_concurrent_calls":str(preferences['max_concurrent_calls'])})
    return {"values":defaults,"providers":{"auth_mode":S.auth_mode,"llm_provider":llm_provider,"telephony_provider":S.telephony_provider,"stt_provider":S.stt_provider,"tts_provider":S.tts_provider,"vosk_model_path":vosk_model_path,"piper_model_path":piper_model_path,"codex_model":llm_model,"reasoning_effort":reasoning_effort}}

@router.put("/settings", dependencies=[Depends(require_user)])
def save_settings(values:SettingsUpdate,db:Session=Depends(get_db)):
    updates=values.model_dump(exclude_unset=True,exclude_none=True)
    for k,v in updates.items():
        row=db.get(AppSetting,k)
        if not row: row=AppSetting(key=k,value=str(v)); db.add(row)
        else: row.value=str(v)
    db.commit()
    invalidate_runtime_providers(set(updates))
    return {"ok":True}

@router.get("/providers/health", dependencies=[Depends(require_user)])
async def providers_health():
    llm=await get_llm_provider().health(); tel=await get_telephony_provider().health(); tts=await get_tts_provider().health(); stt=get_stt_provider().health()
    return {"llm":llm,"telephony":tel,"tts":tts,"stt":stt,"codex_on_path":bool(shutil.which(S.codex_binary))}

@router.post("/telephony/twiml/{call_id}", response_class=Response, dependencies=[Depends(validate_twilio_request)])
def twiml(call_id:int):
    ws=S.public_base_url.replace("https://","wss://").replace("http://","ws://").rstrip('/')
    xml=f"<?xml version='1.0' encoding='UTF-8'?><Response><Connect><Stream url='{ws}/api/telephony/media/{call_id}' /></Connect></Response>"
    return Response(content=xml,media_type="application/xml")

@router.post("/telephony/status/{call_id}", dependencies=[Depends(validate_twilio_request)])
def twilio_status(call_id:int, CallStatus:str=Form(default=""), CallSid:str=Form(default=""), db:Session=Depends(get_db)):
    c=db.get(Call,call_id)
    if c:
        terminal_statuses={"COMPLETED","FAILED","BUSY","NO_ANSWER","CANCELED"}
        was_finalized=c.ended_at is not None and c.status in terminal_statuses and c.result!="provider_error"
        c.twilio_call_sid=CallSid or c.twilio_call_sid
        # Twilio may retry terminal webhook deliveries. Once a callback has
        # finalized this call, later deliveries must not create another retry.
        if was_finalized:
            db.commit()
            return Response(status_code=204)
        status=(CallStatus or "").lower()
        c.status=status.upper().replace("-","_") or c.status
        lead=db.get(Lead,c.lead_id)
        if status in ("answered","in-progress") and not c.answered_at: c.answered_at=datetime.now(timezone.utc)
        if status in ("completed","failed","busy","no-answer","canceled"):
            c.ended_at=datetime.now(timezone.utc)
            if c.started_at:
                started=c.started_at if c.started_at.tzinfo else c.started_at.replace(tzinfo=timezone.utc)
                c.duration=max(0,int((c.ended_at-started).total_seconds()))
            c.result=status.upper().replace("-","_") if c.result=="provider_error" else (c.result or status.upper().replace("-","_"))
            if lead and lead.status != "DO_NOT_CALL":
                pref=call_preferences(db)
                if status=="no-answer": lead.status="NO_ANSWER"; lead.result="No answer"
                elif status=="busy": lead.status="BUSY"; lead.result="Busy"
                elif status in ("failed","canceled"): lead.status="FAILED"; lead.result=status
                elif status=="completed": lead.status="DONE"; lead.result=lead.result or "completed"
                if status in ("no-answer","busy","failed"):
                    from datetime import timedelta
                    active_callback=db.scalars(select(Callback).where(Callback.lead_id==lead.id,Callback.status.in_(["SCHEDULED","DUE"])).order_by(Callback.scheduled_at).limit(1)).first()
                    if active_callback:
                        lead.status="CALLBACK"
                        lead.next_call_at=active_callback.scheduled_at
                    elif lead.attempts < pref["max_attempts"]:
                        lead.status="CALLBACK"; lead.next_call_at=datetime.now(timezone.utc)+timedelta(minutes=pref["retry_delay_minutes"])
                        db.add(Callback(lead_id=lead.id,call_id=c.id,reason=f"Automatic retry after {status}",scheduled_at=lead.next_call_at))
        db.commit()
    return Response(status_code=204)

@router.websocket("/telephony/media/{call_id}")
async def media(websocket:WebSocket,call_id:int):
    if not validate_twilio_websocket(websocket):
        await websocket.close(code=1008,reason="Invalid Twilio request signature")
        return
    setup_db=SessionLocal()
    try:
        c=setup_db.get(Call,call_id)
        campaign=setup_db.get(Campaign,c.campaign_id) if c and c.campaign_id else None
        system_prompt=build_sales_prompt(setup_db,campaign.agent_prompt if campaign else "")
        initial_speech=configured_introduction(setup_db)
        if c and not c.answered_at: c.answered_at=datetime.now(timezone.utc); c.status="IN_PROGRESS"; setup_db.commit()
    finally: setup_db.close()
    async def on_turn(text,decision,stt_ms,llm_ms):
        db=SessionLocal()
        try:
            c=db.get(Call,call_id)
            if c:
                db.add(TranscriptMessage(call_id=call_id,role="user",content=text)); db.add(TranscriptMessage(call_id=call_id,role="assistant",content=decision.speech)); c.stt_ms+=stt_ms; c.llm_ms+=llm_ms; c.total_ms=c.stt_ms+c.llm_ms+c.tts_ms
                lead=db.get(Lead,c.lead_id)
                if lead and decision.action != "continue":
                    c.result=decision.action; c.summary=f"Live decision: {decision.reason or decision.action}"; apply_decision(db,lead,c,decision)
                log.info("call_id=%s lead_id=%s stage=%s STT=%.0fms LLM=%.0fms TOTAL=%.0fms", call_id, c.lead_id, decision.stage, stt_ms, llm_ms, stt_ms+llm_ms)
                db.commit()
        finally: db.close()
    async def on_tts(tts_ms):
        db=SessionLocal()
        try:
            c=db.get(Call,call_id)
            if c:
                c.tts_ms += tts_ms; c.total_ms=c.stt_ms+c.llm_ms+c.tts_ms
                log.info("call_id=%s lead_id=%s TTS=%.0fms TOTAL=%.0fms", call_id, c.lead_id, tts_ms, c.total_ms)
                db.commit()
        finally: db.close()
    await handle_twilio_media(websocket,on_turn,system_prompt,initial_speech,on_tts)
