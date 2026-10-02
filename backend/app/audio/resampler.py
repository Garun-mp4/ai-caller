import struct

def resample_pcm16(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    if len(data) % 2:
        raise ValueError("PCM16 audio must contain complete 16-bit samples")
    if src_rate <= 0 or dst_rate <= 0:
        raise ValueError("Sample rates must be positive")
    if src_rate == dst_rate: return data
    samples=list(struct.unpack("<"+"h"*(len(data)//2), data))
    if not samples: return b""
    out_len=max(1,int(len(samples)*dst_rate/src_rate)); out=[]
    for i in range(out_len):
        pos=i*src_rate/dst_rate; j=int(pos); frac=pos-j
        a=samples[min(j,len(samples)-1)]; b=samples[min(j+1,len(samples)-1)]
        out.append(int(a+(b-a)*frac))
    return struct.pack("<"+"h"*len(out), *out)
