import json, os, threading
from .base import STTProvider
from app.core.config import get_settings
from app.services.settings_service import runtime_setting

class VoskProvider(STTProvider):
    def __init__(self):
        self.path = runtime_setting("vosk_model_path", get_settings().vosk_model_path)
        self._model = None
        self._lock = threading.Lock()
    def _ensure_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    if not os.path.isdir(self.path):
                        raise RuntimeError(f"Vosk model not found: {self.path}")
                    from vosk import Model
                    self._model = Model(self.path)
        return self._model
    def preload(self):
        self._ensure_model()
        return self
    def transcribe_pcm16(self, pcm: bytes, sample_rate: int = 16000) -> str:
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if len(pcm) % 2:
            raise ValueError("PCM16 audio must contain complete 16-bit samples")
        if not pcm:
            return ""

        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self._ensure_model(), sample_rate)
        recognized = []
        # Feed bounded frames so endpoint detection can split longer utterances.
        for offset in range(0, len(pcm), 4000):
            if rec.AcceptWaveform(pcm[offset:offset + 4000]):
                text = json.loads(rec.Result()).get("text", "").strip()
                if text:
                    recognized.append(text)
        final_text = json.loads(rec.FinalResult()).get("text", "").strip()
        if final_text:
            recognized.append(final_text)
        return " ".join(recognized)
    def health(self):
        return {"ok": os.path.isdir(self.path), "detail": self.path}
