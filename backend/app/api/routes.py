from datetime import datetime, timezone
import logging
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, WebSocket, Form
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, or_, text
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
from app.services.call_service import initiate_call, apply_decision
from app.agent.prompt import build_sales_prompt, configured_introduction
from app.services.settings_service import call_preferences
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
    today=datetime.now(timezone.utc).date()
    leads=db.scalar(select(func.count()).select_from(Lead)) or 0
    calls=db.scalars(select(Call).order_by(Call.id.desc()).limit(6)).all()
    callbacks=db.scalars(select(Callback).where(Callback.status.in_(["SCHEDULED","DUE"])).order_by(Callback.scheduled_at).limit(6)).all()
    statuses=dict(db.execute(select(Lead.status,func.count()).group_by(Lead.status)).all())
    calls_today=sum(1 for c in db.scalars(select(Call)).all() if c.started_at.date()==today)
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

@router.get("/leads", response_model=list[LeadOut], dependencies=[Depends(require_user)])
def leads(status: str|None=None,campaign: int|None=None,search: str|None=None,db: Session=Depends(get_db)):
    q=select(Lead)
    if status: q=q.where(Lead.status==status)
    if campaign: q=q.join(CampaignLead,CampaignLead.lead_id==Lead.id).where(CampaignLead.campaign_id==campaign)
    if search: q=q.where(or_(Lead.phone.contains(search),Lead.company.contains(search)))
    return db.scalars(q.order_by(Lead.id.desc())).unique().all()

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
    if lead.status=="DO_NOT_CALL": raise HTTPException(409,"Lead is DO_NOT_CALL")
    c=await initiate_call(db,lead,None); db.refresh(c); return c

@router.get("/campaigns", dependencies=[Depends(require_user)])
def campaigns(db:Session=Depends(get_db)):
    out=[]
    for c in db.scalars(select(Campaign).order_by(Campaign.id.desc())).all():
        stats=dict(db.execute(select(Lead.status,func.count()).join(CampaignLead,CampaignLead.lead_id==Lead.id).where(CampaignLead.campaign_id==c.id).group_by(Lead.status)).all())
        total=sum(stats.values())
        answered=db.scalar(select(func.count()).select_from(Call).where(Call.campaign_id==c.id, Call.answered_at.is_not(None))) or 0
        out.append({**CampaignOut.model_validate(c).model_dump(),"metrics":{"total":total,"queued":stats.get("QUEUED",0)+stats.get("NEW",0),"calling":stats.get("CALLING",0),"answered":answered,"no_answer":stats.get("NO_ANSWER",0),"interested":stats.get("INTERESTED",0),"hot_leads":stats.get("HOT_LEAD",0),"callbacks":stats.get("CALLBACK",0)}})
    return out

@router.post("/campaigns", response_model=CampaignOut, dependencies=[Depends(require_user)])
def create_campaign(req:CampaignCreate,db:Session=Depends(get_db)):
    c=Campaign(**req.model_dump()); db.add(c); db.commit(); db.refresh(c); return c

@router.post("/campaigns/{campaign_id}/attach-all", dependencies=[Depends(require_user)])
def attach_all(campaign_id:int,db:Session=Depends(get_db)):
    if not db.get(Campaign,campaign_id): raise HTTPException(404,"Campaign not found")
    added=0
    existing=set(db.scalars(select(CampaignLead.lead_id).where(CampaignLead.campaign_id==campaign_id)).all())
    for lead in db.scalars(select(Lead).where(Lead.status!="DO_NOT_CALL")).all():
        if lead.id not in existing:
            db.add(CampaignLead(campaign_id=campaign_id,lead_id=lead.id)); added+=1
            if lead.status=="NEW": lead.status="QUEUED"
    db.commit(); return {"attached":added}

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

@router.get("/calls", dependencies=[Depends(require_user)])
def calls(db:Session=Depends(get_db)):
    rows=db.scalars(select(Call).options(selectinload(Call.transcripts)).order_by(Call.id.desc()).limit(200)).all(); return [CallOut.model_validate(c) for c in rows]

@router.get("/callbacks", dependencies=[Depends(require_user)])
def callbacks(db:Session=Depends(get_db)):
    rows=db.scalars(select(Callback).order_by(Callback.scheduled_at)).all()
    out=[]
    for cb in rows:
        lead=db.get(Lead,cb.lead_id); out.append({**CallbackOut.model_validate(cb).model_dump(),"phone":lead.phone if lead else "","company":lead.company if lead else None})
    return out

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
    defaults={"agent_name":"Алекс","company_name":"Веб-студия","what_we_sell":"Разработка сайтов, редизайн и автоматизация для бизнеса","introduction":"Добрый день! Можно задать короткий вопрос о вашем сайте?","offer":"Разработка и улучшение сайтов для бизнеса","allowed_claims":"Мы разрабатываем сайты и автоматизируем процессы.","forbidden_claims":"Не придумывать цены, кейсы, гарантии и сроки.","call_objective":"Понять интерес и договориться о следующем шаге.","max_response_length":"3","calling_hours":f"{S.calling_hours_start}-{S.calling_hours_end}","timezone":S.app_timezone,"max_attempts":str(S.max_attempts),"delay_between_attempts":str(S.retry_delay_minutes),"max_concurrent_calls":str(S.max_concurrent_calls),"vosk_model_path":S.vosk_model_path,"piper_model_path":S.piper_model_path,"llm_provider":S.llm_provider,"llm_model":S.codex_model,"reasoning_effort":S.codex_reasoning_effort}
    stored={x.key:x.value for x in db.scalars(select(AppSetting)).all()}; defaults.update(stored)
    return {"values":defaults,"providers":{"auth_mode":S.auth_mode,"llm_provider":S.llm_provider,"telephony_provider":S.telephony_provider,"stt_provider":S.stt_provider,"tts_provider":S.tts_provider,"vosk_model_path":S.vosk_model_path,"piper_model_path":S.piper_model_path,"codex_model":S.codex_model,"reasoning_effort":S.codex_reasoning_effort}}

@router.put("/settings", dependencies=[Depends(require_user)])
def save_settings(values:dict,db:Session=Depends(get_db)):
    forbidden={"twilio_auth_token","openai_oauth_client_secret","jwt_secret"}
    for k,v in values.items():
        if k in forbidden: continue
        row=db.get(AppSetting,k)
        if not row: row=AppSetting(key=k,value=str(v)); db.add(row)
        else: row.value=str(v)
    db.commit(); return {"ok":True}

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
        status=(CallStatus or "").lower()
        c.twilio_call_sid=CallSid or c.twilio_call_sid; c.status=status.upper().replace("-","_") or c.status
        lead=db.get(Lead,c.lead_id)
        if status in ("answered","in-progress") and not c.answered_at: c.answered_at=datetime.now(timezone.utc)
        if status in ("completed","failed","busy","no-answer","canceled"):
            c.ended_at=datetime.now(timezone.utc)
            if c.started_at:
                started=c.started_at if c.started_at.tzinfo else c.started_at.replace(tzinfo=timezone.utc)
                c.duration=max(0,int((c.ended_at-started).total_seconds()))
            if lead and not c.result and lead.status != "DO_NOT_CALL":
                pref=call_preferences(db)
                if status=="no-answer": lead.status="NO_ANSWER"; lead.result="No answer"
                elif status=="busy": lead.status="BUSY"; lead.result="Busy"
                elif status in ("failed","canceled"): lead.status="FAILED"; lead.result=status
                elif status=="completed": lead.status="DONE"; lead.result=lead.result or "completed"
                if status in ("no-answer","busy","failed") and lead.attempts < pref["max_attempts"]:
                    from datetime import timedelta
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
