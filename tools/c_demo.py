"""Validate the checked-in C compiler artifacts without requiring a compiler."""
import hashlib
import json
from pathlib import Path

from tools.elf32 import read_elf

ROOT = Path(__file__).resolve().parents[1]


def load_demo(directory=None, *, expected_contract='c-array-sum-rv32i-ilp32-v1'):
    directory = Path(directory) if directory is not None else ROOT/'programs/c_array_sum'
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if manifest['contract'] != expected_contract:
        raise ValueError('unsupported C demo contract')
    for name, expected in manifest['input_sha256'].items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'C input changed; rebuild with python -m tools.build_c_demo: {name}')
    for name, expected in manifest['artifact_sha256'].items():
        path = (directory/name).resolve()
        if not path.is_relative_to(directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'C compiler artifact changed: {name}')
    image = read_elf((directory/'program.elf').read_bytes())
    if (tuple(int(s,16) for s in (directory/'program.hex').read_text().split()) != image.program_words or
            tuple(int(s,16) for s in (directory/'initial_memory.txt').read_text().split()) != image.memory_words or
            image.symbols != manifest['symbols']):
        raise ValueError('ELF and exported images disagree')
    return image, manifest
