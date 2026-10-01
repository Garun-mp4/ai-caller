from functools import lru_cache
from .vosk_provider import VoskProvider
@lru_cache
def get_stt_provider(): return VoskProvider()
