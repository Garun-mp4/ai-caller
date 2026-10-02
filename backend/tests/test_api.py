from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from app.main import app
from app.models import Callback, Lead, Campaign, CampaignLead, Call, AppSetting
from app.api.routes import S, twilio_status
from app.stt.factory import get_stt_provider

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
    c=TestClient(app)
    response=c.post('/api/scheduler/tick',headers=auth(c))
    assert response.status_code==403
    assert response.json()["detail"]=="Manual scheduler tick is available only in development"

def test_leads_are_server_paginated_sorted_and_search_contact_name(db):
    db.add_all([
        Lead(phone=f"+7999000{i:04d}",name="Особый контакт" if i==3 else f"Контакт {i}",company=f"Компания {i%3}",status="NEW")
        for i in range(31)
    ])
    db.commit()
    with TestClient(app) as c:
        h=auth(c)
        second=c.get('/api/leads',params={'page':2,'page_size':10,'sort_by':'company','sort_order':'asc'},headers=h)
        assert second.status_code==200
        payload=second.json()
        assert payload['total']==31 and payload['page']==2 and payload['page_size']==10 and payload['page_count']==4
        assert len(payload['items'])==10
        names=[row['company'] for row in payload['items']]
        assert names==sorted(names)

        by_name=c.get('/api/leads',params={'search':'особый контакт'},headers=h)
        assert by_name.status_code==200
        assert by_name.json()['total']==1
        assert by_name.json()['items'][0]['name']=='Особый контакт'

        bounded=c.get('/api/leads',params={'page_size':101},headers=h)
        assert bounded.status_code==422

def test_campaign_audience_excludes_completed_and_dnc_and_attachment_is_idempotent(db):
    campaign=Campaign(name='Safe audience',status='DRAFT')
    db.add(campaign)
    db.flush()
    leads=[
        Lead(phone='+79991110001',status='NEW'),
        Lead(phone='+79991110002',status='QUEUED'),
        Lead(phone='+79991110003',status='CALLBACK'),
        Lead(phone='+79991110004',status='DO_NOT_CALL'),
        Lead(phone='+79991110005',status='DONE'),
        Lead(phone='+79991110006',status='NOT_INTERESTED'),
        Lead(phone='+79991110007',status='CALLING'),
    ]
    db.add_all(leads)
    db.flush()
    db.add(CampaignLead(campaign_id=campaign.id,lead_id=leads[2].id))
    db.commit()

    with TestClient(app) as c:
        h=auth(c)
        preview=c.get(f'/api/campaigns/{campaign.id}/audience',headers=h)
        assert preview.status_code==200
        assert preview.json()=={'to_attach':2,'already_attached':1,'attached_eligible':1,'by_status':{'NEW':1,'QUEUED':1}}

        attached=c.post(f'/api/campaigns/{campaign.id}/attach-all',headers=h)
        assert attached.status_code==200 and attached.json()['attached']==2
        again=c.post(f'/api/campaigns/{campaign.id}/attach-all',headers=h)
        assert again.status_code==200 and again.json()['attached']==0

    db.expire_all()
    assert db.query(CampaignLead).filter(CampaignLead.campaign_id==campaign.id).count()==3
    assert db.get(Lead,leads[0].id).status=='QUEUED'
    assert db.get(Lead,leads[3].id).status=='DO_NOT_CALL'
    assert db.query(CampaignLead).filter(CampaignLead.lead_id.in_([leads[3].id,leads[4].id,leads[5].id,leads[6].id])).count()==0

def test_settings_allowlist_validation_and_provider_cache_reload(db):
    db.add_all([
        AppSetting(key='jwt_secret',value='must-not-leak',secret=True),
        AppSetting(key='agent_name',value='Сохранённое имя'),
        AppSetting(key='max_attempts',value='80'),
        AppSetting(key='delay_between_attempts',value='0'),
        AppSetting(key='calling_hours',value='22:00-06:00'),
        AppSetting(key='timezone',value='Not/A_Timezone'),
    ])
    db.commit()
    get_stt_provider.cache_clear()
    first_provider=get_stt_provider()
    with TestClient(app) as c:
        h=auth(c)
        read=c.get('/api/settings',headers=h)
        assert read.status_code==200
        assert read.json()['values']['agent_name']=='Сохранённое имя'
        assert read.json()['values']['max_attempts']=='50'
        assert read.json()['values']['delay_between_attempts']=='1'
        assert read.json()['values']['calling_hours']==f'{S.calling_hours_start}-{S.calling_hours_end}'
        assert read.json()['values']['timezone']==S.app_timezone
        assert 'jwt_secret' not in read.text and 'must-not-leak' not in read.text

        for invalid in [
            {'jwt_secret':'replacement'},
            {'max_attempts':'51'},
            {'delay_between_attempts':'0'},
            {'timezone':'Not/A_Timezone'},
            {'calling_hours':'22:00-06:00'},
        ]:
            assert c.put('/api/settings',json=invalid,headers=h).status_code==422

        saved=c.put('/api/settings',json={'max_attempts':'50','delay_between_attempts':'10080','vosk_model_path':'/models/new-vos-k'},headers=h)
        assert saved.status_code==200
        assert db.get(AppSetting,'jwt_secret').value=='must-not-leak'
        second_provider=get_stt_provider()
        assert second_provider is not first_provider
        assert second_provider.path=='/models/new-vos-k'

    get_stt_provider.cache_clear()

def test_call_now_rejects_an_active_call_or_dnc_contact(db):
    blocked=Lead(phone='+79992220001',status='DO_NOT_CALL')
    active_lead=Lead(phone='+79992220002',status='CALLING')
    db.add_all([blocked,active_lead])
    db.flush()
    db.add(Call(lead_id=active_lead.id,phone=active_lead.phone,status='IN_PROGRESS'))
    db.add(AppSetting(key='max_concurrent_calls',value='1'))
    db.commit()
    with TestClient(app) as c:
        h=auth(c)
        assert c.post(f'/api/leads/{blocked.id}/call-now',headers=h).status_code==409
        assert c.post(f'/api/leads/{active_lead.id}/call-now',headers=h).status_code==409

def test_dashboard_counts_only_calls_started_in_operator_local_day(db):
    from zoneinfo import ZoneInfo

    db.add(AppSetting(key='timezone',value='Europe/Astrakhan'))
    lead=Lead(phone='+79994440001',status='DONE')
    db.add(lead)
    db.flush()
    now=datetime.now(ZoneInfo('Europe/Astrakhan'))
    start=now.replace(hour=0,minute=0,second=0,microsecond=0)
    yesterday=(start-timedelta(days=1)).astimezone(timezone.utc)
    today=start.astimezone(timezone.utc)
    db.add_all([
        Call(lead_id=lead.id,phone=lead.phone,status='COMPLETED',started_at=yesterday),
        Call(lead_id=lead.id,phone=lead.phone,status='COMPLETED',started_at=today),
    ])
    db.commit()
    with TestClient(app) as c:
        response=c.get('/api/dashboard',headers=auth(c))
        assert response.status_code==200
        assert response.json()['stats']['calls_today']==1

def test_repeated_twilio_terminal_webhook_creates_only_one_retry(db):
    lead=Lead(phone='+79994440002',status='CALLING',attempts=1)
    db.add(lead)
    db.flush()
    call=Call(lead_id=lead.id,phone=lead.phone,status='IN_PROGRESS',started_at=datetime.now(timezone.utc))
    db.add(call)
    db.commit()

    twilio_status(call.id,CallStatus='no-answer',CallSid='',db=db)
    twilio_status(call.id,CallStatus='no-answer',CallSid='',db=db)
    db.expire_all()
    assert db.query(Callback).filter(Callback.lead_id==lead.id).count()==1
    assert db.get(Lead,lead.id).status=='CALLBACK'
    assert db.query(Call).filter(Call.lead_id==lead.id).one().status=='NO_ANSWER'

def test_late_twilio_confirmation_can_recover_a_failed_local_reservation(db):
    lead=Lead(phone='+79994440003',status='FAILED',attempts=1)
    db.add(lead)
    db.flush()
    call=Call(lead_id=lead.id,phone=lead.phone,status='FAILED',result='provider_error',ended_at=datetime.now(timezone.utc),started_at=datetime.now(timezone.utc)-timedelta(minutes=6))
    db.add(call); db.commit()

    twilio_status(call.id,CallStatus='completed',CallSid='CA-late-confirmation',db=db)
    db.expire_all()
    assert db.query(Call).filter(Call.lead_id==lead.id).one().status=='COMPLETED'
    assert db.get(Lead,lead.id).status=='DONE'
