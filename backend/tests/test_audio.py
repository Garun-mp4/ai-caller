import io
import struct
import wave

import pytest

from app.audio.buffer import SpeechBuffer
from app.audio.codec import mulaw_to_pcm16, pcm16_to_mulaw, wav_to_pcm16
from app.audio.resampler import resample_pcm16
from app.audio.vad import EnergyVAD


def make_pcm16(samples: list[int]) -> bytes:
    return struct.pack("<" + "h" * len(samples), *samples)


def make_wav(samples: list[int], sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(sample_rate)
        if sample_width == 2:
            output.writeframes(make_pcm16(samples))
        else:
            output.writeframes(bytes(samples))
    return target.getvalue()


def test_mulaw_conversion_preserves_sample_count_and_decodes_silence():
    encoded = pcm16_to_mulaw(make_pcm16([0, 1000, -1000, 12000, -12000]))

    assert len(encoded) == 5
    assert mulaw_to_pcm16(encoded) == make_pcm16([0, 988, -988, 11900, -11900])
    assert mulaw_to_pcm16(b"\xff\xff") == b"\x00\x00\x00\x00"


@pytest.mark.parametrize("pcm", [b"\x00", b"\x00\x00\x01"])
def test_pcm16_to_mulaw_rejects_partial_samples(pcm: bytes):
    with pytest.raises(ValueError, match="complete 16-bit samples"):
        pcm16_to_mulaw(pcm)


def test_resampler_preserves_duration_and_identity_rate():
    source = make_pcm16([0, 1000, 2000, 3000])

    assert resample_pcm16(source, 8000, 8000) == source
    assert len(resample_pcm16(source, 8000, 16000)) == 2 * len(source)
    assert len(resample_pcm16(source, 16000, 8000)) == len(source) // 2


@pytest.mark.parametrize("src_rate,dst_rate", [(0, 16000), (16000, 0), (-1, 8000)])
def test_resampler_rejects_nonpositive_sample_rates(src_rate: int, dst_rate: int):
    with pytest.raises(ValueError, match="positive"):
        resample_pcm16(b"\x00\x00", src_rate, dst_rate)


def test_resampler_rejects_partial_pcm16_sample_even_for_identity_rate():
    with pytest.raises(ValueError, match="complete 16-bit samples"):
        resample_pcm16(b"\x00", 16000, 16000)


def test_energy_vad_distinguishes_silence_from_speech():
    vad = EnergyVAD(threshold=650)

    assert vad.is_speech(b"") is False
    assert vad.is_speech(b"\x00") is False
    assert vad.is_speech(make_pcm16([0] * 160)) is False
    assert vad.is_speech(make_pcm16([1200, -1200] * 80)) is True


def test_speech_buffer_caps_old_audio_and_take_clears_it():
    buffer = SpeechBuffer(max_bytes=5)
    buffer.add(b"abc")
    buffer.add(b"def")

    assert len(buffer) == 5
    assert buffer.take() == b"bcdef"
    assert len(buffer) == 0
    assert buffer.take() == b""


def test_wav_to_pcm16_reads_only_mono_uncompressed_pcm16():
    pcm = make_pcm16([0, 100, -100])

    assert wav_to_pcm16(make_wav([0, 100, -100])) == (pcm, 16000)


@pytest.mark.parametrize(
    "wav_bytes",
    [make_wav([0, 0], channels=2), make_wav([0, 255], sample_width=1)],
)
def test_wav_to_pcm16_rejects_non_mono_or_non_16bit_audio(wav_bytes: bytes):
    with pytest.raises(ValueError, match="mono PCM16"):
        wav_to_pcm16(wav_bytes)
