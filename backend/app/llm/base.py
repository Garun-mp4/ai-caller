from abc import ABC, abstractmethod
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, history: list[dict[str,str]], user_text: str) -> str: ...
    async def health(self) -> dict: return {"ok": True}
