"""Reproducible register-file cycles, including pre/post-edge expectations."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import random

from model.regfile import RegisterFileReference

ROOT = Path(__file__).resolve().parents[1]
SEED = 0x32F11E


def generate_regfile_vectors(directory: Path) -> dict:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # rst, we, waddr, wdata, raddr1, raddr2: ten easy-to-read teaching cycles.
    cycles = [
        (1, 0, 0, 0, 0, 0), (0, 1, 1, 5, 1, 0),
        (0, 1, 2, 7, 1, 2), (0, 0, 1, 0xDEADBEEF, 1, 2),
        (0, 1, 0, 0xFFFFFFFF, 0, 1), (0, 1, 1, 9, 1, 2),
        (1, 1, 1, 0xDEADBEEF, 1, 2), (0, 0, 0, 0, 1, 2),
        (0, 1, 31, 0xFFFFFFFF, 31, 0),
        (0, 1, 16, 0x80000000, 16, 31),
    ]
    for address in range(1, 32):
        cycles.append((0, 1, address, (address * 0x10204081) & 0xFFFFFFFF,
                       address, (address + 1) % 32))
    for first in range(32):
        for second in range(32):
            cycles.append((0, 0, 0, 0, first, second))
    rng = random.Random(SEED)
    for _ in range(512):
        cycles.append((int(rng.randrange(23) == 0), rng.randrange(2), rng.randrange(32),
                       rng.getrandbits(32), rng.randrange(32), rng.randrange(32)))
    cycles.append((1, 1, 31, 0xFFFFFFFF, 31, 16))
    for address in range(32):
        # Hold reset over two additional write-enabled edges, then release it.
        cycles.append((int(address < 2), int(address < 2), address + 1 if address < 2 else 0,
                       0xDEADBEEF if address < 2 else 0, address, 31 - address))
    reference = RegisterFileReference()
    lines, trace = [], io.StringIO(newline="")
    writer = csv.writer(trace, lineterminator="\n")
    writer.writerow(["cycle", "rst", "we", "waddr", "wdata_hex", "raddr1", "raddr2",
                     "before1_hex", "before2_hex", "after1_hex", "after2_hex"])
    for index, (reset, enable, address, data, first, second) in enumerate(cycles, 1):
        before1, before2 = reference.read(first), reference.read(second)
        reference.edge(reset, enable, address, data)
        after1, after2 = reference.read(first), reference.read(second)
        lines.append(f"{reset} {enable} {address} {data:08X} {first} {second} "
                     f"{before1:08X} {before2:08X} {after1:08X} {after2:08X}\n")
        writer.writerow([index, reset, enable, address, f"{data:08X}", first, second,
                         f"{before1:08X}", f"{before2:08X}", f"{after1:08X}", f"{after2:08X}"])
    path = directory / "regfile_vectors.txt"
    path.write_text("".join(lines), encoding="ascii", newline="\n")
    (directory / "regfile_trace.csv").write_text(trace.getvalue(), encoding="ascii", newline="\n")
    report = {"contract": "regfile32-rv32i-v1", "seed": SEED, "cycle_count": len(cycles),
              "value_checks": len(cycles) * 4, "read_address_pairs": 1024,
              "random_cycles": 512, "period_ns": 10,
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (directory / "regfile_vectors.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                                    encoding="ascii", newline="\n")
    (directory / "vector_count.tcl").write_text(f"set regfile_expected_count {len(cycles)}\n",
                                                encoding="ascii", newline="\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "sim/vectors/regfile32")
    print(json.dumps(generate_regfile_vectors(parser.parse_args().output), indent=2))
