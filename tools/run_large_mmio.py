"""Exercise expanded DMA limits and full maximum-length blocks without Quartus."""
import hashlib,json,re,shutil
from datetime import datetime,timezone
from pathlib import Path
from model.fixed_fir import fir_block
from tools.build_large_firmware import dataset
from tools.run_large_memory import run
from tools.run_large_soc import ROOT,prepare,SOURCES

OUT=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/large_soc/mmio-tests')


def main():
    reports=ROOT/'reports/step20-large-block';report_file=reports/'mmio-validation.json'
    report_file.write_text('{"status":"incomplete"}\n')
    d=prepare(OUT/'baseline');shutil.copyfile(ROOT/'sim/tb/tb_large_mmio.vhd',d/'tb_large_mmio.vhd')
    for source,count in [('demo',8),('maximum',4096)]:
        folder=d/'cases'/source;folder.mkdir(parents=True,exist_ok=True)
        if source=='demo':
            manifest=json.loads((ROOT/'programs/c_fir_accel/manifest.json').read_text())
            x,h=manifest['samples'],manifest['coefficients'];y=fir_block(x,h).outputs
            for name,values in [('input',x),('coefficients',h),('expected',y)]:
                (folder/(name+'.hex')).write_text(''.join(f'{v&0xffffffff:08X}\n' for v in values),encoding='ascii')
        else:
            x,h,_=dataset(1024);x=x*4;y=fir_block(x,h).outputs
            for name,values in [('input',x),('coefficients',h),('expected',y)]:
                (folder/(name+'.hex')).write_text(''.join(f'{v&0xffffffff:08X}\n' for v in values),encoding='ascii')
    prefix='do compile.do\nvcom -93 tb_large_mmio.vhd\n'
    def invocation(count,lanes,protocol):
        name='demo' if count==8 else 'maximum';folder='cases/'+name
        return ('catch {quit -sim}\nvsim -L altera_mf '+f'-gINPUT_FILE={folder}/input.hex -gCOEFF_FILE={folder}/coefficients.hex '+
                f'-gOUTPUT_FILE={folder}/expected.hex -gSAMPLE_COUNT={count} -gMAC_LANES={lanes} '+
                f'-gCHECK_PROTOCOL={str(protocol).lower()} work.tb_large_mmio\nset BreakOnAssertion 3\nrun -all\n')
    body=prefix+''.join(invocation(count,lanes,count==8) for lanes in [1,2,4] for count in [8,4096])
    code,log=run(d,body);(reports/'mmio-baseline.log').write_text(log,encoding='utf-8')
    if code or log.count('FIR_LARGE_MMIO_PASS samples=')!=6 or log.count('FIR_LARGE_MMIO_PROTOCOL_PASS')!=3 or any(s in log for s in ['** Failure:','** Error:','** Warning:']):
        raise ValueError(log[-5000:])
    mutations=[('old_1k_dma_bound','source_addr>32764 or dest_addr>32764','source_addr>1020 or dest_addr>1020'),
               ('old_128_count','count>4096','count>128'),
               ('missing_high_address_guard','source_addr>32764 or dest_addr>32764','false')]
    controls=[]
    for name,old,new in mutations:
        m=OUT/name;shutil.copytree(d,m,ignore=shutil.ignore_patterns('work','*.log','*.wlf'),dirs_exist_ok=True)
        p=m/'fir_mmio_large.vhd';text=p.read_text();assert text.count(old)==1;p.write_text(text.replace(old,new),encoding='ascii')
        rc,mutant_log=run(m,prefix+invocation(8 if name!='old_128_count' else 4096,4,name!='old_128_count'))
        assertions=re.findall(r'\*\* Failure: (LARGE_MMIO_[^\r\n]+)',mutant_log)
        killed=rc!=0 and bool(assertions) and '** Error:' not in mutant_log
        controls.append(dict(name=name,killed=killed,assertions=assertions))
        (reports/f'mmio-{name}.log').write_text(mutant_log,encoding='utf-8')
        if not killed:raise ValueError('undetected MMIO fault '+name+'\n'+mutant_log[-1800:])
    paths=(*SOURCES,'sim/tb/tb_large_mmio.vhd','tools/run_large_mmio.py','tools/run_large_memory.py','tools/build_large_firmware.py')
    result=dict(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),lanes=[1,2,4],
        full_blocks={'length':4096,'jobs_per_lane':2,'outputs_checked':4096*2*3},protocol_suites=3,
        checks=['count 0 and 4097 rejected','32764 last word read/write','range overflow and alignment',
                'buffer overlap','busy writes rejected','byte enables and signed input encoding','reset during read/MAC/blocked write',
                'done only after final accepted write','whole 8192-word RAM compared after each full job'],
        negative_controls=controls,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},quartus='not_run',hardware='not_run')
    report_file.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'pass','max_length':4096,'jobs':6,'faults_killed':3},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
