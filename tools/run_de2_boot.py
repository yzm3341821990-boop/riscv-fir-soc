"""Verify autonomous FPGA boot/reset with the same RTL staged for Quartus."""
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from tools.prepare_de2_project import ROOT,SOURCES,prepare


def simulate(executable,directory):
    p=subprocess.run([str(executable),'-c','-l','boot.log','-do','do run_de2_boot_batch.do'],
                     cwd=directory,capture_output=True,text=True,errors='replace',timeout=30)
    return p.returncode,(directory/'boot.log').read_text(encoding='utf-8',errors='replace')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_boot'))
    parser.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    a=parser.parse_args();build=a.build_dir.resolve();executable=(a.modelsim_bin/'vsim.exe').resolve()
    if not str(build).isascii() or not executable.is_file(): parser.error('ASCII build path and ModelSim required')
    reports=ROOT/'reports/step15-quartus';reports.mkdir(parents=True,exist_ok=True)
    result_file=reports/'boot-validation.json'
    result_file.write_text('{"status":"incomplete"}\n',encoding='ascii')
    baseline=build/'baseline';kit=prepare(baseline)
    code,log=simulate(executable,baseline)
    (reports/'boot-modelsim.log').write_text(log,encoding='utf-8',newline='\n')
    if code or 'DE2_BOOT_SUITE_PASS' not in log or any(s in log for s in ('** Error:','** Failure:','** Warning:')):
        result_file.write_text('{"status":"fail"}\n',encoding='ascii'); print(log[-6000:]);return 1
    controls=[]
    original=(ROOT/'rtl/board/de2_115_top.vhd').read_text(encoding='ascii')
    faults=[('seed_address_shifted','seed_q<=RAM_SEED_IMAGE(to_integer(boot_index));',
             'seed_q<=RAM_SEED_IMAGE((to_integer(boot_index)+1) mod 256);'),
            ('cpu_released_before_load','if boot_index=255 then','if boot_index=0 then'),
            ('all_seed_words_zero','host_wdata=>seed_q','host_wdata=>(others=>\'0\')')]
    for name,old,new in faults:
        if original.count(old)!=1: raise ValueError('nonunique mutation: '+name)
        with tempfile.TemporaryDirectory(prefix='boot-mutant-',dir=build) as tmp:
            d=Path(tmp);prepare(d)
            (d/'de2_115_top.vhd').write_text(original.replace(old,new),encoding='ascii',newline='\n')
            rc,mlog=simulate(executable,d)
            (reports/(name+'.log')).write_text(mlog,encoding='utf-8',newline='\n')
            killed=rc!=0 and '** Failure: DE2_' in mlog and '** Error:' not in mlog
            controls.append({'name':name,'exit_code':rc,'killed_by_runtime_assertion':killed})
            if not killed: print(mlog[-6000:]);raise ValueError('boot fault survived: '+name)
    extra=('tools/prepare_de2_project.py','tools/run_de2_boot.py','tests/test_de2_project.py',
           'docs/de2-reference-contract.md','programs/c_fir_accel/manifest.json','programs/c_fir_accel/program.elf')
    report={'status':'pass','contract':kit['contract'],'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'completed_runs':4,'reset_phases':3,'negative_controls':controls,
            'scope':'autonomous boot, actual output writes and LED status in RTL simulation',
            'physical_board_verified':False,'hardware_programming':'not_run',
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (*SOURCES,*extra)}}
    result_file.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:report[k] for k in ('status','completed_runs','reset_phases','negative_controls')},indent=2))
    return 0


if __name__=='__main__': raise SystemExit(main())
