"""Prepare a separate DE2-115 result display project without modifying the proven kit."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.prepare_de2_project import ROOT,SOURCES as OLD_SOURCES,prepare as prepare_old

PROJECT='riscv_fir_de2_display'
PINS=json.loads((ROOT/'fpga/de2_display/pins.json').read_text(encoding='utf-8'))['pins']
EXTRA_SOURCES=('rtl/board/hex7seg.vhd','rtl/board/de2_115_display_top.vhd',
    'sim/tb/tb_de2_display.vhd','sim/modelsim/run_de2_display_batch.do',
    'fpga/de2_display/display.sdc','fpga/de2_display/pins.json',
    'tools/prepare_de2_display.py','tests/test_de2_display.py','docs/de2-display-contract.md')
SOURCES=(*OLD_SOURCES,*EXTRA_SOURCES,'tools/prepare_de2_project.py',
         'programs/c_fir_accel/manifest.json','programs/c_fir_accel/program.elf')


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(directory):
    directory=Path(directory);r=prepare_old(directory)
    for p in EXTRA_SOURCES:
        if Path(p).suffix in ('.vhd','.do','.sdc'):
            (directory/Path(p).name).write_text((ROOT/p).read_text(encoding='ascii'),encoding='ascii',newline='\n')
    qsf=(ROOT/'fpga/de2_115/riscv_fir_de2_115.qsf').read_text(encoding='ascii')
    lines=[line for line in qsf.splitlines() if not line.startswith(('set_location_assignment','set_instance_assignment'))]
    qsf='\n'.join(lines)+'\n'
    qsf=qsf.replace('TOP_LEVEL_ENTITY de2_115_top','TOP_LEVEL_ENTITY de2_115_display_top').replace('SDC_FILE board.sdc','SDC_FILE display.sdc')
    qsf+='set_global_assignment -name VHDL_FILE hex7seg.vhd\nset_global_assignment -name VHDL_FILE de2_115_display_top.vhd\n'
    for name,pin in PINS.items():
        qsf+=f"set_location_assignment PIN_{pin['pin']} -to {name}\n"
        qsf+=f"set_instance_assignment -name IO_STANDARD \"{pin['standard']}\" -to {name}\n"
    (directory/(PROJECT+'.qsf')).write_text(qsf,encoding='ascii',newline='\n')
    (directory/'display-qsf-before-build.txt').write_text(qsf,encoding='ascii',newline='\n')
    (directory/(PROJECT+'.qpf')).write_text('QUARTUS_VERSION = "17.0"\nPROJECT_REVISION = "'+PROJECT+'"\n',encoding='ascii',newline='\n')
    r.update(contract='de2-display-v1',project=PROJECT,reference_jp6_vccio=3.3,
             source_sha256={p:digest(ROOT/p) for p in SOURCES},pins=PINS)
    r['generated_sha256'].update({name:digest(directory/name) for name in (PROJECT+'.qsf',PROJECT+'.qpf')})
    (directory/'project-manifest.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_display'))
    a=p.parse_args();d=a.output.resolve()
    if not str(d).isascii() or any(c in str(d) for c in '{}\r\n'): p.error('ASCII path required')
    r=prepare(d)
    print(json.dumps({'project':str(d/(PROJECT+'.qpf')),'contract':r['contract'],'pins':len(PINS)},indent=2))
    return 0


if __name__=='__main__': raise SystemExit(main())
