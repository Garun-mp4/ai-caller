import asyncio, base64, json, logging, time
from fastapi import WebSocket
from app.audio.codec import mulaw_to_pcm16, pcm16_to_mulaw, wav_to_pcm16
from app.audio.resampler import resample_pcm16
from app.audio.vad import EnergyVAD
from app.audio.buffer import SpeechBuffer
from app.stt.factory import get_stt_provider
from app.tts.factory import get_tts_provider
from app.llm.factory import get_llm_provider
from app.agent.parser import parse_agent_decision

log=logging.getLogger(__name__)

async def handle_twilio_media(websocket: WebSocket, on_turn, system_prompt: str, initial_speech: str, on_tts=None):
    await websocket.accept()
    vad=EnergyVAD(); buf=SpeechBuffer(); silence=0; stream_sid=None; speaking=False
    history=[]; outgoing_task=None
    async def send_speech(text: str):
        nonlocal speaking
        speaking=True; started=time.perf_counter()
        try:
            wav=await get_tts_provider().synthesize_wav(text)
            tts_ms=(time.perf_counter()-started)*1000
            if on_tts: await on_tts(tts_ms)
            pcm,rate=wav_to_pcm16(wav); pcm8=resample_pcm16(pcm,rate,8000); ulaw=pcm16_to_mulaw(pcm8)
            for i in range(0,len(ulaw),160):
                payload=base64.b64encode(ulaw[i:i+160]).decode()
                await websocket.send_text(json.dumps({"event":"media","streamSid":stream_sid,"media":{"payload":payload}}))
                await asyncio.sleep(0.02)
        finally: speaking=False
    try:
        while True:
            msg=json.loads(await websocket.receive_text()); event=msg.get("event")
            if event=="start":
                stream_sid=msg.get("start",{}).get("streamSid") or msg.get("streamSid")
                if initial_speech:
                    history.append({"role":"assistant","content":initial_speech})
                    outgoing_task=asyncio.create_task(send_speech(initial_speech))
            elif event=="media":
                pcm=mulaw_to_pcm16(base64.b64decode(msg["media"]["payload"])); speech=vad.is_speech(pcm)
                if speech:
                    if speaking and outgoing_task and not outgoing_task.done():
                        outgoing_task.cancel(); speaking=False
                        await websocket.send_text(json.dumps({"event":"clear","streamSid":stream_sid}))
                    buf.add(resample_pcm16(pcm,8000,16000)); silence=0
                elif len(buf)>3200:
                    silence += 1
                    if silence>=20: # ~400 ms
                        audio=buf.take(); silence=0; t0=time.perf_counter()
                        text=await asyncio.to_thread(get_stt_provider().transcribe_pcm16,audio,16000); stt_ms=(time.perf_counter()-t0)*1000
                        if text:
                            t1=time.perf_counter(); raw=await get_llm_provider().generate(system_prompt,history,text); llm_ms=(time.perf_counter()-t1)*1000
                            decision=parse_agent_decision(raw); history += [{"role":"user","content":text},{"role":"assistant","content":decision.speech}]
                            await on_turn(text,decision,stt_ms,llm_ms)
                            outgoing_task=asyncio.create_task(send_speech(decision.speech))
                            if decision.action in {"end_call","do_not_call","callback"}:
                                try: await outgoing_task
                                except asyncio.CancelledError: pass
                                break
            elif event=="stop": break
    except Exception as e:
        log.exception("media stream failed: %s",e)
    finally:
        if outgoing_task and not outgoing_task.done(): outgoing_task.cancel()
