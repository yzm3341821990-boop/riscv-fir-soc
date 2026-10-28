"""Build the pinned freestanding C demo with Zig 0.13.0's Clang 18.1.6."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from model.tiny_cpu import run_program
from tools.elf32 import read_elf

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIG = Path('F:/CodexWorkspace/tools/zig-0.13.0/zig-windows-x86_64-0.13.0/zig.exe')
FLAGS = ['-target', 'riscv32-freestanding', '-mcpu=generic_rv32', '-mabi=ilp32',
         '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fno-pic',
         '-msmall-data-limit=0', '-mno-relax', '-fno-unwind-tables',
         '-fno-asynchronous-unwind-tables', '-O1', '-g0', '-fno-unroll-loops']
INPUTS = ('firmware/c_array_sum/main.c', 'firmware/c_array_sum/start.S',
          'firmware/c_array_sum/link.ld', 'tools/build_c_demo.py', 'tools/elf32.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(zig: Path, directory: Path, output: Path):
    directory, output = Path(directory).resolve(), Path(output).resolve()
    if not str(directory).isascii():
        raise ValueError('use an ASCII build directory')
    directory.mkdir(parents=True, exist_ok=True)
    zig = Path(zig).resolve()

    def run(arguments):
        p = subprocess.run([str(zig), *arguments], cwd=directory, capture_output=True,
                           text=True, errors='replace', timeout=120)
        if p.returncode or p.stderr.strip():
            raise RuntimeError(f'compiler failed or emitted diagnostics: {p.stdout}{p.stderr}')
        return p.stdout.strip()

    version = run(['version'])
    if version != '0.13.0':
        raise ValueError('this reproducible demo pins Zig 0.13.0')
    features = json.loads(run(['targets']))['cpus']['riscv32']['generic_rv32']
    if features != ['32bit']:
        raise ValueError('expected base RV32I without M/A/C/F/D extensions')
    clang = run(['cc', '--version']).splitlines()[0]
    for name in ('main.c', 'start.S', 'link.ld'):
        shutil.copyfile(ROOT/'firmware/c_array_sum'/name, directory/name)
    commands = [
        ['cc', *FLAGS, '-nostdlib', '-Wl,-T,link.ld', '-Wl,--build-id=none',
         'start.S', 'main.c', '-o', 'program.elf'],
        ['cc', *FLAGS, '-S', 'main.c', '-o', 'main.s'],
    ]
    for command in commands:
        run(command)
    image = read_elf((directory/'program.elf').read_bytes())
    required = {'_start': 0, '_stack_top': 1024, 'samples': 512, 'result': 528, 'done': 532}
    if any(image.symbols.get(name) != value for name, value in required.items()):
        raise ValueError('unexpected firmware symbol layout')
    if image.symbols['_program_end'] != 4*len(image.program_words):
        raise ValueError('end sentinel must be immediately after text')
    values = [int.from_bytes(word.to_bytes(4, 'little')[part:part+2], 'little', signed=True)
              for word in image.memory_words[128:132] for part in (0, 2)]
    if values != [12, -3, 25, -10, 7, -2, 30, -4]:
        raise ValueError('unexpected C input initializer')
    result = run_program(image.program_words, initial_memory=image.memory_words)
    loads = [t for t in result.trace if t.instruction & 0x707F == 0x1003]
    if (result.fault or result.registers[10] != 55 or result.registers[2] != 1024 or
            result.memory[132:134] != (55, 1) or len(loads) != 8):
        raise ValueError('C semantic check failed: need eight signed loads, sum55, done1, restored stack')
    (directory/'program.hex').write_text(''.join(f'{w:08X}\n' for w in image.program_words), encoding='ascii', newline='\n')
    (directory/'initial_memory.txt').write_text(''.join(f'{w:08X}\n' for w in image.memory_words), encoding='ascii', newline='\n')
    artifacts = ('program.elf', 'main.s', 'program.hex', 'initial_memory.txt')
    manifest = {
        'contract': 'c-array-sum-rv32i-ilp32-v1', 'zig_version': version, 'clang_version': clang,
        'compiler_sha256': digest(zig), 'cpu_features': features,
        'target': 'riscv32-freestanding', 'abi': 'ilp32',
        'commands': [['zig', *command] for command in commands],
        'input_sha256': {name: digest(ROOT/name) for name in INPUTS},
        'artifact_sha256': {name: digest(directory/name) for name in artifacts},
        'symbols': image.symbols, 'program_words': len(image.program_words),
        'dynamic_commits': len(result.trace), 'memory_requests': len(result.memory_trace),
        'expected_result': 55, 'expected_done': 1, 'signed_samples': values,
        'scope': 'freestanding C and assembly startup; initialized RAM supplied by testbench loader',
    }
    (directory/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n', encoding='utf-8', newline='\n')
    output.mkdir(parents=True, exist_ok=True)
    for name in (*artifacts, 'manifest.json'):
        if (directory/name).resolve() != (output/name).resolve():
            shutil.copyfile(directory/name, output/name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zig', type=Path, default=DEFAULT_ZIG)
    parser.add_argument('--build-dir', type=Path, default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/c-program/build'))
    parser.add_argument('--output', type=Path, default=ROOT/'programs/c_array_sum')
    args = parser.parse_args()
    result = build(args.zig, args.build_dir, args.output)
    print(json.dumps({k: result[k] for k in ('zig_version', 'clang_version', 'program_words',
                                          'dynamic_commits', 'memory_requests', 'expected_result')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
