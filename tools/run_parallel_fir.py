"""Verify lane arithmetic, identical-firmware SoCs and actual board counter boundaries."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from tools.run_fir_accel import prepare as prepare_core,simulate as simulate_core
from tools.run_pipeline_soc import prepare as prepare_soc,simulate as simulate_soc,check_parts,SOURCES
from tools.run_pipeline_board import simulate as simulate_board
from tools.run_soc import prepare as prepare_mmio
from tools.prepare_de2_parallel import prepare as prepare_board
from tools.parallel_comparison import compare_lanes
from tools.fir_benchmark import fingerprint

ROOT=Path(__file__).resolve().parents[1]


def clean_run(code,log,marker):
    if code or marker not in log or any(x in log for x in ('** Failure:','** Error:','** Warning:')):
        raise ValueError('simulation failed or incomplete:\n'+log[-4500:])


def core_suite(exe,base,reports):
    baseline=base/'core';suite=prepare_core(baseline)
    shutil.copyfile(ROOT/'sim/tb/tb_fir_parallel.vhd',baseline/'tb_fir_parallel.vhd')
    helper=(ROOT/'sim/modelsim/fir_accel_helpers.do').read_text().replace('tb_fir_serial','tb_fir_parallel')
    helper=helper.replace('work.tb_fir_parallel','-gMAC_LANES=$::lanes work.tb_fir_parallel')
    (baseline/'parallel_helpers.do').write_text(helper,encoding='ascii')
    prefix='onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\ncatch {quit -sim}\n'
    prefix+='if {![file exists modelsim.ini]} {vmap -c}\nif {![file isdirectory work]} {vlib work}\nvmap work work\n'
    prefix+='vcom -93 fir_serial.vhd tb_fir_parallel.vhd\ndo parallel_helpers.do\ndo fir_serial_cases.tcl\n'
    body='foreach lanes {1 2 4} {\nforeach case $fir_serial_cases {\ncatch {quit -sim}\n'
    body+='load_fir_serial_case $case\nrun -all\ncheck_fir_serial_finished [lindex $case 1]\n'
    body+='echo PARALLEL_CORE_CASE_PASS lanes=$lanes name=[lindex $case 0] samples=[lindex $case 1]\n}\n}\n'
    (baseline/'parallel.do').write_text(prefix+body+'echo PARALLEL_CORE_SUITE_PASS\nquit -code 0 -f\n',encoding='ascii')
    code,log=simulate_core(exe,baseline,'parallel.do');(reports/'core.log').write_text(log,encoding='utf-8')
    clean_run(code,log,'PARALLEL_CORE_SUITE_PASS')
    matches=re.findall(r'PARALLEL_CORE_CASE_PASS lanes=(\d) name=(\w+) samples=(\d+)',log)
    expected=[(str(p),c['name'],str(c['sample_count'])) for p in (1,2,4) for c in suite['cases']]
    if matches!=expected:raise ValueError('incomplete core case list')
    faults=[
        ('omit_lane','for lane in 0 to MAC_LANES-1 loop','for lane in 0 to MAC_LANES-2 loop','impulse'),
        ('reuse_coefficient','coefficients(tap_index+lane)','coefficients(tap_index)','impulse'),
        ('zero_extend','resize(product,40)','signed(resize(unsigned(product),40))','negative_ties'),
        ('narrow_sum','total := accumulator + ((partials(0)+partials(1)) + (partials(2)+partials(3)));',
         'total := resize(resize(accumulator,32) + resize(partials(0)+partials(1)+partials(2)+partials(3),32),40);','accumulator_extreme'),
        ('omit_last_group','output_acc <= total;\n                            output_data <= quantize(total);',
         'output_acc <= accumulator;\n                            output_data <= quantize(accumulator);','last_tap'),
        ('ignore_backpressure',"if m_ready = '1' then state <= IDLE; end if;",'state <= IDLE;','software_fir'),
        ('ignore_reset_in_mac',"if rst = '1' then","if rst = '1' and state /= MAC then",'protocol'),
    ]
    controls=[];rtl=(baseline/'fir_serial.vhd').read_text()
    for p in (2,4):
        for name,old,new,case in faults:
            if rtl.count(old)!=1:raise ValueError('ambiguous mutation '+name)
            d=base/f'core-p{p}-{name}';shutil.copytree(baseline,d,ignore=shutil.ignore_patterns('work','*.wlf','*.log'),dirs_exist_ok=True)
            (d/'fir_serial.vhd').write_text(rtl.replace(old,new),encoding='ascii')
            row=next(c for c in suite['cases'] if c['name']==case)
            script=prefix+f'set lanes {p}\nload_fir_serial_case {{{case} {row["sample_count"]} {str(row["protocol"]).lower()} true}}\nrun -all\nquit -code 0 -f\n'
            (d/'mutant.do').write_text(script,encoding='ascii')
            rc,mlog=simulate_core(exe,d,'mutant.do');(reports/f'core-p{p}-{name}.log').write_text(mlog,encoding='utf-8')
            assertions=re.findall(r'\*\* Failure: (FIR_[^\r\n]+)',mlog)
            killed=rc!=0 and bool(assertions) and '** Error:' not in mlog
            controls.append(dict(lanes=p,name=name,killed=killed,assertions=assertions))
            if not killed:raise ValueError('surviving core mutation '+str(p)+name+'\n'+mlog[-1000:])
    invalid=[]
    for p in (3,8):
        script=prefix+f'vsim -gMAC_LANES={p} work.tb_fir_parallel\nset BreakOnAssertion 3\nrun -all\nquit -code 0 -f\n'
        (baseline/'invalid.do').write_text(script,encoding='ascii')
        rc,mlog=simulate_core(exe,baseline,'invalid.do');(reports/f'invalid-lanes-{p}.log').write_text(mlog,encoding='utf-8')
        if rc==0 or 'FIR_MAC_LANES_MUST_BE_1_2_OR_4' not in mlog:raise ValueError('invalid lane accepted')
        invalid.append(p)
    return dict(cases=len(matches),samples_per_lane=suite['sample_count'],
        checked_stream_samples=3*suite['sample_count'],mac_edges_per_sample={'1':32,'2':16,'4':8},
        negative_controls=controls,invalid_lanes_rejected=invalid)


def system_suite(exe,base,reports):
    all_measurements=[];runs=[]
    cpu_hash=fingerprint({n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in SOURCES if n.startswith('rtl/cpu/')})
    for lanes in (1,2,4):
        d=base/f'system-p{lanes}';soc,bench,image,manifest,firmwares=prepare_soc(d)
        f=d/'pipeline_soc_helpers.do';text=f.read_text()
        for entity in ['tb_pipeline_fir_soc','tb_pipeline_fir_benchmark']:
            text=text.replace('work.'+entity,f'-gFIR_LANES={lanes} work.'+entity)
        f.write_text(text,encoding='ascii')
        code,log=simulate_soc(exe,d);(reports/f'system-p{lanes}.log').write_text(log,encoding='utf-8')
        clean_run(code,log,'PIPELINE_SOC_SUITE_PASS')
        if re.findall(r'SOC_CASE_PASS name=(\w+)',log)!=[c['name'] for c in soc['soc_cases']]:raise ValueError('missing system case')
        if re.findall(r'BENCH_CASE_PASS name=(\w+)',log)!=[c['name'] for c in bench['cases']]:raise ValueError('missing benchmark case')
        audits,measured,paired=check_parts(log,d,soc,bench,image,manifest,firmwares)
        for row in measured:
            fw=firmwares[row['mode']][0]
            row.update(lanes=lanes,cpu_sha256=cpu_hash,firmware_sha256=fingerprint(list(fw.program_words)),
                       platform_sha256=fingerprint({'rtl':row['platform_sha256'],'FIR_LANES':lanes}))
        all_measurements.extend(measured)
        runs.append(dict(lanes=lanes,soc_cases=len(audits),benchmark_cases=len(measured),trace_audits=audits))
        print(f'PARALLEL_SYSTEM_PASS lanes={lanes} system_cases={len(audits)} benchmark_cases={len(measured)}',flush=True)
    comparison=compare_lanes(all_measurements)
    for name,rows in [('measurements.csv',all_measurements),('comparison.csv',comparison)]:
        with (reports/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=sorted({key for row in rows for key in row}));writer.writeheader();writer.writerows(rows)
    return dict(runs=runs,benchmark_cases=len(all_measurements),measurements=all_measurements,comparison=comparison)


def mmio_suite(exe,base,reports):
    d=base/'mmio';suite,_,_=prepare_mmio(d)
    prefix='onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\ndo compile_soc.do\ndo soc_config.tcl\n'
    load=('lassign $case name count protocol\ncatch {quit -sim}\n'
        'vsim -voptargs=+acc -gMAC_LANES=$lanes -gINPUT_FILE=mmio/$name/input.hex '
        '-gCOEFF_FILE=mmio/$name/coefficients.hex -gOUTPUT_FILE=mmio/$name/expected.hex '
        '-gSAMPLE_COUNT=$count -gCHECK_PROTOCOL=$protocol work.tb_fir_mmio\n'
        'set BreakOnAssertion 3\nrun -all\n'
        'if {[string tolower [examine sim:/tb_fir_mmio/finished]] ne "true"} {error "MMIO_CHECK_INCOMPLETE"}\n')
    (d/'parallel-mmio.do').write_text(prefix+'foreach lanes {1 2 4} {\nforeach case $mmio_cases {\n'+load+
        'echo PARALLEL_MMIO_CASE_PASS lanes=$lanes name=$name\n}\n}\necho PARALLEL_MMIO_SUITE_PASS\nquit -code 0 -f\n',encoding='ascii')
    code,log=simulate_soc(exe,d,'parallel-mmio.do');(reports/'mmio.log').write_text(log,encoding='utf-8')
    clean_run(code,log,'PARALLEL_MMIO_SUITE_PASS')
    expected=[(str(p),c['name']) for p in (1,2,4) for c in suite['mmio_cases']]
    if re.findall(r'PARALLEL_MMIO_CASE_PASS lanes=(\d) name=(\w+)',log)!=expected:raise ValueError('incomplete MMIO cases')
    if log.count('FIR_MMIO_PROTOCOL_PASS')!=3:raise ValueError('missing MMIO protocol checks')
    faults=[
        ('done_before_write',"when WAIT_RESULT => if m_valid='1' then state<=WRITE_REQUEST; end if;",
         "when WAIT_RESULT => if m_valid='1' then done_flag<='1'; state<=WRITE_REQUEST; end if;"),
        ('ignore_write_ready',"when WRITE_REQUEST =>\n                        if dma_ready='1' then",'when WRITE_REQUEST =>\n                        if true then'),
        ('busy_write_unprotected','if state/=IDLE then record_error(err,1);','if false then record_error(err,1);'),
        ('new_job_keeps_history',"state<=CLEAR_CORE; done_flag<='0'; err:=(others=>'0');", "state<=READ_REQUEST; done_flag<='0'; err:=(others=>'0');"),
    ]
    controls=[];rtl=(d/'fir_mmio.vhd').read_text()
    for name,old,new in faults:
        if rtl.count(old)!=1:raise ValueError('ambiguous MMIO mutation '+name)
        mutant=base/('mmio-'+name)
        shutil.copytree(d,mutant,ignore=shutil.ignore_patterns('work','*.wlf','*.log'),dirs_exist_ok=True)
        (mutant/'fir_mmio.vhd').write_text(rtl.replace(old,new),encoding='ascii')
        case=next(c for c in suite['mmio_cases'] if c['name']==('hardware_fir' if name=='new_job_keeps_history' else 'protocol'))
        script=prefix+'set lanes 4\nset case {'+case['name']+' '+str(case['sample_count'])+' '+str(case['protocol']).lower()+'}\n'
        (mutant/'mutant.do').write_text(script+load+'quit -code 0 -f\n',encoding='ascii')
        rc,mlog=simulate_soc(exe,mutant,'mutant.do');(reports/f'mmio-{name}.log').write_text(mlog,encoding='utf-8')
        assertions=re.findall(r'\*\* Failure: (MMIO_[^\r\n]+)',mlog)
        killed=rc!=0 and bool(assertions) and '** Error:' not in mlog
        controls.append(dict(name=name,lanes=4,killed=killed,assertions=assertions))
        if not killed:raise ValueError('surviving MMIO fault '+name+'\n'+mlog[-1200:])
    return dict(cases=len(expected),jobs=2*len(expected),protocol_configurations=3,negative_controls=controls)


def board_suite(exe,base,reports):
    result=[]
    for lanes in (1,2,4):
        d=base/f'board-p{lanes}';manifest=prepare_board(d,lanes)
        qsf=(d/(manifest['project']+'.qsf')).read_text()
        selected=re.findall(r'^set_parameter -name FIR_LANES (\d+)$',qsf,re.M)
        if selected!=[str(lanes)]:raise ValueError('QSF lane selection mismatch')
        code,log=simulate_board(exe,d);(reports/f'board-p{lanes}.log').write_text(log,encoding='utf-8')
        clean_run(code,log,'PIPE_BOARD_SUITE_PASS')
        matched=re.findall(r'PIPE_DISPLAY_PASS completed_runs=4 results_checked=32 program_cycles=(\d+)',log)
        if len(matched)!=1:raise ValueError('missing independent board stopwatch')
        result.append(dict(lanes=lanes,program_cycles=int(matched[0]),completed_runs=4,result_selections_checked=32))
    if result[0]['program_cycles']!=694:raise ValueError('single-lane board compatibility changed')
    if not result[2]['program_cycles']<result[1]['program_cycles']<result[0]['program_cycles']:raise ValueError('board parallelism ineffective')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/parallel_fir'))
    p.add_argument('--report-dir',type=Path,default=ROOT/'reports/step19-parallel-fir')
    p.add_argument('--phase',choices=('core','mmio','system','board','all'),default='all')
    a=p.parse_args();base=a.build_dir.resolve();out=a.report_dir;out.mkdir(parents=True,exist_ok=True)
    if not str(base).isascii() or any(c in str(base) for c in '{}\r\n'):p.error('ASCII build path required')
    exe=a.modelsim_bin/'vsim.exe';path=out/('validation.json' if a.phase=='all' else a.phase+'-validation.json')
    report=dict(status='incomplete',contract='fir-parallel-lanes-v1',quartus='not_run',hardware='not_run',phase=a.phase)
    def save():path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    save()
    for name,fn in [('core',core_suite),('mmio',mmio_suite),('system',system_suite),('board',board_suite)]:
        if a.phase not in ('all',name):continue
        report[name]=fn(exe,base,out);save();print('PARALLEL_PHASE_PASS '+name,flush=True)
    sources=(*SOURCES,'rtl/board/de2_115_pipeline_top.vhd','sim/tb/tb_fir_parallel.vhd','sim/tb/tb_de2_pipeline.vhd','sim/tb/tb_fir_mmio.vhd',
        'tools/run_parallel_fir.py','tools/parallel_comparison.py','tools/prepare_de2_parallel.py','docs/parallel-fir-contract.md',
        'tools/run_fir_accel.py','tools/run_pipeline_soc.py','tools/run_soc.py','tools/fir_benchmark.py',
        'tools/audit_soc_trace.py','tools/audit_fir_benchmark.py','model/fixed_fir.py',
        'tests/test_parallel_comparison.py','tests/test_parallel_project.py','vectors/manifest.json')
    version=subprocess.run([str(exe),'-version'],capture_output=True,text=True,errors='replace',timeout=15)
    report.update(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),
        simulator=(version.stdout+version.stderr).strip(),language='VHDL-93',
        source_sha256={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources})
    save();print('PARALLEL_FIR_PASS '+str(path));return 0


if __name__=='__main__':raise SystemExit(main())
