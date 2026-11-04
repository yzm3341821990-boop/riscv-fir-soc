"""Local C editor/compiler/runner; starts disconnected and never programs FPGA."""
import argparse,hashlib,json,os,secrets,threading,uuid,webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from tools.app_session import AppSession
from tools.app_program import prepare_job
from tools.build_app import build
from tools.live_session import NativeTransport

APP_ID='riscv-app-runner-v1'

class AppClient:
    def __init__(self,project,progress):self.transport=NativeTransport(project);self.session=AppSession(self.transport,progress)
    def connect(self):
        try:self.transport.connect();return self.session.initialize()
        except Exception:self.transport.close();raise
    def close(self):self.transport.close()
    def run_elf(self,elf,values):return self.session.run(elf,values)

class AppController:
    def __init__(self,project,factory=None):
        self.project=Path(project).resolve();self.factory=factory or (lambda progress:AppClient(self.project,progress))
        self.lock=threading.RLock();self.client=None;self.compilations={}
        self.state=dict(app_id=APP_ID,project=str(self.project),connection='disconnected',busy=False,phase='idle',error='',build=None,result=None)
    def snapshot(self):
        with self.lock:return self.state.copy()
    def progress(self,phase):
        with self.lock:self.state['phase']=phase
    def start(self,phase,worker,*args):
        with self.lock:
            if self.state['busy']:raise ValueError('Wait for the current operation')
            self.state.update(busy=True,phase=phase,error='')
        threading.Thread(target=self._worker,args=(worker,args),daemon=True).start()
    def _worker(self,worker,args):
        try:worker(*args)
        except Exception as exc:
            with self.lock:self.state.update(error=str(exc),phase='error')
        finally:
            with self.lock:self.state['busy']=False
    def connect(self):
        if self.client:raise ValueError('Already connected')
        self.start('connecting',self._connect)
    def _connect(self):
        client=self.factory(self.progress)
        try:info=client.connect()
        except Exception:
            client.close()
            with self.lock:self.state['connection']='error'
            raise
        with self.lock:self.client=client;self.state.update(connection='connected',identity=info,phase='idle')
    def disconnect(self):self.start('disconnecting',self._disconnect)
    def _disconnect(self):
        if self.client:self.client.close()
        with self.lock:self.client=None;self.state.update(connection='disconnected',phase='idle')
    def compile(self,body):
        if not isinstance(body,dict) or set(body)!={'source'}:raise ValueError('Submit C source')
        source=body['source']
        if not isinstance(source,str) or not 1<=len(source.encode())<=60000:raise ValueError('C source must be 1..60000 bytes')
        self.start('compiling',self._compile,source)
    def _compile(self,source):
        key=uuid.uuid4().hex;folder=self.project/'builds'/key
        with self.lock:self.state['build']=None
        m=build(source,folder);elf=(folder/'program.elf').read_bytes()
        result=dict(id=key,source_sha256=m['source_sha256'],elf_sha256=m['elf_sha256'],text_bytes=m['text_bytes'],capacity_bytes=16380,diagnostics=m['diagnostics'])
        with self.lock:
            self.compilations[key]=elf
            # Bound in-memory artifacts; original source/ELF/log persist under builds.
            while len(self.compilations)>16:self.compilations.pop(next(iter(self.compilations)))
            self.state.update(build=result,phase='compiled')
    def run(self,body,reference=False):
        if not isinstance(body,dict) or set(body)!={'build_id','values'}:raise ValueError('Compile and submit integer input')
        elf=self.compilations.get(body['build_id']);values=body['values']
        if elf is None:raise ValueError('Build is missing or expired; compile again')
        if not isinstance(values,list) or len(values)>128 or any(type(v) is not int or not -2**31<=v<2**31 for v in values):raise ValueError('At most 128 signed32 inputs')
        if not reference and not self.client:raise ValueError('Connect the CPU5 image before running on FPGA')
        self.start('reference',self._run,elf,values,reference)
    def _run(self,elf,values,reference):
        if reference:
            image,_,ref=prepare_job(elf,values)
            result=dict(format='cpu5-reference-v1',image='CPU5',source_kind='isa_reference',input=values,output=ref['output'],console=ref['console'],status=ref['status'],retired=ref['commits'],text_bytes=len(image.program_words)*4,elf_sha256=hashlib.sha256(elf).hexdigest())
        else:
            try:result=self.client.run_elf(elf,values)
            except Exception:
                self.client.close()
                with self.lock:self.client=None;self.state['connection']='error'
                raise
            records=self.project/'run-records';records.mkdir(exist_ok=True)
            stamp=uuid.uuid4().hex
            (records/(stamp+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            temporary=records/'last-run.json.new';temporary.write_text(json.dumps(result,ensure_ascii=False)+'\n',encoding='utf-8');os.replace(temporary,records/'last-run.json')
        with self.lock:self.state.update(result=result,phase='complete')

def server_for(controller,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,body,mime='application/json; charset=utf-8'):
            if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            u=urlsplit(self.path)
            try:
                if u.path=='/api/status':self.send(200,controller.snapshot())
                elif u.path=='/api/example':
                    n=parse_qs(u.query).get('name',['number_lab'])[0]
                    if n not in ('number_lab','matrix','fir'):raise ValueError('Unknown example')
                    self.send(200,dict(source=(controller.project/'examples'/n/'main.c').read_text(encoding='utf-8')))
                elif u.path=='/api/preview':self.send(200,json.loads((controller.project/'rtl-preview.json').read_text(encoding='utf-8')))
                elif u.path=='/':
                    html=(Path(__file__).resolve().parents[1]/'web/app_console.html').read_text(encoding='utf-8').replace('__RUNNER_TOKEN__',self.server.auth_token)
                    self.send(200,html.encode(),'text/html; charset=utf-8')
                elif u.path=='/favicon.ico':self.send(204,b'')
                else:self.send(404,{'error':'Not found'})
            except (ValueError,OSError) as exc:self.send(400,{'error':str(exc)})
        def do_POST(self):
            origin=self.headers.get('Origin')
            if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':self.send(403,{'error':'Use the local console'});return
            if not secrets.compare_digest(self.headers.get('X-Runner-Token',''),self.server.auth_token):self.send(403,{'error':'Use the console buttons'});return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<=n<=100000 or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Invalid JSON request')
                b=json.loads(self.rfile.read(n) or b'{}');path=urlsplit(self.path).path
                if path=='/api/compile':controller.compile(b)
                elif path in ('/api/run','/api/reference'):controller.run(b,path.endswith('reference'))
                elif b:raise ValueError('Unexpected parameters')
                elif path=='/api/connect':controller.connect()
                elif path=='/api/disconnect':controller.disconnect()
                else:raise ValueError('Unknown operation')
                self.send(202,controller.snapshot())
            except (ValueError,TypeError,OSError) as exc:self.send(400,{'error':str(exc)})
    s=ThreadingHTTPServer(('127.0.0.1',port),Handler);s.daemon_threads=True;s.auth_token=secrets.token_hex(24);return s

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--port',type=int,default=61568);p.add_argument('--open',action='store_true');a=p.parse_args()
    c=AppController(a.project);s=server_for(c,a.port);url=f'http://127.0.0.1:{s.server_port}/'
    print('CPU5_READY '+url+' (disconnected; no JTAG opened)',flush=True)
    if a.open:webbrowser.open(url)
    try:s.serve_forever()
    finally:
        if c.client:c.client.close()
        s.server_close()
if __name__=='__main__':main()
