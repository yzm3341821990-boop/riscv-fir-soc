"""Read-only audit of saved physical long runs; no hardware calls."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np

def audit(folder):
    folder=Path(folder);d=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    s=d['summary'];n=s['requested_samples'];rows=d['frames']
    def need(v,m):
        if not v:raise ValueError(m)
    need(d['status']=='complete' and s['source_kind']=='fpga_jtag','not a complete physical run')
    need(d['clock_hz']==25000000 and s['processed_samples']==n,'clock/count mismatch')
    x=np.asarray(d['input'],dtype=np.int64);h=np.asarray(d['coefficients'],dtype=np.int64)
    need(len(x)==n and len(h)==32,'input layout')
    acc=np.convolve(x,h)[:n];y=np.clip(np.where(acc<0,-((-acc+16384)>>15),(acc+16384)>>15),-32768,32767).tolist()
    need(d['cpu_output']==y and d['fir_output']==y,'full independent convolution mismatch')
    raw=[json.loads(line) for line in (folder/'frames.jsonl').read_text(encoding='utf-8').splitlines()]
    need(len(raw)==len(rows)==s['frames']==(n+224)//225,'frame count')
    sums=dict.fromkeys(('software','hardware_cold','hardware_resident'),0);previous=None
    for i,(r,b) in enumerate(zip(rows,raw)):
        live=b['live'];take=min(225,n-225*i);off=225*i
        need(live['source_kind']=='fpga_jtag' and b['clock_hz']==25000000,'mixed source')
        prefix=([0]*31+x[:off].tolist())[-31:];chunk=x[off:off+take].tolist()+[0]*(225-take)
        need(b['input']==prefix+chunk and b['coefficients']==h.tolist(),'raw input continuity')
        a=np.convolve(np.asarray(b['input'],dtype=np.int64),h)[:256]
        z=np.clip(np.where(a<0,-((-a+16384)>>15),(a+16384)>>15),-32768,32767).tolist()
        need(b['cpu_output']==z and b['fir_output']==z,'raw output mismatch')
        need(r['index']==i and r['sample_offset']==off and r['valid_samples']==take,'frame position')
        current=(live['frame_seq'],live['completed_frames'],live['retired_total'])
        need((r['sequence'],r['completed_frames'],r['retired_total'])==current,'frame counters differ')
        if previous:need((current[0]-previous[0])&65535==1 and (current[1]-previous[1])&0xffffffff==1 and current[2]-previous[2]==live['retired_frame'],'stale frame')
        previous=current
        for k in sums:
            need(type(b['cycles'][k]) is int and b['cycles'][k]>0 and b['cycles'][k]==r['cycles'][k],'cycle provenance')
            sums[k]+=b['cycles'][k]
    need(sums==s['cycles'],'aggregate timing')
    for name,key in [('software','software_ms'),('hardware_cold','cold_ms'),('hardware_resident','resident_ms')]:need(abs(sums[name]/25000-s[key])<1e-9,'converted timing')
    need(abs(sums['software']/sums['hardware_cold']-s['speedup_cold'])<1e-10,'speedup mismatch')
    return dict(status='passed',source_kind='fpga_jtag',run=folder.name,samples=n,blocks=len(raw),raw_output_values_checked=512*len(raw),assembled_values_checked=2*n,cycles=sums,software_ms=s['software_ms'],cold_ms=s['cold_ms'],resident_ms=s['resident_ms'],speedup_cold=s['speedup_cold'],host_wall_ms=s['wall_ms'],scope='Aggregate core calls include 31 history samples per block and padded tail; host wall time is separate. Saved physical observation, not live remeasurement.',files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [folder/'result.json',folder/'frames.jsonl']})

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=audit(a.run);a.output.mkdir(parents=True,exist_ok=True)
    for n in ('result.json','frames.jsonl'):shutil.copyfile(a.run/n,a.output/('observed-'+n))
    (a.output/'board-observation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
