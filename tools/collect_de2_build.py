"""Collect a completed reference Quartus build; never equate compile and timing success."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

from tools.prepare_de2_project import ROOT,SOURCES

QUARTUS_17_DEFAULT_ADDITIONS={
    'set_global_assignment -name LAST_QUARTUS_VERSION "17.0.0 Lite Edition"',
    'set_global_assignment -name RESERVE_ALL_UNUSED_PINS_NO_OUTPUT_GND "AS INPUT TRI-STATED"',
    'set_instance_assignment -name PARTITION_HIERARCHY root_partition -to | -section_id Top',
    'set_global_assignment -name PARTITION_NETLIST_TYPE SOURCE -section_id Top',
    'set_global_assignment -name PARTITION_FITTER_PRESERVATION_LEVEL PLACEMENT_AND_ROUTING -section_id Top',
    'set_global_assignment -name PARTITION_COLOR 16764057 -section_id Top'}


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary_fields(text):
    return {k.strip():v.strip() for line in text.splitlines() if ':' in line for k,v in [line.split(':',1)]}


def report_table_fields(text):
    return {k.strip():v.strip() for k,v in re.findall(r'^;\s*([^;\r\n]+);\s*([^;\r\n]+);\s*$',text,re.MULTILINE)}


def canonical_project_text(name,text):
    # The 17.0 GUI adds a SOURCE root partition; preserve the exact QSF in the report.
    lines=[line.rstrip() for line in text.splitlines() if line.strip()]
    if name.endswith('.qsf'): lines=[line for line in lines if line not in QUARTUS_17_DEFAULT_ADDITIONS]
    return lines


def collect(directory):
    directory=Path(directory);out=directory/'output_files';prefix='riscv_fir_de2_115'
    manifest=json.loads((directory/'project-manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['source_sha256'].items():
        if digest(ROOT/name)!=expected: raise ValueError('stale project source: '+name)
    for name,expected in manifest['generated_sha256'].items():
        if digest(directory/name)!=expected: raise ValueError('changed image: '+name)
    for name in SOURCES:
        expected=(ROOT/name).read_text(encoding='ascii')
        actual=(directory/Path(name).name).read_text(encoding='ascii')
        same=(canonical_project_text(name,expected)==canonical_project_text(name,actual)
              if name.endswith(('.qsf','.qpf')) else actual==expected)
        if not same:
            raise ValueError('changed staged source: '+name)
    stages={}
    for stage,key in [('map','Analysis & Synthesis Status'),('fit','Fitter Status'),('asm','Assembler Status')]:
        summary_file=out/f'{prefix}.{stage}.summary'
        if summary_file.is_file():
            fields=summary_fields(summary_file.read_text(errors='replace'))
        else:
            # Quartus 17 emits the assembler summary as a table in .asm.rpt only.
            fields=report_table_fields((out/f'{prefix}.{stage}.rpt').read_text(errors='replace'))
        stages[stage]={'status':fields.get(key,'unknown'),'fields':fields}
    summary=(out/f'{prefix}.sta.summary').read_text(errors='replace')
    entries=[{'type':label.strip(),'slack_ns':float(value)}
             for label,value in re.findall(r'Type\s*:\s*([^\r\n]+)\r?\nSlack\s*:\s*(-?[0-9.]+)',summary)]
    if not entries or not any("Setup 'CORE_25'" in e['type'] for e in entries):
        raise ValueError('missing constrained 25 MHz timing evidence')
    sta=(out/f'{prefix}.sta.rpt').read_text(errors='replace')
    coverage={name.strip():{'setup':int(setup),'hold':int(hold)}
              for name,setup,hold in re.findall(r';\s*(Unconstrained [^;\r\n]+);\s*(\d+)\s*;\s*(\d+)\s*;',sta)}
    if not coverage: raise ValueError('missing unconstrained-path summary')
    full_coverage=all(x==0 for row in coverage.values() for x in row.values())
    pin_text=(out/f'{prefix}.pin').read_text(errors='replace')
    expected_pins={'CLOCK_50':('Y2','3.3-V LVTTL'),'RESET_N':('M23','2.5 V'),
                   'LEDR[0]':('G19','2.5 V'),'LEDR[1]':('F19','2.5 V'),
                   'LEDR[2]':('E19','2.5 V'),'LEDR[3]':('F21','2.5 V')}
    pins={}
    for line in pin_text.splitlines():
        fields=[f.strip() for f in line.split(':')]
        if len(fields)>=4 and fields[0] in expected_pins:
            name=fields[0];pins[name]={'location':fields[1],'direction':fields[2],'standard':fields[3]}
            if (fields[1],fields[3])!=expected_pins[name]: raise ValueError('incorrect fitted pin: '+name)
    if set(pins)!=set(expected_pins): raise ValueError('missing fitted reference pins')
    warnings=[]
    for p in sorted(out.glob(prefix+'*.rpt')):
        for level,code,message in re.findall(r'^\s*(Critical Warning|Warning) \((\d+)\): ([^\r\n]+)',p.read_text(errors='replace'),re.MULTILINE):
            row={'level':level,'code':int(code),'message':message}
            if row not in warnings: warnings.append(row)
    timing_pass=all(e['slack_ns']>=0 for e in entries) and full_coverage
    compiled=all(v['status'].startswith('Successful') for v in stages.values())
    critical=[w for w in warnings if w['level']=='Critical Warning']
    sof=out/(prefix+'.sof')
    compiled=compiled and sof.is_file()
    report_dir=ROOT/'reports/step15-quartus';target=report_dir/'quartus';target.mkdir(parents=True,exist_ok=True)
    artifact_hashes={}
    for p in sorted(out.glob(prefix+'*')):
        if p.suffix in ('.rpt','.summary','.pin'):
            shutil.copyfile(p,target/p.name);artifact_hashes['quartus/'+p.name]=digest(p)
    for name in (prefix+'.qpf',prefix+'.qsf','board.sdc','project-manifest.json'):
        p=directory/name
        shutil.copyfile(p,target/name);artifact_hashes['quartus/'+name]=digest(p)
    qsf_text=(directory/(prefix+'.qsf')).read_text(encoding='ascii')
    recorded_additions=[line for line in qsf_text.splitlines() if line in QUARTUS_17_DEFAULT_ADDITIONS]
    fit=stages['fit']['fields']
    def count(label):
        return int(re.search(r'[\d,]+',fit[label])[0].replace(',',''))
    sources=(*SOURCES,'tools/prepare_de2_project.py','tools/run_de2_boot.py','tools/collect_de2_build.py',
             'tests/test_de2_project.py','docs/de2-reference-contract.md',
             'programs/c_fir_accel/program.elf','programs/c_fir_accel/manifest.json')
    report={'status':'pass' if compiled and timing_pass and not critical else 'fail',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),'reference_device':manifest['reference_device'],
            'physical_board_verified':False,'input_clock_mhz':50,'system_clock_mhz':25,
            'compile_success':compiled,'timing_pass':timing_pass,'stages':stages,
            'resources':{'logic_elements':count('Total logic elements'),'registers':count('Total registers'),
                         'memory_bits':count('Total memory bits'),'multiplier_9bit_elements':count('Embedded Multiplier 9-bit elements'),
                         'pins':count('Total pins'),'plls':count('Total PLLs')},
            'timing_entries':entries,'unconstrained_summary':coverage,
            'worst_setup_slack_ns':min(e['slack_ns'] for e in entries if ' Setup ' in e['type']),
            'worst_hold_slack_ns':min(e['slack_ns'] for e in entries if ' Hold ' in e['type']),
            'fitted_pins':pins,'warnings':warnings,'critical_warnings':critical,
            'source_sha256':{p:digest(ROOT/p) for p in sources},
            'staged_source_sha256':{Path(p).name:digest(directory/Path(p).name) for p in SOURCES},
            'quartus_default_settings_recorded':recorded_additions,
            'reports_sha256':artifact_hashes,'sof_path':str(sof),'sof_sha256':digest(sof) if sof.exists() else None,
            'project_path':str(directory/(prefix+'.qpf')),
            'hardware_programming':'not_run','physical_function':'not_observed',
            'scope':'reference Cyclone IV E implementation and static timing under declared constraints; not board signoff'}
    (report_dir/'quartus-validation.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115'))
    a=p.parse_args();r=collect(a.project_dir)
    print(json.dumps({k:r[k] for k in ('status','reference_device','compile_success','timing_pass','resources',
                                     'worst_setup_slack_ns','worst_hold_slack_ns','project_path')},indent=2))
    return 0 if r['status']=='pass' else 1


if __name__=='__main__': raise SystemExit(main())
