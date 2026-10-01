from abc import ABC, abstractmethod
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize_wav(self, text: str) -> bytes: ...
    async def health(self) -> dict: return {"ok": True}
