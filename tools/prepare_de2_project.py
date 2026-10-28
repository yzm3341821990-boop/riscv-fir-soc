"""Prepare an ASCII Quartus reference project; never programs connected hardware."""
import argparse
import hashlib
import json
from pathlib import Path

from model.fixed_fir import fir_block
from tools.run_soc import SOURCES as SOC_SOURCES,load_firmware

ROOT=Path(__file__).resolve().parents[1]
SOURCES=tuple(p for p in SOC_SOURCES if p.startswith('rtl/'))+(
    'rtl/board/de2_115_top.vhd','sim/tb/tb_de2_boot.vhd','sim/modelsim/run_de2_boot_batch.do',
    'fpga/de2_115/riscv_fir_de2_115.qpf','fpga/de2_115/riscv_fir_de2_115.qsf','fpga/de2_115/board.sdc')


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    for relative in SOURCES:
        text=(ROOT/relative).read_text(encoding='ascii')
        (directory/Path(relative).name).write_text(text,encoding='ascii',newline='\n')
    image,manifest=load_firmware()
    # Existing firmware self-checks the same first-step numeric contract.
    expected=fir_block(manifest['samples'],manifest['coefficients']).outputs
    if list(expected)!=manifest['expected_outputs']: raise ValueError('firmware numeric reference differs')
    program=list(image.program_words)+[0x00000013]*(256-len(image.program_words))
    seeds=list(image.memory_words)
    def array(name,values):
        rows=[f'    constant {name} : word_array := (']
        rows+=['        %d => x"%08X"%s'%(n,v,',' if n<len(values)-1 else '') for n,v in enumerate(values)]
        return '\n'.join(rows+['    );'])
    text='library ieee;\nuse ieee.std_logic_1164.all;\npackage board_images_pkg is\n'
    text+='    type word_array is array(0 to 255) of std_logic_vector(31 downto 0);\n'
    text+=array('PROGRAM_IMAGE',program)+'\n'+array('RAM_SEED_IMAGE',seeds)+'\n'
    text+='    type output_array is array(0 to 7) of std_logic_vector(31 downto 0);\n'
    text+='    constant EXPECTED_Y : output_array := ('+','.join(f'x"{v&0xffffffff:08X}"' for v in expected)+');\n'
    for constant,symbol in [('OUTPUT_BASE','outputs'),('C_DONE_ADDRESS','done'),('C_ERRORS_ADDRESS','errors'),('PROGRAM_END','_program_end')]:
        text+=f"    constant {constant} : natural := {manifest['symbols'][symbol]};\n"
    text+='end package;\n'
    (directory/'board_images_pkg.vhd').write_text(text,encoding='ascii',newline='\n')
    for name,values in [('program.mif',program),('ram_seed.mif',seeds)]:
        mif='WIDTH=32;\nDEPTH=256;\nADDRESS_RADIX=HEX;\nDATA_RADIX=HEX;\nCONTENT BEGIN\n'
        mif+=''.join(f'{n:02X} : {v:08X};\n' for n,v in enumerate(values))+'END;\n'
        (directory/name).write_text(mif,encoding='ascii',newline='\n')
    report={'contract':'de2-reference-boot-v1','reference_device':'EP4CE115F29C7',
            'physical_board_verified':False,'reference_clock_mhz':50,'system_clock_mhz':25,'reference_jp7_vccio':2.5,
            'program_words':len(image.program_words),'ram_seed_words':len(seeds),
            'firmware_symbols':manifest['symbols'],'expected_outputs':list(expected),
            'source_sha256':{p:digest(ROOT/p) for p in (*SOURCES,'tools/prepare_de2_project.py')},
            'firmware_artifact_sha256':manifest['artifact_sha256'],
            'generated_sha256':{p:digest(directory/p) for p in ('board_images_pkg.vhd','program.mif','ram_seed.mif')},
            'scope':'reference project preparation only; simulation, compilation and programming recorded separately'}
    (directory/'project-manifest.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115'))
    a=p.parse_args();directory=a.output.resolve()
    if not str(directory).isascii() or any(c in str(directory) for c in '{}\r\n'):
        p.error('use an ASCII path without braces')
    r=prepare(directory)
    print(json.dumps({'project':str(directory/'riscv_fir_de2_115.qpf'),'reference_device':r['reference_device'],
                      'physical_board_verified':False,'program_words':r['program_words']},indent=2))
    return 0


if __name__=='__main__': raise SystemExit(main())
