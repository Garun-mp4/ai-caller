import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Campaign, CampaignLead, Lead, Callback, Call
from app.services.call_service import initiate_call, CallNotEligibleError, ACTIVE_CALL_STATUSES
from app.services.settings_service import call_preferences

log = logging.getLogger(__name__)


class CallScheduler:
    def __init__(self):
        self.task = None
        self.running = False
        self._tick_lock = asyncio.Lock()

    async def start(self):
        if self.task and not self.task.done():
            return
        self.running = True
        self.task = asyncio.create_task(self._loop(), name="call-scheduler")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def _within_hours(self, db):
        pref = call_preferences(db)
        now = datetime.now(ZoneInfo(pref["timezone"]))
        start_h, start_m = map(int, pref["start"].split(":"))
        end_h, end_m = map(int, pref["end"].split(":"))
        current_minute = now.hour * 60 + now.minute
        start_minute = start_h * 60 + start_m
        end_minute = end_h * 60 + end_m
        return start_minute <= current_minute < end_minute

    async def tick(self, ignore_hours=False):
        # A manual development tick and the background loop share one local
        # scheduler. Serializing the whole step prevents overlapping selections.
        async with self._tick_lock:
            return await self._run_tick(ignore_hours)

    async def _run_tick(self, ignore_hours=False):
        db = SessionLocal()
        processed = 0
        try:
            if not ignore_hours and not self._within_hours(db):
                return 0

            pref = call_preferences(db)
            now = datetime.now(timezone.utc)

            stale_before = now - timedelta(minutes=5)
            stale_reservations = db.execute(
                select(Call, Lead)
                .join(Lead, Lead.id == Call.lead_id)
                .where(
                    Call.status == "STARTING",
                    Call.twilio_call_sid.is_(None),
                    Call.started_at <= stale_before,
                )
            ).all()
            for call, lead in stale_reservations:
                call.status = "FAILED"
                call.result = "provider_error"
                call.summary = "Провайдер не подтвердил запуск звонка. Автоматический повтор отключён во избежание дубля."
                call.ended_at = now
                if lead.status == "CALLING":
                    lead.status = "FAILED"
                    lead.result = "Call provider error"
            if stale_reservations:
                db.commit()

            due_rows = db.execute(
                select(Callback, Lead)
                .join(Lead, Lead.id == Callback.lead_id)
                .where(Callback.status == "SCHEDULED", Callback.scheduled_at <= now)
            ).all()
            for callback, lead in due_rows:
                if lead.status == "DO_NOT_CALL":
                    callback.status = "CANCELED"
                else:
                    lead.status = "QUEUED"
                    callback.status = "DUE"
            db.commit()

            active_count = db.scalar(
                select(func.count()).select_from(Call).where(Call.status.in_(ACTIVE_CALL_STATUSES))
            ) or 0
            available = max(0, pref["max_concurrent_calls"] - active_count)
            if available == 0:
                return 0

            campaign_candidates = (
                select(
                    Lead.id.label("lead_id"),
                    func.min(Campaign.id).label("campaign_id"),
                    Lead.next_call_at.label("next_call_at"),
                )
                .join(CampaignLead, CampaignLead.lead_id == Lead.id)
                .join(Campaign, Campaign.id == CampaignLead.campaign_id)
                .where(
                    Campaign.status == "RUNNING",
                    Campaign.compliance_confirmed_at.is_not(None),
                    Lead.status.in_(["NEW", "QUEUED", "CALLBACK"]),
                )
                .group_by(Lead.id)
                .subquery()
            )
            rows = db.execute(
                select(Campaign, Lead)
                .join(campaign_candidates, campaign_candidates.c.campaign_id == Campaign.id)
                .join(Lead, Lead.id == campaign_candidates.c.lead_id)
                .order_by(campaign_candidates.c.next_call_at.asc().nullsfirst(), campaign_candidates.c.lead_id)
                .limit(available)
            ).all()

            for campaign, lead in rows:
                if lead.status == "DO_NOT_CALL":
                    continue
                if lead.attempts >= pref["max_attempts"]:
                    lead.status = "DONE"
                    lead.result = "Max attempts reached"
                    db.commit()
                    continue
                if lead.next_call_at:
                    next_call_at = lead.next_call_at
                    if next_call_at.tzinfo is None:
                        next_call_at = next_call_at.replace(tzinfo=timezone.utc)
                    if next_call_at > now:
                        continue
                try:
                    await initiate_call(db, lead, campaign)
                except CallNotEligibleError:
                    db.rollback()
                    continue
                except Exception:
                    db.rollback()
                    log.exception("Scheduled call failed for lead_id=%s", lead.id)
                    continue

                processed += 1
                for callback in db.scalars(
                    select(Callback).where(Callback.lead_id == lead.id, Callback.status == "DUE")
                ).all():
                    callback.status = "COMPLETED"
                db.commit()
            return processed
        finally:
            db.close()

    async def _loop(self):
        while self.running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("scheduler tick failed")
            await asyncio.sleep(2)


scheduler = CallScheduler()
