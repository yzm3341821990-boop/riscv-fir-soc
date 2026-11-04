"""Scalar instruction replay for step33; ISA arithmetic inherited from step28.

The harness supplies independently calculated timer reads at recorded acceptance
edges. Interrupt entry is checked against the oracle's next PC, never the RTL mepc.
No pipeline state or actual load/CSR return value is used to predict ISA effects.
"""
TIMER_ADDRESSES={0x02004000,0x02004004,0x0200BFF8,0x0200BFFC}
from model.tiny_cpu import (MASK, REGISTER_OPERATIONS, IMMEDIATE_OPERATIONS,
    SHIFT_IMMEDIATE_OPERATIONS, LOAD_OPERATIONS, STORE_OPERATIONS, _alu)

CSR_NAMES={0x304:'mie',0x344:'mip',0x300:'mstatus',0x305:'mtvec',0x340:'mscratch',0x341:'mepc',0x342:'mcause',0x343:'mtval'}

def sext(value,bits):
    return value-(1<<bits) if value&(1<<(bits-1)) else value

def steps(program, end_pc, initial=(), max_steps=100000):
    if len(program)>4096 or len(initial)>8192: raise ValueError('Memory image exceeds core capacity')
    if any(type(v) is not int or not 0<=v<=MASK for v in (*program,*initial)):
        raise ValueError('Images must contain unsigned32 words')
    if end_pc<0 or end_pc>=16384 or end_pc%4: raise ValueError('Invalid test end PC')
    rom=list(program)+[0x13]*(4096-len(program))
    memory=list(initial)+[0]*(8192-len(initial)); regs=[0]*32
    csrs={a:0 for a in CSR_NAMES};csrs[0x300]=0x1800
    events=[];requests=[];pc=0
    for _ in range(max_steps):
        interrupt = yield ('B',pc,dict(csrs))
        if interrupt:
            if not (csrs[0x300]&8 and csrs[0x304]&128):
                raise ValueError('IRQ_WITH_MASKED_ENABLE')
            csrs[0x341]=pc;csrs[0x342]=0x80000007;csrs[0x343]=0
            csrs[0x300]=(csrs[0x300]&~0x88)|((csrs[0x300]&8)<<4)
            yield ('E',('T',pc,0x80000007,0))
            pc=csrs[0x305]
            continue
        error=None;instruction=rom[pc//4] if pc<16384 and pc%4==0 else 0
        opcode=instruction&127;f=(instruction>>12)&7;f7=instruction>>25
        rd=(instruction>>7)&31;rs1=(instruction>>15)&31;rs2=(instruction>>20)&31
        first=regs[rs1];second=regs[rs2];value=0;next_pc=(pc+4)&MASK
        if pc>=16384 or pc%4: error=(1,pc)
        elif opcode==0x73:
            if instruction==0x73: error=(11,0)
            elif instruction==0x100073: error=(3,pc)
            elif instruction==0x30200073:
                next_pc=csrs[0x341];rd=0
                csrs[0x300]=(csrs[0x300]&~0x88)|((csrs[0x300]>>4)&8)|0x80
            elif f in (1,2,3,5,6,7) and instruction>>20 in csrs:
                address=instruction>>20
                pending=yield ('C',pc,address)
                if address==0x344:csrs[address]=128 if pending else 0
                value=csrs[address]
                operand=rs1 if f>=5 else first
                mode=f&3
                writing=mode==1 or rs1!=0
                update=operand if mode==1 else value|operand if mode==2 else value&~operand
                if writing:
                    update&=MASK
                    if address in (0x305,0x341):update&=~3
                    if address==0x300:update=(update&0x88)|0x1800
                    if address==0x304:update&=128
                    if address==0x344:update=value
                    csrs[address]=update
            else:error=(2,instruction)
        elif opcode in (0x37,0x17):
            value=((instruction&0xFFFFF000)+(pc if opcode==0x17 else 0))&MASK
        elif opcode in (0x6F,0x67,0x63):
            taken=True
            if opcode==0x6F:
                offset=sext(((instruction>>31)<<20)|(instruction&0xFF000)|
                    (((instruction>>20)&1)<<11)|(((instruction>>21)&1023)<<1),21)
                target=(pc+offset)&MASK;value=next_pc
            elif opcode==0x67 and f==0:
                target=((first+sext(instruction>>20,12))&MASK)&~1;value=next_pc
            elif opcode==0x63 and f in (0,1,4,5,6,7):
                offset=sext(((instruction>>31)<<12)|(((instruction>>7)&1)<<11)|
                    (((instruction>>25)&63)<<5)|(((instruction>>8)&15)<<1),13)
                target=(pc+offset)&MASK;rd=0
                taken={0:first==second,1:first!=second,4:sext(first,32)<sext(second,32),
                       5:sext(first,32)>=sext(second,32),6:first<second,7:first>=second}[f]
            else: error=(2,instruction);target=0
            if error is None and taken:
                if target%4:error=(0,target)
                else:next_pc=target
        elif opcode in (3,0x23):
            load=opcode==3
            valid=f in (LOAD_OPERATIONS.values() if load else STORE_OPERATIONS.values())
            offset=instruction>>20 if load else ((instruction>>25)<<5)|((instruction>>7)&31)
            address=(first+sext(offset,12))&MASK
            width=1<<(f&3) if valid else 1
            if not valid:error=(2,instruction)
            elif address%width:error=(4 if load else 6,address)
            elif not (address+width<=32768 or 0x10000000<=address and address+width<=0x10008000 or width==4 and address in TIMER_ADDRESSES):error=(5 if load else 7,address)
            else:
                lane=address%4;be=((1<<width)-1)<<lane
                mask=((1<<(8*width))-1)<<(8*lane)
                if load:
                    raw=(yield ('L',address,be)) if address in TIMER_ADDRESSES else memory[(address&0x7fff)//4]
                    request=('R',address,raw,be);requests.append(request);yield ('M',request)
                    value=(raw&mask)>>(8*lane)
                    if f in (0,1):value=sext(value,8*width)
                else:
                    data=(second<<(8*lane))&mask
                    if address not in TIMER_ADDRESSES:memory[(address&0x7fff)//4]=(memory[(address&0x7fff)//4]&~mask)|data
                    request=('W',address,data,be);requests.append(request);yield ('M',request);rd=0
        elif opcode==0x33 and f7==1:
            from model.rv32m import OPERATIONS,evaluate
            value=evaluate(OPERATIONS[f],first,second)
        elif opcode in (0x13,0x33):
            operation=None;operand=second
            if opcode==0x33:
                operation=next((n for n,e in REGISTER_OPERATIONS.items() if e==(f7,f)),None)
            elif f in (1,5):
                n=next((n for n,e in SHIFT_IMMEDIATE_OPERATIONS.items() if e==(f7,f)),None)
                operation=n[:-1] if n else None;operand=rs2
            else:
                n=next((n for n,e in IMMEDIATE_OPERATIONS.items() if e==f),None)
                operation='SLTU' if n=='SLTIU' else n[:-1] if n else None
                operand=sext(instruction>>20,12)&MASK
            if operation:value=_alu(operation,first,operand)
            else:error=(2,instruction)
        else:error=(2,instruction)
        if error is not None:
            cause,detail=error;event=('T',pc,cause,detail);events.append(event)
            csrs[0x341]=pc;csrs[0x342]=cause;csrs[0x343]=detail
            csrs[0x300]=(csrs[0x300]&~0x88)|((csrs[0x300]&8)<<4)
            yield ('E',event)
            pc=csrs[0x305]
            continue
        value=(value&MASK) if rd else 0
        if rd:regs[rd]=value
        event=('I',pc,instruction,rd,value,next_pc);events.append(event)
        yield ('E',event)
        if pc==end_pc:
            return dict(events=events,requests=requests,registers=regs,memory=memory,
                        csrs={CSR_NAMES[a]:v for a,v in csrs.items()})
        pc=next_pc
    raise RuntimeError('Machine reference exceeded bounded execution budget')
