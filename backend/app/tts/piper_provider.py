import asyncio, io, os, shutil, tempfile, threading, wave
from .base import TTSProvider
from app.core.config import get_settings
from app.services.settings_service import runtime_setting

class PiperProvider(TTSProvider):
    _voice = None
    _lock = threading.Lock()
    def __init__(self):
        s=get_settings(); self.binary=shutil.which(s.piper_binary); self.model=runtime_setting("piper_model_path", s.piper_model_path); self.config=s.piper_config_path

    def _ensure_voice(self):
        if self.__class__._voice is None:
            with self.__class__._lock:
                if self.__class__._voice is None:
                    if not os.path.isfile(self.model):
                        raise RuntimeError(f"Piper model not found: {self.model}")
                    try:
                        from piper.voice import PiperVoice
                    except ImportError:
                        try:
                            from piper import PiperVoice
                        except ImportError as e:
                            raise RuntimeError("piper-tts Python package is not installed") from e
                    kwargs={}
                    if self.config and os.path.isfile(self.config): kwargs["config_path"]=self.config
                    self.__class__._voice=PiperVoice.load(self.model, **kwargs)
        return self.__class__._voice

    def preload(self):
        self._ensure_voice(); return self

    async def health(self):
        model_ok=os.path.isfile(self.model)
        return {"ok": model_ok and (bool(self.binary) or self._python_available()), "detail": {"python":self._python_available(),"binary": bool(self.binary), "model": self.model}}

    def _python_available(self):
        try:
            import piper  # noqa: F401
            return True
        except ImportError:
            return False

    def _synthesize_in_process(self, text: str) -> bytes:
        voice=self._ensure_voice(); out=io.BytesIO()
        with wave.open(out,"wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        return out.getvalue()

    async def synthesize_wav(self, text: str) -> bytes:
        if self._python_available() and os.path.isfile(self.model):
            return await asyncio.to_thread(self._synthesize_in_process, text)
        if not self.binary or not os.path.isfile(self.model):
            raise RuntimeError("Piper is not configured: install piper-tts or Piper CLI and configure the model path")
        # Compatibility fallback. The preferred piper-tts path above keeps the model resident in memory.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out_path=f.name
        args=[self.binary,"--model",self.model,"--output_file",out_path]
        if self.config and os.path.isfile(self.config): args += ["--config", self.config]
        proc=await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _,err=await proc.communicate(text.encode("utf-8"))
        if proc.returncode != 0: raise RuntimeError(err.decode(errors="ignore")[-500:])
        try:
            return open(out_path,"rb").read()
        finally:
            try: os.unlink(out_path)
            except OSError: pass
