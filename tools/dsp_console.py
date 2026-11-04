"""User-operated DSP6 benchmark console; starts with no hardware connection."""
import argparse,hashlib,json,secrets,webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from tools.app_console import AppController
from tools.live_session import NativeTransport
from tools.dsp_session import DspSession
APP_ID='riscv-dsp6-v1'
class Client:
    def __init__(self,project,progress):
        self.project=Path(project);self.transport=NativeTransport(project)
        self.session=DspSession(self.transport,hashlib.sha256((self.project/'firmware/program.elf').read_bytes()).hexdigest(),progress)
    def connect(self):
        try:self.transport.connect();return self.session.initialize()
        except Exception:self.transport.close();raise
    def close(self):self.transport.close()
    def run_elf(self,elf,values):return self.session.run(elf,values)
class Controller(AppController):
    def __init__(self,project,factory=None):
        super().__init__(project,factory or (lambda progress:Client(project,progress)))
        self.state['app_id']=APP_ID
        elf=(self.project/'firmware/program.elf').read_bytes()
        manifest=json.loads((self.project/'dsp-project-manifest.json').read_text(encoding='utf-8'))
        if hashlib.sha256(elf).hexdigest()!=manifest['firmware_elf_sha256']:raise ValueError('Frozen benchmark ELF differs')
        self.compilations['benchmark']=elf
    def run_samples(self,body):
        if not isinstance(body,dict) or set(body)!={'samples'} or type(body['samples']) is not int or not 1<=body['samples']<=262144:raise ValueError('Samples must be 1..262144')
        self.run(dict(build_id='benchmark',values=[body['samples']]))
def server_for(c,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,body,mime='application/json; charset=utf-8'):
            b=body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(b)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            try:
                if self.path=='/api/status':self.send(200,c.snapshot())
                elif self.path=='/api/preview':self.send(200,json.loads((c.project/'rtl-preview.json').read_text(encoding='utf-8')))
                elif self.path=='/api/result':self.send(200,c.snapshot()['result'])
                elif self.path=='/api/source':self.send(200,dict(source=(c.project/'firmware/main.c').read_text(encoding='utf-8')))
                elif self.path=='/':self.send(200,(Path(__file__).resolve().parents[1]/'web/dsp_console.html').read_text(encoding='utf-8').replace('__TOKEN__',self.server.auth_token).encode(),'text/html; charset=utf-8')
                elif self.path=='/favicon.ico':self.send(204,b'')
                else:self.send(404,dict(error='Not found'))
            except (OSError,ValueError) as e:self.send(400,dict(error=str(e)))
        def do_POST(self):
            if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{self.server.server_port}') or not secrets.compare_digest(self.headers.get('X-Runner-Token',''),self.server.auth_token):self.send(403,dict(error='Use local console buttons'));return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<=n<=2048 or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Expected small JSON request')
                b=json.loads(self.rfile.read(n) or b'{}')
                if self.path=='/api/run':c.run_samples(b)
                elif b:raise ValueError('Unexpected body')
                elif self.path=='/api/connect':c.connect()
                elif self.path=='/api/disconnect':c.disconnect()
                else:raise ValueError('Unknown operation')
                self.send(202,c.snapshot())
            except (ValueError,TypeError) as e:self.send(400,dict(error=str(e)))
    s=ThreadingHTTPServer(('127.0.0.1',port),Handler);s.auth_token=secrets.token_hex(24);s.daemon_threads=True;return s
def main():
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--port',type=int,default=61571);p.add_argument('--open',action='store_true');a=p.parse_args()
    c=Controller(a.project);s=server_for(c,a.port);url=f'http://127.0.0.1:{s.server_port}/';print('DSP6_READY '+url+' disconnected',flush=True)
    if a.open:webbrowser.open(url)
    try:s.serve_forever()
    finally:
        if c.client:c.client.close()
        s.server_close()
if __name__=='__main__':main()
