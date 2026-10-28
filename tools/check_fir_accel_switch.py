"""Check actual CPU/FIR GUI macros and signed output readback in console mode."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    report_dir=ROOT/'reports/step12-fir-accelerator'
    accel=json.loads((report_dir/'validation.json').read_text(encoding='utf-8'))
    cpu=json.loads((ROOT/'reports/step11-software-fir/validation.json').read_text(encoding='utf-8'))
    if accel.get('status')!='pass' or cpu.get('status')!='pass':
        raise ValueError('Run both simulation gates first')
    # Refuse to combine an old simulation result with changed implementation.
    for report in (accel,cpu):
        for relative,expected in report['source_sha256'].items():
            if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
                raise ValueError('stale simulation source: '+relative)
    directory=Path(accel['gui_script']).parent
    cpu_macro=cpu['fir_gui_script']
    fir_macro=accel['gui_script']
    expected=[8192,12288,-22528,17408,-12288,15360,-7680,-2048]
    script=['onerror {quit -code 1 -f}', 'onbreak {quit -code 1 -f}']
    for number,macro in enumerate((cpu_macro,fir_macro,cpu_macro,fir_macro),1):
        script.append('do {'+macro+'}')
        top='tb_fir_serial' if number%2==0 else 'tb_tiny_cpu'
        script.append('if {[string tolower [examine sim:/'+top+'/finished]] ne "true"} {error "SWITCH_INCOMPLETE"}')
        if number%2==0:
            for n,value in enumerate(expected):
                script.append('if {[examine -radix decimal {sim:/tb_fir_serial/observed_y('+str(n)+')}] != '+str(value)+'} {error "FIR_SIGNED_READBACK"}')
            script.append('echo "FIR_SIGNED_READBACK_PASS outputs='+','.join(map(str,expected))+'"')
        script.append('echo "FIR_SWITCH_'+str(number)+'_PASS"')
    script+=['echo "FIR_ACCEL_SWITCH_PASS transitions=3"', 'quit -code 0 -f']
    driver=directory/'check_fir_accel_switch.do'
    driver.write_text('\n'.join(script)+'\n',encoding='ascii',newline='\n')
    executable=Path('E:/quartus/modelsim_ase/win32aloem/vsim.exe')
    result=subprocess.run([str(executable),'-c','-l','fir-switch.log','-do','do '+driver.name],
                          cwd=directory,capture_output=True,text=True,errors='replace',timeout=60)
    log=(directory/'fir-switch.log').read_text(encoding='utf-8',errors='replace')
    (report_dir/'gui-switch.log').write_text(log,encoding='utf-8',newline='\n')
    passed=(result.returncode==0 and 'FIR_ACCEL_SWITCH_PASS transitions=3' in log and
            log.count('FIR_SIGNED_READBACK_PASS outputs=')==2 and
            all('FIR_SWITCH_'+str(i)+'_PASS' in log for i in range(1,5)) and
            not any(s in log for s in ('** Error:','** Failure:','** Warning:')))
    sources=(*accel['source_sha256'],*cpu['source_sha256'],'tools/check_fir_accel_switch.py')
    report={'status':'pass' if passed else 'fail','exit_code':result.returncode,
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'loaded_design_transitions':3,'macros_completed':4,
            'actual_signed_output_readbacks':2,'outputs':expected,
            'scope':'production GUI macros in ModelSim console mode; GUI rendering not inspected',
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
    (report_dir/'gui-switch.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:report[k] for k in ('status','loaded_design_transitions','macros_completed','outputs')},indent=2))
    if not passed: print(log[-10000:])
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
