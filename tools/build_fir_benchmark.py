"""Build matched software, cold-hardware and resident-coefficient FIR images."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

from model.fixed_fir import fir_block
from model.tiny_cpu import (REGISTER_OPERATIONS, IMMEDIATE_OPERATIONS,
                            SHIFT_IMMEDIATE_OPERATIONS, LOAD_OPERATIONS,
                            STORE_OPERATIONS, BRANCH_OPERATIONS, run_program)
from tools.build_c_demo import DEFAULT_ZIG, FLAGS, digest
from tools.c_demo import load_demo
from tools.elf32 import read_elf

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = 'c-fir-benchmark-v1'
MODES = {'software': 0, 'hardware_cold': 1, 'hardware_resident': 2}
BENCH_FLAGS = [f if f != '-mcpu=generic_rv32' else '-mcpu=generic_rv32+m' for f in FLAGS]
LAYOUT = {'bench_data': 512, 'samples': 512, 'coefficients': 544, 'outputs': 672,
          'marker': 704, 'done': 708, 'errors': 712, 'polls': 716,
          'hw_cycles': 720, 'hw_written': 724, '_stack_top': 1024}
INPUTS = ('firmware/fir_benchmark/main.c', 'firmware/fir_benchmark/link.ld',
          'firmware/c_array_sum/start.S', 'tools/build_fir_benchmark.py',
          'tools/build_c_demo.py', 'tools/elf32.py', 'model/fixed_fir.py', 'model/tiny_cpu.py')


def validate_instructions(words):
    """Every static instruction must belong to the implemented 38-instruction subset."""
    for word in words:
        opcode, f3, f7 = word & 127, (word >> 12) & 7, word >> 25
        legal = False
        if opcode in (0x37, 0x17, 0x6f): legal = True
        elif opcode == 0x67: legal = f3 == 0
        elif opcode == 0x63: legal = f3 in BRANCH_OPERATIONS.values()
        elif opcode == 0x03: legal = f3 in LOAD_OPERATIONS.values()
        elif opcode == 0x23: legal = f3 in STORE_OPERATIONS.values()
        elif opcode == 0x33: legal = (f7, f3) in REGISTER_OPERATIONS.values()
        elif opcode == 0x13:
            legal = ((f7, f3) in SHIFT_IMMEDIATE_OPERATIONS.values() if f3 in (1, 5)
                     else f3 in IMMEDIATE_OPERATIONS.values())
        if not legal: raise ValueError(f'compiler emitted unsupported instruction {word:08X}')


def load_firmware(mode, directory=None):
    if mode not in MODES: raise ValueError('unknown benchmark mode')
    folder = Path(directory) if directory is not None else ROOT/'programs/fir_benchmark'/mode
    image, manifest = load_demo(folder, expected_contract=CONTRACT)
    if manifest['mode'] != mode: raise ValueError('benchmark mode/manifest mismatch')
    if any(image.symbols.get(k) != v for k, v in LAYOUT.items()):
        raise ValueError('benchmark shared layout changed')
    validate_instructions(image.program_words)
    return image, manifest


def load_benchmark(mode, directory=None):
    """Named alias for callers that load several kinds of firmware."""
    return load_firmware(mode, directory)


def build(zig, directory, output):
    """Compile all three modes into child directories; return manifests by mode."""
    zig, directory, output = Path(zig).resolve(), Path(directory).resolve(), Path(output).resolve()
    if not str(directory).isascii(): raise ValueError('use an ASCII build directory')
    directory.mkdir(parents=True, exist_ok=True)
    def run(args, cwd):
        p = subprocess.run([str(zig), *args], cwd=cwd, capture_output=True,
                           text=True, errors='replace', timeout=120)
        if p.returncode or p.stderr.strip(): raise RuntimeError(p.stdout+p.stderr)
        return p.stdout.strip()
    version = run(['version'], directory)
    if version != '0.13.0': raise ValueError('pin Zig 0.13.0')
    clang = run(['cc', '--version'], directory).splitlines()[0]
    manifests, images = {}, {}
    for mode, number in MODES.items():
        work = directory/mode; work.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/'firmware/fir_benchmark/main.c', work/'main.c')
        shutil.copyfile(ROOT/'firmware/fir_benchmark/link.ld', work/'link.ld')
        shutil.copyfile(ROOT/'firmware/c_array_sum/start.S', work/'start.S')
        commands = [
            ['cc', *BENCH_FLAGS, f'-DBENCH_MODE={number}', '-nostdlib', '-Wl,-T,link.ld',
             '-Wl,--build-id=none', 'start.S', 'main.c', '-o', 'program.elf'],
            ['cc', *BENCH_FLAGS, f'-DBENCH_MODE={number}', '-S', 'main.c', '-o', 'main.s'],
        ]
        for command in commands: run(command, work)
        image = read_elf((work/'program.elf').read_bytes())
        validate_instructions(image.program_words)
        if any(image.symbols.get(k) != v for k, v in LAYOUT.items()):
            raise ValueError('compiler/linker changed shared RAM layout')
        memory = struct.pack('<256I', *image.memory_words)
        x = struct.unpack_from('<8i', memory, LAYOUT['samples'])
        h = struct.unpack_from('<32i', memory, LAYOUT['coefficients'])
        expected = fir_block(x, h)
        if mode == 'software':
            r = run_program(image.program_words, initial_memory=image.memory_words)
            raw = struct.pack('<256I', *r.memory)
            if (r.fault or struct.unpack_from('<8i', raw, LAYOUT['outputs']) != expected.outputs
                    or r.memory[LAYOUT['marker']//4:LAYOUT['errors']//4+1] != (2, 1, 0)
                    or r.registers[2] != 1024):
                raise ValueError('compiled software FIR failed numerical/ABI audit')
        for name, words in (('program.hex', image.program_words), ('initial_memory.txt', image.memory_words)):
            (work/name).write_text(''.join(f'{v:08X}\n' for v in words), encoding='ascii', newline='\n')
        artifacts = ('program.elf', 'main.s', 'program.hex', 'initial_memory.txt')
        manifest = {
            'contract': CONTRACT, 'numeric_contract': 'fir-q15-block-v1', 'mode': mode,
            'mode_define': number, 'zig_version': version, 'clang_version': clang,
            'compiler_sha256': digest(zig), 'compiler_cpu': 'generic_rv32+m', 'abi': 'ilp32',
            'compiler_flags': BENCH_FLAGS, 'implemented_m_subset': ['MUL'],
            'commands': [['zig', *c] for c in commands],
            'input_sha256': {p: digest(ROOT/p) for p in INPUTS},
            'artifact_sha256': {p: digest(work/p) for p in artifacts},
            'symbols': image.symbols, 'layout': LAYOUT, 'shared_object_bytes': 216,
            'program_words': len(image.program_words), 'samples': list(x), 'coefficients': list(h),
            'expected_outputs': list(expected.outputs), 'marker_start': 1, 'marker_stop': 2,
            'scope': 'matched compiler artifact; ModelSim timing verified separately',
        }
        (work/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n',
                                         encoding='utf-8', newline='\n')
        dest = output/mode; dest.mkdir(parents=True, exist_ok=True)
        for name in (*artifacts, 'manifest.json'):
            if work/name != dest/name: shutil.copyfile(work/name, dest/name)
        manifests[mode], images[mode] = manifest, image
    if len({i.memory_words for i in images.values()}) != 1:
        raise ValueError('initial RAM differs between benchmark modes')
    return manifests


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig', type=Path, default=DEFAULT_ZIG)
    p.add_argument('--build-dir', type=Path,
                   default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/benchmark-firmware/build'))
    p.add_argument('--output', type=Path, default=ROOT/'programs/fir_benchmark')
    a = p.parse_args(); result = build(a.zig, a.build_dir, a.output)
    print(json.dumps({mode: {'program_words': m['program_words'], 'layout': m['layout']}
                      for mode, m in result.items()}, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
