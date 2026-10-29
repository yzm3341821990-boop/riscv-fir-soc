"""Generate a separate five-stage FIR Quartus project; never compile/program it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.prepare_de2_display import PINS
from tools.prepare_de2_project import prepare as prepare_reference
from tools.run_pipeline_soc import ROOT,SOURCES as SOC_SOURCES

PROJECT='riscv_fir_de2_pipeline'
SOURCES=tuple(p for p in SOC_SOURCES if p.startswith('rtl/'))+(
    'rtl/board/hex7seg.vhd','rtl/board/de2_115_pipeline_top.vhd')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    # Keep the legacy generator's products isolated; only checked image data is reused.
    ref=directory/'reference-images'
    reference=prepare_reference(ref)
    for name in ('board_images_pkg.vhd','program.mif','ram_seed.mif'):
        shutil.copyfile(ref/name,directory/name)
    for relative in SOURCES:shutil.copyfile(ROOT/relative,directory/Path(relative).name)
    shutil.copyfile(ROOT/'fpga/de2_display/display.sdc',directory/'pipeline.sdc')
    shutil.copyfile(ROOT/'sim/tb/tb_de2_pipeline.vhd',directory/'tb_de2_pipeline.vhd')
    template=(ROOT/'fpga/de2_115/riscv_fir_de2_115.qsf').read_text(encoding='ascii')
    rows=[line for line in template.splitlines() if not
          (line.startswith(('set_location_assignment','set_instance_assignment')) or
           '-name VHDL_FILE ' in line)]
    qsf='\n'.join(rows)+'\n'
    qsf=qsf.replace('TOP_LEVEL_ENTITY de2_115_top','TOP_LEVEL_ENTITY de2_115_pipeline_top')
    qsf=qsf.replace('SDC_FILE board.sdc','SDC_FILE pipeline.sdc')
    qsf+='set_global_assignment -name VHDL_FILE board_images_pkg.vhd\n'
    qsf+=''.join(f'set_global_assignment -name VHDL_FILE {Path(p).name}\n' for p in SOURCES)
    for name,pin in PINS.items():
        qsf+=f"set_location_assignment PIN_{pin['pin']} -to {name}\n"
        qsf+=f"set_instance_assignment -name IO_STANDARD \"{pin['standard']}\" -to {name}\n"
    (directory/f'{PROJECT}.qsf').write_text(qsf,encoding='ascii')
    (directory/'pipeline-qsf-before-build.txt').write_text(qsf,encoding='ascii')
    (directory/f'{PROJECT}.qpf').write_text('QUARTUS_VERSION = "17.0"\nPROJECT_REVISION = "'+PROJECT+'"\n',encoding='ascii')
    compile_line='vcom -93 board_images_pkg.vhd '+' '.join(Path(p).name for p in SOURCES)+' tb_de2_pipeline.vhd\n'
    (directory/'compile_pipeline_board.do').write_text('catch {quit -sim}\n'
        'if {![file exists modelsim.ini]} {vmap -c}\nif {![file isdirectory work]} {vlib work}\nvmap work work\n'+compile_line,encoding='ascii')
    (directory/'run_pipeline_board_batch.do').write_text('onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\n'
        'do compile_pipeline_board.do\nvsim -voptargs=+acc work.tb_de2_pipeline\nset BreakOnAssertion 3\nrun -all\n'
        'if {[string tolower [examine sim:/tb_de2_pipeline/finished]] ne "true"} {error "PIPE_BOARD_NOT_FINISHED"}\n'
        'echo PIPE_BOARD_SUITE_PASS\nquit -code 0 -f\n',encoding='ascii')
    provenance=(*SOURCES,'sim/tb/tb_de2_pipeline.vhd','tools/prepare_de2_pipeline.py',
                'fpga/de2_display/display.sdc','fpga/de2_display/pins.json','docs/pipeline-soc-contract.md')
    reference.update(contract='pipeline-fir-soc-v1',project=PROJECT,pins=PINS,
        reference_jp6_vccio=3.3,physical_board_verified=False,
        source_sha256={p:digest(ROOT/p) for p in provenance},
        generated_sha256={name:digest(directory/name) for name in (
            *(Path(p).name for p in SOURCES),'board_images_pkg.vhd','program.mif','ram_seed.mif',
            'pipeline.sdc','tb_de2_pipeline.vhd',f'{PROJECT}.qsf',f'{PROJECT}.qpf',
            'pipeline-qsf-before-build.txt','compile_pipeline_board.do','run_pipeline_board_batch.do')},
        scope='Pipeline project preparation only. Quartus compilation, timing and hardware observation pending.')
    (directory/'project-manifest.json').write_text(json.dumps(reference,indent=2)+'\n',encoding='utf-8')
    return reference


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_pipeline'))
    a=p.parse_args();d=a.output.resolve()
    if not str(d).isascii() or any(c in str(d) for c in '{}\r\n'):p.error('Use an ASCII output path without braces')
    r=prepare(d)
    print(json.dumps(dict(project=str(d/f'{PROJECT}.qpf'),pins=len(PINS),quartus_compiled=False),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
