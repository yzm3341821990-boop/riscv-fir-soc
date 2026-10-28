"""Measure matched software/cold/resident FIR calls on unchanged SoC RTL."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from tools.fir_benchmark import (matched_cases,pair_measurements,fingerprint,compiler_configuration)
from tools.run_soc import SOURCES as SOC_SOURCES

ROOT=Path(__file__).resolve().parents[1]
SOURCES=tuple(p for p in SOC_SOURCES if p.startswith('rtl/'))+(
    'sim/tb/tb_fir_benchmark.vhd','sim/modelsim/compile_benchmark.do',
    'sim/modelsim/benchmark_helpers.do','sim/modelsim/run_benchmark_batch.do',
    'sim/modelsim/run_benchmark_gui.do')


def prepare(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    for relative in SOURCES:
        text=(ROOT/relative).read_text(encoding='ascii')
        if relative.endswith('run_benchmark_gui.do'):
            text=f'set benchmark_directory {{{directory.as_posix()}}}\n'+text
        (directory/Path(relative).name).write_text(text,encoding='ascii',newline='\n')
    datasets,firmwares=matched_cases()
    for mode in firmwares:
        d=directory/'images'/mode;d.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'programs/fir_benchmark'/mode/'program.hex',d/'program.hex')
    (directory/'results').mkdir(exist_ok=True)
    records=[];rows=['set benchmark_cases {']
    for data in datasets:
        d=directory/'inputs'/data['name'];d.mkdir(parents=True,exist_ok=True)
        (d/'initial_memory.txt').write_text(''.join(f'{v:08X}\n' for v in data['initial_memory']),encoding='ascii',newline='\n')
        for wait_policy in ('none','periodic'):
            for mode,(image,manifest) in firmwares.items():
                name=f"{data['name']}_{mode}_{wait_policy}"
                record={'name':name,'case':data['name'],'mode':mode,'wait_policy':wait_policy,
                        'initial_memory':data['initial_memory'],
                        'initial_memory_sha256':data['initial_memory_sha256'],'outputs':data['outputs']}
                records.append(record)
                rows.append('    {%s %s inputs/%s/initial_memory.txt %d %s %s}' %
                            (name,mode,data['name'],manifest['symbols']['_program_end'],
                             str(wait_policy=='periodic').lower(),str(mode!='software').lower()))
    rows.append('}')
    (directory/'benchmark_cases.tcl').write_text('\n'.join(rows)+'\n',encoding='ascii',newline='\n')
    suite={'contract':'fir-benchmark-cycles-v1','cases':records}
    (directory/'cases.json').write_text(json.dumps(suite,indent=2)+'\n',encoding='ascii',newline='\n')
    return suite,firmwares


def read_hex(path): return [int(v,16) for v in path.read_text().split()]


def simulate(executable,directory,macro='run_benchmark_batch.do'):
    process=subprocess.run([str(executable),'-c','-l','modelsim.log','-wlf','benchmark.wlf','-do','do '+macro],
                           cwd=directory,capture_output=True,text=True,errors='replace',timeout=180)
    log=(directory/'modelsim.log').read_text(encoding='utf-8',errors='replace')
    return process.returncode,log


def main():
    from tools.audit_fir_benchmark import audit_benchmark,measure_interval
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/benchmark'))
    p.add_argument('--report-dir',type=Path,default=ROOT/'reports/step14-fir-benchmark')
    a=p.parse_args();executable=(a.modelsim_bin/'vsim.exe').resolve();build=a.build_dir.resolve()
    if not executable.is_file() or not str(build).isascii() or any(c in str(build) for c in '{}\r\n'):
        p.error('ModelSim and an ASCII build path without braces required')
    reports=a.report_dir;reports.mkdir(parents=True,exist_ok=True)
    def save(data):
        (reports/'validation.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    save({'status':'incomplete','stage':'simulation'})
    baseline=build/'baseline';suite,firmwares=prepare(baseline)
    additional=('tools/run_fir_benchmark.py','tools/fir_benchmark.py','tools/audit_fir_benchmark.py',
                'tools/build_fir_benchmark.py','tools/elf32.py','tools/c_demo.py','tools/audit_soc_trace.py',
                'model/tiny_cpu.py','model/fixed_fir.py','tools/software_fir.py',
                'firmware/fir_benchmark/main.c','firmware/fir_benchmark/link.ld','firmware/c_array_sum/start.S',
                'docs/fir-benchmark-contract.md','tests/test_benchmark_pairing.py',
                'tests/test_benchmark_measurement.py','tests/test_benchmark_firmware.py')
    image_files=tuple(f'programs/fir_benchmark/{mode}/{name}' for mode in firmwares
                      for name in ('program.elf','program.hex','initial_memory.txt','main.s','manifest.json'))
    source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (*SOURCES,*additional,*image_files)}
    platform=fingerprint({name:h for name,h in source_hashes.items() if name.startswith('rtl/')})
    code,log=simulate(executable,baseline)
    (reports/'modelsim.log').write_text(log,encoding='utf-8',newline='\n')
    if (code!=0 or 'FIR_BENCHMARK_SUITE_PASS cases=42' not in log or
        re.findall(r'BENCH_CASE_PASS name=(\w+)',log)!=[c['name'] for c in suite['cases']] or
        any(s in log for s in ('** Error:','** Failure:','** Warning:'))):
        save({'status':'fail','stage':'simulation','exit_code':code});print(log[-9000:]);return 1
    measurements=[];parts={}
    for case in suite['cases']:
        name,mode=case['name'],case['mode'];image,manifest=firmwares[mode]
        part=log.split('BENCH_CASE_BEGIN name='+name+'\n',1)[1].split('BENCH_CASE_PASS name='+name,1)[0]
        parts[name]=part
        result=audit_benchmark(part,image,case['initial_memory'],manifest,
                               read_hex(baseline/'results'/f'{name}-memory.txt'),
                               read_hex(baseline/'results'/f'{name}-registers.txt'),mode=mode)
        measurements.append({'name':name,'case':case['case'],'wait_policy':case['wait_policy'],'mode':mode,
                             'initial_memory_sha256':case['initial_memory_sha256'],
                             'compiler_configuration':compiler_configuration(manifest),
                             'layout_sha256':fingerprint(manifest['layout']),'platform_sha256':platform,**result})
    comparisons=pair_measurements(measurements)
    controls=[]
    symbols=firmwares['hardware_cold'][1]['symbols'];marker=f"{symbols['marker']:08X}"
    cold=parts['base_hardware_cold_none']
    def replace_once(text,old,new):
        if old not in text: raise ValueError('negative-control anchor missing: '+old)
        return text.replace(old,new,1)
    begin_line=next(l for l in cold.splitlines() if f'SOC_BUS mode=W addr={marker} data=00000001' in l)
    end_line=next(l for l in cold.splitlines() if f'SOC_BUS mode=W addr={marker} data=00000002' in l)
    last_poll=next(l for l in cold.splitlines() if 'SOC_BUS mode=R addr=40003004 data=00000002' in l)
    begin_cycle=int(re.search(r'cycle=(\d+)',begin_line)[1]);end_cycle=int(re.search(r'cycle=(\d+)',end_line)[1])
    start_line=next(l for l in cold.splitlines() if 'SOC_BUS mode=W addr=40003000 data=00000001' in l)
    start_cycle=int(re.search(r'cycle=(\d+)',start_line)[1])
    bad_logs=[('missing_begin',cold.replace(begin_line,'',1)),
              ('duplicate_begin',cold.replace(begin_line,begin_line+'\n'+begin_line,1)),
              ('wrong_end_value',replace_once(cold,end_line,end_line.replace('data=00000002','data=00000003'))),
              ('end_before_start',replace_once(cold,end_line,re.sub(r'cycle=\d+',f'cycle={begin_cycle-1}',end_line))),
              ('cold_load_outside_interval',replace_once(cold,begin_line,re.sub(r'cycle=\d+',f'cycle={start_cycle-1}',begin_line))),
              ('stop_before_result',replace_once(cold,end_line,re.sub(r'cycle=\d+',f'cycle={start_cycle+1}',end_line))),
              ('completion_poll_missing',cold.replace(last_poll,'',1))]
    for name,bad in bad_logs:
        try: measure_interval(bad,'hardware_cold',symbols)
        except ValueError as exc: controls.append({'name':name,'rejected':True,'diagnostic':str(exc),'scope':'accepted-event measurement integrity'})
        else:
            save({'status':'fail','stage':'negative_controls','survived':name});raise ValueError('measurement control survived: '+name)
    # A numeric mutation in accepted DMA output must fail the complete ISA/RAM/oracle gate too.
    base_case=next(c for c in suite['cases'] if c['name']=='base_hardware_cold_none')
    dma_line=next(l for l in cold.splitlines() if 'SOC_DMA mode=W' in l)
    bad=replace_once(cold,dma_line,re.sub(r'data=([0-9A-F]{8})',lambda m:f'data={int(m[1],16)^1:08X}',dma_line))
    image,manifest=firmwares['hardware_cold']
    try:
        audit_benchmark(bad,image,base_case['initial_memory'],manifest,
                        read_hex(baseline/'results/base_hardware_cold_none-memory.txt'),
                        read_hex(baseline/'results/base_hardware_cold_none-registers.txt'),mode='hardware_cold')
    except ValueError as exc: controls.append({'name':'corrupt_dma_output','rejected':True,'diagnostic':str(exc),'scope':'independent numerical replay'})
    else: raise ValueError('corrupt DMA output survived')
    for name,expected in source_hashes.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            save({'status':'fail','stage':'source_changed','source':name});raise ValueError('sources changed during verification')
    for filename,data in [('measurements.json',measurements),('comparison.json',comparisons),('negative-controls.json',controls)]:
        (reports/filename).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    with (reports/'comparison.csv').open('w',encoding='ascii',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)
    base=next(c for c in comparisons if c['case']=='base' and c['wait_policy']=='none')
    summary='software=%d cold=%d resident=%d cold_ratio=%.4f resident_ratio=%.4f'%(
        base['software_cycles'],base['hardware_cold_cycles'],base['hardware_resident_cycles'],base['cold_cycle_ratio'],base['resident_cycle_ratio'])
    (baseline/'benchmark_summary.tcl').write_text('set benchmark_summary {'+summary+'}\n',encoding='ascii',newline='\n')
    version=subprocess.run([str(executable),'-version'],capture_output=True,text=True,errors='replace',timeout=15)
    report={'status':'pass','contract':suite['contract'],'numeric_contract':'fir-q15-block-v1',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),'language':'VHDL-93',
            'simulator':(version.stdout+version.stderr).strip(),'measurements':len(measurements),'paired_cases':len(comparisons),
            'datasets':7,'modes':list(firmwares),'wait_policies':['none','periodic'],
            'comparison':comparisons,'negative_controls':controls,
            'source_sha256':source_hashes,'staged_cases_sha256':hashlib.sha256((baseline/'cases.json').read_bytes()).hexdigest(),
            'gui_script':(baseline/'run_benchmark_gui.do').as_posix(),
            'scope':'matched complete-call simulated clock-cycle comparison; no physical speedup claim',
            'synthesis':'not_run','timing':'not_run','hardware_programming':'not_run'}
    save(report)
    print(json.dumps({'status':'pass','measurements':len(measurements),'paired_cases':len(comparisons),
                      'negative_controls':len(controls),'base_no_wait':base,'gui_script':report['gui_script']},indent=2))
    return 0


if __name__=='__main__': raise SystemExit(main())
