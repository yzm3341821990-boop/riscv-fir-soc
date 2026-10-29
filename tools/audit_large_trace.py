"""Stream the real CPU/DMA trace, replay ISA and compare all 8192 RAM words."""
from collections import deque
from pathlib import Path
from model.fixed_fir import fir_block
from model.tiny_cpu import REGISTER_OPERATIONS,IMMEDIATE_OPERATIONS,SHIFT_IMMEDIATE_OPERATIONS,_alu
from tools.audit_soc_trace import signed
MASK=(1<<32)-1
BASE=0x40003000


def audit(trace_file,program,initial,manifest,final_memory,final_registers):
    memory=list(initial);registers=[0]*32;pc=0;commits=0;pending=deque()
    symbols=manifest['symbols'];n=manifest['sample_count'];mode=manifest['mode']
    x=[signed(memory[symbols['samples']//4+i]) for i in range(n)]
    h=[signed(memory[symbols['coefficients']//4+i]) for i in range(32)]
    golden=fir_block(x,h)
    config={8:0,12:0,16:0};coeff=[0]*32;mask=set();busy=done=False
    start_cycle=elapsed=reads=writes=starts=bus_count=0
    markers=[];coeff_cycles=[];output_cycles=[];dma_cycles=[];polls=0;previous_cycle=-1
    def need(condition,message):
        if not condition:raise ValueError(message)
    with Path(trace_file).open(encoding='ascii') as stream:
        for line in stream:
            parts=line.split()
            if not parts:continue
            cycle=int(parts[-1]);need(cycle>=previous_cycle,'nonmonotonic accepted trace cycles');previous_cycle=cycle
            if parts[0]=='C':
                rw=parts[1];addr,data,be=[int(v,16) for v in parts[2:5]];cycle=int(parts[5])
                pending.append((rw,addr,data,be));bus_count+=1
                if addr<32768:
                    if rw=='R':need(data==memory[addr//4],'CPU RAM read differs from replay')
                    else:
                        bits=sum(255<<(8*k) for k in range(4) if be&(1<<k))
                        memory[addr//4]=(memory[addr//4]&(~bits&MASK))|(data&bits)
                        if addr==symbols['marker']:
                            need(be==15,'marker is not full word');markers.append((data,cycle))
                        if symbols['outputs']<=addr<symbols['outputs']+4*n:output_cycles.append(cycle)
                else:
                    need(mode!='software' and BASE<=addr<BASE+4096 and addr%4==0 and be==15,'invalid long MMIO access')
                    off=addr-BASE
                    if rw=='W':
                        need(not busy,'CPU wrote configuration during busy')
                        if 256<=off<=380:
                            need(signed(data)==signed(data&65535,16),'coefficient sign extension')
                            coeff[(off-256)//4]=signed(data);mask.add((off-256)//4);coeff_cycles.append(cycle)
                        elif off in config:config[off]=data
                        elif off==0 and data==2:done=False
                        elif off==0 and data==1:
                            need(len(mask)==32 and coeff==h,'wrong long coefficients')
                            need(config=={8:symbols['samples'],12:symbols['outputs'],16:n},'wrong long task configuration')
                            busy=True;done=False;start_cycle=cycle;elapsed=reads=writes=0;starts+=1
                        else:raise ValueError('unexpected long MMIO command')
                    else:
                        expected={0:0,4:int(busy)+2*int(done),**config,20:elapsed,24:writes,28:0}
                        need(off in expected and data==expected[off],'long MMIO read mismatch')
                        if off==4:polls+=1
                continue
            if parts[0]=='D':
                rw=parts[1];addr,data=int(parts[2],16),int(parts[3],16);cycle=int(parts[4]);dma_cycles.append(cycle)
                need(busy and addr%4==0 and addr<32768,'DMA outside active valid task')
                if rw=='R':
                    need(reads==writes and addr==config[8]+4*reads and data==memory[addr//4],'long DMA read data/address/order')
                    reads+=1
                else:
                    need(reads==writes+1 and addr==config[12]+4*writes,'long DMA write address/order')
                    need(data==golden.outputs[writes]&MASK,'long DMA numerical mismatch')
                    memory[addr//4]=data;writes+=1
                    if writes==n:busy=False;done=True;elapsed=cycle-start_cycle
                continue
            need(parts[0]=='I' and len(parts)==7,'unknown long trace record')
            actual_pc,insn=int(parts[1],16),int(parts[2],16)
            need(actual_pc==pc and insn==program[pc//4],'CPU PC/instruction sequence mismatch')
            op=insn&127;rd=(insn>>7)&31;f3=(insn>>12)&7;rs1=(insn>>15)&31;rs2=(insn>>20)&31;f7=insn>>25
            first,second=registers[rs1],registers[rs2]; nxt=(pc+4)&MASK; value=0
            if op==0x37: value=insn&0xfffff000
            elif op==0x17: value=pc+(insn&0xfffff000)
            elif op in (0x03,0x23):
                immediate=signed(insn>>20,12) if op==3 else signed(((insn>>25)<<5)|((insn>>7)&31),12)
                address=(first+immediate)&MASK; width=1<<(f3&3);lane=address%4
                need(width<=4 and address%width==0,'illegal replay memory instruction')
                need(bool(pending),'CPU memory instruction had no accepted request')
                access_mode,a,data,be=pending.popleft()
                need(a==address and be==((1<<width)-1)<<lane,'CPU bus address/width differs from ISA')
                if op==3:
                    need(access_mode=='R','load used write bus')
                    value=(data>>(8*lane))&((1<<(8*width))-1)
                    if f3 in (0,1): value=signed(value,8*width)
                else:
                    need(access_mode=='W' and data==((second&((1<<(8*width))-1))<<(8*lane)),'store data differs from ISA')
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
            need((int(parts[3]),int(parts[4],16),int(parts[5],16))==(rd,value,nxt),'CPU writeback/next PC differs from ISA')
            if rd: registers[rd]=value
            pc=nxt;commits+=1
    need(not pending,'CPU pending requests at end')
    need(pc==symbols['_program_end'],'C did not reach terminal PC')
    need(registers==list(final_registers),'actual register file differs from ISA replay')
    need(memory==list(final_memory),'complete 32 KiB RAM differs from accepted transactions')
    need(registers[2]==32768 and registers[10]==0,'C stack or return value incorrect')
    need(memory[symbols['done']//4]==1 and memory[symbols['errors']//4]==0,'C full-block verification failed')
    need([v for v,_ in markers]==[1,2],'missing full-call boundary markers')
    begin,end=markers[0][1],markers[1][1];need(end>begin,'invalid complete-call interval')
    if mode=='software':
        need(starts==reads==writes==0 and len(output_cycles)==n,'software path used DMA or omitted outputs')
        need(all(begin<c<end for c in output_cycles),'software outputs outside timed call')
    else:
        need(starts==1 and reads==writes==n and done and not busy,'incomplete long hardware job')
        need(len(coeff_cycles)==32 and len(dma_cycles)==2*n,'missing configuration or DMA')
        need(all(begin<c<end for c in dma_cycles),'DMA outside complete-call interval')
        need(all((c<begin if mode=='hardware_resident' else begin<c<end) for c in coeff_cycles),'coefficient setup timing boundary')
        need(memory[symbols['hw_cycles']//4]==elapsed and memory[symbols['hw_written']//4]==n,'C diagnostics differ from DMA timeline')
        need(memory[symbols['polls']//4]==polls and 1<=polls<=n*64+256,'bounded polling incorrect')
    need([signed(memory[symbols['outputs']//4+i]) for i in range(n)]==list(golden.outputs),'full long-block output mismatch')
    return {'cycles':end-begin,'hardware_cycles':elapsed,'checked_commits':commits,'cpu_requests':bus_count,
            'dma_reads':reads,'dma_writes':writes,'outputs_checked':n,'complete_ram_words_checked':8192,
            'registers_checked':32,'status_polls':polls,'begin_cycle':begin,'end_cycle':end}
