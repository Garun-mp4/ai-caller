import struct

def resample_pcm16(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    if src_rate == dst_rate: return data
    samples=list(struct.unpack("<"+"h"*(len(data)//2), data[:len(data)//2*2]))
    if not samples: return b""
    out_len=max(1,int(len(samples)*dst_rate/src_rate)); out=[]
    for i in range(out_len):
        pos=i*src_rate/dst_rate; j=int(pos); frac=pos-j
        a=samples[min(j,len(samples)-1)]; b=samples[min(j+1,len(samples)-1)]
        out.append(int(a+(b-a)*frac))
    return struct.pack("<"+"h"*len(out), *out)
