from functools import lru_cache
from .piper_provider import PiperProvider
@lru_cache
def get_tts_provider(): return PiperProvider()
