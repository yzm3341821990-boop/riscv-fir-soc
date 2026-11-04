"""DSP6 upload and result verification. Construction never connects to JTAG."""
from datetime import datetime,timezone
import hashlib,struct,time
from tools.app_protocol import *
from tools.dsp_program import initial
from tools.app_program import signed

class DspSession:
    def __init__(self,transport,expected_elf_sha256,progress=None,execution_timeout=120):
        self.execution_timeout=execution_timeout
        self.expected_elf_sha256=expected_elf_sha256
        self.transport=transport;self.token=transport.initial_token;self.seq=0
        self.progress=progress or (lambda *_:None);self.completed=0;self.total=0;self.initialized=False
    def request(self,op,address=0,count=0,values=()):
        self.token=1-self.token
        if op==STATUS and 13<=address<=15:
            if count or values:raise ValueError('Status has no payload')
            p=f'{(0x51<<312)|(self.token<<311)|(op<<308)|(self.seq<<292)|(address<<279)|(1<<258):080X}'
        else:p=encode(self.token,op,self.seq,address,count,values)
        return decode(self.transport.exchange(p),p)
    def read(self,op,address,count):
        result=[]
        for i in range(0,count,8):result.extend(self.request(op,address+i,min(8,count-i)).u32[:min(8,count-i)])
        return result
    def initialize(self):
        s=self.request(STATUS)
        if s.u32[:3]!=(0x44535036,0x00360001,25000000):raise ProtocolError('Download the new DSP6 image first; current CPU identity differs')
        if s.state in (1,3):raise ProtocolError('Board is busy; wait for the current task')
        self.seq=s.u32[4];self.completed=s.u32[6]
        if self.request(STATUS,2).u32!=(4096,8192,8,326,128,128,256,0x10000000):raise ProtocolError('DSP6 memory layout differs')
        f=self.request(STATUS,3)
        if f.u32[0]!=127 or f.u32[7]!=25000000:raise ProtocolError('DSP6 capabilities differ')
        st=self.request(STATUS,1);self.total=st.u32[2]|st.u32[3]<<32;self.initialized=True
        return dict(image='DSP6',abi='00360001',instruction_bytes=16384,data_bytes=32768,clock_hz=25000000)
    def run(self,elf,values):
        if not self.initialized:raise ProtocolError('Connect DSP6 first')
        if hashlib.sha256(elf).hexdigest()!=self.expected_elf_sha256:raise ValueError('Use the frozen DSP benchmark ELF; arbitrary C is not admitted by this benchmark host')
        if not isinstance(values,list) or len(values)!=1:raise ValueError('Provide [sample_count]')
        self.progress('reference');image,memory,expected=initial(elf,values[0])
        exit_pc=image.symbols['_exit_commit'];ref=dict(output=expected,status=0,last=(None,exit_pc,image.program_words[exit_pc//4]),console_bytes=f'DSP6 CPU + four-lane FIR; checked samples={values[0]}\n'.encode())
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
        self.progress('running');self.request(RUN);deadline=time.monotonic()+self.execution_timeout
        while True:
            s=self.request(STATUS)
            if s.u32[4]!=self.seq:raise ProtocolError('Task sequence changed')
            if s.state==5:raise ProtocolError('DSP6 task failed, code '+str(s.u32[7]))
            if s.state==4:break
            if time.monotonic()>deadline:raise ProtocolError('DSP6 execution timed out')
            time.sleep(.005)
        if (s.u32[6]-self.completed)&0xffffffff!=1:raise ProtocolError('Cached or skipped completion')
        self.progress('reading');st=self.request(STATUS,1);total=st.u32[2]|st.u32[3]<<32
        if st.u32[1]==0 or (total-self.total)&0xffffffffffffffff!=st.u32[1] or st.u32[0]<st.u32[1]:raise ProtocolError('Retirement counters differ')
        if st.u32[4:6]!=(ref['last'][1],ref['last'][2]) or st.u32[6]!=ref['status']:raise ProtocolError('Exit commit or return value differs')
        f=self.request(STATUS,3);timer=self.request(STATUS,12)
        if f.u32[0]!=127 or any(f.u32[1:7]) or f.u32[7]!=25000000:raise ProtocolError('Unexpected trap/event')
        if timer.u32[2:]!=(0xffffffff,0xffffffff,0,0,25000000,16) or (timer.u32[0]|timer.u32[1]<<32)+1!=st.u32[0]:raise ProtocolError('Unexpected timer state')
        header=self.read(READ,0,2);n=self.read(READ,130,1)[0];tail=self.read(READ,259,3)
        if header!=[0x43505535,len(values)] or n!=len(ref['output']) or tail!=[1,ref['status'],len(ref['console_bytes'])]:raise ProtocolError('Application ABI result header differs')
        out=self.read(READ,131,n);text=struct.pack('<64I',*self.read(READ,262,64))[:tail[2]]
        if out!=[v&0xffffffff for v in ref['output']] or text!=ref['console_bytes']:raise ProtocolError('Output or console differs from independent stream reference')
        final=self.request(STATUS)
        if final.state!=4 or final.u32[4:7]!=s.u32[4:7]:raise ProtocolError('Result changed during readback')
        profiles=[]
        for page in range(13,16):
            p=self.request(STATUS,page).u32
            if p[2]!=expected[1] or any(p[3:]) or (p[0]|p[1]<<32)==0:raise ProtocolError('Invalid accepted-marker profiling counters')
            profiles.append(p[0]|p[1]<<32)
        self.completed=s.u32[6];self.total=total
        return dict(format='dsp6-stream-run-v1',image='DSP6',abi='00360001',source_kind=self.transport.source_kind,source=self.transport.device_info,
            captured_at_utc=datetime.now(timezone.utc).isoformat(),input=list(values),output=[signed(v) for v in out],console=text.decode('utf-8',errors='replace'),console_hex=text.hex(),
            status=ref['status'],sequence=self.seq,completed_tasks=self.completed,cycles=st.u32[0],retired=st.u32[1],retired_total=total,
            last_pc=st.u32[4],last_instruction=st.u32[5],clock_hz=25000000,execution_ms=st.u32[0]/25000,host_ms=(time.perf_counter()-start)*1000,
            text_bytes=len(image.program_words)*4,elf_sha256=hashlib.sha256(elf).hexdigest(),independent_stream_verified=True,reference_kind='numpy_int64_convolution',trap_count=0,profile_cycles=profiles,profile_ms=[v/25000 for v in profiles],speedup_cold=profiles[0]/profiles[1],blocks=expected[1])
