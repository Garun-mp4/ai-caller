import json, os, threading
from .base import STTProvider
from app.core.config import get_settings
from app.services.settings_service import runtime_setting

class VoskProvider(STTProvider):
    _model = None
    _lock = threading.Lock()
    def __init__(self):
        self.path = runtime_setting("vosk_model_path", get_settings().vosk_model_path)
    def _ensure_model(self):
        if self.__class__._model is None:
            with self.__class__._lock:
                if self.__class__._model is None:
                    if not os.path.isdir(self.path):
                        raise RuntimeError(f"Vosk model not found: {self.path}")
                    from vosk import Model
                    self.__class__._model = Model(self.path)
        return self.__class__._model
    def preload(self):
        self._ensure_model()
        return self
    def transcribe_pcm16(self, pcm: bytes, sample_rate: int = 16000) -> str:
        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self._ensure_model(), sample_rate)
        rec.AcceptWaveform(pcm)
        return json.loads(rec.FinalResult()).get("text", "").strip()
    def health(self):
        return {"ok": os.path.isdir(self.path), "detail": self.path}
