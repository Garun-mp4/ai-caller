from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from app.main import app
from app.models import Callback, Lead, Campaign, CampaignLead, Call, TranscriptMessage, AppSetting
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
        listed=c.get('/api/callbacks',headers=h).json()['items'][0]
        assert listed['company']=="Альфа"
        assert listed['phone']==lead.phone

def test_callbacks_are_paginated_filtered_and_searchable(db):
    scheduled=datetime.now(timezone.utc)+timedelta(days=2)
    leads=[]
    callbacks=[]
    for index in range(205):
        lead=Lead(
            phone=f"+7999777{index:04d}",
            name="Избранный клиент" if index==204 else f"Клиент {index}",
            company="ООО Ёлка 204" if index==204 else f"Компания {index}",
            status="CALLBACK",
        )
        leads.append(lead)
    db.add_all(leads); db.flush()
    for index,lead in enumerate(leads):
        status="COMPLETED" if index==1 else "CANCELED" if index==2 else "DUE" if index==0 else "SCHEDULED"
        reason="Найти 100% решение" if index==204 else f"Связаться {index}"
        callbacks.append(Callback(
            lead_id=lead.id,
            reason=reason,
            scheduled_at=scheduled+timedelta(minutes=index),
            status=status,
        ))
    db.add_all(callbacks); db.commit()

    with TestClient(app) as c:
        h=auth(c)
        second=c.get('/api/callbacks',params={'page':2,'page_size':50},headers=h)
        assert second.status_code==200
        payload=second.json()
        assert (payload['total'],payload['page'],payload['page_size'],payload['page_count'])==(205,2,50,5)
        assert len(payload['items'])==50
        assert payload['items'][0]['status'] in ('SCHEDULED','DUE')
        assert payload['stats']['total']==205
        assert payload['stats']['active']==203
        assert payload['stats']['completed']==1

        last=c.get('/api/callbacks',params={'page':5,'page_size':50},headers=h).json()
        assert len(last['items'])==5
        assert {row['status'] for row in last['items'][-2:]}=={'COMPLETED','CANCELED'}

        active=c.get('/api/callbacks',params={'status':'ACTIVE','page_size':100},headers=h).json()
        assert active['total']==203
        assert all(row['status'] in ('SCHEDULED','DUE') for row in active['items'])
        completed=c.get('/api/callbacks',params={'status':'COMPLETED'},headers=h).json()
        assert completed['total']==1 and completed['items'][0]['status']=='COMPLETED'

        by_name=c.get('/api/callbacks',params={'search':'изБРаНный'},headers=h).json()
        assert by_name['total']==1 and by_name['items'][0]['lead_id']==leads[204].id
        by_reason=c.get('/api/callbacks',params={'search':'%'},headers=h).json()
        assert by_reason['total']==1 and by_reason['items'][0]['reason']=='Найти 100% решение'
        assert by_reason['stats']['total']==205
        assert c.get('/api/callbacks',params={'page':0},headers=h).status_code==422
        assert c.get('/api/callbacks',params={'page_size':101},headers=h).status_code==422
        assert c.get('/api/callbacks',params={'status':'UNKNOWN'},headers=h).status_code==422

def test_callback_stats_use_configured_timezone_and_exclusive_buckets(db,monkeypatch):
    from app.api import routes
    from zoneinfo import ZoneInfo

    timezone_name="Europe/Astrakhan"
    local_now=datetime.now(timezone.utc).astimezone(ZoneInfo(timezone_name))
    local_tomorrow=local_now.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
    fixed_now=local_tomorrow.replace(hour=21).astimezone(timezone.utc)
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls,tz=None):
            return fixed_now.astimezone(tz) if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(routes,"datetime",FrozenDateTime)
    assert routes.datetime.now(timezone.utc)==fixed_now
    db.add(AppSetting(key="timezone",value=timezone_name))
    db.flush()
    schedules=[
        ("DUE",fixed_now+timedelta(minutes=10)),
        ("SCHEDULED",fixed_now-timedelta(minutes=10)),
        ("SCHEDULED",fixed_now+timedelta(minutes=15)),
        ("SCHEDULED",fixed_now+timedelta(hours=4)),
        ("COMPLETED",fixed_now+timedelta(minutes=20)),
        ("CANCELED",fixed_now+timedelta(minutes=20)),
    ]
    for index,(status,scheduled_at) in enumerate(schedules):
        lead=Lead(phone=f"+7999666{index:04d}",company=f"Часовой пояс {index}",status="CALLBACK")
        db.add(lead); db.flush()
        db.add(Callback(lead_id=lead.id,reason="Проверка времени",scheduled_at=scheduled_at,status=status))
    db.commit()

    with TestClient(app) as c:
        payload=c.get('/api/callbacks',params={'status':'ACTIVE','search':'нет совпадения'},headers=auth(c)).json()
        assert payload['items']==[] and payload['total']==0
        assert payload['stats']=={
            'total':6,
            'active':4,
            'overdue':2,
            'today':1,
            'upcoming':1,
            'completed':1,
        }

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

def test_calls_are_server_paginated_searchable_and_count_answered_calls_globally(db):
    lead=Lead(phone='+79991110000',status='NEW')
    db.add(lead)
    db.flush()
    now=datetime.now(timezone.utc)
    calls=[]
    for i in range(205):
        status='ANSWERED' if i==1 else ('COMPLETED','NO_ANSWER','IN_PROGRESS','FAILED')[i%4]
        call=Call(
            lead_id=lead.id,
            phone=f'+7999{i:07d}',
            status=status,
            result='INTERESTED' if i%4==0 else ('no-answer' if i%4==1 else None),
            started_at=now-timedelta(seconds=i),
            answered_at=now-timedelta(seconds=i) if i%4==0 else None,
            duration=i,
        )
        if i%10==0:
            call.transcripts.append(TranscriptMessage(role='user',content=f'Фраза {i}'))
        calls.append(call)
    db.add_all(calls)
    db.commit()

    with TestClient(app) as c:
        h=auth(c)
        unauthorized=c.get('/api/calls')
        assert unauthorized.status_code==401

        second=c.get('/api/calls',params={'page':2,'page_size':25},headers=h)
        assert second.status_code==200
        payload=second.json()
        assert payload['total']==205 and payload['page']==2 and payload['page_size']==25 and payload['page_count']==9
        assert len(payload['items'])==25
        assert payload['items'][0]['phone']==f'+7999{25:07d}'
        assert payload['stats']=={'total':205,'answered':53,'average_duration':102.0,'with_transcript':21}

        answered=c.get('/api/calls',params={'status':'ANSWERED','page_size':100},headers=h).json()
        assert answered['total']==53
        assert all(item['answered_at'] or item['status']=='ANSWERED' for item in answered['items'])
        assert answered['stats']==payload['stats']

        searched=c.get('/api/calls',params={'search':'0000042'},headers=h).json()
        assert searched['total']==1
        assert searched['items'][0]['phone']==f'+7999{42:07d}'

        literal_wildcard=c.get('/api/calls',params={'search':'%'},headers=h).json()
        assert literal_wildcard['total']==0

        bounded=c.get('/api/calls',params={'page_size':101},headers=h)
        invalid_status=c.get('/api/calls',params={'status':'UNKNOWN'},headers=h)
        assert bounded.status_code==422
        assert invalid_status.status_code==422

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
