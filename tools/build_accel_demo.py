"""Compile the bounded C MMIO driver with the existing pinned RV32I toolchain."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
from model.fixed_fir import fir_block
from tools.build_c_demo import DEFAULT_ZIG, FLAGS, digest
from tools.elf32 import read_elf

ROOT=Path(__file__).resolve().parents[1]
INPUTS=('firmware/c_fir_accel/main.c','firmware/c_array_sum/start.S','firmware/c_array_sum/link.ld',
        'tools/build_accel_demo.py','tools/build_c_demo.py','tools/elf32.py','model/fixed_fir.py')


def build(zig,directory,output):
    zig,directory,output=Path(zig).resolve(),Path(directory).resolve(),Path(output).resolve()
    if not str(directory).isascii(): raise ValueError('use ASCII build directory')
    directory.mkdir(parents=True,exist_ok=True)
    def run(args):
        p=subprocess.run([str(zig),*args],cwd=directory,capture_output=True,text=True,errors='replace',timeout=120)
        if p.returncode or p.stderr.strip(): raise RuntimeError(p.stdout+p.stderr)
        return p.stdout.strip()
    version=run(['version'])
    if version!='0.13.0': raise ValueError('pin Zig 0.13.0')
    clang=run(['cc','--version']).splitlines()[0]
    shutil.copyfile(ROOT/'firmware/c_fir_accel/main.c',directory/'main.c')
    for name in ('start.S','link.ld'): shutil.copyfile(ROOT/'firmware/c_array_sum'/name,directory/name)
    commands=[['cc',*FLAGS,'-nostdlib','-Wl,-T,link.ld','-Wl,--build-id=none','start.S','main.c','-o','program.elf'],
              ['cc',*FLAGS,'-S','main.c','-o','main.s']]
    for command in commands: run(command)
    image=read_elf((directory/'program.elf').read_bytes())
    memory=struct.pack('<256I',*image.memory_words); syms=image.symbols
    x=struct.unpack_from('<8i',memory,syms['samples']);h=struct.unpack_from('<32i',memory,syms['coefficients'])
    result=fir_block(x,h)
    if struct.unpack_from('<8i',memory,syms['expected'])!=result.outputs: raise ValueError('C expected initializer mismatch')
    if any(w&0x7F==0x33 and w>>25==1 for w in image.program_words): raise ValueError('driver must not need M instructions')
    for name,words in (('program.hex',image.program_words),('initial_memory.txt',image.memory_words)):
        (directory/name).write_text(''.join(f'{w:08X}\n' for w in words),encoding='ascii',newline='\n')
    artifacts=('program.elf','main.s','program.hex','initial_memory.txt')
    manifest={'contract':'c-fir-mmio-1k-v1','numeric_contract':'fir-q15-block-v1','mmio_base':0x40003000,
              'zig_version':version,'clang_version':clang,'compiler_sha256':digest(zig),
              'compiler_cpu':'generic_rv32','abi':'ilp32','commands':[['zig',*c] for c in commands],
              'input_sha256':{p:digest(ROOT/p) for p in INPUTS},
              'artifact_sha256':{p:digest(directory/p) for p in artifacts},
              'symbols':syms,'program_words':len(image.program_words),'samples':list(x),'coefficients':list(h),
              'expected_outputs':list(result.outputs),'scope':'compiled artifact; execution verified by tools.run_soc'}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    output.mkdir(parents=True,exist_ok=True)
    for name in (*artifacts,'manifest.json'):
        if directory/name!=output/name: shutil.copyfile(directory/name,output/name)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig',type=Path,default=DEFAULT_ZIG)
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/c-fir-accel/build'))
    p.add_argument('--output',type=Path,default=ROOT/'programs/c_fir_accel')
    a=p.parse_args(); r=build(a.zig,a.build_dir,a.output)
    print(json.dumps({k:r[k] for k in ('program_words','symbols','expected_outputs')},indent=2))
    return 0


if __name__=='__main__': raise SystemExit(main())
