import asyncio
import io
import json
import re
import struct
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.audio.codec import wav_to_pcm16
from app.audio.resampler import resample_pcm16
from app.stt.vosk_provider import VoskProvider
from app.tts.piper_provider import PiperProvider


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VOSK_MODEL_PATH = PROJECT_ROOT / "models" / "vosk" / "model"
PIPER_MODEL_PATH = PROJECT_ROOT / "models" / "piper" / "voice.onnx"
PIPER_CONFIG_PATH = PROJECT_ROOT / "models" / "piper" / "voice.onnx.json"
FLEURS_SAMPLES = Path(__file__).parent / "assets" / "fleurs-ru-dev"


def _normalize(text: str) -> list[str]:
    return re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).split()


def _wave_pcm16(path: Path) -> tuple[bytes, int]:
    pcm, sample_rate = wav_to_pcm16(path.read_bytes())
    if sample_rate != 16000:
        pcm = resample_pcm16(pcm, sample_rate, 16000)
        sample_rate = 16000
    return pcm, sample_rate


def _short_wav() -> bytes:
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(struct.pack("<220h", *([700] * 220)))
    return target.getvalue()


@pytest.fixture(scope="module")
def loaded_vosk() -> VoskProvider:
    if not VOSK_MODEL_PATH.is_dir():
        pytest.skip("Download the optional Russian Vosk model to models/vosk/model")
    provider = VoskProvider()
    provider.path = str(VOSK_MODEL_PATH)
    assert provider.health()["ok"] is True
    assert provider.preload() is provider
    return provider


@pytest.fixture(scope="module")
def loaded_piper() -> PiperProvider:
    if not PIPER_MODEL_PATH.is_file() or not PIPER_CONFIG_PATH.is_file():
        pytest.skip("Download the optional Russian Piper voice to models/piper")
    provider = PiperProvider()
    provider.model = str(PIPER_MODEL_PATH)
    provider.config = str(PIPER_CONFIG_PATH)
    assert asyncio.run(provider.health())["ok"] is True
    assert provider.preload() is provider
    return provider


def test_vosk_model_load_is_thread_safe_and_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import vosk

    calls = []
    model_directory = tmp_path / "model"
    model_directory.mkdir()

    class ModelStub:
        def __init__(self, path: str):
            calls.append(path)
            time.sleep(0.02)

    monkeypatch.setattr(vosk, "Model", ModelStub)
    provider = VoskProvider()
    provider.path = str(model_directory)

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: provider._ensure_model(), range(5)))

    assert len(calls) == 1
    assert all(model is results[0] for model in results)


def test_vosk_raises_a_clear_error_for_missing_model(tmp_path: Path):
    provider = VoskProvider()
    provider.path = str(tmp_path / "missing")

    with pytest.raises(RuntimeError, match="Vosk model not found"):
        provider.preload()


def test_vosk_returns_empty_for_empty_audio_without_loading_model():
    provider = VoskProvider()
    provider.path = "/does/not/exist"

    assert provider.transcribe_pcm16(b"") == ""


@pytest.mark.parametrize("pcm,sample_rate", [(b"\x00", 16000), (b"\x00\x00", 0)])
def test_vosk_rejects_malformed_audio(pcm: bytes, sample_rate: int):
    provider = VoskProvider()
    provider.path = "/does/not/exist"

    with pytest.raises(ValueError):
        provider.transcribe_pcm16(pcm, sample_rate)


def test_vosk_joins_completed_and_final_utterance_segments(monkeypatch: pytest.MonkeyPatch):
    import vosk

    class RecognizerStub:
        def __init__(self, model, sample_rate):
            assert sample_rate == 16000
            self.frames = 0

        def AcceptWaveform(self, frame: bytes) -> bool:
            self.frames += 1
            return self.frames == 1

        def Result(self) -> str:
            return json.dumps({"text": "первый сегмент"})

        def FinalResult(self) -> str:
            return json.dumps({"text": "последний сегмент"})

    monkeypatch.setattr(vosk, "KaldiRecognizer", RecognizerStub)
    provider = VoskProvider()
    provider._model = object()

    assert provider.transcribe_pcm16(b"\x00\x00" * 2500) == "первый сегмент последний сегмент"


@pytest.mark.model_integration
@pytest.mark.parametrize(
    "filename,reference",
    [
        (
            "15303984925433418748.wav",
            "в новом царстве древних египтян восхищались памятниками созданными их предшественниками более тысячи лет назад",
        ),
        (
            "15171374791724408002.wav",
            "хотя внутри здания в тот момент когда в него врезался автомобиль находились три человека никто не пострадал",
        ),
    ],
)
def test_vosk_transcribes_online_russian_speech(loaded_vosk: VoskProvider, filename: str, reference: str):
    pcm, sample_rate = _wave_pcm16(FLEURS_SAMPLES / filename)
    actual = _normalize(loaded_vosk.transcribe_pcm16(pcm, sample_rate))
    expected = set(_normalize(reference))

    assert actual
    assert len(expected.intersection(actual)) / len(expected) >= 0.7


@pytest.mark.model_integration
@pytest.mark.asyncio
async def test_piper_synthesizes_valid_audio_and_vosk_recognizes_it(
    loaded_piper: PiperProvider, loaded_vosk: VoskProvider
):
    wav_bytes = await loaded_piper.synthesize_wav("Здравствуйте. Это тест синтеза и распознавания русской речи.")
    pcm, sample_rate = wav_to_pcm16(wav_bytes)
    recognized_pcm = resample_pcm16(pcm, sample_rate, 16000)
    actual = _normalize(loaded_vosk.transcribe_pcm16(recognized_pcm, 16000))

    assert pcm
    assert sample_rate == 22050
    assert len(pcm) % 2 == 0
    # TTS synthesis and small-model decoding vary slightly across CPU runs;
    # keep the smoke check semantic without requiring exact word-for-word output.
    assert "здравствуйте" in actual and "речи" in actual, actual
    assert len(actual) >= 4, actual


@pytest.mark.asyncio
async def test_piper_cli_removes_temporary_wav_when_process_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import app.tts.piper_provider as piper_module

    model = tmp_path / "voice.onnx"
    model.write_bytes(b"model")
    output = tmp_path / "generated.wav"

    class TempFileStub:
        name = str(output)

        def __enter__(self):
            output.write_bytes(b"")
            return self

        def __exit__(self, *args):
            return False

    async def fail_to_start(*args, **kwargs):
        raise OSError("binary not executable")

    provider = PiperProvider()
    provider.binary = "piper"
    provider.model = str(model)
    provider.config = None
    monkeypatch.setattr(provider, "_python_available", lambda: False)
    monkeypatch.setattr(piper_module.tempfile, "NamedTemporaryFile", lambda **kwargs: TempFileStub())
    monkeypatch.setattr(piper_module.asyncio, "create_subprocess_exec", fail_to_start)

    with pytest.raises(OSError, match="not executable"):
        await provider.synthesize_wav("тест")

    assert not output.exists()


@pytest.mark.asyncio
async def test_piper_cli_fallback_returns_audio_and_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import app.tts.piper_provider as piper_module

    model = tmp_path / "voice.onnx"
    model.write_bytes(b"model")
    output = tmp_path / "generated.wav"
    command = []

    class TempFileStub:
        name = str(output)

        def __enter__(self):
            output.write_bytes(b"")
            return self

        def __exit__(self, *args):
            return False

    class ProcessStub:
        returncode = 0

        async def communicate(self, text):
            assert text == "тест".encode("utf-8")
            output.write_bytes(_short_wav())
            return b"", b""

    async def start_process(*args, **kwargs):
        command.extend(args)
        return ProcessStub()

    provider = PiperProvider()
    provider.binary = "piper"
    provider.model = str(model)
    provider.config = None
    monkeypatch.setattr(provider, "_python_available", lambda: False)
    monkeypatch.setattr(piper_module.tempfile, "NamedTemporaryFile", lambda **kwargs: TempFileStub())
    monkeypatch.setattr(piper_module.asyncio, "create_subprocess_exec", start_process)

    result = await provider.synthesize_wav("тест")

    assert wav_to_pcm16(result)[1] == 22050
    assert command[0] == "piper"
    assert command[command.index("--model") + 1] == str(model)
    assert not output.exists()


@pytest.mark.model_integration
@pytest.mark.asyncio
async def test_piper_preloads_and_reports_model_readiness(loaded_piper: PiperProvider):
    assert (await loaded_piper.health())["ok"] is True
    assert loaded_piper._voice is not None
