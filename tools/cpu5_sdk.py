"""Python API and bounded batch CLI for the existing CPU5 image.

Import, construction, compilation and reference() never connect hardware.
Only an explicit connect() or CLI --hardware opens a JTAG session.
"""
from dataclasses import dataclass
from datetime import datetime,timezone
import argparse,hashlib,json,math,time,uuid,threading
from contextlib import contextmanager
from pathlib import Path
from tools.app_program import prepare_job,program_image
from tools.app_session import AppSession
from tools.build_app import build,DEFAULT_ZIG
from tools.live_session import NativeTransport

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_PROJECT=ROOT/'link' if (ROOT/'link').is_dir() else Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_app')
DEFAULT_OUTPUT=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/step34-python-sdk/runs')

@dataclass(frozen=True)
class Program:
    elf:bytes
    elf_sha256:str
    text_bytes:int
    name:str
    @classmethod
    def load(cls,path):
        path=Path(path)
        if path.stat().st_size>262144:raise ValueError('ELF file exceeds 256 KiB')
        elf=path.read_bytes();image=program_image(elf)
        return cls(elf,hashlib.sha256(elf).hexdigest(),len(image.program_words)*4,path.stem)
    @classmethod
    def compile(cls,source,directory,zig=DEFAULT_ZIG):
        build(source,directory,zig);return cls.load(Path(directory)/'program.elf')
    def verify(self):
        if not isinstance(self.elf,bytes) or hashlib.sha256(self.elf).hexdigest()!=self.elf_sha256:raise ValueError('Program bytes or fingerprint changed')
        if len(program_image(self.elf).program_words)*4!=self.text_bytes:raise ValueError('Program descriptor differs')

def reference(program,values):
    program.verify();start=time.perf_counter();_,_,ref=prepare_job(program.elf,values)
    return dict(format='cpu5-sdk-run-v1',image='CPU5',abi='00330001',source_kind='isa_reference',input=list(values),output=ref['output'],console=ref['console'],console_hex=ref['console_bytes'].hex(),status=ref['status'],
        retired=ref['commits'],cycles=None,clock_hz=None,execution_ms=None,sdk_call_ms=(time.perf_counter()-start)*1000,elf_sha256=program.elf_sha256,text_bytes=program.text_bytes,
        captured_at_utc=datetime.now(timezone.utc).isoformat(),reference_verified=True)

class CPU5:
    def __init__(self,project=DEFAULT_PROJECT,transport_factory=None,progress=None):
        self.project=Path(project);self.factory=transport_factory or (lambda:NativeTransport(self.project))
        self.progress=progress;self.transport=None;self.session=None
        self._lock=threading.Lock()
    @contextmanager
    def _operation(self):
        if not self._lock.acquire(blocking=False):raise ValueError('CPU5 client is busy; serialize calls')
        try:yield
        finally:self._lock.release()
    def connect(self):
        with self._operation():
            if self.transport is not None:raise ValueError('CPU5 is already connected')
            transport=self.factory()
            try:
                transport.connect();session=AppSession(transport,self.progress);identity=session.initialize()
            except Exception:transport.close();raise
            self.transport=transport;self.session=session
            return {**identity,'source_kind':transport.source_kind}
    def close(self):
        with self._operation():self._close()
    def _close(self):
        transport=self.transport;self.transport=None;self.session=None
        if transport is not None:transport.close()
    def run(self,program,values):
        with self._operation():return self._execute(program,checked_cases([values])[0])
    def _execute(self,program,values):
        if self.session is None:raise ValueError('Call connect() before running on CPU5')
        program.verify();prepare_job(program.elf,values) # invalid input has no board side effect
        start=time.perf_counter()
        try:result=self.session.run(program.elf,values)
        except Exception:self._close();raise
        return {**result,'sdk_call_ms':(time.perf_counter()-start)*1000}
    def run_many(self,program,cases):
        with self._operation():
            cases=checked_cases(cases)
            if self.session is None:raise ValueError('Call connect() before running on CPU5')
            program.verify()
            for values in cases:prepare_job(program.elf,values)
            records=[self._execute(program,values) for values in cases]
            return {'format':'cpu5-sdk-batch-v1','records':records,'summary':batch_summary(records)}

def checked_cases(cases):
    if not isinstance(cases,(list,tuple)) or not 1<=len(cases)<=100:raise ValueError('Batch needs 1..100 input arrays')
    if any(not isinstance(v,(list,tuple)) for v in cases):raise ValueError('Each batch case must be an integer array')
    return [list(v) for v in cases]

def batch_summary(records):
    if not records:raise ValueError('Cannot summarize an empty batch')
    kinds={r['source_kind'] for r in records}
    if len(kinds)!=1 or not kinds<={'fpga_jtag','rtl_simulation','isa_reference'}:raise ValueError('Mixed or unknown result sources')
    kind=next(iter(kinds));measured=kind!='isa_reference'
    if measured:
        for r in records:
            if type(r['cycles']) is not int or r['cycles']<0 or r['clock_hz']!=25000000:raise ValueError('Missing CPU timing')
    calls=[r.get('sdk_call_ms') for r in records]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in calls):raise ValueError('Missing host call timing')
    return dict(source_kind=kind,tasks=len(records),successful_status=sum(r['status']==0 for r in records),retired=sum(r['retired'] for r in records),
        cycles=sum(r['cycles'] for r in records) if measured else None,core_ms=sum(r['cycles']/25000 for r in records) if measured else None,
        sdk_call_ms=sum(calls),timing_note='core_ms is CPU execution only; sdk_call_ms also includes scalar preflight, upload, polling and readback. Compilation and initial connection are excluded. Reference mode has no core timing. RTL core time is simulated cycles divided by the declared clock, not a physical measurement.')

def save_report(path,report):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    return path

def save_html_report(path,report):
    """Standalone read-only report; DOM content uses textContent, never HTML."""
    batch_summary(report['records'])
    template=(ROOT/'web/sdk_report.html').read_text(encoding='utf-8')
    payload=json.dumps(report,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html=template.replace('__CPU5_BATCH_JSON__',payload)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:f.write(html)
    return path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'examples/cpu5_sdk/square.c');p.add_argument('--elf',type=Path)
    p.add_argument('--cases',type=Path,default=ROOT/'examples/cpu5_sdk/inputs.json');p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);p.add_argument('--project',type=Path,default=DEFAULT_PROJECT);p.add_argument('--hardware',action='store_true')
    p.add_argument('--open',action='store_true');a=p.parse_args();folder=a.output/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True)
    if a.cases.stat().st_size>65536:raise ValueError('Input JSON exceeds 64 KiB')
    cases=checked_cases(json.loads(a.cases.read_text(encoding='utf-8')))
    if a.elf:program=Program.load(a.elf)
    else:
        if a.source.stat().st_size>60000:raise ValueError('C source exceeds 60000 bytes')
        program=Program.compile(a.source.read_text(encoding='utf-8'),folder/'build')
    # Whole batch must finish reference preflight before any JTAG connection.
    previews=[reference(program,v) for v in cases]
    if a.hardware:
        print('Opening CPU5. Disconnect the web console first.',flush=True)
        cpu=CPU5(a.project,progress=lambda phase:print('  '+phase,flush=True))
        try:cpu.connect();report=cpu.run_many(program,cases)
        finally:cpu.close()
    else:report={'format':'cpu5-sdk-batch-v1','records':previews,'summary':batch_summary(previews)}
    report['program']={'elf_sha256':program.elf_sha256,'text_bytes':program.text_bytes};path=save_report(folder/'batch.json',report);html=save_html_report(folder/'report.html',report)
    print('SOURCE: '+report['summary']['source_kind'])
    for i,r in enumerate(report['records']):print(f'{i+1}: input={r["input"]} output={r["output"]} status={r["status"]} cycles={r["cycles"]}')
    print('REPORT: '+str(path));print('VIEW: '+str(html));print(json.dumps(report['summary'],ensure_ascii=False))
    if a.open:
        import webbrowser
        webbrowser.open(html.resolve().as_uri())
    return 0 if report['summary']['successful_status']==report['summary']['tasks'] else 1
if __name__=='__main__':raise SystemExit(main())
