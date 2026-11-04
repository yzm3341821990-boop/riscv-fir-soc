"""Generic RAM-only C ABI validation and independent bounded scalar replay."""
import struct
from tools.app_elf import read_app_elf
from model.app_machine import steps
from model.tiny_cpu import REGISTER_OPERATIONS,BRANCH_OPERATIONS,LOAD_OPERATIONS,STORE_OPERATIONS,IMMEDIATE_OPERATIONS,SHIFT_IMMEDIATE_OPERATIONS

def signed(v):return v if v<2**31 else v-2**32

def program_image(elf):
    if not isinstance(elf,bytes) or len(elf)>262144:raise ValueError('ELF must be <=256 KiB')
    image=read_app_elf(elf);length=4*len(image.program_words)
    for word in image.program_words:
        op,f3,f7=word&127,(word>>12)&7,word>>25
        legal=op in (0x37,0x17,0x6f) or op==0x67 and f3==0 or op==0x63 and f3 in BRANCH_OPERATIONS.values() or op==3 and f3 in LOAD_OPERATIONS.values() or op==0x23 and f3 in STORE_OPERATIONS.values() or op==0x33 and ((f7,f3) in REGISTER_OPERATIONS.values() or f7==1)
        if op==0x13:legal=(f7,f3) in SHIFT_IMMEDIATE_OPERATIONS.values() if f3 in (1,5) else f3 in IMMEDIATE_OPERATIONS.values()
        if not legal:raise ValueError(f'Unsupported application instruction {word:08X}; RAM-only RV32IM profile')
    symbols=image.symbols
    if any(symbols.get(n)!=v for n,v in {'job':0x10000000,'_stack_top':0x10008000,'_program_end':length,'_start':0}.items()):raise ValueError('Use the CPU5 startup, header and linker layout')
    pc=symbols.get('_exit_commit',-1)
    if not 0<=pc<length or pc%4:raise ValueError('Missing CRT exit commit')
    w=image.program_words[pc//4]
    offset=((w>>31)<<20)|(w&0xff000)|(((w>>20)&1)<<11)|(((w>>21)&1023)<<1)
    if offset&(1<<20):offset-=1<<21
    if w&0xfff!=0x6f or pc+offset!=length:raise ValueError('CRT exit must jump to end sentinel')
    if symbols.get('_data_end',0)>0x10007800:raise ValueError('Insufficient reserved stack')
    return image

def prepare_job(elf,values):
    if not isinstance(values,(list,tuple)) or len(values)>128 or any(type(v) is not int or not -2**31<=v<2**31 for v in values):raise ValueError('Input needs at most 128 signed32 integers')
    image=program_image(elf);memory=list(image.memory_words)
    memory[:326]=[0]*326;memory[0:2]=[0x43505535,len(values)];memory[2:2+len(values)]=[v&0xffffffff for v in values]
    gen=steps(image.program_words,image.symbols['_exit_commit'],memory,max_steps=250000)
    state=next(gen);commits=0;last=None
    while True:
        kind=state[0]
        if kind=='B':
            if not 0<=state[1]<len(image.program_words)*4:raise ValueError('Application escaped its text')
        elif kind=='E':
            if state[1][0]!='I':raise ValueError('Application raised an exception')
            commits+=1;last=state[1]
        elif kind=='M':
            if not 0x10000000<=state[1][1]<0x10008000:raise ValueError('Application accessed outside high RAM profile')
        else:raise ValueError('Application attempted peripheral or SYSTEM access')
        try:state=gen.send(False if kind=='B' else None)
        except StopIteration as done:final=done.value;break
        except RuntimeError as exc:raise ValueError(str(exc)) from exc
    ram=final['memory'];n=ram[130];textlen=ram[261]
    if ram[259]!=1 or n>128 or textlen>256 or ram[260]!=final['registers'][10]:raise ValueError('Application ABI completion/result bounds differ')
    console=struct.pack('<64I',*ram[262:326])[:textlen]
    reference=dict(output=[signed(v) for v in ram[131:131+n]],console_bytes=console,console=console.decode('utf-8',errors='replace'),status=ram[260],commits=commits,last=last,
        memory=ram,registers=final['registers'],csrs=final['csrs'])
    return image,memory,reference
