"""Pair actual long-block executions only when inputs, CPU and compiler agree."""
import csv,hashlib,json
from pathlib import Path
from tools.run_large_soc import ROOT


def compare(report):
    def need(condition,message):
        if not condition:raise ValueError(message)
    rows=report['measurements'];index={(r['n'],r['mode'],r['lanes'],r['wait']):r for r in rows}
    expected={(n,mode,p,wait) for n in [64,256,1024] for mode in ['software','hardware_cold','hardware_resident']
              for p in [1,2,4] for wait in ([False] if mode=='software' else [False,True])}
    need(report['status']=='pass' and len(rows)==len(index)==45 and set(index)==expected,'incomplete/duplicate matched long-block matrix')
    for field in ['cpu_sha256','compiler_sha256','compiler_flags']:
        need(len({r[field] for r in rows})==1,'different '+field)
    for n in [64,256,1024]:
        group=[r for r in rows if r['n']==n]
        need(len({r['initial_memory_sha256'] for r in group})==1,'different initial RAM')
        for mode in ['software','hardware_cold','hardware_resident']:
            need(len({r['program_sha256'] for r in group if r['mode']==mode})==1,'different mode firmware across lanes/waits')
        need(len({r['cycles'] for r in group if r['mode']=='software'})==1,'software baseline varies with lanes')
        for row in group:
            need(row['cycles']>0 and row['outputs_checked']==n and row['complete_ram_words_checked']==8192 and row['registers_checked']==32,'incomplete final-state audit')
    comparisons=[]
    for n,mode,p,wait in sorted(index):
        if mode=='software':continue
        r=index[n,mode,p,wait];sw=index[n,'software',p,False]
        need(r['hardware_cycles']>0 and r['dma_reads']==r['dma_writes']==n,'incomplete hardware transfer')
        comparisons.append(dict(sample_count=n,mode=mode,lanes=p,dma_wait='periodic' if wait else 'none',
            software_cycles=sw['cycles'],complete_call_cycles=r['cycles'],kernel_cycles=r['hardware_cycles'],
            cycles_per_sample=r['cycles']/n,software_to_hardware_ratio=sw['cycles']/r['cycles'],
            initial_memory_sha256=r['initial_memory_sha256'],firmware_sha256=r['program_sha256'],
            cpu_sha256=r['cpu_sha256'],compiler_sha256=r['compiler_sha256']))
    return comparisons


def main():
    folder=ROOT/'reports/step20-large-block';source=folder/'system-validation.json'
    report=json.loads(source.read_text());rows=compare(report)
    for name,expected in report['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('stale long-system source '+name)
    with (folder/'comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result=dict(status='pass',scope='Functional RTL simulation of complete C calls; hardware area/timing/physical speedup pending',
        lengths=[64,256,1024],matched_runs=45,comparisons=rows,
        system_report_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        compiler_flags=report['measurements'][0]['compiler_flags'],
        source_sha256={'tools/compare_large_blocks.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (folder/'comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='pass',matched_runs=45,comparisons=len(rows)),indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
