"""Persistent, explicitly connected JTAG transport and checked frame exchange."""
from collections import deque
from dataclasses import asdict
from datetime import datetime,timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from tools.live_protocol import (BEGIN,READ,RUN,STATUS,WRITE,COEFF_WORD,EXPECTED_WORD,
    FIR_WORD,INPUT_WORD,SAVED_WORD,ProtocolError,decode_response,encode_request)


class NativeTransport:
    source_kind='fpga_jtag'
    def __init__(self,project,quartus_stp=None,popen_factory=None):
        self.project=Path(project)
        self.executable=Path(quartus_stp or os.environ.get('QUARTUS_STP') or shutil.which('quartus_stp') or 'quartus_stp')
        self._factory=popen_factory or subprocess.Popen;self.process=None;self._thread=None
        self.events=queue.Queue();self.diagnostics=deque(maxlen=100)
        self.initial_token=0;self.device_info={}
        self.log_path=self.project/'logs/live-link.log';self._log_handler=None

    def _record(self,message):
        if self._log_handler:
            self._log_handler.handle(logging.LogRecord('fpga.live',logging.INFO,'',0,message,(),None))

    def _open_log(self):
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        self._log_handler=RotatingFileHandler(self.log_path,maxBytes=1024*1024,backupCount=2,encoding='utf-8')
        self._log_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        self._record('CONNECT '+str(self.executable)+' -t '+str(self.project/'live_service.tcl'))

    def _close_log(self):
        if self._log_handler:
            handler=self._log_handler;self._log_handler=None;handler.close()

    def _diagnostic_error(self,message):
        detail='\n'.join(self.diagnostics)[-1800:]
        message+='\nLog: '+str(self.log_path)
        if detail:message+='\n'+detail
        self._record('ERROR '+message);return ProtocolError(message)

    def _pump(self,process,events):
        try:
            for line in process.stdout:
                line=line.rstrip('\r\n')
                self._record('NATIVE '+line)
                if line.startswith(('LIVE_READY ','LIVE_R ','LIVE_ERROR ')):
                    kind,value=line.split(' ',1);events.put((kind,value))
                elif line=='LIVE_BYE':events.put(('LIVE_BYE',''))
                else:self.diagnostics.append(line)
        finally:self._record('NATIVE EOF');events.put(('EOF',''))

    def _await(self,kind,timeout):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:event,value=self.events.get(timeout=max(.01,deadline-time.monotonic()))
            except queue.Empty:break
            if event==kind:return value
            if event=='LIVE_ERROR':
                try:value=json.loads(value)
                except ValueError:pass
                raise self._diagnostic_error(str(value))
            if event in ('EOF','LIVE_BYE'):raise self._diagnostic_error('JTAG service ended while waiting for '+kind)
        raise self._diagnostic_error('JTAG service response timed out waiting for '+kind+'; no new frame is available')

    def connect(self):
        if self.process is not None:raise ProtocolError('JTAG service already connected')
        script=self.project/'live_service.tcl'
        if not self.executable.is_file() or not script.is_file():raise ProtocolError('Quartus runtime or step25 live_service.tcl is missing')
        self.events=queue.Queue();self.diagnostics.clear()
        try:
            self._open_log()
            self.process=self._factory([str(self.executable),'-t',str(script)],cwd=self.project,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                encoding='utf-8',errors='replace',bufsize=1,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
            self._thread=threading.Thread(target=self._pump,args=(self.process,self.events),daemon=True);self._thread.start()
            info=json.loads(self._await('LIVE_READY',15))
            if type(info.get('token')) is not int or info['token'] not in (0,1):raise ProtocolError('Invalid initial JTAG token')
            self.initial_token=info.pop('token');self.device_info=info
        except Exception:
            self.close();raise

    def exchange(self,packet):
        if self.process is None:raise ProtocolError('JTAG service is not connected')
        self._record('HOST X '+packet)
        try:self.process.stdin.write('X '+packet+'\n');self.process.stdin.flush()
        except (OSError,ValueError) as exc:raise ProtocolError('JTAG command pipe closed') from exc
        return self._await('LIVE_R',11)

    def close(self):
        process=self.process
        if process is None:self._close_log();return
        self.process=None
        try:
            if process.poll() is None:
                try:process.stdin.write('QUIT\n');process.stdin.flush()
                except (OSError,ValueError):pass
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=3)
        finally:
            for stream in (process.stdin,process.stdout):
                if stream:
                    try:stream.close()
                    except OSError:pass
            if self._thread:self._thread.join(timeout=1)
            self._record('CLOSE');self._close_log()


class MailboxSession:
    def __init__(self,transport,progress=None,computation_timeout=8):
        if not 0<computation_timeout<=300:raise ValueError('Computation timeout must be in (0,300] seconds')
        self.computation_timeout=computation_timeout
        self.transport=transport;self.token=transport.initial_token;self.progress=progress or (lambda *args:None)
        self.sequence=0;self.completed=0;self.retired_total=0;self.commands=0;self.initialized=False

    def _request(self,opcode,seq,address=0,count=0,values=()):
        self.token=1-self.token
        packet=encode_request(self.token,opcode,seq,address,count,values)
        reply=decode_response(self.transport.exchange(packet),packet);self.commands+=1
        self.progress('board_state',reply.state,0)
        return reply

    def _status(self,seq,page=0):
        reply=self._request(STATUS,seq,page)
        if page==0:
            if reply.u32[:4]!=(0x4c495645,0x00250001,25000000,256):raise ProtocolError('Wrong step25 live image identity/clock/frame size')
            if (reply.u32[5]>>8)&15 != reply.state:raise ProtocolError('Inconsistent board state snapshot')
        return reply

    def initialize(self):
        deadline=time.monotonic()+self.computation_timeout
        while True:
            status=self._status(0)
            if status.state not in (1,3):break
            if time.monotonic()>deadline:raise ProtocolError('Previous board task did not finish')
            time.sleep(.005)
        layout=self._status(0,2)
        if layout.u32!=(2048,3072,16384,3200,4224,32,16,225):raise ProtocolError('Unsupported live RAM layout')
        counters=self._status(0,1)
        self.sequence=status.u32[4];self.completed=status.u32[6]
        self.retired_total=counters.u32[4] | counters.u32[5]<<32;self.initialized=True
        return {'frame_seq':self.sequence,'completed_frames':self.completed,'retired_total':self.retired_total,'board_state':status.state}

    def _write(self,seq,address,values,done,total):
        for index in range(0,len(values),16):
            chunk=values[index:index+16];self._request(WRITE,seq,address+index,len(chunk),chunk)
            self.progress('uploading',done+index+len(chunk),total)

    def _read(self,seq,address,count,done,total):
        result=[]
        for index in range(0,count,16):
            size=min(16,count-index);reply=self._request(READ,seq,address+index,size)
            result.extend(reply.words[:size]);self.progress('reading',done+index+size,total)
        return result

    def run_frame(self,frame,config_revision=0):
        if not self.initialized:raise ProtocolError('Live session has not been initialized')
        started=time.perf_counter();commands=self.commands;seq=(self.sequence+1)&65535
        self._request(BEGIN,seq);self.sequence=seq
        self._write(seq,INPUT_WORD,frame.samples,0,544)
        self._write(seq,COEFF_WORD,frame.coefficients,256,544)
        self._write(seq,EXPECTED_WORD,frame.expected,288,544)
        self._request(RUN,seq);self.progress('waiting',0,1)
        deadline=time.monotonic()+self.computation_timeout
        while True:
            status=self._status(seq)
            if status.u32[4]!=seq:raise ProtocolError('Board task number changed during processing')
            if status.state==5:raise ProtocolError(f'CPU/FIR task failed, detail={status.u32[7]}')
            if status.state==4:break
            if time.monotonic()>deadline:raise ProtocolError('Board computation timed out')
            time.sleep(.002)
        if (status.u32[6]-self.completed)&0xffffffff != 1:raise ProtocolError('Cached or skipped completed frame')
        counters=self._status(seq,1)
        cycles=dict(zip(('software','hardware_cold','hardware_resident'),counters.u32[:3]))
        total_retired=counters.u32[4] | counters.u32[5]<<32
        if not all(cycles.values()) or counters.u32[3]<=0 or total_retired<=self.retired_total:
            raise ProtocolError('Missing actual timer or CPU retirement counters')
        cpu=self._read(seq,SAVED_WORD,256,0,512);fir=self._read(seq,FIR_WORD,256,256,512)
        final=self._status(seq)
        if final.state!=4 or final.u32[4]!=seq or final.u32[6]!=status.u32[6]:raise ProtocolError('Frame changed during result readback')
        if cpu!=frame.expected or fir!=frame.expected:raise ProtocolError('CPU/FIR output does not match all 256 reference samples')
        self.completed=status.u32[6];self.retired_total=total_retired
        kind=self.transport.source_kind
        return dict(format='riscv-fir-capture-v1',origin='user_board_record' if kind=='fpga_jtag' else 'rtl_simulation',
            sample_rate_hz=48000,clock_hz=25000000,input=frame.samples,coefficients=frame.coefficients,
            cpu_output=cpu,fir_output=fir,cycles=cycles,
            source=dict(self.transport.device_info,instance_name='LIV0',captured_at_utc=datetime.now(timezone.utc).isoformat()),
            live=dict(source_kind=kind,frame_seq=seq,config_revision=config_revision,config=asdict(frame.config),
                valid_start=frame.valid_start,valid_samples=225,sample_offset=frame.sample_offset,
                completed_frames=self.completed,retired_frame=counters.u32[3],retired_total=total_retired,
                last_commit_pc=counters.u32[6],last_commit_instruction=counters.u32[7],
                transaction_ms=(time.perf_counter()-started)*1000,mailbox_transactions=self.commands-commands))
