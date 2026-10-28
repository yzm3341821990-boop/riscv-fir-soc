"""Build and audit the C Q15 FIR against the original 32-tap reference."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

from model.fixed_fir import fir_block
from model.tiny_cpu import run_program
from tools.elf32 import read_elf
from tools.build_c_demo import DEFAULT_ZIG, FLAGS, digest

ROOT=Path(__file__).resolve().parents[1]
INPUTS=('firmware/c_fir_q15/main.c','firmware/c_array_sum/start.S','firmware/c_array_sum/link.ld',
        'tools/build_fir_demo.py','tools/build_c_demo.py','tools/elf32.py','model/fixed_fir.py')
FIR_FLAGS=[flag if flag!='-mcpu=generic_rv32' else '-mcpu=generic_rv32+m' for flag in FLAGS]


def build(zig, directory, output):
    zig,directory,output=Path(zig).resolve(),Path(directory).resolve(),Path(output).resolve()
    if not str(directory).isascii(): raise ValueError('use an ASCII build directory')
    directory.mkdir(parents=True,exist_ok=True)
    def run(args):
        p=subprocess.run([str(zig),*args],cwd=directory,capture_output=True,text=True,errors='replace',timeout=120)
        if p.returncode or p.stderr.strip():raise RuntimeError(p.stdout+p.stderr)
        return p.stdout.strip()
    version=run(['version'])
    if version!='0.13.0':raise ValueError('pin Zig 0.13.0')
    clang=run(['cc','--version']).splitlines()[0]
    shutil.copyfile(ROOT/'firmware/c_fir_q15/main.c',directory/'main.c')
    for name in ('start.S','link.ld'):shutil.copyfile(ROOT/'firmware/c_array_sum'/name,directory/name)
    commands=[['cc',*FIR_FLAGS,'-nostdlib','-Wl,-T,link.ld','-Wl,--build-id=none','start.S','main.c','-o','program.elf'],
              ['cc',*FIR_FLAGS,'-S','main.c','-o','main.s']]
    for command in commands:run(command)
    image=read_elf((directory/'program.elf').read_bytes())
    if any(w&0x7F==0x33 and w>>25==1 and (w>>12)&7!=0 for w in image.program_words):
        raise ValueError('compiler used an M instruction beyond implemented MUL')
    memory=struct.pack('<256I',*image.memory_words)
    syms=image.symbols
    x=struct.unpack_from('<8h',memory,syms['samples'])
    h=struct.unpack_from('<32h',memory,syms['coefficients'])
    expected=fir_block(x,h)
    result=run_program(image.program_words,initial_memory=image.memory_words)
    final=struct.pack('<256I',*result.memory)
    y=struct.unpack_from('<8h',final,syms['outputs'])
    acc=struct.unpack_from('<8q',final,syms['accumulators'])
    mul_count=sum(t.instruction&0xFE00707F==0x02000033 for t in result.trace)
    if (result.fault or y!=expected.outputs or acc!=expected.accumulators or result.registers[2]!=1024 or
            struct.unpack_from('<I',final,syms['done'])[0]!=1 or mul_count!=36):
        raise ValueError(f'FIR semantic audit failed: fault={result.fault}, y={y}, acc={acc}, mul={mul_count}')
    for name,words in (('program.hex',image.program_words),('initial_memory.txt',image.memory_words)):
        (directory/name).write_text(''.join(f'{w:08X}\n' for w in words),encoding='ascii',newline='\n')
    cycles=sum(4 if t.instruction&0x7F==3 else 3 for t in result.trace)
    artifacts=('program.elf','main.s','program.hex','initial_memory.txt')
    manifest={'contract':'c-fir-q15-block-v1','numeric_contract':'fir-q15-block-v1',
              'zig_version':version,'clang_version':clang,'compiler_sha256':digest(zig),
              'compiler_cpu':'generic_rv32+m','implemented_m_subset':['MUL'],
              'abi':'ilp32','commands':[['zig',*c] for c in commands],
              'input_sha256':{name:digest(ROOT/name) for name in INPUTS},
              'artifact_sha256':{name:digest(directory/name) for name in artifacts},
              'symbols':syms,'samples':list(x),'coefficients':list(h),
              'expected_outputs':list(y),'expected_accumulators':list(acc),
              'program_words':len(image.program_words),'dynamic_commits':len(result.trace),
              'memory_requests':len(result.memory_trace),'multiply_commits':mul_count,
              'execution_clock_edges':cycles,'simulation_finish_ns':2576+10*cycles,
              'scope':'32-tap Q15 C software, eight inputs, zero history; 64-bit C accumulator within signed40 bounds'}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    output.mkdir(parents=True,exist_ok=True)
    for name in (*artifacts,'manifest.json'):
        if (directory/name).resolve()!=(output/name).resolve():shutil.copyfile(directory/name,output/name)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig',type=Path,default=DEFAULT_ZIG)
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/software-fir/build'))
    p.add_argument('--output',type=Path,default=ROOT/'programs/c_fir_q15')
    a=p.parse_args();r=build(a.zig,a.build_dir,a.output)
    print(json.dumps({k:r[k] for k in ('program_words','dynamic_commits','memory_requests','multiply_commits','expected_outputs','symbols','simulation_finish_ns')},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
