"""Replay the actual CPU and DMA trace; independently maintain RAM and MMIO state."""
import re
from model.fixed_fir import fir_block
from model.tiny_cpu import REGISTER_OPERATIONS, IMMEDIATE_OPERATIONS, SHIFT_IMMEDIATE_OPERATIONS, _alu

MASK=(1<<32)-1
BASE=0x40003000


def signed(value,bits=32):
    return value-(1<<bits) if value&(1<<(bits-1)) else value


def audit(log,image,initial,manifest,final_memory,final_registers,*,expect_timeout=False):
    memory=list(initial); registers=[0]*32; pc=0; commits=0; pending=[]
    symbols=manifest['symbols']
    x=[signed(memory[symbols['samples']//4+n]) for n in range(8)]
    h=[signed(memory[symbols['coefficients']//4+k]) for k in range(32)]
    golden=fir_block(x,h)
    config={8:0,12:0,16:0}; coeff=[0]*32; mask=set()
    busy=done=False; start_cycle=elapsed=reads=writes=0; bus_count=0; starts=0
    def need(condition,message):
        if not condition: raise ValueError(message)
    for line in log.splitlines():
        m=re.search(r'SOC_BUS mode=([RW]) addr=([0-9A-F]{8}) data=([0-9A-F]{8}) be=([0-9A-F]{8}) cycle=(\d+)',line)
        if m:
            mode=m[1]; addr,data,be=[int(m[n],16) for n in (2,3,4)]; cycle=int(m[5])
            pending.append((mode,addr,data,be)); bus_count+=1
            if addr<1024:
                if mode=='R': need(data==memory[addr//4],'CPU RAM read differs from independently replayed RAM')
                else:
                    bits=sum(255<<(8*k) for k in range(4) if be&(1<<k))
                    memory[addr//4]=(memory[addr//4]&(~bits&MASK))|(data&bits)
            else:
                need(BASE<=addr<BASE+4096 and addr%4==0 and be==15,'unexpected MMIO access')
                off=addr-BASE
                if mode=='W':
                    need(not busy,'C driver wrote MMIO while busy')
                    if 256<=off<=380:
                        need(signed(data)==signed(data&65535,16),'bad coefficient encoding')
                        coeff[(off-256)//4]=signed(data); mask.add((off-256)//4)
                    elif off in config: config[off]=data
                    elif off==0 and data==2: done=False
                    elif off==0 and data==1:
                        need(len(mask)==32 and coeff==h,'C driver did not configure all coefficients')
                        need(config=={8:symbols['samples'],12:symbols['outputs'],16:8},'C driver configured wrong buffers')
                        busy=True;done=False;start_cycle=cycle;elapsed=reads=writes=0;starts+=1
                    else: raise ValueError('unexpected C MMIO command')
                else:
                    expected={0:0,4:int(busy)+2*int(done),**config,20:elapsed,24:writes,28:0}
                    if 256<=off<=380: value=coeff[(off-256)//4]&MASK
                    else:
                        need(off in expected,'unexpected C MMIO read'); value=expected[off]
                    need(data==value,f'MMIO read mismatch offset={off} got={data} expected={value}')
            continue
        m=re.search(r'SOC_DMA mode=([RW]) addr=([0-9A-F]{8}) data=([0-9A-F]{8}) cycle=(\d+)',line)
        if m:
            mode=m[1];addr,data=int(m[2],16),int(m[3],16);cycle=int(m[4])
            need(busy and addr%4==0 and addr<1024,'DMA outside an active valid job')
            if mode=='R':
                need(reads==writes and addr==config[8]+4*reads and data==memory[addr//4],'DMA input address/data/order mismatch')
                reads+=1
            else:
                need(reads==writes+1 and addr==config[12]+4*writes,'DMA output address/order mismatch')
                need(data==golden.outputs[writes]&MASK,'DMA output differs from original Q15 reference')
                memory[addr//4]=data;writes+=1
                if writes==8: busy=False;done=True;elapsed=cycle-start_cycle
            continue
        m=re.search(r'SOC_COMMIT pc=([0-9A-F]{8}) insn=([0-9A-F]{8}) rd=(\d+) value=([0-9A-F]{8}) next=([0-9A-F]{8})',line)
        if not m: continue
        actual_pc,insn=int(m[1],16),int(m[2],16)
        need(actual_pc==pc and insn==image.program_words[pc//4],'CPU PC/instruction sequence mismatch')
        op=insn&127;rd=(insn>>7)&31;f3=(insn>>12)&7;rs1=(insn>>15)&31;rs2=(insn>>20)&31;f7=insn>>25
        first,second=registers[rs1],registers[rs2]; nxt=(pc+4)&MASK; value=0
        if op==0x37: value=insn&0xfffff000
        elif op==0x17: value=pc+(insn&0xfffff000)
        elif op in (0x03,0x23):
            immediate=signed(insn>>20,12) if op==3 else signed(((insn>>25)<<5)|((insn>>7)&31),12)
            address=(first+immediate)&MASK; width=1<<(f3&3);lane=address%4
            need(width<=4 and address%width==0,'illegal replay memory instruction')
            need(bool(pending),'CPU memory instruction had no accepted request')
            mode,a,data,be=pending.pop(0)
            need(a==address and be==((1<<width)-1)<<lane,'CPU bus address/width differs from ISA')
            if op==3:
                need(mode=='R','load used write bus')
                value=(data>>(8*lane))&((1<<(8*width))-1)
                if f3 in (0,1): value=signed(value,8*width)
            else:
                need(mode=='W' and data==((second&((1<<(8*width))-1))<<(8*lane)),'store data differs from ISA')
                rd=0
        elif op==0x63:
            comparisons={0:first==second,1:first!=second,4:signed(first)<signed(second),
                         5:signed(first)>=signed(second),6:first<second,7:first>=second}
            need(f3 in comparisons,'unsupported branch')
            imm=((insn>>31)<<12)|(((insn>>7)&1)<<11)|(((insn>>25)&63)<<5)|(((insn>>8)&15)<<1)
            if comparisons[f3]: nxt=(pc+signed(imm,13))&MASK
            rd=0
        elif op==0x6f:
            imm=((insn>>31)<<20)|(insn&0xff000)|(((insn>>20)&1)<<11)|(((insn>>21)&1023)<<1)
            value=nxt;nxt=(pc+signed(imm,21))&MASK
        elif op==0x67:
            need(f3==0,'unsupported JALR');value=nxt;nxt=((first+signed(insn>>20,12))&MASK)&~1
        elif op in (0x13,0x33):
            if op==0x33:
                operation=next((n for n,c in REGISTER_OPERATIONS.items() if c==(f7,f3)),None);operand=second
            elif f3 in (1,5):
                name=next((n for n,c in SHIFT_IMMEDIATE_OPERATIONS.items() if c==(f7,f3)),None)
                operation=name[:-1] if name else None;operand=rs2
            else:
                name=next((n for n,c in IMMEDIATE_OPERATIONS.items() if c==f3),None)
                operation='SLTU' if name=='SLTIU' else name[:-1] if name else None;operand=signed(insn>>20,12)&MASK
            need(operation is not None,'unsupported arithmetic encoding');value=_alu(operation,first,operand)
        else: raise ValueError('unsupported CPU opcode')
        value=value&MASK if rd else 0
        need((int(m[3]),int(m[4],16),int(m[5],16))==(rd,value,nxt),'CPU writeback/next PC differs from ISA')
        if rd: registers[rd]=value
        pc=nxt;commits+=1
    need(not pending and starts==1,'incomplete CPU execution')
    if expect_timeout: need(reads==writes==0 and busy and not done,'timeout failed to leave output ownership with hardware')
    else: need(reads==writes==8 and done and not busy,'incomplete DMA execution')
    need(pc==manifest['symbols']['_program_end'],'C startup did not reach end sentinel')
    need(memory==list(final_memory),'final complete RAM differs from trace replay')
    need(registers==list(final_registers),'final register file differs from ISA replay')
    need(registers[2]==1024 and registers[10]==int(expect_timeout),'C calling convention/return status failed')
    for name,value in [('done',1),('errors',int(expect_timeout)),('hw_written',0 if expect_timeout else 8),('hw_cycles',elapsed)]:
        need(memory[symbols[name]//4]==value,'C result mismatch: '+name)
    polls=memory[symbols['polls']//4];need(1<=polls<=64,'C polling bound failed')
    if expect_timeout: need(polls==64,'timeout did not respect polling bound')
    return {'checked_commits':commits,'cpu_requests':bus_count,'dma_reads':reads,'dma_writes':writes,
            'hardware_cycles':elapsed,'polls':polls,'outputs':[signed(memory[symbols['outputs']//4+n]) for n in range(8)],
            'expected_timeout':expect_timeout,
            'complete_ram_words_checked':256,'registers_checked':32}
