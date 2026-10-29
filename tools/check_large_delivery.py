"""Read-only evidence check for the step20 source and prepared Quartus project."""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from tools.run_large_soc import ROOT
from tools.compare_large_blocks import compare
from tools.prepare_de2_display import PINS


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(project):
    folder=ROOT/'reports/step20-large-block';sources={};reports={}
    def need(condition,message):
        if not condition:raise ValueError(message)
    names=['binding-validation.json','memory-validation.json','mmio-validation.json','system-validation.json','board-validation.json','python/validation.json']
    for name in names:
        report=json.loads((folder/name).read_text(encoding='utf-8'));need(report['status']=='pass','incomplete report '+name)
        for source,expected in report['source_sha256'].items():
            need(digest(ROOT/source)==expected,'stale evidence '+name+': '+source)
            if source in sources:need(sources[source]==expected,'inconsistent report source '+source)
            sources[source]=expected
        reports[name]=digest(folder/name)
    python=json.loads((folder/'python/validation.json').read_text())
    current={p.relative_to(ROOT).as_posix() for part in ['model','tests','tools'] for p in (ROOT/part).glob('*.py')}
    need(current==set(python['source_sha256']),'Python report omits a current source')
    system=json.loads((folder/'system-validation.json').read_text());compare(system)
    controls=[]
    for name in ['memory-validation.json','mmio-validation.json','board-validation.json']:
        report=json.loads((folder/name).read_text());controls.extend(report['negative_controls'])
    need(len(controls)==13 and all(c['killed'] for c in controls),'RTL negative control missing')
    board=json.loads((folder/'board-validation.json').read_text())
    need(board['error_indication']['c_error_store_observed'] and board['error_indication']['corrupted_output']==1023,'C tail-output fault not demonstrated')
    manifest=json.loads((project/'project-manifest.json').read_text())
    need(manifest['sample_count']==1024 and manifest['fir_lanes']==4 and manifest['ram_seed_words']==8192,'wrong board configuration')
    for name,value in manifest['source_sha256'].items():need(digest(ROOT/name)==value,'stale prepared source '+name)
    for name,value in manifest['generated_sha256'].items():need(digest(project/name)==value,'modified generated project file '+name)
    qsf=(project/'riscv_fir_de2_large.qsf').read_text()
    locations={name:pin for pin,name in re.findall(r'^set_location_assignment PIN_(\w+) -to (\S+)$',qsf,re.M)}
    standards={name:standard for standard,name in re.findall(r'^set_instance_assignment -name IO_STANDARD "([^"]+)" -to (\S+)$',qsf,re.M)}
    need(locations=={n:p['pin'] for n,p in PINS.items()},'prepared board pin mismatch')
    need(standards=={n:p['standard'] for n,p in PINS.items()},'prepared board voltage mismatch')
    need('TOP_LEVEL_ENTITY de2_115_large_top' in qsf and 'DEVICE EP4CE115F29C7' in qsf,'wrong board top/device')
    comparison=json.loads((folder/'comparison.json').read_text());need(comparison['system_report_sha256']==digest(folder/'system-validation.json'),'stale comparison')
    plot=json.loads((ROOT/'artifacts/step20/plot-manifest.json').read_text());need(plot['system_report_sha256']==digest(folder/'system-validation.json'),'stale plot')
    need(plot['plot_source_sha256']==digest(ROOT/'tools/plot_large_blocks.py'),'stale plot source')
    for name,value in plot['files'].items():need(digest(ROOT/'artifacts/step20'/name)==value,'modified plot '+name)
    links=[]
    for doc in [ROOT/'README.md',ROOT/'THIRD_PARTY.md',*sorted((ROOT/'docs').glob('*.md'))]:
        for target in re.findall(r'!?\[[^\]]*\]\(([^)\s]+)\)',doc.read_text(encoding='utf-8')):
            if target.startswith(('http:','https:','#','mailto:')):continue
            target=target.split('#')[0]
            if target:need((doc.parent/target).exists(),'broken local doc link '+doc.name+': '+target);links.append(target)
    return dict(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),scope='Source, functional-simulation and prepared-project evidence only',
        python_tests=python['unit_tests']['count'],actual_c_runs=system['cases'],checked_commits=system['checked_commits'],
        full_ram_words_per_case=8192,rtl_faults_killed=13,c_tail_output_fault_detected=True,
        board_program_cycles=board['program_cycles'],board_program_cycles_hex=board['program_cycles_hex'],
        pins_checked=len(PINS),doc_links_checked=len(links),report_sha256=reports,
        source_sha256=sources,prepared_project_manifest_sha256=digest(project/'project-manifest.json'),
        generated_sha256=manifest['generated_sha256'],revision=manifest.get('revision','step20-initial'),
        quartus='awaiting_user_recompile' if 'revision' in manifest else 'awaiting_user_compilation',hardware='not_run',github='not_uploaded')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_large'))
    a=p.parse_args();result=check(a.project)
    (ROOT/'reports/step20-large-block/delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','python_tests','actual_c_runs','checked_commits','rtl_faults_killed','board_program_cycles_hex','pins_checked','doc_links_checked']},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
