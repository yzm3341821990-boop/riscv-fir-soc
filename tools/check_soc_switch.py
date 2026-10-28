"""Load the real CPU, core and SoC GUI macros; verify signed shared-RAM results."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    reports=ROOT/'reports/step13-fir-soc'
    cpu=json.loads((ROOT/'reports/step11-software-fir/validation.json').read_text(encoding='utf-8'))
    core=json.loads((ROOT/'reports/step12-fir-accelerator/validation.json').read_text(encoding='utf-8'))
    soc=json.loads((reports/'validation.json').read_text(encoding='utf-8'))
    for r in (cpu,core,soc):
        if r.get('status')!='pass': raise ValueError('Run CPU, core and SoC gates first')
        for p,h in r['source_sha256'].items():
            if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h: raise ValueError('stale source: '+p)
    directory=Path(soc['gui_script']).parent
    manifest=json.loads((ROOT/'programs/c_fir_accel/manifest.json').read_text(encoding='utf-8'))
    expected=manifest['expected_outputs'];syms=manifest['symbols']
    macros=[(cpu['fir_gui_script'],'tb_tiny_cpu'),(core['gui_script'],'tb_fir_serial'),
            (soc['gui_script'],'tb_fir_soc'),(cpu['fir_gui_script'],'tb_tiny_cpu'),(soc['gui_script'],'tb_fir_soc')]
    script=['onerror {quit -code 1 -f}','onbreak {quit -code 1 -f}']
    for i,(macro,top) in enumerate(macros,1):
        script.append('do {'+macro+'}')
        script.append('if {[string tolower [examine sim:/'+top+'/finished]] ne "true"} {error "SOC_SWITCH_INCOMPLETE"}')
        if top=='tb_fir_soc':
            for n,value in enumerate(expected):
                path='{sim:/tb_fir_soc/dut/shared_memory/bank('+str(syms['outputs']//4+n)+')}'
                script.append('if {[examine -radix decimal '+path+'] != '+str(value)+'} {error "SOC_SIGNED_READBACK"}')
            script.append('echo "SOC_SIGNED_READBACK_PASS outputs='+','.join(map(str,expected))+'"')
        script.append('echo "SOC_SWITCH_'+str(i)+'_PASS"')
    script+=['echo "SOC_GUI_SWITCH_PASS transitions=4"','quit -code 0 -f']
    (directory/'check_soc_switch.do').write_text('\n'.join(script)+'\n',encoding='ascii',newline='\n')
    result=subprocess.run(['E:/quartus/modelsim_ase/win32aloem/vsim.exe','-c','-l','soc-switch.log','-do','do check_soc_switch.do'],
                          cwd=directory,capture_output=True,text=True,errors='replace',timeout=60)
    log=(directory/'soc-switch.log').read_text(encoding='utf-8',errors='replace')
    (reports/'gui-switch.log').write_text(log,encoding='utf-8',newline='\n')
    passed=(result.returncode==0 and 'SOC_GUI_SWITCH_PASS transitions=4' in log and
            log.count('SOC_SIGNED_READBACK_PASS outputs=')==2 and
            all('SOC_SWITCH_'+str(i)+'_PASS' in log for i in range(1,6)) and
            not any(s in log for s in ('** Error:','** Failure:','** Warning:')))
    files={p:h for r in (cpu,core,soc) for p,h in r['source_sha256'].items()}
    files['tools/check_soc_switch.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report={'status':'pass' if passed else 'fail','exit_code':result.returncode,
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),'macros_completed':5,
            'loaded_design_transitions':4,'actual_signed_output_readbacks':2,'outputs':expected,
            'scope':'actual GUI loader macros in console mode; GUI rendering not inspected','source_sha256':files}
    (reports/'gui-switch.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:report[k] for k in ('status','macros_completed','loaded_design_transitions','outputs')},indent=2))
    if not passed: print(log[-8000:])
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
