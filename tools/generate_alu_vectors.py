"""Export literal examples, boundary combinations and seeded ALU vectors."""

import argparse
import hashlib
import json
from pathlib import Path
import random

from model.alu import alu_result

ROOT = Path(__file__).resolve().parents[1]
SEED = 0xA10032


def generate_alu_vectors(directory: Path) -> dict:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Hand-derived examples appear first to make the GUI wave easy to read.
    vectors = [
        (0, 0xFFFFFFFF, 1, 0), (0, 0x7FFFFFFF, 1, 0x80000000),
        (1, 0, 1, 0xFFFFFFFF), (2, 0x55AA55AA, 0xAA55AA55, 0),
        (3, 0x55AA55AA, 0xAA55AA55, 0xFFFFFFFF),
        (4, 0x55AA55AA, 0xAA55AA55, 0xFFFFFFFF),
        (5, 0x80000001, 31, 0x80000000), (6, 0x80000000, 1, 0x40000000),
        (7, 0x80000000, 1, 0xC0000000), (8, 0xFFFFFFFF, 1, 1),
        (9, 0xFFFFFFFF, 1, 0), (5, 0x89ABCDEF, 32, 0x89ABCDEF),
        (7, 0x89ABCDEF, 0xFFFFFFFF, 0xFFFFFFFF),
        (8, 0x80000000, 0x80000000, 0), (9, 0x80000000, 0xFFFFFFFF, 1),
        (10, 0xFFFFFFFF, 1, 0),
    ]
    for operation, a, b, expected in vectors:
        if alu_result(a, b, operation) != expected:
            raise ValueError("ALU reference disagrees with a hand-derived example")
    edges = (0, 1, 2, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF,
             0x55555555, 0xAAAAAAAA, 31, 32, 33, 0x80000001)
    for operation in range(16):
        for a in edges:
            for b in edges:
                vectors.append((operation, a, b, alu_result(a, b, operation)))
    rng = random.Random(SEED)
    for operation in range(10):
        for _ in range(256):
            a, b = rng.getrandbits(32), rng.getrandbits(32)
            vectors.append((operation, a, b, alu_result(a, b, operation)))
    text = "".join(f"{operation:X} {a:08X} {b:08X} {result:08X}\n"
                   for operation, a, b, result in vectors)
    path = directory / "alu_vectors.txt"
    path.write_text(text, encoding="ascii", newline="\n")
    report = {"contract": "alu32-rv32i-v1", "seed": SEED, "vector_count": len(vectors),
              "hand_derived": 16, "boundary_cross_product": 2304,
              "random": 2560, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (directory / "alu_vectors.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                                encoding="ascii", newline="\n")
    (directory / "vector_count.tcl").write_text(f"set alu_expected_count {len(vectors)}\n",
                                                encoding="ascii", newline="\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "sim/vectors/alu32")
    print(json.dumps(generate_alu_vectors(parser.parse_args().output), indent=2))
