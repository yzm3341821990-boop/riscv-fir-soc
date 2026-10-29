"""Validate M9K transactions, CPU address limits and controlled implementation faults."""
import hashlib,json,re,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
from tools.run_large_soc import ROOT,SOURCES,prepare
from model.tiny_cpu import encode_load,encode_store,encode_lui,encode_addi

OUT=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/large_soc/memory-tests')
EXE=Path('E:/quartus/modelsim_ase/win32aloem/vsim.exe')


def run(d,text):
    (d/'test.do').write_text('onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\n'+text+'\nquit -code 0 -f\n',encoding='ascii')
    p=subprocess.run([str(EXE),'-c','-l','test.log','-do','do test.do'],cwd=d,capture_output=True,text=True,errors='replace',timeout=90)
    return p.returncode,(d/'test.log').read_text(errors='replace')


def main():
    reports=ROOT/'reports/step20-large-block';reports.mkdir(exist_ok=True)
    report_file=reports/'memory-validation.json';report_file.write_text('{"status":"incomplete"}\n')
    d=prepare(OUT/'baseline')
    for path in ['sim/tb/tb_shared_ram_m9k.vhd','sim/tb/tb_large_cpu_guard.vhd']:shutil.copyfile(ROOT/path,d/Path(path).name)
    prefix='do compile.do\nvcom -93 tb_shared_ram_m9k.vhd tb_large_cpu_guard.vhd\n'
    cases=[]
    for op,base,offset in [('LW',1024,0),('LW',4096,0),('SW',32768,-4),('LW',32768,-4),('LBU',32768,-1),('LH',32768,-2),('SB',32768,-1),('SH',32768,-2),('LW',32768,0),('SW',32768,0),('LW',32768,-2),('LH',32768,-1),('LW',0x80000000,0),('LW',0x40003000,0),('SW',0x40003000,0),('LB',0x40003000,0),('LW',0x40002000,0)]:
        address=base+offset;width={'B':1,'H':2,'W':4}[op[-1] if op[-1]!='U' else op[-2]]
        valid=(0<=address<32768 and address%width==0) or (base==0x40003000 and op in ['LW','SW'])
        word=encode_store(op,2,1,offset) if op.startswith('S') else encode_load(op,2,1,offset)
        value=(0x12345678>>(8*(address%4)))&((1<<(8*width))-1)
        cases.append(dict(name=f'{op}_{base:08X}_{offset+2048}',instruction=word,base=base,address=address if valid else 0,
            byte_enable=((1<<width)-1)<<(address%4) if valid else 15,value=value,valid=valid))
    def invocation(c):
        setup=encode_addi(1,0,c['base']) if c['base']<2048 else encode_lui(1,c['base']>>12)
        return ('vsim -L altera_mf -gMEM_HEX='+f'{c["instruction"]:08X}'+f' -gLUI_HEX={setup:08X}'
            +f' -gEXPECTED_ADDR={c["address"]} -gEXPECTED_BE={c["byte_enable"]} -gEXPECTED_VALUE={c["value"]}'
            +f' -gEXPECT_FAULT={str(not c["valid"]).lower()} work.tb_large_cpu_guard\nset BreakOnAssertion 3\nrun -all\n')
    body=prefix+'vsim -L altera_mf work.tb_shared_ram_m9k\nset BreakOnAssertion 3\nrun -all\n'
    for c in cases:body+='catch {quit -sim}\n'+invocation(c)+'echo LARGE_ADDRESS_PASS name='+c['name']+'\n'
    code,log=run(d,body);(reports/'memory-baseline.log').write_text(log,encoding='utf-8')
    if code or log.count('LARGE_ADDRESS_PASS name=')!=len(cases) or 'M9K_RAM_PASS' not in log or any(x in log for x in ['** Failure:','** Error:','** Warning:']):raise ValueError(log[-4000:])
    faults=[
        ('byte_mask_ignored','shared_ram_m9k.vhd','byteena_a=>a_be','byteena_a=>"1111"','ram',None),
        ('address_alias','shared_ram_m9k.vhd',"address_a<=a_addr(14 downto 2)","address_a<=\"00000\"&a_addr(9 downto 2)",'ram',None),
        ('collision_unprotected','shared_ram_m9k.vhd','b_allow and not rst and not conflict','b_allow and not rst','ram',None),
        ('response_without_acceptance','shared_ram_m9k.vhd','b_rvalid<=rb','b_rvalid<=b_req','ram',None),
        ('old_1k_cpu_range','pipeline_large_cpu.vhd','unsigned(alu_result)>=32768','unsigned(alu_result)>=1024','cpu',cases[1]),
        ('no_upper_cpu_bound','pipeline_large_cpu.vhd','unsigned(alu_result)>=32768','false','cpu',cases[8]),
    ]
    controls=[]
    for name,file,old,new,kind,c in faults:
        mutant=OUT/name;shutil.copytree(d,mutant,ignore=shutil.ignore_patterns('work','*.log','*.wlf'),dirs_exist_ok=True)
        path=mutant/file;text=path.read_text();assert text.count(old)==1,(name,old)
        path.write_text(text.replace(old,new),encoding='ascii')
        body=prefix+(invocation(c) if kind=='cpu' else 'vsim -L altera_mf work.tb_shared_ram_m9k\nset BreakOnAssertion 3\nrun -all\n')
        rc,mlog=run(mutant,body);(reports/f'memory-{name}.log').write_text(mlog,encoding='utf-8')
        errors=re.findall(r'\*\* Failure: ((?:M9K_|LARGE_GUARD)[^\r\n]+)',mlog)
        killed=rc!=0 and bool(errors) and '** Error:' not in mlog
        controls.append(dict(name=name,killed=killed,assertions=errors))
        if not killed:raise ValueError('undetected memory fault '+name+'\n'+mlog[-1600:])
    source=(*SOURCES,'sim/tb/tb_shared_ram_m9k.vhd','sim/tb/tb_large_cpu_guard.vhd','tools/run_large_memory.py','docs/large-block-contract.md')
    report=dict(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),ram_words_checked=8192,cpu_address_cases=cases,
        negative_controls=controls,model='Quartus 17 ModelSim 10.5b altera_mf.altsyncram',
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source},quartus='not_run',hardware='not_run')
    report_file.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'pass','ram_words':8192,'address_cases':len(cases),'faults_killed':len(controls)},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
