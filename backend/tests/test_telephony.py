import asyncio
import base64
import io
import json
import struct
import wave

import pytest

from app.audio.codec import pcm16_to_mulaw
from app.telephony.mock_provider import MockTelephonyProvider


@pytest.mark.asyncio
async def test_mock_telephony():
    r=await MockTelephonyProvider().create_call("+79991111111",12); assert r["sid"]=="MOCK-12"


class FakeMediaWebSocket:
    def __init__(self, messages, wait_for_media_before_stop=False):
        self.messages = list(messages)
        self.sent = []
        self.accepted = False
        self.media_sent = asyncio.Event()
        self.wait_for_media_before_stop = wait_for_media_before_stop

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        raw = self.messages.pop(0)
        event = json.loads(raw).get("event")
        if event == "stop" and self.wait_for_media_before_stop:
            await asyncio.wait_for(self.media_sent.wait(), timeout=1)
        else:
            await asyncio.sleep(0.002)
        return raw

    async def send_text(self, message):
        event = json.loads(message)
        self.sent.append(event)
        if event.get("event") == "media":
            self.media_sent.set()


def _twilio_message(event: str, **values) -> str:
    return json.dumps({"event": event, **values})


def _media_message(pcm16: bytes) -> str:
    payload = base64.b64encode(pcm16_to_mulaw(pcm16)).decode("ascii")
    return _twilio_message("media", media={"payload": payload})


def _short_pcm16_wav() -> bytes:
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(struct.pack("<160h", *([800] * 160)))
    return target.getvalue()


@pytest.mark.asyncio
async def test_twilio_media_round_trip_decodes_speech_and_sends_20ms_audio(monkeypatch):
    import app.telephony.media_stream as media_stream

    class STTStub:
        def transcribe_pcm16(self, pcm, sample_rate):
            assert len(pcm) > 3200
            assert sample_rate == 16000
            return "перезвоните завтра"

    class LLMStub:
        async def generate(self, system_prompt, history, user_text):
            assert user_text == "перезвоните завтра"
            return json.dumps({"speech": "Хорошо, договорились.", "action": "continue"}, ensure_ascii=False)

    class TTSStub:
        def __init__(self):
            self.calls = 0
            self.texts = []

        async def synthesize_wav(self, text):
            self.calls += 1
            self.texts.append(text)
            assert text == "Хорошо, договорились."
            return _short_pcm16_wav()

    spoken_frame = struct.pack("<160h", *([8000] * 160))
    silent_frame = b"\x00\x00" * 160
    messages = [_twilio_message("start", start={"streamSid": "MZ-test"})]
    messages.extend(_media_message(spoken_frame) for _ in range(10))
    messages.extend(_media_message(silent_frame) for _ in range(20))
    messages.append(_twilio_message("stop"))
    websocket = FakeMediaWebSocket(messages, wait_for_media_before_stop=True)
    turns = []
    tts_times = []
    tts_provider = TTSStub()

    async def on_turn(text, decision, stt_ms, llm_ms):
        turns.append((text, decision.action))

    async def on_tts(duration_ms):
        tts_times.append(duration_ms)

    monkeypatch.setattr(media_stream, "get_stt_provider", lambda: STTStub())
    monkeypatch.setattr(media_stream, "get_llm_provider", lambda: LLMStub())
    monkeypatch.setattr(media_stream, "get_tts_provider", lambda: tts_provider)

    await media_stream.handle_twilio_media(websocket, on_turn, "system", "", on_tts)

    assert websocket.accepted is True
    assert turns == [("перезвоните завтра", "continue")]
    assert tts_provider.calls == 1
    assert tts_provider.texts == ["Хорошо, договорились."]
    assert len(tts_times) == 1
    outgoing = [event for event in websocket.sent if event["event"] == "media"]
    assert len(outgoing) == 1
    assert outgoing[0]["streamSid"] == "MZ-test"
    assert len(base64.b64decode(outgoing[0]["media"]["payload"])) == 160


@pytest.mark.asyncio
async def test_twilio_media_clears_pending_tts_on_barge_in(monkeypatch):
    import app.telephony.media_stream as media_stream

    class BlockingTTS:
        def __init__(self):
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def synthesize_wav(self, text):
            self.started.set()
            try:
                await asyncio.Future()
            finally:
                self.cancelled.set()

    provider = BlockingTTS()
    websocket = FakeMediaWebSocket(
        [
            _twilio_message("start", start={"streamSid": "MZ-barge"}),
            _media_message(struct.pack("<160h", *([8000] * 160))),
            _twilio_message("stop"),
        ]
    )
    monkeypatch.setattr(media_stream, "get_tts_provider", lambda: provider)

    async def on_turn(*args):
        return None

    await media_stream.handle_twilio_media(websocket, on_turn, "system", "Добрый день.")

    assert provider.started.is_set()
    assert provider.cancelled.is_set()
    assert any(event["event"] == "clear" and event["streamSid"] == "MZ-barge" for event in websocket.sent)
