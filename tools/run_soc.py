"""Verify C -> CPU -> FIR MMIO -> dual-port RAM and replay the complete trace."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from model.fixed_fir import fir_block,to_memory_word
from model.tiny_cpu import encode_load,encode_store
from tools.audit_soc_trace import audit
from tools.c_demo import load_demo
from tools.run_cpu import SOURCES as CPU_SOURCES
from tools.software_fir import fir_inputs,load_fir

ROOT=Path(__file__).resolve().parents[1]
SOURCES=tuple(p for p in CPU_SOURCES if p.startswith('rtl/cpu/'))+(
    'rtl/fir/fir_serial.vhd','rtl/fir/fir_mmio.vhd','rtl/soc/shared_ram.vhd','rtl/soc/fir_soc.vhd',
    'sim/tb/tb_fir_mmio.vhd','sim/tb/tb_fir_soc.vhd','sim/tb/tb_cpu_mmio_guard.vhd','sim/modelsim/compile_soc.do',
    'sim/modelsim/soc_helpers.do','sim/modelsim/run_soc_batch.do','sim/modelsim/run_soc_gui.do')


def load_firmware():
    return load_demo(ROOT/'programs/c_fir_accel',expected_contract='c-fir-mmio-1k-v1')


def prepare(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    for p in SOURCES:
        text=(ROOT/p).read_text(encoding='ascii')
        if p.endswith('run_soc_gui.do'): text=f'set soc_directory {{{directory.as_posix()}}}\n'+text
        (directory/Path(p).name).write_text(text,encoding='ascii',newline='\n')
    image,manifest=load_firmware();syms=manifest['symbols']
    shutil.copyfile(ROOT/'programs/c_fir_accel/program.hex',directory/'program.hex')
    _,old=load_fir();settings={}
    for name,words in fir_inputs().items():
        raw=struct.pack('<256I',*words)
        x=struct.unpack_from('<8h',raw,old['symbols']['samples'])
        h=struct.unpack_from('<32h',raw,old['symbols']['coefficients'])
        settings[name.replace('software_fir','hardware_fir')]=(x,h)
    soc_cases=[];mmio_cases=[]
    for name,(x,h) in settings.items():
        expected=fir_block(x,h)
        raw=bytearray(struct.pack('<256I',*image.memory_words))
        for symbol,values in [('samples',x),('coefficients',h),('expected',expected.outputs)]:
            struct.pack_into('<'+str(len(values))+'i',raw,syms[symbol],*values)
        memory=struct.unpack('<256I',raw)
        d=directory/'cases'/name;d.mkdir(parents=True,exist_ok=True)
        (d/'initial_memory.txt').write_text(''.join(f'{v:08X}\n' for v in memory),encoding='ascii',newline='\n')
        soc_cases.append({'name':name,'stalls':True,'initial_memory':list(memory),'outputs':list(expected.outputs)})

    def add_mmio(name,x,h,protocol=False):
        d=directory/'mmio'/name;d.mkdir(parents=True,exist_ok=True)
        result=fir_block(x,h)
        for f,values in [('input.hex',x),('coefficients.hex',h),('expected.hex',result.outputs)]:
            (d/f).write_text(''.join(to_memory_word(v)+'\n' for v in values),encoding='ascii',newline='\n')
        mmio_cases.append({'name':name,'sample_count':len(x),'protocol':protocol})
    for name,(x,h) in settings.items(): add_mmio(name,x,h)
    original=json.loads((ROOT/'vectors/manifest.json').read_text())
    def read_signed(p): return [int(v,16)-(1<<32) if int(v,16)&(1<<31) else int(v,16) for v in p.read_text().split()]
    for c in original['cases']:
        if c['sample_count']==0: continue
        x=read_signed(ROOT/'vectors'/c['files']['inputs']['path'])[:128]
        h=read_signed(ROOT/'vectors'/c['files']['coefficients']['path'])
        add_mmio(c['name'],x,h)
    add_mmio('protocol',*settings['hardware_fir'],protocol=True)
    base=soc_cases[0];name='hardware_fir_no_stall'
    (directory/'cases'/name).mkdir(parents=True,exist_ok=True)
    shutil.copyfile(directory/'cases'/base['name']/'initial_memory.txt',directory/'cases'/name/'initial_memory.txt')
    soc_cases.append({**base,'name':name,'stalls':False})
    name='hardware_fir_timeout'
    (directory/'cases'/name).mkdir(parents=True,exist_ok=True)
    shutil.copyfile(directory/'cases'/base['name']/'initial_memory.txt',directory/'cases'/name/'initial_memory.txt')
    soc_cases.append({**base,'name':name,'stalls':True,'timeout':True})
    data={'contract':'fir-mmio-1k-v1','soc_cases':soc_cases,'mmio_cases':mmio_cases}
    (directory/'cases.json').write_text(json.dumps(data,indent=2)+'\n',encoding='ascii',newline='\n')
    rows=[f"set soc_end_pc {syms['_program_end']}",f"set soc_output_addr {syms['outputs']}",
          'set soc_symbols {'+' '.join(f'{k} {v}' for k,v in syms.items())+'}', 'set soc_cases {']
    rows += ['    {%s %s %s %d}'%(c['name'],str(c['stalls']).lower(),str(c.get('timeout',False)).lower(),int(c.get('timeout',False))) for c in soc_cases]
    rows += ['}', 'set mmio_cases {']
    rows += ['    {%s %d %s}'%(c['name'],c['sample_count'],str(c['protocol']).lower()) for c in mmio_cases]
    rows += ['}']
    guards=[]
    for name in ('LB','LBU','LH','LHU','LW'):
        guards.append((name,encode_load(name,2,1,0),0x400030B7,True,name!='LW'))
    for name in ('SB','SH','SW'):
        guards.append((name,encode_store(name,0,1,0),0x400030B7,True,name!='SW'))
    guards.extend([('disabled',encode_load('LW',2,1,0),0x400030B7,False,True),
                   ('misaligned',encode_load('LW',2,1,1),0x400030B7,True,True),
                   ('other_page',encode_load('LW',2,1,0),0x400040B7,True,True)])
    rows+=['set guard_cases {']+['    {%s %d %d %s %s}'%(n,w,b,str(e).lower(),str(f).lower()) for n,w,b,e,f in guards]+['}']
    data['guard_cases']=[g[0] for g in guards]
    (directory/'cases.json').write_text(json.dumps(data,indent=2)+'\n',encoding='ascii',newline='\n')
    (directory/'soc_config.tcl').write_text('\n'.join(rows)+'\n',encoding='ascii',newline='\n')
    return data,image,manifest


def simulate(executable,directory,macro='run_soc_batch.do'):
    p=subprocess.run([str(executable),'-c','-l','modelsim.log','-wlf','soc.wlf','-do','do '+macro],
                     cwd=directory,capture_output=True,text=True,errors='replace',timeout=120)
    log=(directory/'modelsim.log').read_text(encoding='utf-8',errors='replace')
    return p.returncode,log


def read_hex(path): return [int(v,16) for v in path.read_text().split()]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/soc'))
    p.add_argument('--report-dir',type=Path,default=ROOT/'reports/step13-fir-soc')
    p.add_argument('--baseline-only',action='store_true')
    a=p.parse_args();executable=(a.modelsim_bin/'vsim.exe').resolve();build=a.build_dir.resolve()
    if not executable.is_file() or not str(build).isascii() or any(c in str(build) for c in '{}\r\n'):
        p.error('ModelSim and an ASCII build path without braces required')
    reports=a.report_dir;reports.mkdir(parents=True,exist_ok=True)
    def save(data): (reports/'validation.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    save({'status':'incomplete','stage':'baseline'})
    baseline=build/'baseline';suite,image,manifest=prepare(baseline)
    code,log=simulate(executable,baseline)
    (reports/'modelsim.log').write_text(log,encoding='utf-8',newline='\n')
    if (code!=0 or 'FIR_SOC_SUITE_PASS' not in log or '** Error:' in log or '** Failure:' in log or '** Warning:' in log or
        re.findall(r'MMIO_CASE_PASS name=(\w+)',log)!=[c['name'] for c in suite['mmio_cases']] or
        re.findall(r'SOC_CASE_PASS name=(\w+)',log)!=[c['name'] for c in suite['soc_cases']] or
        re.findall(r'GUARD_CASE_PASS name=(\w+)',log)!=suite['guard_cases'] or
        log.count('FIR_MMIO_PROTOCOL_PASS')!=1):
        save({'status':'fail','stage':'baseline','exit_code':code});print(log[-10000:]);return 1
    audits=[]
    for c in suite['soc_cases']:
        name=c['name'];part=log.split('SOC_CASE_BEGIN name='+name+'\n',1)[1].split('SOC_CASE_PASS name='+name,1)[0]
        d=baseline/'cases'/name
        result=audit(part,image,c['initial_memory'],manifest,read_hex(d/'final_memory.txt'),read_hex(d/'final_registers.txt'),expect_timeout=c.get('timeout',False))
        audits.append({'name':name,**result})
    (reports/'trace-audits.json').write_text(json.dumps(audits,indent=2)+'\n',encoding='utf-8',newline='\n')
    if a.baseline_only:
        save({'status':'incomplete','stage':'baseline_passed','trace_audits':audits})
        print(json.dumps(audits,indent=2));return 0
    faults=[
        ('done_before_write','rtl/fir/fir_mmio.vhd',
         "when WAIT_RESULT => if m_valid='1' then state<=WRITE_REQUEST; end if;",
         "when WAIT_RESULT => if m_valid='1' then done_flag<='1'; state<=WRITE_REQUEST; end if;",'mmio','protocol'),
        ('write_ignores_ready','rtl/fir/fir_mmio.vhd',
         "when WRITE_REQUEST =>\n                        if dma_ready='1' then",
         'when WRITE_REQUEST =>\n                        if true then','mmio','protocol'),
        ('read_ignores_ready','rtl/fir/fir_mmio.vhd',
         "when READ_REQUEST => if dma_ready='1' then state<=READ_WAIT; end if;",
         'when READ_REQUEST => state<=READ_WAIT;','mmio','protocol'),
        ('new_job_keeps_history','rtl/fir/fir_mmio.vhd',
         "state<=CLEAR_CORE; done_flag<='0'; err:=(others=>'0');",
         "state<=READ_REQUEST; done_flag<='0'; err:=(others=>'0');",'mmio','hardware_fir'),
        ('source_stride_eight','rtl/fir/fir_mmio.vhd',
         'source_addr+shift_left(sample_index,2)','source_addr+shift_left(sample_index,3)','mmio','hardware_fir'),
        ('unsigned_output_word','rtl/fir/fir_mmio.vhd',
         'std_logic_vector(resize(core_output,32))','std_logic_vector(resize(unsigned(core_output),32))','mmio','hardware_fir'),
        ('busy_write_unprotected','rtl/fir/fir_mmio.vhd',
         'if state/=IDLE then record_error(err,1);','if false then record_error(err,1);','mmio','protocol'),
        ('busy_error_missing','rtl/fir/fir_mmio.vhd',
         'if state/=IDLE then record_error(err,1);','if state/=IDLE then null;','mmio','protocol'),
        ('end_range_not_checked','rtl/fir/fir_mmio.vhd',
         'elsif source_addr+shift_left(count,2)>1024 or dest_addr+shift_left(count,2)>1024 then invalid:=4;',
         'elsif false then invalid:=4;','mmio','protocol'),
        ('overlap_not_checked','rtl/fir/fir_mmio.vhd',
         'elsif source_addr<dest_addr+shift_left(count,2) and dest_addr<source_addr+shift_left(count,2) then invalid:=5;',
         'elsif false then invalid:=5;','mmio','protocol'),
        ('partial_coefficients_accepted','rtl/fir/fir_mmio.vhd',
         'elsif coefficient_mask/=x"FFFFFFFF" then invalid:=6;',
         "elsif coefficient_mask(0)/='1' then invalid:=6;",'mmio','protocol'),
        ('cpu_mmio_disabled','rtl/soc/fir_soc.vhd',
         'generic map(ENABLE_FIR_MMIO=>true)','generic map(ENABLE_FIR_MMIO=>false)','soc','hardware_fir'),
        ('response_wrong_slave','rtl/soc/fir_soc.vhd',
         "cpu_rdata<=mmio_rdata when response_mmio='1' else a_rdata;",'cpu_rdata<=a_rdata;','soc','hardware_fir'),
        ('ram_dma_write_lost','rtl/soc/shared_ram.vhd',
         "if b_we='1' then bank(to_integer(unsigned(b_addr(9 downto 2))))<=b_wdata;",
         "if b_we='1' then null;",'soc','hardware_fir'),
        ('mmio_subwords_allowed','rtl/cpu/tiny_cpu.vhd',
         'instruction_reg(14 downto 12) = "010" and alu_value(1 downto 0) = "00")',
         'instruction_reg(14) = \'0\' and alu_value(1 downto 0) = "00")','guard','LB'),
    ]
    controls=[]
    for name,path,old,new,kind,case in faults:
        original=(ROOT/path).read_text(encoding='ascii')
        if original.count(old)!=1: raise ValueError('mutation anchor not unique: '+name)
        with tempfile.TemporaryDirectory(prefix='soc-mutant-',dir=build) as tmp:
            directory=Path(tmp)
            for pth in SOURCES: shutil.copyfile(baseline/Path(pth).name,directory/Path(pth).name)
            for folder in ('mmio','cases'): shutil.copytree(baseline/folder,directory/folder)
            for filename in ('soc_config.tcl','program.hex'): shutil.copyfile(baseline/filename,directory/filename)
            with (directory/'soc_config.tcl').open('a',encoding='ascii') as config:
                config.write('set guard_cases {}\nset mmio_cases {}\nset soc_cases {}\n')
                if kind=='mmio':
                    c=next(c for c in suite['mmio_cases'] if c['name']==case)
                    config.write('set mmio_cases {{%s %d %s}}\n'%(case,c['sample_count'],str(c['protocol']).lower()))
                elif kind=='soc': config.write('set soc_cases {{hardware_fir true false 0}}\n')
                else: config.write('set guard_cases {{LB %d %d true true}}\n'%(encode_load('LB',2,1,0),0x400030B7))
            (directory/Path(path).name).write_text(original.replace(old,new),encoding='ascii',newline='\n')
            rc,mlog=simulate(executable,directory)
            (reports/(name+'.log')).write_text(mlog,encoding='utf-8',newline='\n')
            failures=re.findall(r'\*\* Failure: ([^\r\n]+)',mlog)
            diagnostics=failures or re.findall(r'(SOC_CHECK_\w+)',mlog)
            # Tcl reports deliberate final-RAM checks as ** Error too; only
            # those named runtime assertions count, never compilation errors.
            errors=re.findall(r'\*\* Error: ([^\r\n]+)',mlog)
            unexpected_errors=[e for e in errors if not e.startswith('SOC_CHECK_')]
            killed=rc!=0 and bool(diagnostics) and not unexpected_errors
            controls.append({'name':name,'scope':kind,'case':case,'exit_code':rc,
                             'killed_by_runtime_checker':killed,'diagnostics':diagnostics})
            if not killed:
                save({'status':'fail','stage':'negative_controls','controls':controls})
                print(mlog[-7000:]);return 1
    version=subprocess.run([str(executable),'-version'],capture_output=True,text=True,errors='replace',timeout=15)
    extra=('tools/run_soc.py','tools/audit_soc_trace.py','tools/build_accel_demo.py','tools/build_c_demo.py',
           'tools/elf32.py','tools/c_demo.py','model/tiny_cpu.py','model/fixed_fir.py','tools/software_fir.py',
           'firmware/c_fir_accel/main.c','firmware/c_array_sum/start.S','firmware/c_array_sum/link.ld',
           'programs/c_fir_accel/manifest.json','programs/c_fir_accel/program.elf','programs/c_fir_accel/program.hex',
           'programs/c_fir_accel/main.s','programs/c_fir_accel/initial_memory.txt','docs/fir-mmio-contract.md',
           'tests/test_soc.py','sim/fixtures/c-fir-accel-trace.json')
    report={'status':'pass','contract':suite['contract'],'numeric_contract':'fir-q15-block-v1',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'simulator':(version.stdout+version.stderr).strip(),'language':'VHDL-93',
            'scope':'CPU/C driver, FIR MMIO, dual-port synchronous RAM, DMA stalls and firmware timeout',
            'cpu_guard_cases':len(suite['guard_cases']),'mmio_cases':len(suite['mmio_cases']),
            'mmio_complete_jobs':2*len(suite['mmio_cases']),
            'mmio_main_samples':2*sum(c['sample_count'] for c in suite['mmio_cases']),
            'system_cases':len(audits),'normal_system_cases':len(audits)-1,'timeout_system_cases':1,
            'checked_commits':sum(c['checked_commits'] for c in audits),
            'checked_cpu_requests':sum(c['cpu_requests'] for c in audits),
            'system_dma_reads':sum(c['dma_reads'] for c in audits),'system_dma_writes':sum(c['dma_writes'] for c in audits),
            'trace_audits':audits,'negative_controls':controls,
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (*SOURCES,*extra)},
            'gui_script':(baseline/'run_soc_gui.do').as_posix(),
            'synthesis':'not_run','timing':'not_run','hardware_programming':'not_run','system_speedup':'not_measured'}
    save(report)
    print(json.dumps({k:report[k] for k in ('status','cpu_guard_cases','mmio_cases','mmio_main_samples',
                      'normal_system_cases','timeout_system_cases','checked_commits','checked_cpu_requests','gui_script')},indent=2))
    print('SOC_MUTATIONS_KILLED='+str(len(controls)))
    return 0


if __name__=='__main__': raise SystemExit(main())
