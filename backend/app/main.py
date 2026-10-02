from contextlib import asynccontextmanager
import asyncio, logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.runtime_safety import validate_runtime_configuration
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import engine
import app.models
from app.api.routes import router
from app.scheduler.call_scheduler import scheduler
from app.stt.factory import get_stt_provider
from app.tts.factory import get_tts_provider
from app.llm.factory import get_llm_provider

configure_logging(); s=get_settings(); log=logging.getLogger(__name__)

async def warm_providers():
    # Keep these references scoped to startup. Settings changes can then clear
    # cached provider instances and release an old in-memory speech model.
    try:
        stt=get_stt_provider()
        if stt.health().get("ok") and hasattr(stt,"preload"):
            await asyncio.to_thread(stt.preload); log.info("Vosk model preloaded once")
        else: log.info("Vosk model is not configured; voice STT remains unavailable until configured")
    except Exception as e: log.warning("STT preload skipped: %s",e)
    try:
        tts=get_tts_provider(); tts_health=await tts.health()
        if tts_health.get("ok") and hasattr(tts,"preload"):
            await asyncio.to_thread(tts.preload); log.info("Piper model preloaded once")
        else: log.info("Piper model is not configured; voice TTS remains unavailable until configured")
    except Exception as e: log.warning("TTS preload skipped: %s",e)
    try:
        llm_health=await get_llm_provider().health()
        if not llm_health.get("ok"): log.warning("LLM provider check failed: %s",llm_health.get("detail"))
    except Exception as e: log.warning("LLM provider check failed: %s",e)

@asynccontextmanager
async def lifespan(app:FastAPI):
    validate_runtime_configuration(s)
    Base.metadata.create_all(bind=engine)
    # Preload optional models without keeping startup-local references alive.
    await warm_providers()
    await scheduler.start()
    yield
    await scheduler.stop()

app=FastAPI(title=s.app_name,version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[s.frontend_url,"http://127.0.0.1:3000"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router)
@app.get("/")
def root(): return {"name":s.app_name,"docs":"/docs","health":"/api/health"}
