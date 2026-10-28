"""Archive the display build with fitted pins, clock coverage and image identity."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from tools.prepare_de2_display import ROOT,PROJECT,PINS,SOURCES
from tools.collect_de2_build import canonical_project_text,summary_fields,report_table_fields


def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def collect(directory):
    d=Path(directory);out=d/'output_files'
    manifest=json.loads((d/'project-manifest.json').read_text())
    for name,h in manifest['source_sha256'].items():
        if digest(ROOT/name)!=h: raise ValueError('stale manifest source: '+name)
        p=d/Path(name).name
        if Path(name).suffix in ('.vhd','.sdc','.do') and p.is_file():
            if p.read_text(encoding='ascii')!=(ROOT/name).read_text(encoding='ascii'):
                raise ValueError('changed staged RTL/constraint: '+name)
    # The project QSF may only have Quartus' documented default additions.
    qsf=d/(PROJECT+'.qsf');qpf=d/(PROJECT+'.qpf')
    base_qsf=d/'display-qsf-before-build.txt'
    if not base_qsf.is_file(): raise ValueError('missing pre-build settings snapshot')
    if digest(base_qsf)!=manifest['generated_sha256'][PROJECT+'.qsf']:
        raise ValueError('changed pre-build settings snapshot')
    if canonical_project_text(qsf.name,qsf.read_text())!=canonical_project_text(qsf.name,base_qsf.read_text()):
        raise ValueError('changed build settings')
    for name,h in manifest['generated_sha256'].items():
        if name.endswith(('.qpf','.qsf')): continue
        if digest(d/name)!=h: raise ValueError('changed generated ROM '+name)
    stages={}
    for stage,key in [('map','Analysis & Synthesis Status'),('fit','Fitter Status'),('asm','Assembler Status')]:
        p=out/f'{PROJECT}.{stage}.summary'
        fields=summary_fields(p.read_text()) if p.exists() else report_table_fields((out/f'{PROJECT}.{stage}.rpt').read_text())
        stages[stage]={'status':fields.get(key,'unknown'),'fields':fields}
    if stages['fit']['fields'].get('Device')!=manifest['reference_device']: raise ValueError('wrong fitted device')
    sta=(out/f'{PROJECT}.sta.rpt').read_text()
    entries=[{'type':s.strip(),'slack_ns':float(v)} for s,v in
             re.findall(r'Type\s*:\s*([^\r\n]+)\nSlack\s*:\s*(-?[\d.]+)',(out/f'{PROJECT}.sta.summary').read_text())]
    if not any("Setup 'CORE_25'" in e['type'] for e in entries): raise ValueError('missing 25 MHz setup check')
    coverage={name.strip():[int(a),int(b)] for name,a,b in
              re.findall(r';\s*(Unconstrained [^;\r\n]+);\s*(\d+)\s*;\s*(\d+)\s*;',sta)}
    if len(coverage)!=5: raise ValueError('incomplete constraint coverage summary')
    fitted={}
    for line in (out/f'{PROJECT}.pin').read_text().splitlines():
        fields=[x.strip() for x in line.split(':')]
        if len(fields)>3 and fields[0] in PINS:
            name=fields[0];fitted[name]={'pin':fields[1],'standard':fields[3]}
    if fitted!=PINS: raise ValueError('fitted pin/voltage mismatch')
    warnings=[]
    for p in out.glob(PROJECT+'*.rpt'):
        for level,code,message in re.findall(r'^\s*(Critical Warning|Warning) \((\d+)\): ([^\r\n]+)',p.read_text(),re.MULTILINE):
            row={'level':level,'code':int(code),'message':message}
            if row not in warnings: warnings.append(row)
    timing=all(e['slack_ns']>=0 for e in entries) and all(x==0 for row in coverage.values() for x in row)
    compiled=all(s['status'].startswith('Successful') for s in stages.values())
    sof=out/(PROJECT+'.sof');compiled=compiled and sof.is_file()
    reports=ROOT/'reports/step16-display';target=reports/'quartus';target.mkdir(parents=True,exist_ok=True)
    hashes={}
    files=[p for p in out.glob(PROJECT+'*') if p.suffix in ('.rpt','.summary','.pin')]
    files += [qsf,qpf,d/'display.sdc',d/'project-manifest.json',base_qsf]
    for p in files:
        shutil.copyfile(p,target/p.name);hashes['quartus/'+p.name]=digest(p)
    def count(key): return int(re.search(r'[\d,]+',stages['fit']['fields'][key])[0].replace(',',''))
    r={'status':'pass' if compiled and timing and not any(w['level']=='Critical Warning' for w in warnings) else 'fail',
       'generated_at_utc':datetime.now(timezone.utc).isoformat(),'reference_device':manifest['reference_device'],
       'compile_success':compiled,'timing_pass':timing,'system_clock_mhz':25,'stages':stages,
       'fitted_pins':fitted,'timing_entries':entries,'unconstrained_summary':coverage,'warnings':warnings,
       'resources':{key:count(label) for key,label in [('logic_elements','Total logic elements'),('registers','Total registers'),
           ('pins','Total pins'),('memory_bits','Total memory bits'),('multiplier_9bit_elements','Embedded Multiplier 9-bit elements')]},
       'worst_setup_slack_ns':min(e['slack_ns'] for e in entries if ' Setup ' in e['type']),
       'worst_hold_slack_ns':min(e['slack_ns'] for e in entries if ' Hold ' in e['type']),
       'source_sha256':{p:digest(ROOT/p) for p in (*SOURCES,'tools/run_de2_display.py','tools/collect_de2_display.py')},
       'staged_source_sha256':{p.name:digest(p) for p in d.glob('*.vhd')},
       'reports_sha256':hashes,'sof_path':str(sof),'sof_sha256':digest(sof),
       'project_path':str(qpf),'hardware_programming':'not_run','physical_display':'not_observed'}
    (reports/'quartus-validation.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_display'))
    r=collect(p.parse_args().project_dir)
    print(json.dumps({k:r[k] for k in ('status','compile_success','timing_pass','resources','worst_setup_slack_ns','worst_hold_slack_ns')},indent=2))
    return 0 if r['status']=='pass' else 1


if __name__=='__main__': raise SystemExit(main())
