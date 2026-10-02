import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from app.models import Lead, Campaign, CampaignLead, Callback, Call
from app.scheduler.call_scheduler import scheduler
from app.services import call_service

@pytest.mark.asyncio
async def test_scheduler_and_do_not_call(db):
    c=Campaign(name="Test",status="RUNNING",compliance_confirmed_at=datetime.now(timezone.utc)); a=Lead(phone="+79991111111",status="QUEUED"); b=Lead(phone="+79991111113",status="DO_NOT_CALL")
    db.add_all([c,a,b]); db.commit(); db.add_all([CampaignLead(campaign_id=c.id,lead_id=a.id),CampaignLead(campaign_id=c.id,lead_id=b.id)]); db.commit()
    n=await scheduler.tick(ignore_hours=True); db.expire_all(); assert n==1; assert db.get(Lead,b.id).status=="DO_NOT_CALL"
    assert db.query(Call).first().summary.startswith("Тестовый звонок.")

@pytest.mark.asyncio
async def test_callback_scheduling(db):
    c=Campaign(name="Test",status="RUNNING",compliance_confirmed_at=datetime.now(timezone.utc)); lead=Lead(phone="+79992222222",status="CALLBACK",next_call_at=datetime.now(timezone.utc)-timedelta(minutes=1)); db.add_all([c,lead]); db.commit(); db.add(CampaignLead(campaign_id=c.id,lead_id=lead.id)); db.add(Callback(lead_id=lead.id,reason="test",scheduled_at=datetime.now(timezone.utc)-timedelta(minutes=1))); db.commit()
    n=await scheduler.tick(ignore_hours=True); assert n==1

@pytest.mark.asyncio
async def test_overlapping_campaign_membership_and_ticks_only_start_one_call(db,monkeypatch):
    now=datetime.now(timezone.utc)
    first=Campaign(name='First',status='RUNNING',compliance_confirmed_at=now)
    second=Campaign(name='Second',status='RUNNING',compliance_confirmed_at=now)
    lead=Lead(phone='+79993333001',status='QUEUED')
    db.add_all([first,second,lead]); db.commit()
    db.add_all([CampaignLead(campaign_id=first.id,lead_id=lead.id),CampaignLead(campaign_id=second.id,lead_id=lead.id)])
    db.commit()

    class DelayedProvider:
        async def create_call(self,phone,call_id):
            await asyncio.sleep(0.05)
            return {'sid':f'MOCK-{call_id}','status':'queued'}
    monkeypatch.setattr(call_service,'get_telephony_provider',lambda:DelayedProvider())
    results=await asyncio.gather(scheduler.tick(ignore_hours=True),scheduler.tick(ignore_hours=True))
    db.expire_all()
    assert sorted(results)==[0,1]
    assert db.query(Call).filter(Call.lead_id==lead.id).count()==1

@pytest.mark.asyncio
async def test_provider_failure_closes_reserved_call_and_lead(db,monkeypatch):
    lead=Lead(phone='+79993333002',status='NEW')
    db.add(lead); db.commit()
    class FailedProvider:
        async def create_call(self,phone,call_id):
            raise RuntimeError('provider unavailable')
    monkeypatch.setattr(call_service,'get_telephony_provider',lambda:FailedProvider())
    with pytest.raises(RuntimeError,match='provider unavailable'):
        await call_service.initiate_call(db,lead,None)
    db.expire_all()
    saved_lead=db.get(Lead,lead.id)
    saved_call=db.query(Call).filter(Call.lead_id==lead.id).one()
    assert saved_lead.status=='FAILED' and saved_lead.attempts==1
    assert saved_call.status=='FAILED' and saved_call.ended_at is not None

@pytest.mark.asyncio
async def test_scheduler_closes_stale_unconfirmed_call_reservations(db):
    lead=Lead(phone='+79993333003',status='CALLING',attempts=1)
    db.add(lead); db.flush()
    call=Call(lead_id=lead.id,phone=lead.phone,status='STARTING',started_at=datetime.now(timezone.utc)-timedelta(minutes=6))
    db.add(call); db.commit()

    assert await scheduler.tick(ignore_hours=True)==0
    db.expire_all()
    assert db.get(Lead,lead.id).status=='FAILED'
    saved_call=db.get(Call,call.id)
    assert saved_call.status=='FAILED' and saved_call.result=='provider_error'
