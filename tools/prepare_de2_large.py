"""Prepare the separate 32 KiB, 1024-sample DE2-115 project; do not compile it."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from tools.prepare_de2_display import PINS
from tools.run_large_soc import ROOT,SOURCES as SOC_SOURCES
from tools.build_large_firmware import dataset,layout
from tools.large_elf import read_large_elf

PROJECT='riscv_fir_de2_large'
SOURCES=tuple(p for p in SOC_SOURCES if p.startswith('rtl/'))+(
    'rtl/board/hex7seg.vhd','rtl/board/de2_115_large_top.vhd')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_images():
    folder=ROOT/'programs/fir_large/n1024/hardware_cold'
    manifest=json.loads((folder/'manifest.json').read_text())
    for name,value in manifest['artifact_sha256'].items():
        if digest(folder/name)!=value:raise ValueError('stale large firmware artifact: '+name)
    for name,value in manifest['input_sha256'].items():
        if digest(ROOT/name)!=value:raise ValueError('stale large firmware input: '+name)
    image=read_large_elf((folder/'program.elf').read_bytes())
    program=[int(v,16) for v in (folder/'program.hex').read_text().split()]
    memory=[int(v,16) for v in (folder/'initial_memory.txt').read_text().split()]
    x,h,y=dataset(1024);syms=layout(1024)
    if list(image.program_words)!=program or len(memory)!=8192 or manifest['layout']!=syms:
        raise ValueError('large firmware ELF/image/layout mismatch')
    if hashlib.sha256(struct.pack('<8192I',*memory)).hexdigest()!=manifest['initial_memory_sha256']:
        raise ValueError('large RAM image identity mismatch')
    for name,values in [('samples',x),('coefficients',h),('expected',y)]:
        if memory[syms[name]//4:syms[name]//4+len(values)]!=[v&0xffffffff for v in values]:
            raise ValueError('large board reference differs: '+name)
    return program+[0x13]*(256-len(program)),memory,y,manifest


def prepare(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    program,seeds,expected,firmware=load_images()
    text='library ieee;\nuse ieee.std_logic_1164.all;\npackage large_board_images_pkg is\n'
    text+='    type word_array is array(natural range <>) of std_logic_vector(31 downto 0);\n'
    for name,values in [('PROGRAM_IMAGE',program),('RAM_SEED_IMAGE',seeds)]:
        text+=f'    constant {name} : word_array(0 to {len(values)-1}) := (\n'
        text+=',\n'.join(f'        {i} => x"{v:08X}"' for i,v in enumerate(values))+'\n    );\n'
    text+='    constant SAMPLE_COUNT : positive := 1024;\n'
    text+='    constant EXPECTED_Y : word_array(0 to 7) := ('+','.join(f'x"{v&0xffffffff:08X}"' for v in expected[:8])+');\n'
    for name,symbol in [('OUTPUT_BASE','outputs'),('C_DONE_ADDRESS','done'),('C_ERRORS_ADDRESS','errors'),('PROGRAM_END','_program_end')]:
        text+=f"    constant {name} : natural := {firmware['symbols'][symbol]};\n"
    text+='end package;\n'
    (directory/'large_board_images_pkg.vhd').write_text(text,encoding='ascii')
    for name,values in [('program.mif',program),('ram_seed.mif',seeds)]:
        mif=f'WIDTH=32;\nDEPTH={len(values)};\nADDRESS_RADIX=HEX;\nDATA_RADIX=HEX;\nCONTENT BEGIN\n'
        mif+=''.join(f'{i:04X} : {v:08X};\n' for i,v in enumerate(values))+'END;\n'
        (directory/name).write_text(mif,encoding='ascii')
    for relative in (*SOURCES,'sim/tb/tb_de2_large.vhd'):shutil.copyfile(ROOT/relative,directory/Path(relative).name)
    shutil.copyfile(ROOT/'fpga/de2_display/display.sdc',directory/'large.sdc')
    template=(ROOT/'fpga/de2_115/riscv_fir_de2_115.qsf').read_text(encoding='ascii')
    qsf='\n'.join(line for line in template.splitlines() if not
        (line.startswith(('set_location_assignment','set_instance_assignment')) or '-name VHDL_FILE ' in line))+'\n'
    qsf=qsf.replace('TOP_LEVEL_ENTITY de2_115_top','TOP_LEVEL_ENTITY de2_115_large_top').replace('SDC_FILE board.sdc','SDC_FILE large.sdc')
    qsf+='set_global_assignment -name VHDL_FILE large_board_images_pkg.vhd\n'
    qsf+=''.join(f'set_global_assignment -name VHDL_FILE {Path(p).name}\n' for p in SOURCES)
    for name,pin in PINS.items():
        qsf+=f"set_location_assignment PIN_{pin['pin']} -to {name}\n"
        qsf+=f"set_instance_assignment -name IO_STANDARD \"{pin['standard']}\" -to {name}\n"
    (directory/f'{PROJECT}.qsf').write_text(qsf,encoding='ascii')
    (directory/'large-qsf-before-build.txt').write_text(qsf,encoding='ascii')
    (directory/f'{PROJECT}.qpf').write_text('QUARTUS_VERSION = "17.0"\nPROJECT_REVISION = "'+PROJECT+'"\n',encoding='ascii')
    (directory/'compile_large_board.do').write_text('catch {quit -sim}\nif {![file exists modelsim.ini]} {vmap -c}\n'
        'if {![file isdirectory work]} {vlib work}\nvmap work work\nvcom -93 large_board_images_pkg.vhd '+
        ' '.join(Path(p).name for p in SOURCES)+' tb_de2_large.vhd\n',encoding='ascii')
    (directory/'run_large_board_batch.do').write_text('onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\n'
        'do compile_large_board.do\nvsim -voptargs=+acc -L altera_mf work.tb_de2_large\nset BreakOnAssertion 3\nrun -all\n'
        'if {[string tolower [examine sim:/tb_de2_large/finished]] ne "true"} {error "LARGE_BOARD_NOT_FINISHED"}\n'
        'echo LARGE_BOARD_SUITE_PASS\nquit -code 0 -f\n',encoding='ascii')
    provenance=(*SOURCES,'sim/tb/tb_de2_large.vhd','tools/prepare_de2_large.py','docs/large-block-contract.md',
                'fpga/de2_display/display.sdc','fpga/de2_display/pins.json')
    generated=(*(Path(p).name for p in SOURCES),'tb_de2_large.vhd','large_board_images_pkg.vhd','program.mif','ram_seed.mif',
               'large.sdc',f'{PROJECT}.qsf',f'{PROJECT}.qpf','large-qsf-before-build.txt','compile_large_board.do','run_large_board_batch.do')
    report=dict(contract='fir-large-block-v1',project=PROJECT,reference_device='EP4CE115F29C7',system_clock_mhz=25,
        reference_clock_mhz=50,reference_jp7_vccio=2.5,reference_jp6_vccio=3.3,pins=PINS,
        sample_count=1024,fir_lanes=4,ram_seed_words=8192,program_words=firmware['program_words'],
        firmware_symbols=firmware['symbols'],firmware_artifact_sha256=firmware['artifact_sha256'],
        initial_memory_sha256=firmware['initial_memory_sha256'],expected_display_outputs=expected[:8],
        full_output_check='C compares every one of 1024 outputs; hardware checks all DMA addresses/count plus first eight values',
        source_sha256={name:digest(ROOT/name) for name in provenance},generated_sha256={name:digest(directory/name) for name in generated},
        quartus='not_run',timing='not_run',hardware='not_run')
    (directory/'project-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_large'))
    a=p.parse_args();d=a.output.resolve()
    if not str(d).isascii() or any(v in str(d) for v in '{}\r\n'):p.error('ASCII output directory without braces required')
    report=prepare(d);print(json.dumps(dict(project=str(d/f'{PROJECT}.qpf'),sample_count=report['sample_count'],quartus='not_run'),indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
