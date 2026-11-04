"""Separate functional DSP replay and independent deterministic-stream anchor."""
import math,struct
from model.dsp_machine import steps
from model.dsp_peripheral import Peripheral,s32
from model.fixed_fir import fir_block
from tools.app_program import program_image
COEFFICIENTS=(52,62,64,35,-52,-208,-402,-556,-552,-271,363,1343,2552,3786,4799,5371,5371,4799,3786,2552,1343,363,-271,-552,-556,-402,-208,-52,35,64,62,52)
SIGNAL=tuple(round(32768*(.45*math.sin(2*math.pi*i/48)+.35*math.sin(22*math.pi*i/48))) for i in range(48))
def anchor(n):
    if type(n) is not int or not 1<=n<=262144:raise ValueError('N must be 1..262144')
    # NumPy int64 is a second implementation, independent of the C and RTL.
    import numpy as np
    x=np.resize(np.asarray(SIGNAL,dtype=np.int64),n);a=np.convolve(x,np.asarray(COEFFICIENTS,dtype=np.int64))[:n]
    y=np.clip(np.where(a<0,-((-a+16384)>>15),(a+16384)>>15),-32768,32767).tolist()
    checksum=0
    for v in y:checksum=(checksum*16777619+v)&0xffffffff
    return [n,(n+224)//225]+[s32(checksum)]*3+[0,min(n,96)]+y[-96:]

def initial(elf,n):
    anchor_n=anchor(n);image=program_image(elf);ram=list(image.memory_words)
    ram[:326]=[0]*326;ram[:3]=[0x43505535,1,n]
    return image,ram,anchor_n

def replay(elf,n,max_steps=2000000):
    image,ram,expected=initial(elf,n);p=Peripheral();g=steps(image.program_words,image.symbols['_exit_commit'],ram,max_steps,peripheral=p)
    item=next(g);count=0
    while True:
        if item[0]=='E':
            if item[1][0]!='I':raise ValueError('DSP application trapped')
            count+=1
        elif item[0] not in ('B','M'):raise ValueError('Unexpected timer/SYSTEM access')
        try:item=g.send(False if item[0]=='B' else None)
        except StopIteration as done:final=done.value;break
    mem=final['memory'];actual=[s32(v) for v in mem[131:131+mem[130]]]
    if actual!=expected or mem[259:261]!=[1,0] or p.intervals!=[(n+224)//225]*3:raise ValueError('DSP C differs from independent stream anchor')
    return dict(status='passed',source_kind='isa_reference',output=actual,commits=count,intervals=p.intervals,starts=p.starts,memory=mem,registers=final['registers'])
