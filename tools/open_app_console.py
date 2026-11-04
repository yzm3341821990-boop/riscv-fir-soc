"""Open/reuse the local CPU5 web service without connecting FPGA hardware."""
import argparse,json,os,subprocess,sys,time,urllib.error,urllib.request,webbrowser
from datetime import datetime,timezone
from pathlib import Path

def read_status(url):
    try:
        with urllib.request.urlopen(url,timeout=.5) as response:return json.load(response)
    except urllib.error.HTTPError as exc:raise ValueError('CPU5 local port returned HTTP '+str(exc.code)) from exc
    except urllib.error.URLError:return None
    except (json.JSONDecodeError,UnicodeError) as exc:raise ValueError('CPU5 local port is occupied by another application') from exc

def start_background(project,port):
    script=project/'desktop/launch_app.py'
    if not script.is_file():raise FileNotFoundError('CPU5 launcher missing: '+str(script))
    logs=project/'logs';logs.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    args=[sys.executable,str(script),'--project',str(project),'--port',str(port)]
    options=dict(cwd=project,stdin=subprocess.DEVNULL,stderr=subprocess.STDOUT,close_fds=True)
    if os.name=='nt':options['creationflags']=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP
    else:options['start_new_session']=True
    with (logs/('web-start-'+stamp+'.log')).open('ab') as log:
        return subprocess.Popen(args,stdout=log,**options)

def ensure_running(project,port=61568,probe=None,spawn=None,pause=None,attempts=50):
    project=Path(project).resolve();probe=probe or read_status;spawn=spawn or start_background;pause=pause or time.sleep
    url=f'http://127.0.0.1:{port}/';status_url=url+'api/status'
    def result(snapshot,state):
        if snapshot.get('app_id')!='riscv-app-runner-v1':raise ValueError('Local port is used by another application')
        if os.path.normcase(str(Path(snapshot.get('project','')).resolve()))!=os.path.normcase(str(project)):
            raise ValueError('Local port is used by another project')
        return dict(status=state,url=url,project=str(project),connection=snapshot.get('connection'),hardware_action=False)
    existing=probe(status_url)
    if existing is not None:return result(existing,'already_running')
    child=spawn(project,port)
    for _ in range(attempts):
        snapshot=probe(status_url)
        if snapshot is not None:return result(snapshot,'started')
        if child.poll() is not None:raise RuntimeError('CPU5 web service exited; see '+str(project/'logs'))
        pause(.1)
    raise TimeoutError('CPU5 web service did not become ready; see '+str(project/'logs'))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_app'));parser.add_argument('--port',type=int,default=61568);parser.add_argument('--no-open',action='store_true');args=parser.parse_args()
    try:
        result=ensure_running(args.project,args.port)
        if not args.no_open:webbrowser.open(result['url'])
        print(json.dumps(result));return 0
    except Exception as exc:print('CPU5_WEB_START_FAILED: '+str(exc),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
