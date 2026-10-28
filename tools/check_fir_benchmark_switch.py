"""Exercise real SoC/benchmark GUI macros and read signed benchmark RAM values."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    reports=ROOT/'reports/step14-fir-benchmark'
    bench=json.loads((reports/'validation.json').read_text(encoding='utf-8'))
    soc=json.loads((ROOT/'reports/step13-fir-soc/validation.json').read_text(encoding='utf-8'))
    for report in (soc,bench):
        if report.get('status')!='pass': raise ValueError('Run both validation gates first')
        for name,expected in report['source_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
                raise ValueError('stale validated source: '+name)
    directory=Path(bench['gui_script']).parent
    measurements=json.loads((reports/'measurements.json').read_text(encoding='utf-8'))
    demo=next(r for r in measurements if r['name']=='base_hardware_cold_none')
    expected=demo['outputs']
    script=['onerror {quit -code 1 -f}','onbreak {quit -code 1 -f}']
    for index,(macro,top) in enumerate(((soc['gui_script'],'tb_fir_soc'),(bench['gui_script'],'tb_fir_benchmark'),
                                        (soc['gui_script'],'tb_fir_soc'),(bench['gui_script'],'tb_fir_benchmark')),1):
        script.append('do {'+macro+'}')
        script.append('if {[string tolower [examine sim:/'+top+'/finished]] ne "true"} {error "BENCH_SWITCH_INCOMPLETE"}')
        if top=='tb_fir_benchmark':
            values={168+n:value for n,value in enumerate(expected)}
            values.update({176:2,177:1,178:0,180:demo['hardware_cycles'],181:8})
            for word,value in values.items():
                path='{sim:/tb_fir_benchmark/dut/shared_memory/bank('+str(word)+')}'
                script.append('if {[examine -radix decimal '+path+'] != '+str(value)+'} {error "BENCH_GUI_RAM_READBACK"}')
            script.append('echo "BENCH_SIGNED_READBACK_PASS outputs='+','.join(map(str,expected))+'"')
        script.append('echo "BENCH_SWITCH_'+str(index)+'_PASS"')
    script+=['echo "BENCH_GUI_SWITCH_PASS transitions=3"','quit -code 0 -f']
    (directory/'check_benchmark_switch.do').write_text('\n'.join(script)+'\n',encoding='ascii',newline='\n')
    p=subprocess.run(['E:/quartus/modelsim_ase/win32aloem/vsim.exe','-c','-l','benchmark-switch.log',
                      '-do','do check_benchmark_switch.do'],cwd=directory,capture_output=True,text=True,errors='replace',timeout=60)
    log=(directory/'benchmark-switch.log').read_text(encoding='utf-8',errors='replace')
    (reports/'gui-switch.log').write_text(log,encoding='utf-8',newline='\n')
    passed=(p.returncode==0 and 'BENCH_GUI_SWITCH_PASS transitions=3' in log and
            log.count('BENCH_SIGNED_READBACK_PASS outputs=')==2 and
            all('BENCH_SWITCH_'+str(n)+'_PASS' in log for n in range(1,5)) and
            not any(s in log for s in ('** Error:','** Failure:','** Warning:')))
    files={name:sha for report in (soc,bench) for name,sha in report['source_sha256'].items()}
    files['tools/check_fir_benchmark_switch.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result={'status':'pass' if passed else 'fail','exit_code':p.returncode,
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),'macros_completed':4,
            'loaded_design_transitions':3,'actual_signed_ram_readbacks':2,'outputs':expected,
            'scope':'actual GUI macros in console mode; GUI rendering not inspected','source_sha256':files}
    (reports/'gui-switch.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('status','macros_completed','loaded_design_transitions','outputs')},indent=2))
    if not passed: print(log[-8000:])
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
