"""CPU5 upload and result verification. Construction never connects to JTAG."""
from datetime import datetime,timezone
import hashlib,struct,time
from tools.app_protocol import *
from tools.app_program import prepare_job

class AppSession:
    def __init__(self,transport,progress=None):
        self.transport=transport;self.token=transport.initial_token;self.seq=0
        self.progress=progress or (lambda *_:None);self.completed=0;self.total=0;self.initialized=False
    def request(self,op,address=0,count=0,values=()):
        self.token=1-self.token;p=encode(self.token,op,self.seq,address,count,values)
        return decode(self.transport.exchange(p),p)
    def read(self,op,address,count):
        result=[]
        for i in range(0,count,8):result.extend(self.request(op,address+i,min(8,count-i)).u32[:min(8,count-i)])
        return result
    def initialize(self):
        s=self.request(STATUS)
        if s.u32[:3]!=(0x43505535,0x00330001,25000000):raise ProtocolError('Download the new CPU5 image first; current CPU identity differs')
        if s.state in (1,3):raise ProtocolError('Board is busy; wait for the current task')
        self.seq=s.u32[4];self.completed=s.u32[6]
        if self.request(STATUS,2).u32!=(4096,8192,8,326,128,128,256,0x10000000):raise ProtocolError('CPU5 memory layout differs')
        f=self.request(STATUS,3)
        if f.u32[0]!=63 or f.u32[7]!=25000000:raise ProtocolError('CPU5 capabilities differ')
        st=self.request(STATUS,1);self.total=st.u32[2]|st.u32[3]<<32;self.initialized=True
        return dict(image='CPU5',abi='00330001',instruction_bytes=16384,data_bytes=32768,clock_hz=25000000)
    def run(self,elf,values):
        if not self.initialized:raise ProtocolError('Connect CPU5 first')
        self.progress('reference');image,memory,ref=prepare_job(elf,values)
        start=time.perf_counter();self.seq=(self.seq+1)&65535
        self.progress('clearing');self.request(BEGIN,values=[len(image.program_words)])
        self.progress('uploading_code')
        for i in range(0,len(image.program_words),8):
            c=image.program_words[i:i+8];self.request(WRITE_CODE,i,len(c),c)
        if self.read(READ_CODE,0,len(image.program_words))!=list(image.program_words):raise ProtocolError('Instruction readback differs')
        self.progress('uploading_data')
        for i in range(0,8192,8):
            c=memory[i:i+8]
            if any(c):
                self.request(WRITE,i,len(c),c)
                if self.read(READ,i,len(c))!=c:raise ProtocolError('Initial RAM readback differs')
        self.progress('running');self.request(RUN);deadline=time.monotonic()+10
        while True:
            s=self.request(STATUS)
            if s.u32[4]!=self.seq:raise ProtocolError('Task sequence changed')
            if s.state==5:raise ProtocolError('CPU5 task failed, code '+str(s.u32[7]))
            if s.state==4:break
            if time.monotonic()>deadline:raise ProtocolError('CPU5 execution timed out')
            time.sleep(.005)
        if (s.u32[6]-self.completed)&0xffffffff!=1:raise ProtocolError('Cached or skipped completion')
        self.progress('reading');st=self.request(STATUS,1);total=st.u32[2]|st.u32[3]<<32
        if st.u32[1]!=ref['commits'] or (total-self.total)&0xffffffffffffffff!=ref['commits'] or st.u32[0]<ref['commits']:raise ProtocolError('Retirement counters differ')
        if st.u32[4:6]!=(ref['last'][1],ref['last'][2]) or st.u32[6]!=ref['status']:raise ProtocolError('Exit commit or return value differs')
        f=self.request(STATUS,3);timer=self.request(STATUS,12)
        if f.u32[0]!=63 or any(f.u32[1:7]) or f.u32[7]!=25000000:raise ProtocolError('Unexpected trap/event')
        if timer.u32[2:]!=(0xffffffff,0xffffffff,0,0,25000000,16) or (timer.u32[0]|timer.u32[1]<<32)+1!=st.u32[0]:raise ProtocolError('Unexpected timer state')
        header=self.read(READ,0,2);n=self.read(READ,130,1)[0];tail=self.read(READ,259,3)
        if header!=[0x43505535,len(values)] or n!=len(ref['output']) or tail!=[1,ref['status'],len(ref['console_bytes'])]:raise ProtocolError('Application ABI result header differs')
        out=self.read(READ,131,n);text=struct.pack('<64I',*self.read(READ,262,64))[:tail[2]]
        if out!=[v&0xffffffff for v in ref['output']] or text!=ref['console_bytes']:raise ProtocolError('Output or console differs from ISA reference')
        final=self.request(STATUS)
        if final.state!=4 or final.u32[4:7]!=s.u32[4:7]:raise ProtocolError('Result changed during readback')
        self.completed=s.u32[6];self.total=total
        return dict(format='cpu5-app-run-v1',image='CPU5',abi='00330001',source_kind=self.transport.source_kind,source=self.transport.device_info,
            captured_at_utc=datetime.now(timezone.utc).isoformat(),input=list(values),output=ref['output'],console=text.decode('utf-8',errors='replace'),console_hex=text.hex(),
            status=ref['status'],sequence=self.seq,completed_tasks=self.completed,cycles=st.u32[0],retired=st.u32[1],retired_total=total,
            last_pc=st.u32[4],last_instruction=st.u32[5],clock_hz=25000000,execution_ms=st.u32[0]/25000,host_ms=(time.perf_counter()-start)*1000,
            text_bytes=len(image.program_words)*4,elf_sha256=hashlib.sha256(elf).hexdigest(),reference_verified=True,trap_count=0)
