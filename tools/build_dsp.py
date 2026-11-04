"""Compile the separate DSP6 application with the existing pinned C toolchain."""
import argparse,shutil,json,hashlib
from pathlib import Path
from tools.build_app import build,ROOT
def build_dsp(output,source=None):
    d=Path(output);d.mkdir(parents=True,exist_ok=True)
    for n in ('dsp6.h','dsp_signal.h'):shutil.copyfile(ROOT/'firmware/app_runtime'/n,d/n)
    m=build((Path(source) if source else ROOT/'firmware/apps/dsp_stream.c').read_text(encoding='utf-8'),d)
    m['format']='dsp6-c-build-v1'
    m['dsp_runtime_sha256']={n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in ('dsp6.h','dsp_signal.h')}
    (d/'manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--source');a=p.parse_args();print(build_dsp(a.output,a.source))
