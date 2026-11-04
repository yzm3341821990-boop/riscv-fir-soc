"""Independent accepted-bus/DMA oracle plus complete scalar RV32IM replay."""
from collections import deque
from pathlib import Path
from model.fixed_fir import fir_block
from model.rv32m import OPERATIONS,evaluate
from model.tiny_cpu import REGISTER_OPERATIONS,IMMEDIATE_OPERATIONS,SHIFT_IMMEDIATE_OPERATIONS,_alu
from model.dsp_peripheral import BASE,MARKER
from tools.dsp_program import initial
MASK=0xffffffff
def signed(v,bits=32):return v-(1<<bits) if v&(1<<(bits-1)) else v
def audit(folder,index,elf,record):
    d=Path(folder);image,memory,expected=initial(elf,record['input'][0]);program=image.program_words
    registers=[0]*32;pc=0;commits=0;pending=deque();config={8:0,12:0,16:0};coeff=[0]*32;mask=set()
    busy=done=False;start=elapsed=reads=writes=starts=0;golden=[];totals=[0]*3;intervals=[0]*3;active=0;began=0
    dma_reads=dma_writes=bus=0;previous=-1
    def need(v,m):
        if not v:raise ValueError(m)
    for line in (d/f'trace-{index}.txt').read_text(encoding='ascii').splitlines():
        p=line.split();cycle=int(p[-1]);need(cycle>=previous,'trace cycle order');previous=cycle
        if p[0]=='C':
            rw=p[1];addr,data,be=[int(v,16) for v in p[2:5]];pending.append((rw,addr,data,be));bus+=1
            if addr<32768 or 0x10000000<=addr<0x10008000:
                word=(addr&0x7fff)//4
                if rw=='R':need(data==memory[word],'CPU RAM differs from independent memory')
                else:
                    bits=sum(255<<(8*k) for k in range(4) if be&(1<<k));memory[word]=(memory[word]&(~bits&MASK))|(data&bits)
            elif addr==MARKER:
                need(rw=='W' and be==15,'invalid marker access')
                if data in (1,2,3):need(active==0,'nested marker');active=data;began=cycle
                else:
                    need(data==0 and active!=0,'unmatched marker end');totals[active-1]+=cycle-began;intervals[active-1]+=1;active=0
            else:
                need(BASE<=addr<BASE+4096 and be==15 and addr%4==0,'CPU accessed undefined peripheral')
                off=addr-BASE
                if rw=='W':
                    need(not busy,'configuration write while busy')
                    if 256<=off<=380:coeff[(off-256)//4]=signed(data);mask.add((off-256)//4)
                    elif off in config:config[off]=data
                    elif off==0 and data==2:done=False
                    elif off==0 and data==1:
                        src,dst,n=(config[k] for k in (8,12,16))
                        need(mask==set(range(32)) and all(-32768<=v<=32767 for v in coeff),'coefficient contract')
                        need(1<=n<=4096 and max(src,dst)+4*n<=32768 and min(src,dst)+4*n<=max(src,dst) and src%4==dst%4==0,'DMA range/overlap')
                        golden=list(fir_block([signed(v) for v in memory[src//4:src//4+n]],coeff).outputs)
                        busy=True;done=False;start=cycle;elapsed=reads=writes=0;starts+=1
                    else:raise ValueError('unexpected FIR command')
                else:
                    values={0:0,4:int(busy)+2*int(done),**config,20:(cycle-start if busy else elapsed),24:writes,28:0}
                    need(off in values and data==values[off],'FIR register read differs from accepted DMA timeline')
            continue
        if p[0]=='D':
            rw=p[1];addr,data=[int(v,16) for v in p[2:4]];need(busy,'DMA outside a start/done interval')
            if rw=='R':
                need(reads==writes and addr==config[8]+4*reads and data==memory[addr//4],'DMA input address/data/order');reads+=1;dma_reads+=1
            else:
                need(reads==writes+1 and addr==config[12]+4*writes and data==golden[writes]&MASK,'DMA FIR output/address/order')
                memory[addr//4]=data;writes+=1;dma_writes+=1
                if writes==config[16]:busy=False;done=True;elapsed=cycle-start
            continue
        need(p[0]=='I' and len(p)==7,'unknown trace event')
        actual_pc,insn=int(p[1],16),int(p[2],16);need(actual_pc==pc and insn==program[pc//4],'CPU PC/instruction sequence')
        op=insn&127;rd=(insn>>7)&31;f=(insn>>12)&7;rs1=(insn>>15)&31;rs2=(insn>>20)&31;f7=insn>>25
        first,second=registers[rs1],registers[rs2];nxt=(pc+4)&MASK;value=0
        if op in (0x37,0x17):value=(insn&0xfffff000)+(pc if op==0x17 else 0)
        elif op in (3,0x23):
            imm=signed(insn>>20,12) if op==3 else signed(((insn>>25)<<5)|((insn>>7)&31),12)
            addr=(first+imm)&MASK;width=1<<(f&3);lane=addr%4
            need(bool(pending),'missing accepted CPU request');rw,a,data,be=pending.popleft()
            need(width<=4 and addr%width==0 and a==addr and be==((1<<width)-1)<<lane,'CPU load/store address/width')
            if op==3:
                need(rw=='R','load became write');value=(data>>(8*lane))&((1<<(8*width))-1)
                if f in (0,1):value=signed(value,8*width)
            else:need(rw=='W' and data==(second&((1<<(8*width))-1))<<(8*lane),'store operand');rd=0
        elif op==0x63:
            take={0:first==second,1:first!=second,4:signed(first)<signed(second),5:signed(first)>=signed(second),6:first<second,7:first>=second}[f]
            imm=((insn>>31)<<12)|(((insn>>7)&1)<<11)|(((insn>>25)&63)<<5)|(((insn>>8)&15)<<1)
            if take:nxt=(pc+signed(imm,13))&MASK
            rd=0
        elif op==0x6f:
            imm=((insn>>31)<<20)|(insn&0xff000)|(((insn>>20)&1)<<11)|(((insn>>21)&1023)<<1);value=nxt;nxt=(pc+signed(imm,21))&MASK
        elif op==0x67:value=nxt;nxt=((first+signed(insn>>20,12))&MASK)&~1
        elif op==0x33 and f7==1:value=evaluate(OPERATIONS[f],first,second)
        elif op in (0x13,0x33):
            if op==0x33:operation=next(n for n,c in REGISTER_OPERATIONS.items() if c==(f7,f));operand=second
            elif f in (1,5):
                name=next(n for n,c in SHIFT_IMMEDIATE_OPERATIONS.items() if c==(f7,f));operation=name[:-1];operand=rs2
            else:
                name=next(n for n,c in IMMEDIATE_OPERATIONS.items() if c==f);operation='SLTU' if name=='SLTIU' else name[:-1];operand=signed(insn>>20,12)&MASK
            value=_alu(operation,first,operand)
        else:raise ValueError('unexpected instruction')
        value=value&MASK if rd else 0
        need((int(p[3]),int(p[4],16),int(p[5],16))==(rd,value,nxt),'CPU register writeback or next PC')
        if rd:registers[rd]=value
        pc=nxt;commits+=1
    need(not pending and not busy and active==0,'unfinished bus/DMA/marker')
    need(pc==len(program)*4 and commits==record['retired'],'terminal PC or retirement counter')
    need(totals==record['profile_cycles'] and intervals==[expected[1]]*3,'accepted-marker timing differs')
    need(starts==expected[1]*2 and dma_reads==dma_writes==starts*256,'missing DMA work')
    actual_ram=[int(v,16) for v in (d/f'memory-{index}.txt').read_text().split()]
    actual_regs=[int(v,16) for v in (d/f'registers-{index}.txt').read_text().split()]
    need(memory==actual_ram,'complete 8192-word RAM differs from independent transactions')
    need(registers==actual_regs,'all 32 physical register values differ from ISA')
    return dict(status='passed',checked_commits=commits,cpu_requests=bus,dma_reads=dma_reads,dma_writes=dma_writes,starts=starts,profile_cycles=totals,intervals=intervals,ram_words_checked=8192,registers_checked=32)
