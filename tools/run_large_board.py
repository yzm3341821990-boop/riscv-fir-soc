"""Verify the long-block board top, stopwatch, reset paths and hidden-output errors."""
import hashlib,json,re,subprocess
from datetime import datetime,timezone
from pathlib import Path
from tools.prepare_de2_large import ROOT,prepare

OUT=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/large_soc/board')
EXE=Path('E:/quartus/modelsim_ase/win32aloem/vsim.exe')


def simulate(d):
    r=subprocess.run([str(EXE),'-c','-l','board.log','-do','do run_large_board_batch.do'],cwd=d,
        capture_output=True,text=True,errors='replace',timeout=90)
    return r.returncode,(d/'board.log').read_text(errors='replace')


def main():
    reports=ROOT/'reports/step20-large-block';report_file=reports/'board-validation.json'
    report_file.write_text('{"status":"incomplete"}\n')
    manifest=prepare(OUT/'baseline');rc,log=simulate(OUT/'baseline');(reports/'board-baseline.log').write_text(log,encoding='utf-8')
    if rc or any(s in log for s in ['** Failure:','** Error:','** Warning:']):raise ValueError(log[-3000:])
    match=re.search(r'LARGE_DISPLAY_PASS completed_runs=4 results_checked=32 program_cycles=(\d+)',log)
    if not match:raise ValueError('missing board external-clock stopwatch test')
    mutations=[('rom_ignores_enable',"elsif imem_en='1' then imem_data<=PROGRAM_IMAGE",'else imem_data<=PROGRAM_IMAGE'),
        ('counter_double_increment','program_cycles<=program_cycles+1;','program_cycles<=program_cycles+2;'),
        ('capture_wrong_word','snapshots(result_count)<=dma_wdata;','snapshots(result_count)<=dma_wdata xor x"00000001";'),
        ('finish_early',"if commit_valid='1' and unsigned(commit_next_pc)=PROGRAM_END then",'if unsigned(imem_addr)=PROGRAM_END then')]
    controls=[]
    for name,old,new in mutations:
        d=OUT/name;prepare(d);p=d/'de2_115_large_top.vhd';text=p.read_text();assert text.count(old)==1
        p.write_text(text.replace(old,new),encoding='ascii');code,mlog=simulate(d)
        (reports/f'board-{name}.log').write_text(mlog,encoding='utf-8')
        errors=re.findall(r'\*\* Failure: (LARGE_DISPLAY_[^\r\n]+)',mlog)
        killed=code!=0 and bool(errors) and '** Error:' not in mlog
        controls.append(dict(name=name,killed=killed,assertions=errors))
        if not killed:raise ValueError('undetected board fault '+name+'\n'+mlog[-1500:])
    d=OUT/'last_output_corruption';prepare(d);p=d/'fir_mmio_large.vhd';text=p.read_text()
    old='dma_wdata<=std_logic_vector(resize(core_output,32));'
    assert text.count(old)==1
    p.write_text(text.replace(old,'dma_wdata<=std_logic_vector(resize(core_output,32)) xor x"00000001" when std_logic_vector(sample_index)=x"000003FF" else std_logic_vector(resize(core_output,32));'),encoding='ascii')
    p=d/'run_large_board_batch.do';text=p.read_text()
    p.write_text(text.replace('work.tb_de2_large\n','-gEXPECT_ERROR=true -gEXPECT_C_ERROR=true work.tb_de2_large\n'),encoding='ascii')
    rc,elog=simulate(d);(reports/'board-last-output-corruption.log').write_text(elog,encoding='utf-8')
    if rc or 'LARGE_DISPLAY_C_DETECTED_LAST_OUTPUT_PASS' not in elog or 'LARGE_DISPLAY_EXPECTED_ERROR_PASS' not in elog or any(s in elog for s in ['** Failure:','** Error:','** Warning:']):
        raise ValueError('last output error indication not verified\n'+elog[-2000:])
    report=dict(status='pass',generated_at_utc=datetime.now(timezone.utc).isoformat(),sample_count=1024,fir_lanes=4,
        completed_runs=4,c_outputs_checked_per_run=1024,result_selections_checked=32,program_cycles=int(match[1]),
        program_cycles_hex=f'{int(match[1]):08X}',independent_external_clock_stopwatch=True,
        reset_cases=['power-up','KEY0 restart','KEY0 during full-RAM loader','KEY0 during CPU/DMA job'],
        negative_controls=controls,error_indication=dict(corrupted_output=1023,c_error_store_observed=True,ledr='101',display='EEEEEEEE'),
        expected_display_outputs=manifest['expected_display_outputs'],
        source_sha256={**manifest['source_sha256'],'tools/run_large_board.py':hashlib.sha256((ROOT/'tools/run_large_board.py').read_bytes()).hexdigest()},
        quartus='not_run',timing='not_run',hardware='not_run')
    report_file.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'pass','program_cycles':report['program_cycles'],'program_cycles_hex':report['program_cycles_hex'],'faults_killed':4,'last_output_error_detected':True},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
