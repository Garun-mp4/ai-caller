import asyncio, logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Campaign, CampaignLead, Lead, Callback, Call
from app.services.call_service import initiate_call
from app.services.settings_service import call_preferences

log=logging.getLogger(__name__)

class CallScheduler:
    def __init__(self): self.task=None; self.running=False; self.sem=asyncio.Semaphore(max(1,get_settings().max_concurrent_calls))
    async def start(self):
        if self.task and not self.task.done(): return
        self.running=True; self.task=asyncio.create_task(self._loop(), name="call-scheduler")
    async def stop(self):
        self.running=False
        if self.task: self.task.cancel()
    def _within_hours(self, db):
        pref=call_preferences(db)
        try: now=datetime.now(ZoneInfo(pref["timezone"]))
        except Exception: now=datetime.now(timezone.utc)
        start_h,start_m=map(int,pref["start"].split(':')); end_h,end_m=map(int,pref["end"].split(':'))
        cur=now.hour*60+now.minute
        return start_h*60+start_m <= cur <= end_h*60+end_m
    async def tick(self, ignore_hours=False):
        db=SessionLocal(); count=0
        try:
            if not ignore_hours and not self._within_hours(db): return 0
            pref=call_preferences(db)
            # Activate due callbacks.
            now=datetime.now(timezone.utc)
            due=db.scalars(select(Callback).where(Callback.status=="SCHEDULED", Callback.scheduled_at<=now)).all()
            for cb in due:
                lead=db.get(Lead,cb.lead_id)
                if lead and lead.status!="DO_NOT_CALL": lead.status="QUEUED"; cb.status="DUE"
            db.commit()
            active_statuses=["STARTING","QUEUED","INITIATED","RINGING","ANSWERED","IN_PROGRESS"]
            active=db.scalar(select(func.count()).select_from(Call).where(Call.status.in_(active_statuses))) or 0
            available=max(0,pref["max_concurrent_calls"]-active)
            if available <= 0: return 0
            rows=db.execute(select(CampaignLead,Campaign,Lead).join(Campaign,Campaign.id==CampaignLead.campaign_id).join(Lead,Lead.id==CampaignLead.lead_id).where(Campaign.status=="RUNNING",Lead.status.in_(["NEW","QUEUED","CALLBACK"])).order_by(Lead.next_call_at.asc().nullsfirst(),Lead.id).limit(available)).all()
            for _, campaign, lead in rows:
                if lead.status=="DO_NOT_CALL": continue
                if lead.attempts >= pref["max_attempts"]:
                    lead.status="DONE"; lead.result="Max attempts reached"; db.commit(); continue
                if lead.next_call_at:
                    dt=lead.next_call_at
                    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                    if dt > now: continue
                async with self.sem:
                    await initiate_call(db,lead,campaign); count+=1
                    for cb in db.scalars(select(Callback).where(Callback.lead_id==lead.id, Callback.status=="DUE")).all(): cb.status="COMPLETED"
                    db.commit()
            return count
        finally: db.close()
    async def _loop(self):
        while self.running:
            try: await self.tick()
            except asyncio.CancelledError: break
            except Exception: log.exception("scheduler tick failed")
            await asyncio.sleep(2)

scheduler=CallScheduler()
