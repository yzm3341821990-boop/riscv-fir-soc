"""Same compiled FIR, seven independent RAM inputs, exact Q15 audits."""
from pathlib import Path
import struct
from model.fixed_fir import fir_block
from tools.c_demo import load_demo

ROOT=Path(__file__).resolve().parents[1]


def load_fir():
    return load_demo(ROOT/'programs/c_fir_q15',expected_contract='c-fir-q15-block-v1')


def fir_inputs():
    im,m=load_fir()
    base_x=m['samples'];base_h=m['coefficients']
    settings={
        'software_fir':(base_x,base_h),
        'software_fir_impulse':([32767]+[0]*7,base_h),
        'software_fir_ties':([1,-1,3,-3,32767,-32768,0,2],[16384]+[0]*31),
        'software_fir_positive_extreme':([-32768]*8,[-32768]*32),
        'software_fir_negative_extreme':([-32768]*8,[32767]*32),
        'software_fir_zero':([0]*8,[32767,-32768]*16),
        'software_fir_zero_coefficients':(base_x,[0]*32),
    }
    memories={}
    for name,(x,h) in settings.items():
        memory=bytearray(struct.pack('<256I',*im.memory_words))
        struct.pack_into('<8h',memory,m['symbols']['samples'],*x)
        struct.pack_into('<32h',memory,m['symbols']['coefficients'],*h)
        memories[name]=struct.unpack('<256I',memory)
    return memories


def audit_result(result, initial_memory, manifest):
    syms=manifest['symbols']
    initial=struct.pack('<256I',*initial_memory)
    x=struct.unpack_from('<8h',initial,syms['samples'])
    h=struct.unpack_from('<32h',initial,syms['coefficients'])
    expected=fir_block(x,h)
    actual=struct.pack('<256I',*result.memory)
    y=struct.unpack_from('<8h',actual,syms['outputs'])
    acc=struct.unpack_from('<8q',actual,syms['accumulators'])
    if (result.fault or y!=expected.outputs or acc!=expected.accumulators or
            result.registers[2]!=1024 or struct.unpack_from('<I',actual,syms['done'])[0]!=1):
        raise ValueError('compiled software FIR disagrees with Q15 reference or calling contract')
    return y,acc
