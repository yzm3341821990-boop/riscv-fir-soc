"""Run physical-segment checks, boot/reset tests and controlled display faults."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from tools.prepare_de2_display import ROOT,SOURCES,prepare


def simulate(executable,directory,expected_error=False):
    command=('set expected_error 1; ' if expected_error else '')+'do run_de2_display_batch.do'
    p=subprocess.run([str(executable),'-c','-l','display.log','-do',command],cwd=directory,
                     capture_output=True,text=True,errors='replace',timeout=40)
    return p.returncode,(directory/'display.log').read_text(encoding='utf-8',errors='replace')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_display_sim'))
    parser.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    a=parser.parse_args();build=a.build_dir.resolve();executable=(a.modelsim_bin/'vsim.exe').resolve()
    if not str(build).isascii() or not executable.is_file(): parser.error('ASCII path and ModelSim required')
    reports=ROOT/'reports/step16-display';reports.mkdir(parents=True,exist_ok=True)
    report_path=reports/'simulation-validation.json'
    report_path.write_text('{"status":"incomplete"}\n',encoding='ascii')
    base=build/'baseline';prepare(base);rc,log=simulate(executable,base)
    (reports/'modelsim.log').write_text(log,encoding='utf-8',newline='\n')
    if rc or 'DISPLAY_SUITE_PASS' not in log or any(x in log for x in ('** Warning:','** Error:','** Failure:')):
        print(log[-5000:]);return 1
    match=re.search(r'DISPLAY_PASS completed_runs=4 results_checked=32 program_cycles=(\d+)',log)
    if not match: raise ValueError('missing completed display checks')
    controls=[]
    faults=(
        ('inverted_segments','hex7seg.vhd','"1000000" when "0000"','"0111111" when "0000"'),
        ('wrong_capture_data','de2_115_display_top.vhd','snapshots(result_count)<=dma_wdata;',
         'snapshots(result_count)<=dma_wdata xor x"00000001";'),
        ('reversed_result_index','de2_115_display_top.vhd','unsigned(sw_sync(2 downto 0))',
         'unsigned(not sw_sync(2 downto 0))'),
        ('double_cycle_counter','de2_115_display_top.vhd','program_cycles<=program_cycles+1;',
         'program_cycles<=program_cycles+2;'),
        ('counter_not_frozen','de2_115_display_top.vhd',"elsif boot_done='1' and halted='0' then",
         "elsif boot_done='1' then"),
        ('lost_sign_extension','de2_115_display_top.vhd','snapshots(result_count)<=dma_wdata;',
         'snapshots(result_count)<=x"0000"&dma_wdata(15 downto 0);'))
    for name,file,old,new in faults:
        with tempfile.TemporaryDirectory(prefix='display-mutant-',dir=build) as tmp:
            d=Path(tmp);prepare(d);p=d/file;t=p.read_text(encoding='ascii')
            if t.count(old)!=1: raise ValueError('nonunique fault '+name)
            p.write_text(t.replace(old,new),encoding='ascii',newline='\n')
            rc,mlog=simulate(executable,d)
            (reports/(name+'.log')).write_text(mlog,encoding='utf-8',newline='\n')
            killed=rc!=0 and '** Failure: DISPLAY_' in mlog and '** Error:' not in mlog
            controls.append({'name':name,'exit_code':rc,'killed_by_runtime_assertion':killed})
            if not killed: print(mlog[-3500:]);raise ValueError('display fault survived '+name)
    with tempfile.TemporaryDirectory(prefix='display-error-',dir=build) as tmp:
        d=Path(tmp);prepare(d);p=d/'de2_115_display_top.vhd'
        p.write_text(p.read_text(encoding='ascii').replace('host_wdata=>seed_q',"host_wdata=>(others=>'0')"),encoding='ascii',newline='\n')
        rc,elog=simulate(executable,d,True)
        (reports/'expected-error.log').write_text(elog,encoding='utf-8',newline='\n')
        if rc or 'DISPLAY_EXPECTED_ERROR_PASS' not in elog or '** Failure:' in elog:
            print(elog[-3500:]);raise ValueError('error indication not verified')
    source_files=(*SOURCES,'tools/run_de2_display.py')
    report={'status':'pass','generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'contract':'de2-display-v1','completed_runs':4,'results_checked':32,
        'decoder_nibbles_checked':16,'unknown_nibble_blanks':True,
        'program_cycles':int(match[1]),'cycle_boundary_check':'independent external-clock stopwatch excluding documented reset/loader edges',
        'error_indication_verified':True,'negative_controls':controls,
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files},
        'hardware_programming':'not_run','physical_display':'not_observed'}
    report_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:report[k] for k in ('status','program_cycles','completed_runs','results_checked','negative_controls')},indent=2))
    return 0


if __name__=='__main__': raise SystemExit(main())
