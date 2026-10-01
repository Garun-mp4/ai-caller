import asyncio
from .base import TelephonyProvider
from app.core.config import get_settings

class TwilioService(TelephonyProvider):
    def __init__(self):
        s=get_settings(); self.sid=s.twilio_account_sid; self.token=s.twilio_auth_token; self.from_number=s.twilio_phone_number; self.base=s.public_base_url.rstrip("/")
    async def health(self):
        return {"ok": bool(self.sid and self.token and self.from_number), "detail": "configured" if self.sid and self.token and self.from_number else "missing credentials"}
    async def create_call(self, phone_number: str, call_id: int) -> dict:
        if not (self.sid and self.token and self.from_number):
            raise RuntimeError("Twilio is not configured")
        def _call():
            try:
                from twilio.rest import Client
            except ImportError as e:
                raise RuntimeError("Twilio Python package is not installed") from e
            c=Client(self.sid,self.token)
            call=c.calls.create(to=phone_number, from_=self.from_number, url=f"{self.base}/api/telephony/twiml/{call_id}", status_callback=f"{self.base}/api/telephony/status/{call_id}", status_callback_event=["initiated","ringing","answered","completed"])
            return {"sid":call.sid,"status":call.status}
        return await asyncio.to_thread(_call)
