"""Verify pipeline board outputs, resets, cycles and deliberately corrupted logic."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import shutil

from tools.prepare_de2_pipeline import ROOT,prepare


def simulate(exe,d):
    r=subprocess.run([str(exe),'-c','-l','board.log','-do','do run_pipeline_board_batch.do'],
                     cwd=d,capture_output=True,text=True,errors='replace',timeout=60)
    return r.returncode,(d/'board.log').read_text(encoding='utf-8',errors='replace')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/pipeline_board'))
    p.add_argument('--report-dir',type=Path,default=ROOT/'reports/step18-pipeline-soc/board')
    a=p.parse_args();base=a.build_dir.resolve();out=a.report_dir;out.mkdir(parents=True,exist_ok=True)
    if not str(base).isascii():p.error('ASCII build path required')
    path=out/'validation.json';path.write_text('{"status":"incomplete"}\n')
    manifest=prepare(base/'baseline');exe=a.modelsim_bin/'vsim.exe'
    rc,log=simulate(exe,base/'baseline');(out/'modelsim.log').write_text(log,encoding='utf-8')
    if rc or any(x in log for x in ('** Failure:','** Error:','** Warning:')):
        print(log[-4500:]);return 1
    m=re.search(r'PIPE_DISPLAY_PASS completed_runs=4 results_checked=32 program_cycles=(\d+)',log)
    if not m:raise ValueError('missing board stopwatch validation')
    faults=[
       ('rom_ignores_enable',"elsif imem_en='1' then imem_data<=PROGRAM_IMAGE",'else imem_data<=PROGRAM_IMAGE'),
       ('counter_double_increment','program_cycles<=program_cycles+1;','program_cycles<=program_cycles+2;'),
       ('capture_wrong_word','snapshots(result_count)<=dma_wdata;','snapshots(result_count)<=dma_wdata xor x"00000001";'),
       ('finish_early',"if commit_valid='1' and unsigned(commit_next_pc)=PROGRAM_END then",'if unsigned(imem_addr)=PROGRAM_END then'),
    ]
    controls=[]
    for name,old,new in faults:
        d=base/name;prepare(d);f=d/'de2_115_pipeline_top.vhd';t=f.read_text()
        if t.count(old)!=1:raise ValueError('ambiguous board mutation '+name)
        f.write_text(t.replace(old,new,1),encoding='ascii')
        rc,mlog=simulate(exe,d);(out/f'mutation-{name}.log').write_text(mlog,encoding='utf-8')
        killed=rc!=0 and '** Failure: PIPE_DISPLAY_' in mlog and '** Error:' not in mlog
        controls.append(dict(name=name,killed=killed,exit_code=rc))
        if not killed:raise ValueError('surviving board fault '+name)
    d=base/'expected_error';prepare(d);f=d/'de2_115_pipeline_top.vhd'
    f.write_text(f.read_text().replace('host_wdata=>seed_q',"host_wdata=>(others=>'0')"),encoding='ascii')
    f=d/'run_pipeline_board_batch.do'
    f.write_text(f.read_text().replace('work.tb_de2_pipeline\n','work.tb_de2_pipeline -gEXPECT_ERROR=true\n'),encoding='ascii')
    rc,elog=simulate(exe,d);(out/'expected-error.log').write_text(elog,encoding='utf-8')
    if rc or 'PIPE_DISPLAY_EXPECTED_ERROR_PASS' not in elog:raise ValueError('error indication not validated')
    report=dict(status='pass',program_cycles=int(m[1]),completed_runs=4,result_selections_checked=32,
                independent_external_clock_stopwatch=True,error_indication_checked=True,negative_controls=controls,
                source_sha256={**manifest['source_sha256'],'tools/run_pipeline_board.py':hashlib.sha256((ROOT/'tools/run_pipeline_board.py').read_bytes()).hexdigest()},
                synthesis='not_run',timing='not_run',hardware='not_run')
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','program_cycles','negative_controls')},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
