"""Functional DSP MMIO oracle. Immediate completion is NOT a timing model."""
from model.fixed_fir import fir_block
BASE=0x40003000
MARKER=0x40004000
def s32(v):return v if v<0x80000000 else v-0x100000000

class Peripheral:
    def __init__(self):
        self.memory=None;self.coefficients=[0]*32;self.mask=set();self.config={8:0,12:0,16:0}
        self.done=False;self.error=0;self.written=0;self.starts=0;self.active=0;self.intervals=[0,0,0]
    def write(self,addr,data):
        if addr==MARKER:
            if data==0 and self.active:self.intervals[self.active-1]+=1;self.active=0
            elif data in (1,2,3) and not self.active:self.active=data
            else:raise ValueError('Invalid profiler marker ordering')
            return
        off=addr-BASE
        if 256<=off<=380 and off%4==0:
            v=s32(data)
            if not -32768<=v<=32767:raise ValueError('Coefficient is not signed16')
            self.coefficients[(off-256)//4]=v;self.mask.add((off-256)//4)
        elif off in self.config:self.config[off]=data
        elif off==0 and data in (0,2):
            if data==2:self.done=False;self.error=0
        elif off==0 and data==1:
            src,dst,n=(self.config[k] for k in (8,12,16))
            if not 1<=n<=4096 or src%4 or dst%4 or max(src,dst)+4*n>32768 or min(src,dst)+4*n>max(src,dst) or len(self.mask)!=32:
                raise ValueError('Invalid FIR DMA configuration')
            x=[s32(v) for v in self.memory[src//4:src//4+n]]
            if any(not -32768<=v<=32767 for v in x):raise ValueError('FIR input is not signed16')
            y=fir_block(x,self.coefficients).outputs
            self.memory[dst//4:dst//4+n]=[v&0xffffffff for v in y]
            self.written=n;self.done=True;self.starts+=1
        else:raise ValueError('Unsupported DSP write')
    def read(self,addr):
        off=addr-BASE
        if off in self.config:return self.config[off]
        if 256<=off<=380 and off%4==0:return self.coefficients[(off-256)//4]&0xffffffff
        if off in (0,4,24,28):return {0:0,4:2*int(self.done),24:self.written,28:self.error}[off]
        raise ValueError('Timing-dependent or unsupported peripheral read')
