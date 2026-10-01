from abc import ABC, abstractmethod
class STTProvider(ABC):
    @abstractmethod
    def transcribe_pcm16(self, pcm: bytes, sample_rate: int = 16000) -> str: ...
    def health(self) -> dict: return {"ok": True}
