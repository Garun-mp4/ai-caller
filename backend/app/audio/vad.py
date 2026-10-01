import struct, math
class EnergyVAD:
    def __init__(self, threshold: int = 650): self.threshold=threshold
    def is_speech(self, pcm16: bytes) -> bool:
        if len(pcm16)<2: return False
        s=struct.unpack("<"+"h"*(len(pcm16)//2), pcm16[:len(pcm16)//2*2])
        rms=math.sqrt(sum(x*x for x in s)/max(1,len(s)))
        return rms >= self.threshold
