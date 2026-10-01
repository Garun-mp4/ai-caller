import io, wave, struct
MU = 255

def mulaw_byte_to_pcm16(b: int) -> int:
    b = ~b & 0xFF
    sign = b & 0x80
    exponent = (b >> 4) & 0x07
    mantissa = b & 0x0F
    sample = ((mantissa << 3) + 0x84) << exponent
    sample -= 0x84
    return -sample if sign else sample

def mulaw_to_pcm16(data: bytes) -> bytes:
    return b"".join(struct.pack("<h", max(-32768,min(32767,mulaw_byte_to_pcm16(b)))) for b in data)

def pcm16_to_mulaw_sample(sample: int) -> int:
    BIAS=0x84; CLIP=32635
    sign=0x80 if sample < 0 else 0
    if sample < 0: sample=-sample
    sample=min(sample,CLIP)+BIAS
    exponent=7
    mask=0x4000
    while exponent>0 and not (sample & mask): exponent-=1; mask >>= 1
    mantissa=(sample >> (exponent+3)) & 0x0F
    return (~(sign | (exponent<<4) | mantissa)) & 0xFF

def pcm16_to_mulaw(data: bytes) -> bytes:
    samples=struct.unpack("<"+"h"*(len(data)//2), data[:len(data)//2*2])
    return bytes(pcm16_to_mulaw_sample(s) for s in samples)

def wav_to_pcm16(wav_bytes: bytes):
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        if w.getsampwidth()!=2 or w.getnchannels()!=1: raise ValueError("Piper WAV must be mono PCM16")
        return w.readframes(w.getnframes()), w.getframerate()
