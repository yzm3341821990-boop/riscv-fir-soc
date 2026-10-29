"""Verify the pipelined CPU + FIR system and matched software/hardware calls."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from tools.run_soc import prepare as prepare_soc, load_firmware, read_hex
from tools.run_fir_benchmark import prepare as prepare_benchmark
from tools.audit_soc_trace import audit
from tools.audit_fir_benchmark import audit_benchmark
from tools.fir_benchmark import pair_measurements, compiler_configuration, fingerprint
from tools.run_pipeline_cpu import RTL
from model.tiny_cpu import encode_load

ROOT=Path(__file__).resolve().parents[1]
SOURCES=tuple(f'rtl/cpu/{n}.vhd' for n in RTL)+( 'rtl/fir/fir_serial.vhd','rtl/fir/fir_mmio.vhd',
    'rtl/soc/shared_ram.vhd','rtl/soc/pipeline_fir_soc.vhd','sim/tb/tb_pipeline_fir_soc.vhd',
    'sim/tb/tb_pipeline_fir_benchmark.vhd','sim/tb/tb_pipeline_mmio_guard.vhd','sim/tb/tb_pipeline_bus_order.vhd')


def prepare(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    soc,image,manifest=prepare_soc(directory)
    benchmark,firmwares=prepare_benchmark(directory)
    for relative in SOURCES: shutil.copyfile(ROOT/relative,directory/Path(relative).name)
    helpers=(ROOT/'sim/modelsim/soc_helpers.do').read_text().replace('tb_fir_soc','tb_pipeline_fir_soc')
    helpers+='\n'+(ROOT/'sim/modelsim/benchmark_helpers.do').read_text().replace('tb_fir_benchmark','tb_pipeline_fir_benchmark')
    (directory/'pipeline_soc_helpers.do').write_text(helpers,encoding='ascii')
    compile_line='vcom -93 '+' '.join(Path(p).name for p in SOURCES)+'\n'
    (directory/'compile_pipeline_soc.do').write_text(
        'catch {quit -sim}\nif {![file exists modelsim.ini]} {vmap -c}\n'
        'if {![file isdirectory work]} {vlib work}\nvmap work work\n'+compile_line,encoding='ascii')
    rows=['onerror {quit -code 1 -f}','onbreak {quit -code 1 -f}',
          'do compile_pipeline_soc.do','do pipeline_soc_helpers.do','do soc_config.tcl']
    rows += ['vsim -voptargs=+acc work.tb_pipeline_bus_order','set BreakOnAssertion 3','run -all',
             'if {[string tolower [examine sim:/tb_pipeline_bus_order/finished]] ne "true"} {error "PIPE_ORDER_NOT_FINISHED"}']
    rows += ['foreach case $guard_cases {',
             '  lassign $case name word lui enable fault',
             '  catch {quit -sim}',
             '  vsim -voptargs=+acc -gMEM_WORD=$word -gLUI_WORD=$lui -gENABLE_MMIO=$enable -gEXPECT_FAULT=$fault work.tb_pipeline_mmio_guard',
             '  set BreakOnAssertion 3','  run -all',
             '  if {[examine sim:/tb_pipeline_mmio_guard/finished] ne "TRUE" && [string tolower [examine sim:/tb_pipeline_mmio_guard/finished]] ne "true"} {error "PIPE_GUARD_NOT_FINISHED"}',
             '  echo PIPE_GUARD_CASE_PASS name=$name','}']
    rows += ['foreach case $soc_cases {','  catch {quit -sim}',
             '  load_soc_case {*}$case','  run -all','  check_soc_finished',
             '  dump_soc_state [lindex $case 0]','  echo SOC_CASE_PASS name=[lindex $case 0]','}']
    rows += ['do benchmark_cases.tcl','foreach case $benchmark_cases {',
             '  catch {quit -sim}','  load_benchmark_case $case','  run -all',
             '  check_benchmark_finished','  dump_benchmark_state [lindex $case 0]',
             '  echo BENCH_CASE_PASS name=[lindex $case 0]','}',
             'echo PIPELINE_SOC_SUITE_PASS','quit -code 0 -f']
    (directory/'run_pipeline_soc_batch.do').write_text('\n'.join(rows)+'\n',encoding='ascii')
    return soc,benchmark,image,manifest,firmwares


def simulate(executable,directory,macro='run_pipeline_soc_batch.do'):
    r=subprocess.run([str(executable),'-c','-l','modelsim.log','-do','do '+macro],cwd=directory,
                     capture_output=True,text=True,errors='replace',timeout=240)
    log=(directory/'modelsim.log').read_text(encoding='utf-8',errors='replace')
    (directory/'process-output.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    return r.returncode,log


def check_parts(log,base,soc,bench,image,manifest,firmwares):
    audits=[]
    for case in soc['soc_cases']:
        n=case['name'];part=log.split('SOC_CASE_BEGIN name='+n+'\n',1)[1].split('SOC_CASE_PASS name='+n,1)[0]
        result=audit(part,image,case['initial_memory'],manifest,
                     read_hex(base/'cases'/n/'final_memory.txt'),read_hex(base/'cases'/n/'final_registers.txt'),
                     expect_timeout=case.get('timeout',False))
        audits.append(dict(name=n,**result))
    measured=[]
    platform=fingerprint({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES if p.startswith('rtl/')})
    for case in bench['cases']:
        n,mode=case['name'],case['mode'];bi,bm=firmwares[mode]
        part=log.split('BENCH_CASE_BEGIN name='+n+'\n',1)[1].split('BENCH_CASE_PASS name='+n,1)[0]
        result=audit_benchmark(part,bi,case['initial_memory'],bm,
                              read_hex(base/'results'/f'{n}-memory.txt'),read_hex(base/'results'/f'{n}-registers.txt'),mode=mode)
        edges=re.findall(r'PIPE_EXECUTION_EDGES count=(\d+)',part)
        if len(edges)!=1:raise ValueError('missing independent program edge count')
        result['total_execution_edges']=int(edges[0])
        measured.append(dict(name=n,case=case['case'],wait_policy=case['wait_policy'],
                             initial_memory_sha256=case['initial_memory_sha256'],
                             compiler_configuration=compiler_configuration(bm),layout_sha256=fingerprint(bm['layout']),
                             platform_sha256=platform,**result))
    return audits,measured,pair_measurements(measured)


def controls(executable,base,reports):
    faults=[
      ('disabled_mmio','pipeline_fir_soc.vhd','ENABLE_FIR_MMIO=>true','ENABLE_FIR_MMIO=>false','soc'),
      ('wrong_response_source','pipeline_fir_soc.vhd',"cpu_rdata<=mmio_rdata when response_mmio='1' else a_rdata;",'cpu_rdata<=a_rdata;','soc'),
      ('ungated_rom','tb_pipeline_fir_soc.vhd',"rising_edge(clk) and imem_en='1'","rising_edge(clk) and rst='0' and host_active='0'",'soc'),
      ('bad_commit_next_pc','pipeline_cpu.vhd','commit_next_pc <= wb.next_pc;','commit_next_pc <= wb.pc;','soc'),
      ('dma_output_corrupted','fir_mmio.vhd','std_logic_vector(resize(core_output,32))','std_logic_vector(resize(core_output,32)) xor x"00000001"','soc'),
      ('mmio_subword_allowed','pipeline_cpu.vhd','ex.instruction(14 downto 12)="010"','true','guard'),
      ('response_uses_younger_address','pipeline_fir_soc.vhd',"when response_mmio='1' else a_rdata;", "when mmio_select='1' else a_rdata;",'order'),
    ]
    result=[]
    for name,file,old,new,kind in faults:
        d=base.parent/'mutations'/name
        d.mkdir(parents=True,exist_ok=True)
        for p in base.iterdir():
            if p.is_file() and p.suffix in ('.vhd','.do','.tcl','.hex'):shutil.copyfile(p,d/p.name)
        shutil.copytree(base/'cases'/'hardware_fir',d/'cases'/'hardware_fir',dirs_exist_ok=True)
        target=d/file;t=target.read_text(encoding='ascii')
        if t.count(old)!=1:raise ValueError('nonunique mutation '+name)
        target.write_text(t.replace(old,new,1),encoding='ascii')
        if kind=='soc':
            action='load_soc_case hardware_fir true\nrun -all\ncheck_soc_finished\ndump_soc_state hardware_fir\n'
        elif kind=='guard':
            action=f'vsim work.tb_pipeline_mmio_guard -gMEM_WORD={encode_load("LB",2,1,0)} -gEXPECT_FAULT=true\nset BreakOnAssertion 3\nrun -all\n'
        else:
            action='vsim work.tb_pipeline_bus_order\nset BreakOnAssertion 3\nrun -all\n'
        (d/'mutant.do').write_text('onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\n'
            'do compile_pipeline_soc.do\ndo pipeline_soc_helpers.do\ndo soc_config.tcl\n'+action+'quit -code 0 -f\n',encoding='ascii')
        code,log=simulate(executable,d,'mutant.do')
        (reports/f'mutation-{name}.log').write_text(log,encoding='utf-8')
        assertions=re.findall(r'\*\* (?:Failure|Error): ((?:SOC_|PIPE_)[A-Za-z_]+)',log)
        killed=code!=0 and bool(assertions) and 'vcom-' not in log
        if not killed and code==0 and kind=='soc':
            try:
                image,manifest=load_firmware()
                initial=read_hex(d/'cases/hardware_fir/initial_memory.txt')
                audit(log,image,initial,manifest,read_hex(d/'cases/hardware_fir/final_memory.txt'),
                      read_hex(d/'cases/hardware_fir/final_registers.txt'))
            except ValueError as error:
                killed=True;assertions.append('independent_trace_replay: '+str(error))
        result.append(dict(name=name,exit_code=code,killed=killed,detected_assertions=assertions))
        if not killed:raise ValueError('surviving controlled fault '+name)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/pipeline_soc'))
    p.add_argument('--report-dir',type=Path,default=ROOT/'reports/step18-pipeline-soc')
    p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args();base=a.build_dir.resolve()/'baseline';reports=a.report_dir;reports.mkdir(parents=True,exist_ok=True)
    if not str(base).isascii() or any(c in str(base) for c in '{}\r\n'):p.error('ASCII path required')
    soc,bench,image,manifest,firmwares=prepare(base)
    if a.prepare_only:print('Prepared pipeline SoC in '+str(base));return 0
    report=dict(status='incomplete',contract='pipeline-fir-soc-v1',synthesis='not_run',timing='not_run',hardware='not_run')
    path=reports/'validation.json';path.write_text(json.dumps(report)+'\n')
    code,log=simulate(a.modelsim_bin/'vsim.exe',base)
    (reports/'modelsim.log').write_text(log,encoding='utf-8')
    if code or 'PIPELINE_SOC_SUITE_PASS' not in log or any(s in log for s in ('** Error:','** Failure:','** Warning:')):
        print(log[-4500:]);return 1
    assert re.findall(r'SOC_CASE_PASS name=(\w+)',log)==[c['name'] for c in soc['soc_cases']]
    assert re.findall(r'BENCH_CASE_PASS name=(\w+)',log)==[c['name'] for c in bench['cases']]
    assert re.findall(r'PIPE_GUARD_CASE_PASS name=(\w+)',log)==soc['guard_cases']
    audits,measurements,comparisons=check_parts(log,base,soc,bench,image,manifest,firmwares)
    report.update(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),baseline_exit_code=code,
                  soc_cases=len(audits),benchmark_cases=len(measurements),guard_cases=len(soc['guard_cases']),
                  trace_audits=audits,measurements=measurements,comparisons=comparisons,
                  negative_controls=controls(a.modelsim_bin/'vsim.exe',base,reports),
                  source_sha256={r:hashlib.sha256((ROOT/r).read_bytes()).hexdigest() for r in
                    (*SOURCES,'tools/run_pipeline_soc.py','tools/audit_soc_trace.py','tools/audit_fir_benchmark.py',
                     'docs/pipeline-soc-contract.md')})
    for filename,rows in [('measurements.csv',measurements),('comparison.csv',comparisons)]:
        with (reports/filename).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=sorted({key for row in rows for key in row}));w.writeheader();w.writerows(rows)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','soc_cases','benchmark_cases','guard_cases','comparisons','negative_controls')},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
