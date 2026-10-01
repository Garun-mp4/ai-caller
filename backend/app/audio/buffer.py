class SpeechBuffer:
    def __init__(self, max_bytes=32000*15): self.data=bytearray(); self.max_bytes=max_bytes
    def add(self, chunk: bytes):
        self.data.extend(chunk)
        if len(self.data)>self.max_bytes: del self.data[:-self.max_bytes]
    def take(self) -> bytes:
        d=bytes(self.data); self.data.clear(); return d
    def __len__(self): return len(self.data)
