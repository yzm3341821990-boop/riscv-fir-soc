"""Read and archive a user-compiled parallel FIR image. Never run Quartus."""
import argparse
from datetime import datetime,timezone
import hashlib,json,re,shutil
from pathlib import Path
import sys

ROOT=Path('F:/大三科目工作区域/riscv-fir-soc')
sys.path.insert(0,str(ROOT))
from tools.collect_de2_build import canonical_project_text,report_table_fields,summary_fields

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def collect(directory,report_dir):
    d=Path(directory);out=d/'output_files';m=json.loads((d/'project-manifest.json').read_text(encoding='utf-8'))
    project=m['project'];lanes=m['fir_lanes']
    for path,expected in m['source_sha256'].items():assert digest(ROOT/path)==expected,('source',path)
    for name,expected in m['generated_sha256'].items():
        if name!=project+'.qsf':assert digest(d/name)==expected,('staged',name)
    qsf=d/(project+'.qsf');original=d/'large-qsf-before-build.txt'
    # GUI may reorder its six known default assignments; compare effective settings below.
    assert canonical_project_text(qsf.name,qsf.read_text())==canonical_project_text(qsf.name,original.read_text())
    assert lanes==4 and m['sample_count']==1024
    stages={}
    for stage,label in [('map','Analysis & Synthesis Status'),('fit','Fitter Status'),('asm','Assembler Status')]:
        summary=out/f'{project}.{stage}.summary';report=out/f'{project}.{stage}.rpt'
        fields=summary_fields(summary.read_text(errors='replace')) if summary.exists() else report_table_fields(report.read_text(errors='replace'))
        assert fields[label].startswith('Successful'),(stage,fields.get(label))
        stages[stage]=fields
    assert stages['fit']['Device']==m['reference_device']=='EP4CE115F29C7'
    sta=(out/f'{project}.sta.rpt').read_text(errors='replace')
    timing=[{'type':label,'slack_ns':float(value)} for label,value in re.findall(r'Type\s*:\s*([^\r\n]+)\nSlack\s*:\s*(-?[\d.]+)',(out/f'{project}.sta.summary').read_text())]
    assert len(timing)==18 and min(e['slack_ns'] for e in timing)>=0
    assert re.search(r'CORE_25\s*;\s*Generated\s*;\s*40.000\s*;\s*25.0 MHz',sta)
    coverage={name.strip():[int(a),int(b)] for name,a,b in re.findall(r';\s*((?:Unconstrained |Illegal Clocks)[^;\r\n]*);\s*(\d+)\s*;\s*(\d+)\s*;',sta)}
    assert len(coverage)==6 and all(v==[0,0] for v in coverage.values())
    pins={}
    for line in (out/f'{project}.pin').read_text(errors='replace').splitlines():
        fields=[s.strip() for s in line.split(':')]
        if len(fields)>3 and fields[0] in m['pins']:pins[fields[0]]={'pin':fields[1],'standard':fields[3]}
    assert pins==m['pins'] and len(pins)==66
    fit=(out/f'{project}.fit.rpt').read_text(errors='replace')
    fir_multipliers=sorted(set(re.findall(r'fir_serial:core\|lpm_mult:Mult(\d+)\|',fit)))
    assert len(fir_multipliers)==lanes,(lanes,fir_multipliers)
    warnings=[]
    for p in sorted(out.glob(project+'*.rpt')):
        for level,code,message in re.findall(r'^\s*(Critical Warning|Warning) \((\d+)\): ([^\r\n]+)',p.read_text(errors='replace'),re.M):
            warnings.append(dict(report=p.name,level=level,code=int(code),message=message))
    assert not any(w['level']=='Critical Warning' for w in warnings)
    sof=out/(project+'.sof');assert sof.exists()
    def count(label):return int(re.search(r'[\d,]+',stages['fit'][label])[0].replace(',',''))
    fields=[('logic_elements','Total logic elements'),('registers','Total registers'),('pins','Total pins'),('memory_bits','Total memory bits'),('multiplier_9bit_elements','Embedded Multiplier 9-bit elements')]
    report_dir=Path(report_dir);target=report_dir/'quartus';target.mkdir(parents=True,exist_ok=True)
    files=[p for p in out.glob(project+'*') if p.suffix in ('.rpt','.summary','.pin')]
    files += [qsf,d/(project+'.qpf'),d/'large.sdc',d/'project-manifest.json',original]
    hashes={}
    for p in files:
        shutil.copyfile(p,target/p.name);assert digest(p)==digest(target/p.name)
        hashes['quartus/'+p.name]=digest(p)
    record=dict(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),
        compilation_performed_by='user',quartus_invoked_by_agent=False,project=project,top='de2_115_large_top',
        lanes=lanes,device=m['reference_device'],quartus_version='17.0.0 Build 595 SJ Lite Edition',
        compile_success=True,timing_pass=True,core_clock_mhz=25,stages=stages,
        resources={key:count(label) for key,label in fields},fitted_fir_multiply_channels=len(fir_multipliers),
        worst_setup_slack_ns=min(e['slack_ns'] for e in timing if ' Setup ' in e['type']),
        worst_hold_slack_ns=min(e['slack_ns'] for e in timing if ' Hold ' in e['type']),
        timing_entries=timing,unconstrained_summary=coverage,pins_checked=66,
        warnings=warnings,warning_count=len(warnings),critical_warning_count=0,
        warning_review='Unused signals, IEEE meta-value choices, CPU DSP optimization, LogicLock availability, default drive/slew settings and CLOCK_50 interface advisory retained. Pin locations and IO standards match.',
        source_sha256=m['source_sha256'],staged_files_checked=len(m['generated_sha256'])-1,
        canonical_qsf_matches=True,reports_sha256=hashes,sof_path=str(sof),sof_sha256=digest(sof),
        expected_selftest_cycles=24917,
        hardware_programming='not performed by agent',physical_observation='not_received_for_step20')
    def ram_rows(text):
        start=re.search(r'^;\s*Fitter RAM Summary\s*;$',text,re.M).end()
        keys=None;rows=[]
        for line in text[start:].splitlines():
            if line.startswith('+'):continue
            if not line.strip():
                if rows:break
                continue
            if not line.startswith(';'):break
            fields=[v.strip() for v in line.strip().strip(';').split(';')]
            if keys is None:keys=fields
            elif len(fields)==len(keys):rows.append(dict(zip(keys,fields)))
        return rows
    memories=ram_rows(fit)
    data=next(row for row in memories if 'shared_ram_m9k:shared_memory' in row['Name'])
    seeds=next(row for row in memories if row['Mode']=='ROM')
    assert data['Type']=='M9K' and data['Mode']=='True Dual Port' and data['Clock Mode']=='Single Clock'
    assert [int(data[key]) for key in ['Port A Depth','Port A Width','Port B Depth','Port B Width']]==[8192,32,8192,32]
    assert int(data['M9Ks'])==32 and int(seeds['M9Ks'])==16
    assert int(data['Implementation Bits'])==262144 and int(seeds['Implementation Bits'])==131072
    assert sum(int(row['Implementation Bits']) for row in memories)==record['resources']['memory_bits']
    assert data['Mixed Width RDW Mode']=='Old data'
    record['resources'].update(m9k_blocks=48,data_ram_m9k_blocks=32,seed_rom_m9k_blocks=16)
    record.update(revision='step20-r1-component-binding',sample_count=1024,ram_summary=memories,
        constraints_scope='CLOCK_50 base 50 MHz; core_clock divide-by-2 25 MHz. Only asynchronous KEY0/SW to first synchronizers and human LED/HEX outputs excluded.',
        warning_review='27 ordinary diagnostics retained: unused debug/decode signals; IEEE meta-value synthesis choices; unused high CPU DSP product pieces; LogicLock subscription advisory; human output default drive/slew; CLOCK_50 interface advisory. No STA diagnostics; all fitted pin locations/IO standards match reference.',
        prepared_manifest_sha256=digest(d/'project-manifest.json'),qsf_sha256=digest(qsf),qsf_review='Only the six known GUI defaults differ from the frozen canonical QSF; their ordering changed on save')
    assert record['warning_count']==27
    # Assert the reports were produced after the corrected RAM source was staged.
    assert (out/(project+'.map.rpt')).stat().st_mtime>(d/'shared_ram_m9k.vhd').stat().st_mtime
    verified=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/step20-r1-verified');verified.mkdir(exist_ok=True)
    backup=verified/sof.name;shutil.copyfile(sof,backup);assert digest(backup)==record['sof_sha256']
    record['verified_sof_path']=str(backup)
    (verified/'sof-sha256.txt').write_text(record['sof_sha256']+'  '+sof.name+'\n',encoding='ascii')
    path=report_dir/'quartus-validation.json'
    path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    assert json.loads(path.read_text())['sof_sha256']==digest(sof)
    return record


if __name__=='__main__':
    result=collect(Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_large'),ROOT/'reports/step20-large-block')
    print(json.dumps({k:result[k] for k in ['status','resources','worst_setup_slack_ns','worst_hold_slack_ns','warning_count','critical_warning_count','sof_sha256','verified_sof_path']},indent=2))
