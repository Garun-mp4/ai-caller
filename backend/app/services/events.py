import json
from sqlalchemy.orm import Session
from app.models import Event

def emit_hot_lead(db: Session, lead_id: int, company: str | None, phone: str, summary: str):
    db.add(Event(type="HotLeadCreated", payload=json.dumps({"lead_id":lead_id,"company":company,"phone":phone,"summary":summary},ensure_ascii=False)))
