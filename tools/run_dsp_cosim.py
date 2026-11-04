"""Production Python/Tcl protocol against DSP6 CPU, DMA and vendor RAM RTL."""
import os,argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from tools.prepare_de2_dsp import SOURCES,ROOT,digest
from tools.live_session import NativeTransport
from tools.dsp_session import DspSession

class ModelSimOutput:
    """Normalize ModelSim's transcript prefix at the test boundary only."""
    def __init__(self,stream,log):self.stream=stream;self.log=log
    def __iter__(self):
        for line in self.stream:
            self.log.append(line)
            yield line[2:] if line.startswith('# LIVE_') else line
    def close(self):self.stream.close()

def run(project,output,counts=(1,226,451),full_memory=True):
    project,output=Path(project),Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Use a new output directory')
    output.mkdir(parents=True,exist_ok=True)
    for s in SOURCES:shutil.copyfile(ROOT/s,output/Path(s).name)
    for n in ('live_link_lib.tcl','live_service.tcl'):shutil.copyfile(project/n,output/n)
    shutil.copyfile(ROOT/'sim/tb/tb_dsp_link.vhd',output/'tb_dsp_link.vhd')
    elf=(project/'firmware/program.elf').read_bytes();elfhash=hashlib.sha256(elf).hexdigest()
    from tools.app_program import program_image
    end=4*len(program_image(elf).program_words)
    api='''proc load_package args {}
proc get_hardware_names args {return [list {USB-Blaster [RTL_SIMULATION_NO_HARDWARE]}]}
proc get_device_names args {return [list {@1: 10CL120(Y|Z)/EP3C120/.. (0x020F70DD)}]}
proc get_insystem_source_probe_instance_info args {return [list [list 0 320 320 DSP6]]}
proc start_insystem_source_probe args {}
proc end_insystem_source_probe args {}
proc read_source_data args {return [examine -radix hexadecimal sim:/tb_dsp_link/source_bus]}
proc write_source_data args {set v [lindex $args [expr [lsearch -exact $args -value]+1]];force -freeze sim:/tb_dsp_link/source_bus 16#$v}
proc read_probe_data args {
 set state [examine -radix hexadecimal sim:/tb_dsp_link/dut/state_code]
 if {$state eq "3"} {run 5 us} elseif {$state eq "1"} {run 400 us} else {run 2 us}
 if {[examine -radix unsigned sim:/tb_dsp_link/freeze] == 1} {
  set index [examine -radix unsigned sim:/tb_dsp_link/job_index]
  set f [open registers-$index.txt w];puts $f 00000000
  for {set k 1} {$k<32} {incr k} {puts $f [format %08X [examine -radix unsigned [format {sim:/tb_dsp_link/dut/processor/registers/bank(%d)} $k]]]}
  close $f;force -deposit sim:/tb_dsp_link/freeze 0;run 2 us
 }
 return [examine -radix hexadecimal sim:/tb_dsp_link/probe_bus]
}
source live_service.tcl
'''
    (output/'api.tcl').write_text(api,encoding='ascii')
    script='onerror {quit -code 2 -f}\nonbreak {quit -code 3 -f}\nvmap -c\nvlib work\nvcom -93 '+' '.join(Path(s).name for s in SOURCES)+f' tb_dsp_link.vhd\nvsim -voptargs=+acc -L altera_mf -gEND_PC={end} work.tb_dsp_link\nset BreakOnAssertion 3\nrun 500 us\nsource api.tcl\nquit -code 0 -f\n'
    (output/'run.tcl').write_text(script,encoding='ascii');log=[];exe=Path(os.environ.get('MODELSIM_VSIM') or shutil.which('vsim') or 'vsim')
    def launch(unused,**kwargs):
        kwargs['cwd']=output;p=subprocess.Popen([str(exe),'-c','-do','source {run.tcl}'],**kwargs);p.stdout=ModelSimOutput(p.stdout,log);return p
    t=NativeTransport(output,quartus_stp=exe,popen_factory=launch);t.source_kind='rtl_simulation'
    provenance=(*SOURCES,'sim/tb/tb_dsp_link.vhd','tools/dsp_session.py','tools/dsp_program.py','tools/run_dsp_cosim.py')
    hashes={s:digest(ROOT/s) for s in provenance}
    (output/'executed-sources.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
    records=[]
    try:
        t.connect();s=DspSession(t,elfhash,execution_timeout=600);s.initialize()
        for i,n in enumerate(counts,1):
            r=s.run(elf,[n]);records.append(r)
            if full_memory:
                ram=s.read(2,0,8192)
                (output/f'memory-{i}.txt').write_text(''.join(f'{v:08X}\n' for v in ram),encoding='ascii')
            (output/f'result-{i}.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(samples=n,cycles=r['cycles'],profiles=r['profile_cycles'],source_kind=r['source_kind'])),flush=True)
    finally:t.close();(output/'modelsim.log').write_text(''.join(log),encoding='utf-8')
    if any(digest(ROOT/s)!=h for s,h in hashes.items()):raise ValueError('Sources changed during execution; do not label them as the tested revision')
    report=dict(status='passed',source_kind='rtl_simulation',records=records,source_sha256=hashes,full_memory_readback=full_memory,hardware_access=False,quartus_run=False)
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',required=True);p.add_argument('--counts',default='1,226,451');p.add_argument('--no-memory',action='store_true');a=p.parse_args();run(a.project,a.output,tuple(map(int,a.counts.split(','))),not a.no_memory)
