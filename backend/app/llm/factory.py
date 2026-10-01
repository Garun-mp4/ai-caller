from functools import lru_cache
from app.core.config import get_settings
from .mock_provider import MockLLMProvider
from .codex_provider import CodexCLIProvider
from app.services.settings_service import runtime_setting

@lru_cache
def get_llm_provider():
    return CodexCLIProvider() if runtime_setting("llm_provider", get_settings().llm_provider) == "codex" else MockLLMProvider()
