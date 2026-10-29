"""Validate real board marker counts, resets, latency sensitivity and checker faults."""
import argparse,concurrent.futures,hashlib,json,re,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
from tools.prepare_de2_benchmark import ROOT,prepare

REFERENCES=[24045,1126,867,116856,3622,3363,489233,13608,13349]


def execute(exe,d,macro='run_benchmark_batch.do',logfile='benchmark.log'):
    p=subprocess.run([str(exe),'-c','-l',logfile,'-do','do '+macro],cwd=d,capture_output=True,text=True,errors='replace',timeout=600)
    return p.returncode,(d/logfile).read_text(errors='replace')


def replace_once(path,old,new):
    text=path.read_text();assert text.count(old)==1,(path.name,old);path.write_text(text.replace(old,new),encoding='ascii')


def stall_first_dma(d):
    path=d/'de2_115_benchmark_top.vhd'
    replace_once(path,'    signal system_reset :',"    signal injected_count : unsigned(4 downto 0) := (others=>'0');\n    signal injected_allow : std_logic;\n    signal system_reset :")
    replace_once(path,'    clock_divider : process',
        "    injected_allow<='1' when injected_count=31 else '0';\n    injection : process(core_clock) begin if rising_edge(core_clock) then\n"
        "        if system_reset='1' then injected_count<=(others=>'0');\n        elsif dma_req='1' and injected_count<31 then injected_count<=injected_count+1;end if;end if;end process;\n"
        '    clock_divider : process')
    replace_once(path,"dma_allow=>'1'","dma_allow=>injected_allow")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/board_benchmark/final'))
    parser.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    a=parser.parse_args();base=a.build_dir.resolve();exe=a.modelsim_bin/'vsim.exe'
    reports=ROOT/'reports/step21-board-benchmark';report_file=reports/'validation.json';report_file.write_text('{"status":"incomplete"}\n')
    # Unit tests also verify that small-width counters cannot silently wrap.
    td=base/'timer';td.mkdir(parents=True,exist_ok=True)
    for name in ['rtl/board/call_cycle_timer.vhd','sim/tb/tb_call_cycle_timer.vhd']:shutil.copyfile(ROOT/name,td/Path(name).name)
    macro='onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\nif {![file exists modelsim.ini]} {vmap -c}\nif {![file isdirectory work]} {vlib work}\nvmap work work\nvcom -93 call_cycle_timer.vhd tb_call_cycle_timer.vhd\nvsim work.tb_call_cycle_timer\nset BreakOnAssertion 3\nrun -all\nquit -code 0 -f\n'
    (td/'timer.do').write_text(macro);rc,log=execute(exe,td,'timer.do','timer.log');(reports/'timer-baseline.log').write_text(log,encoding='utf-8')
    if rc or 'CALL_TIMER_PASS' not in log or any(s in log for s in ['** Failure:','** Error:','** Warning:']):raise ValueError(log[-2000:])
    unit_faults=[('double_increment','counter<=counter+1;','counter<=counter+2;'),
        ('end_off_by_one',"if stop_event='1' then state<=COMPLETE;end if;","if stop_event='1' then state<=COMPLETE;counter<=counter;end if;"),
        ('not_frozen','when COMPLETE =>','when COMPLETE => counter<=counter+1;'),
        ('reset_retains_count',"state<=IDLE;counter<=(others=>'0');","state<=IDLE;")]
    unit_controls=[]
    for name,old,new in unit_faults:
        d=base/('timer-'+name);shutil.copytree(td,d,ignore=shutil.ignore_patterns('work','*.log','*.wlf'),dirs_exist_ok=True)
        replace_once(d/'call_cycle_timer.vhd',old,new);code,mlog=execute(exe,d,'timer.do','timer.log')
        killed=code!=0 and '** Failure: CALL_TIMER_' in mlog and '** Error:' not in mlog
        (reports/f'timer-{name}.log').write_text(mlog,encoding='utf-8');unit_controls.append(dict(name=name,killed=killed))
        if not killed:raise ValueError('timer fault survived '+name+'\n'+mlog[-1200:])
    jobs=[];manifests={}
    names=['baseline','counter_double','wrong_rom_bank','finish_first','wrong_seed_bank','stalled','fake_lookup_stalled','last_output_corruption']
    for name in names:
        d=base/name;manifests[name]=prepare(d)
        flags='' if name=='baseline' else '-gSINGLE_RUN=true '
        if name in ['stalled','fake_lookup_stalled']:flags+='-gCHECK_REFERENCES=false ';stall_first_dma(d)
        if name=='last_output_corruption':flags+='-gEXPECT_ERROR=true '
        if flags:replace_once(d/'run_benchmark_batch.do','work.tb_de2_benchmark\n',flags+'work.tb_de2_benchmark\n')
        top=d/'de2_115_benchmark_top.vhd'
        if name=='counter_double':replace_once(d/'call_cycle_timer.vhd','counter<=counter+1;','counter<=counter+2;')
        elif name=='wrong_rom_bank':replace_once(top,'256*profile_index+to_integer','0*profile_index+to_integer')
        elif name=='finish_first':replace_once(top,'if profile_index=8 then','if profile_index=0 then')
        elif name=='wrong_seed_bank':replace_once(top,'8192*(profile_index/3)+to_integer','8192*0+to_integer')
        elif name=='fake_lookup_stalled':
            fake='    constant FAKE_MEASUREMENTS : measurement_array := ('+','.join(f'x"{v:08X}"' for v in REFERENCES)+');\n'
            replace_once(top,'    signal measurements :',fake+'    signal measurements :')
            replace_once(top,'measurements(profile_index)<=timer_ticks;','measurements(profile_index)<=FAKE_MEASUREMENTS(profile_index);')
        elif name=='last_output_corruption':
            replace_once(d/'fir_mmio_large.vhd','dma_wdata<=std_logic_vector(resize(core_output,32));',
                'dma_wdata<=std_logic_vector(resize(core_output,32)) xor x"00000001" when std_logic_vector(sample_index)=x"000003FF" else std_logic_vector(resize(core_output,32));')
        jobs.append((name,d))
    results={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(execute,exe,d):name for name,d in jobs}
        for future in concurrent.futures.as_completed(futures):
            name=futures[future];code,log=future.result();results[name]=(code,log)
            (reports/(name+'.log')).write_text(log,encoding='utf-8')
            print('BOARD_BENCH_CASE_FINISHED '+name+' exit='+str(code),flush=True)
    controls=[]
    def clean(name,token):
        code,log=results[name]
        if code or token not in log or any(s in log for s in ['** Failure:','** Error:','** Warning:']):raise ValueError(name+'\n'+log[-2300:])
        return [(int(p),int(v)) for p,v in re.findall(r'BOARD_BENCH_MEASUREMENT index=(\d+) cycles=(\d+)',log)]
    observed=clean('baseline','BOARD_BENCH_PASS completed_runs=4 measurements_checked=36')
    if observed!=list(enumerate(REFERENCES))*4:raise ValueError('missing/reordered baseline measurement')
    stalled=clean('stalled','BOARD_BENCH_PASS completed_runs=1 measurements_checked=9')
    if len(stalled)!=9 or any((v!=REFERENCES[p] if p%3==0 else v<=REFERENCES[p]) for p,v in stalled):raise ValueError('stall injection did not change only hardware measurements')
    for name in ['counter_double','wrong_rom_bank','finish_first','wrong_seed_bank','fake_lookup_stalled']:
        code,log=results[name];failures=re.findall(r'\*\* Failure: (BOARD_BENCH_[^\r\n]+)',log)
        killed=code!=0 and bool(failures) and '** Error:' not in log;controls.append(dict(name=name,killed=killed,assertions=failures))
        if not killed:raise ValueError('undetected board fault '+name+'\n'+log[-1800:])
    clean('last_output_corruption','BOARD_BENCH_LAST_OUTPUT_ERROR_PASS profile=7 sample=1023')
    manifest=manifests['baseline']
    paths={**manifest['source_sha256'],**{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/run_board_benchmark.py','sim/tb/tb_call_cycle_timer.vhd']}}
    report=dict(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),completed_runs=4,profiles_per_run=9,display_measurements_checked=36,
        independent_external_clock_stopwatch=True,baseline_measurements=[dict(index=p,cycles=v,hex=f'{v:08X}') for p,v in enumerate(REFERENCES)],
        latency_sensitivity=dict(extra_initial_dma_wait_edges=31,measurements=[dict(index=p,cycles=v) for p,v in stalled],software_unchanged=True,all_hardware_calls_increased=True),
        fake_cycle_table_rejected=True,timer_negative_controls=unit_controls,board_negative_controls=controls,
        reset_cases=['power-up','KEY0 full restart','KEY0 during loader','KEY0 during profile7 DMA'],
        c_last_output_error_detected=dict(profile=7,sample=1023,display='EEEEEEEE'),
        source_sha256=paths,quartus='not_run',hardware='not_run',github='not_uploaded')
    report_file.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','completed_runs','display_measurements_checked','fake_cycle_table_rejected','baseline_measurements']},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
