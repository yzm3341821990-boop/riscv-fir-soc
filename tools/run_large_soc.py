"""Run actual C firmware against the 32 KiB M9K SoC, retaining complete traces."""
import argparse,hashlib,json,re,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
from tools.run_pipeline_cpu import RTL
from tools.audit_large_trace import audit

ROOT=Path(__file__).resolve().parents[1]
SOURCES=tuple('rtl/cpu/'+n+'.vhd' for n in RTL if n!='pipeline_cpu')+(
    'rtl/cpu/pipeline_large_cpu.vhd','rtl/fir/fir_serial.vhd','rtl/fir/fir_mmio_large.vhd',
    'rtl/soc/shared_ram_m9k.vhd','rtl/soc/pipeline_large_soc.vhd','sim/tb/tb_large_soc.vhd')


def prepare(directory):
    d=Path(directory);d.mkdir(parents=True,exist_ok=True)
    for f in SOURCES:shutil.copyfile(ROOT/f,d/Path(f).name)
    (d/'compile.do').write_text('catch {quit -sim}\nif {![file exists modelsim.ini]} {vmap -c}\n'
        'if {![file isdirectory work]} {vlib work}\nvmap work work\nvcom -93 '+' '.join(Path(f).name for f in SOURCES)+'\n',encoding='ascii')
    return d


def simulate(exe,directory,cases):
    d=Path(directory)
    lines=['onerror {quit -code 1 -f}','onbreak {quit -code 1 -f}','do compile.do']
    for case in cases:
        source=ROOT/'programs/fir_large'/f"n{case['n']}"/case['mode']
        folder=d/'images'/f"n{case['n']}"/case['mode'];folder.mkdir(parents=True,exist_ok=True)
        for name in ['program.hex','initial_memory.txt','manifest.json']:shutil.copyfile(source/name,folder/name)
        manifest=json.loads((folder/'manifest.json').read_text())
        relative=folder.relative_to(d).as_posix()
        prefix=case['name']
        lines+=['catch {quit -sim}',f'echo LARGE_CASE_BEGIN name={prefix}',
            f'vsim -voptargs=+acc -L altera_mf -gPROGRAM_FILE={relative}/program.hex '+
            f'-gINITIAL_FILE={relative}/initial_memory.txt -gTRACE_FILE={prefix}-trace.txt -gFINAL_FILE={prefix}-memory.txt '+
            f'-gEND_PC={manifest["symbols"]["_program_end"]} -gFIR_LANES={case["lanes"]} -gSTALL_DMA={str(case["wait"]).lower()} work.tb_large_soc',
            'set BreakOnAssertion 3',
            'for {set chunk 0} {$chunk < 1000 && [string tolower [examine sim:/tb_large_soc/execution_done]] ne "true"} {incr chunk} {run 100 us}',
            'if {[string tolower [examine sim:/tb_large_soc/execution_done]] ne "true"} {error "LARGE_NO_END"}',
            f'set fd [open {prefix}-registers.txt w]','puts $fd 00000000',
            'for {set n 1} {$n < 32} {incr n} {puts $fd [format %08X [examine -radix unsigned [format {sim:/tb_large_soc/dut/processor/registers/bank(%d)} $n]]]}','close $fd',
            'force -freeze sim:/tb_large_soc/begin_readback true','run -all',
            'if {[string tolower [examine sim:/tb_large_soc/finished]] ne "true"} {error "LARGE_READBACK_INCOMPLETE"}',
            f'echo LARGE_CASE_PASS name={prefix}']
    lines+=['quit -code 0 -f']
    (d/'run.do').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    p=subprocess.run([str(exe),'-c','-l','large.log','-do','do run.do'],cwd=d,capture_output=True,text=True,errors='replace',timeout=900)
    log=(d/'large.log').read_text(errors='replace')
    if p.returncode or any(x in log for x in ['** Error:','** Failure:','** Warning:']):
        raise ValueError(log[-6000:])
    if re.findall(r'LARGE_CASE_PASS name=(\w+)',log)!=[c['name'] for c in cases]:raise ValueError('missing long simulation case')
    return log


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/large_soc/system'))
    p.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    p.add_argument('--smoke',action='store_true')
    p.add_argument('--audit-only',action='store_true')
    a=p.parse_args();d=a.build_dir.resolve() if a.audit_only else prepare(a.build_dir)
    cases=[{'name':'n64_cold_p4_none','n':64,'mode':'hardware_cold','lanes':4,'wait':False}] if a.smoke else [
        {'name':f'n{n}_{mode}_p{lanes}_{wait}','n':n,'mode':mode,'lanes':lanes,'wait':wait=='periodic'}
        for n in [64,256,1024] for mode in ['software','hardware_cold','hardware_resident'] for lanes in [1,2,4]
        for wait in (['none'] if mode=='software' else ['none','periodic'])]
    if a.audit_only:cases=json.loads((d/'case-list.json').read_text())
    else:
        simulate(a.modelsim_bin/'vsim.exe',d,cases)
        print('LARGE_SIMULATION_PASS cases='+str(len(cases)),flush=True)
        (d/'case-list.json').write_text(json.dumps(cases,indent=2)+'\n',encoding='utf-8')
    for name in SOURCES:
        if (ROOT/name).read_bytes()!=(d/Path(name).name).read_bytes():raise ValueError('staged simulation source changed: '+name)
    rows=[]
    cpu_sha=hashlib.sha256(json.dumps({s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest()
        for s in SOURCES if s.startswith('rtl/cpu/')},sort_keys=True).encode('ascii')).hexdigest()
    def read(path):return [int(v,16) for v in path.read_text().split()]
    for case in cases:
        folder=d/'images'/f"n{case['n']}"/case['mode'];manifest=json.loads((folder/'manifest.json').read_text());name=case['name']
        original=ROOT/'programs/fir_large'/f"n{case['n']}"/case['mode']
        if manifest['sample_count']!=case['n'] or manifest['mode']!=case['mode']:raise ValueError('staged firmware mode/length mismatch')
        for filename in ['program.hex','initial_memory.txt','manifest.json']:
            if (folder/filename).read_bytes()!=(original/filename).read_bytes():raise ValueError('staged firmware changed: '+name+'/'+filename)
        for filename,expected in manifest['artifact_sha256'].items():
            if hashlib.sha256((original/filename).read_bytes()).hexdigest()!=expected:raise ValueError('stale firmware artifact: '+filename)
        for filename,expected in manifest['input_sha256'].items():
            if hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()!=expected:raise ValueError('stale firmware source: '+filename)
        result=audit(d/(name+'-trace.txt'),read(folder/'program.hex'),read(folder/'initial_memory.txt'),manifest,
                     read(d/(name+'-memory.txt')),read(d/(name+'-registers.txt')))
        rows.append({**case,**result,'initial_memory_sha256':manifest['initial_memory_sha256'],
                     'program_sha256':manifest['artifact_sha256']['program.hex'],'cpu_sha256':cpu_sha,
                     'compiler_sha256':manifest['compiler_sha256'],'compiler_flags':' '.join(manifest['compiler_flags']),
                     'trace_sha256':hashlib.sha256((d/(name+'-trace.txt')).read_bytes()).hexdigest()})
        print(f'LARGE_AUDIT_PASS {name} cycles={result["cycles"]}',flush=True)
    reports=ROOT/'reports/step20-large-block';reports.mkdir(exist_ok=True)
    import csv
    with (reports/'measurements.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    provenance=(*SOURCES,'tools/audit_large_trace.py','tools/run_large_soc.py','tools/build_large_firmware.py','tools/large_elf.py','docs/large-block-contract.md')
    report={'status':'pass' if len(rows)==45 else 'development_smoke_pass','generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'cases':len(rows),'checked_commits':sum(x['checked_commits'] for x in rows),'measurements':rows,
        'full_ram_words_per_case':8192,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in provenance},
        'quartus':'not_run','hardware':'not_run','scope':'Actual C executions with full ISA/bus/DMA replay and final RAM/register audit. Board validation separate.'}
    (reports/('system-smoke.json' if a.smoke else 'system-validation.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0


if __name__=='__main__':raise SystemExit(main())
