from functools import lru_cache
from app.core.config import get_settings
from .mock_provider import MockTelephonyProvider
from .twilio_service import TwilioService
@lru_cache
def get_telephony_provider(): return TwilioService() if get_settings().telephony_provider=="twilio" else MockTelephonyProvider()
