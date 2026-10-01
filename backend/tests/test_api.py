from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from app.main import app
from app.models import Callback, Lead
from app.api.routes import S

def auth(client):
    r=client.post('/api/auth/login',json={'username':'admin','password':'admin'}); return {'Authorization':'Bearer '+r.json()['access_token']}

def test_health_and_campaign_flow():
    with TestClient(app) as c:
        assert c.get('/api/health').status_code==200
        h=auth(c)
        r=c.post('/api/campaigns',json={'name':'Campaign A','description':'','agent_prompt':''},headers=h); assert r.status_code==200
        cid=r.json()['id']
        r=c.post(f'/api/campaigns/{cid}/start',json={'confirm_compliance':False},headers=h); assert r.status_code==400
        r=c.post(f'/api/campaigns/{cid}/start',json={'confirm_compliance':True},headers=h); assert r.status_code==200

def _lead_with_callback(db, phone="+79991112233"):
    scheduled=datetime.now(timezone.utc)+timedelta(days=2)
    lead=Lead(phone=phone,company="Альфа",status="CALLBACK",next_call_at=scheduled)
    db.add(lead); db.flush()
    callback=Callback(lead_id=lead.id,reason="Уточнить детали",scheduled_at=scheduled,status="SCHEDULED")
    db.add(callback); db.commit(); db.refresh(lead); db.refresh(callback)
    return lead,callback

def test_callback_can_be_rescheduled_and_completed(db):
    lead,callback=_lead_with_callback(db)
    next_time=datetime.now(timezone.utc)+timedelta(days=4)
    with TestClient(app) as c:
        h=auth(c)
        updated=c.patch(f'/api/callbacks/{callback.id}',json={'scheduled_at':next_time.isoformat()},headers=h)
        assert updated.status_code==200
        assert updated.json()['status']=="SCHEDULED"
        saved_time=datetime.fromisoformat(updated.json()['scheduled_at']).astimezone(timezone.utc)
        assert abs(saved_time-next_time)<timedelta(seconds=1)

        completed=c.patch(f'/api/callbacks/{callback.id}',json={'status':'COMPLETED'},headers=h)
        assert completed.status_code==200
        assert completed.json()['status']=="COMPLETED"
        db.refresh(lead)
        assert lead.status=="DONE"
        assert lead.next_call_at is None
        listed=c.get('/api/callbacks',headers=h).json()[0]
        assert listed['company']=="Альфа"
        assert listed['phone']==lead.phone

def test_dnc_cancels_callback_and_prevents_rescheduling(db):
    lead,callback=_lead_with_callback(db,"+79992223344")
    with TestClient(app) as c:
        h=auth(c)
        changed=c.patch(f'/api/leads/{lead.id}',json={'status':'DO_NOT_CALL'},headers=h)
        assert changed.status_code==200
        db.refresh(callback); db.refresh(lead)
        assert callback.status=="CANCELED"
        assert lead.next_call_at is None
        attempt=c.patch(f'/api/callbacks/{callback.id}',json={'status':'SCHEDULED'},headers=h)
        assert attempt.status_code==409

def test_callback_rejects_past_schedule_and_requires_authentication(db):
    _,callback=_lead_with_callback(db,"+79993334455")
    with TestClient(app) as c:
        unauthorized=c.patch(f'/api/callbacks/{callback.id}',json={'status':'COMPLETED'})
        assert unauthorized.status_code==401
        h=auth(c)
        past=c.patch(f'/api/callbacks/{callback.id}',json={'scheduled_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()},headers=h)
        assert past.status_code==422

def test_manual_scheduler_tick_is_disabled_in_production(monkeypatch):
    monkeypatch.setattr(S, "app_env", "production")
    with TestClient(app) as c:
        response=c.post('/api/scheduler/tick',headers=auth(c))
        assert response.status_code==403
        assert response.json()["detail"]=="Manual scheduler tick is available only in development"
