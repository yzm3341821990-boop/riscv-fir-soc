"""Prepare one nine-profile board benchmark image without running Quartus."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from tools.prepare_de2_large import ROOT,SOURCES as LARGE_SOURCES
from tools.prepare_de2_display import PINS
from tools.build_large_firmware import dataset,layout
from tools.large_elf import read_large_elf

PROJECT='riscv_fir_de2_benchmark'
SOURCES=tuple(p for p in LARGE_SOURCES if p!='rtl/board/de2_115_large_top.vhd')+(
    'rtl/board/call_cycle_timer.vhd','rtl/board/de2_115_benchmark_top.vhd')
MODES=['software','hardware_cold','hardware_resident']


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_profiles():
    profiles=[];programs=[];seeds=[];compiler=set();first_outputs=[]
    for n in [64,256,1024]:
        memories=[];x,h,y=dataset(n);first_outputs.append(y[:8])
        for mode in MODES:
            folder=ROOT/'programs/fir_large'/f'n{n}'/mode;m=json.loads((folder/'manifest.json').read_text())
            for name,sha in m['artifact_sha256'].items():
                if digest(folder/name)!=sha:raise ValueError('stale firmware artifact '+str(folder/name))
            for name,sha in m['input_sha256'].items():
                if digest(ROOT/name)!=sha:raise ValueError('stale firmware source '+name)
            image=read_large_elf((folder/'program.elf').read_bytes())
            program=[int(v,16) for v in (folder/'program.hex').read_text().split()]
            memory=[int(v,16) for v in (folder/'initial_memory.txt').read_text().split()]
            if list(image.program_words)!=program or len(memory)!=8192 or m['layout']!=layout(n):raise ValueError('profile layout/image mismatch')
            if hashlib.sha256(struct.pack('<8192I',*memory)).hexdigest()!=m['initial_memory_sha256']:raise ValueError('profile initial RAM hash mismatch')
            for name,values in [('samples',x),('coefficients',h),('expected',y)]:
                if memory[m['symbols'][name]//4:m['symbols'][name]//4+len(values)]!=[v&0xffffffff for v in values]:raise ValueError('bad profile numeric reference')
            compiler.add((m['compiler_sha256'],tuple(m['compiler_flags'])))
            programs.extend(program+[0x13]*(256-len(program)));memories.append(memory)
            profiles.append(dict(index=len(profiles),sample_count=n,mode=mode,symbols=m['symbols'],
                initial_memory_sha256=m['initial_memory_sha256'],firmware_artifact_sha256=m['artifact_sha256']))
        if not memories[0]==memories[1]==memories[2]:raise ValueError('mode-dependent initial RAM')
        seeds.extend(memories[0])
    if len(compiler)!=1 or not first_outputs[0]==first_outputs[1]==first_outputs[2]:raise ValueError('nonmatching comparison conditions')
    return profiles,programs,seeds,first_outputs[0]


def prepare(directory):
    d=Path(directory);d.mkdir(parents=True,exist_ok=True)
    profiles,programs,seeds,expected=load_profiles()
    text='library ieee;\nuse ieee.std_logic_1164.all;\npackage benchmark_images_pkg is\n'
    text+='    type word_array is array(natural range <>) of std_logic_vector(31 downto 0);\n'
    text+='    type natural_array is array(natural range <>) of natural;\n'
    for name,values in [('PROGRAM_IMAGE',programs),('RAM_SEED_IMAGE',seeds)]:
        text+=f'    constant {name} : word_array(0 to {len(values)-1}) := (\n'
        text+=',\n'.join(f'        {i} => x"{v:08X}"' for i,v in enumerate(values))+'\n    );\n'
    arrays={'SAMPLE_COUNTS':[p['sample_count'] for p in profiles]}
    for name,symbol in [('OUTPUT_BASES','outputs'),('MARKER_ADDRS','marker'),('DONE_ADDRS','done'),('ERROR_ADDRS','errors'),('PROGRAM_ENDS','_program_end')]:
        arrays[name]=[p['symbols'][symbol] for p in profiles]
    for name,values in arrays.items():text+=f'    constant {name} : natural_array(0 to 8) := ('+','.join(map(str,values))+');\n'
    text+='    constant EXPECTED_Y : word_array(0 to 7) := ('+','.join(f'x"{v&0xffffffff:08X}"' for v in expected)+');\nend package;\n'
    (d/'benchmark_images_pkg.vhd').write_text(text,encoding='ascii')
    for name,values in [('program.mif',programs),('ram_seed.mif',seeds)]:
        (d/name).write_text(f'WIDTH=32;\nDEPTH={len(values)};\nADDRESS_RADIX=HEX;\nDATA_RADIX=HEX;\nCONTENT BEGIN\n'+
            ''.join(f'{i:05X} : {v:08X};\n' for i,v in enumerate(values))+'END;\n',encoding='ascii')
    for source in (*SOURCES,'sim/tb/tb_de2_benchmark.vhd'):shutil.copyfile(ROOT/source,d/Path(source).name)
    shutil.copyfile(ROOT/'fpga/de2_display/display.sdc',d/'benchmark.sdc')
    template=(ROOT/'fpga/de2_115/riscv_fir_de2_115.qsf').read_text(encoding='ascii')
    qsf='\n'.join(line for line in template.splitlines() if not(line.startswith(('set_location_assignment','set_instance_assignment')) or '-name VHDL_FILE ' in line))+'\n'
    qsf=qsf.replace('TOP_LEVEL_ENTITY de2_115_top','TOP_LEVEL_ENTITY de2_115_benchmark_top').replace('SDC_FILE board.sdc','SDC_FILE benchmark.sdc')
    qsf+='set_global_assignment -name VHDL_FILE benchmark_images_pkg.vhd\n'
    qsf+=''.join(f'set_global_assignment -name VHDL_FILE {Path(p).name}\n' for p in SOURCES)
    for name,pin in PINS.items():
        qsf+=f"set_location_assignment PIN_{pin['pin']} -to {name}\nset_instance_assignment -name IO_STANDARD \"{pin['standard']}\" -to {name}\n"
    (d/f'{PROJECT}.qsf').write_text(qsf,encoding='ascii');(d/'benchmark-qsf-before-build.txt').write_text(qsf,encoding='ascii')
    (d/f'{PROJECT}.qpf').write_text('QUARTUS_VERSION = "17.0"\nPROJECT_REVISION = "'+PROJECT+'"\n',encoding='ascii')
    (d/'compile_benchmark.do').write_text('catch {quit -sim}\nif {![file exists modelsim.ini]} {vmap -c}\nif {![file isdirectory work]} {vlib work}\nvmap work work\nvcom -93 benchmark_images_pkg.vhd '+
        ' '.join(Path(s).name for s in SOURCES)+' tb_de2_benchmark.vhd\n',encoding='ascii')
    (d/'run_benchmark_batch.do').write_text('onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\ndo compile_benchmark.do\n'
        'vsim -voptargs=+acc -L altera_mf work.tb_de2_benchmark\nset BreakOnAssertion 3\nrun -all\n'
        'if {[string tolower [examine sim:/tb_de2_benchmark/finished]] ne "true"} {error "BOARD_BENCH_NOT_FINISHED"}\n'
        'echo BOARD_BENCH_SUITE_PASS\nquit -code 0 -f\n',encoding='ascii')
    provenance=(*SOURCES,'sim/tb/tb_de2_benchmark.vhd','tools/prepare_de2_benchmark.py','docs/board-benchmark-contract.md','fpga/de2_display/display.sdc','fpga/de2_display/pins.json')
    generated=[*(Path(p).name for p in SOURCES),'tb_de2_benchmark.vhd','benchmark_images_pkg.vhd','program.mif','ram_seed.mif',
        'benchmark.sdc',f'{PROJECT}.qsf',f'{PROJECT}.qpf','benchmark-qsf-before-build.txt','compile_benchmark.do','run_benchmark_batch.do']
    result=dict(contract='board-fir-benchmark-v1',project=PROJECT,top='de2_115_benchmark_top',profiles=profiles,fir_lanes=4,
        reference_device='EP4CE115F29C7',system_clock_mhz=25,pins=PINS,reference_jp7_vccio=2.5,reference_jp6_vccio=3.3,
        timer='Accepted marker=1 to marker=2 core-edge interval, computed in hardware; no expected cycle constants in RTL',
        source_sha256={p:digest(ROOT/p) for p in provenance},generated_sha256={p:digest(d/p) for p in generated},
        quartus='not_run',hardware='not_run',github='not_uploaded')
    (d/'project-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_benchmark'))
    a=p.parse_args();d=a.output.resolve()
    if not str(d).isascii() or any(c in str(d) for c in '{}\r\n'):p.error('ASCII output path required')
    m=prepare(d);print(json.dumps(dict(project=str(d/f'{PROJECT}.qpf'),profiles=len(m['profiles']),quartus='not_run'),indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
