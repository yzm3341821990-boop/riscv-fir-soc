"""Generate deterministic, word-addressed FIR verification fixtures."""

import argparse
import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import random

from model.fixed_fir import fir_block, to_memory_word

ROOT = Path(__file__).resolve().parents[1]
SEED = 0xC0DE
CONTRACT = {
    "id": "fir-q15-block-v1", "taps": 32, "sample_bits": 16,
    "fraction_bits": 15, "accumulator_bits": 40,
    "rounding": "nearest_ties_away_from_zero", "output": "saturate_signed_16",
    "history": "zero_each_block", "output_length": "same_as_input",
    "coefficient_order": "h[0] multiplies x[n]",
    "memory_word_bits": 32, "sample_encoding": "sign_extend_16_to_32",
    "byte_order_when_loaded_into_memory": "little_endian",
}


@dataclass(frozen=True)
class VectorCase:
    name: str
    description: str
    samples: tuple[int, ...]
    coefficients: tuple[int, ...]
    seed: int | None = None


def _cases():
    half = (16384,) + (0,) * 31
    cases = [
        VectorCase("zero", "Zero input with nonzero coefficients.",
                   (0,) * 64, (32767,) * 32),
        VectorCase("impulse", "Half-scale impulse, not unrepresentable Q15 +1.",
                   (16384,) + (0,) * 63,
                   tuple((k - 16) * 1024 for k in range(32))),
        VectorCase("step", "Half-scale step and zero-initialized history.",
                   (16384,) * 64, (16384, 8192, -4096) + (0,) * 29),
        VectorCase("positive_ties", "Positive half-LSB ties round away from zero.",
                   (1, 3, 5, 32767), half),
        VectorCase("negative_ties", "Negative half-LSB ties round away from zero.",
                   (-1, -3, -5, -32767), half),
        VectorCase("positive_saturation", "Positive output saturation.",
                   (32767,) * 64, (32767,) * 32),
        VectorCase("negative_saturation", "Negative output saturation.",
                   (-32768,) * 64, (32767,) * 32),
        VectorCase("accumulator_extreme", "32*(-32768)*(-32768) = 2**35.",
                   (-32768,) * 32, (-32768,) * 32),
        VectorCase("alternating_extrema", "Alternating full-scale signs.",
                   (-32768, 32767) * 32, (32767, -32768) * 16),
        VectorCase("short_block", "Seven samples, shorter than the impulse response.",
                   (32767, -32768, 1, -1, 12345, -23456, 0),
                   tuple((k - 16) * 512 for k in range(32))),
        VectorCase("empty_block", "Numerical empty-block behavior; not an MMIO command.",
                   (), (0,) * 32),
    ]
    for length in (256, 1024):
        seed = SEED ^ length
        rng = random.Random(seed)
        cases.append(VectorCase(
            f"random_{length}", "Fixed-seed full-range input and bounded coefficients.",
            tuple(rng.randint(-32768, 32767) for _ in range(length)),
            tuple(rng.randint(-8192, 8192) for _ in range(32)), seed))
    return cases


def _write_words(path, words):
    text = "".join(word + "\n" for word in words)
    path.write_text(text, encoding="ascii", newline="\n")


def generate_vectors(directory: Path) -> dict:
    """Write a deterministic suite; overwrite only the named generated files."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for case in _cases():
        case_dir = directory / case.name
        case_dir.mkdir(exist_ok=True)
        result = fir_block(case.samples, case.coefficients)
        _write_words(case_dir / "input.hex", map(to_memory_word, case.samples))
        _write_words(case_dir / "coefficients.hex", map(to_memory_word, case.coefficients))
        _write_words(case_dir / "expected.hex", map(to_memory_word, result.outputs))
        _write_words(case_dir / "accumulators.hex",
                     (f"{value & ((1 << 40) - 1):010X}" for value in result.accumulators))
        trace = io.StringIO(newline="")
        writer = csv.writer(trace, lineterminator="\n")
        writer.writerow(["n", "input", "accumulator", "output"])
        writer.writerows((n, sample, accumulator, output) for n, (sample, accumulator, output)
                         in enumerate(zip(case.samples, result.accumulators, result.outputs)))
        (case_dir / "trace.csv").write_text(trace.getvalue(), encoding="ascii", newline="\n")
        files = {}
        for key, filename in [("inputs", "input.hex"), ("coefficients", "coefficients.hex"),
                              ("outputs", "expected.hex"), ("accumulators", "accumulators.hex"),
                              ("trace", "trace.csv")]:
            path = case_dir / filename
            files[key] = {"path": path.relative_to(directory).as_posix(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        records.append({"name": case.name, "description": case.description,
                        "sample_count": len(case.samples), "seed": case.seed, "files": files})
    sources = {}
    for relative in ("model/fixed_fir.py", "tools/generate_vectors.py"):
        sources[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    manifest = {"schema": "riscv-fir-vectors-v1", "contract": CONTRACT,
                "base_seed": SEED, "source_sha256": sources, "cases": records}
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii", newline="\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "vectors")
    arguments = parser.parse_args()
    manifest = generate_vectors(arguments.output)
    print(json.dumps({"case_count": len(manifest["cases"]),
                      "sample_count": sum(case["sample_count"] for case in manifest["cases"])}))


if __name__ == "__main__":
    main()
