import pytest
from datetime import datetime, timezone, timedelta
from app.models import Lead, Campaign, CampaignLead, Callback, Call
from app.scheduler.call_scheduler import scheduler

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
