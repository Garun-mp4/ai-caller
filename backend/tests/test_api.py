from fastapi.testclient import TestClient
from app.main import app

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
