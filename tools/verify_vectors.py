"""Audit fixture hashes, encodings, CSV traces and rational FIR results.

Intentionally does not import the production FIR or its rounding helpers.
"""

import argparse
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys


def _words(path, bits, sample=False):
    values = []
    for index, line in enumerate(path.read_text(encoding="ascii").splitlines()):
        if len(line) != bits // 4 or any(c not in "0123456789abcdefABCDEF" for c in line):
            raise ValueError(f"invalid word: {path.name}:{index + 1}")
        raw = int(line, 16)
        value = raw - (1 << bits) if raw & (1 << (bits - 1)) else raw
        if sample and not -32768 <= value <= 32767:
            raise ValueError(f"invalid sign extension: {path.name}:{index + 1}")
        values.append(value)
    return values


def _oracle(samples, coefficients):
    # Scatter contributions forward, independent of the model's dot-product loop.
    accumulators = [0] * len(samples)
    for start, sample in enumerate(samples):
        for delay, coefficient in enumerate(coefficients):
            if start + delay < len(samples):
                accumulators[start + delay] += sample * coefficient
    outputs = []
    for accumulator in accumulators:
        exact = Fraction(accumulator, 32768)
        lower = abs(exact.numerator) // exact.denominator
        rounded = lower + int(abs(exact) - lower >= Fraction(1, 2))
        if exact < 0:
            rounded = -rounded
        outputs.append(max(-32768, min(32767, rounded)))
    return accumulators, outputs


def verify_vectors(directory: Path) -> dict:
    directory = Path(directory).resolve()
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("missing manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    if manifest.get("schema") != "riscv-fir-vectors-v1":
        raise ValueError("unsupported manifest schema")
    contract = manifest.get("contract", {})
    required = {"id": "fir-q15-block-v1", "taps": 32, "sample_bits": 16,
                "fraction_bits": 15, "accumulator_bits": 40,
                "rounding": "nearest_ties_away_from_zero", "output": "saturate_signed_16",
                "history": "zero_each_block", "output_length": "same_as_input",
                "coefficient_order": "h[0] multiplies x[n]", "memory_word_bits": 32,
                "sample_encoding": "sign_extend_16_to_32",
                "byte_order_when_loaded_into_memory": "little_endian"}
    if contract != required:
        raise ValueError("unsupported numeric contract")
    sample_count = hashes_checked = max_abs_accumulator = 0
    for case in manifest["cases"]:
        paths = {}
        for key in ("inputs", "coefficients", "outputs", "accumulators", "trace"):
            record = case["files"][key]
            path = (directory / record["path"]).resolve()
            if not path.is_relative_to(directory):
                raise ValueError("fixture path escapes suite directory")
            if not path.is_file():
                raise ValueError(f"missing file: {record['path']}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError(f"hash mismatch: {record['path']}")
            hashes_checked += 1
            paths[key] = path
        samples = _words(paths["inputs"], 32, sample=True)
        coefficients = _words(paths["coefficients"], 32, sample=True)
        outputs = _words(paths["outputs"], 32, sample=True)
        accumulators = _words(paths["accumulators"], 40)
        if len(coefficients) != 32 or len(samples) != case["sample_count"]:
            raise ValueError(f"fixture length mismatch: {case['name']}")
        expected_accumulators, expected_outputs = _oracle(samples, coefficients)
        if accumulators != expected_accumulators:
            raise ValueError(f"accumulator mismatch: {case['name']}")
        if outputs != expected_outputs:
            raise ValueError(f"output mismatch: {case['name']}")
        with paths["trace"].open(encoding="ascii", newline="") as source:
            reader = csv.reader(source)
            if next(reader, None) != ["n", "input", "accumulator", "output"]:
                raise ValueError(f"trace mismatch: {case['name']}")
            rows = [tuple(map(int, row)) for row in reader]
        expected_rows = [(n, sample, accumulator, output)
                         for n, (sample, accumulator, output) in enumerate(
                             zip(samples, expected_accumulators, expected_outputs))]
        if rows != expected_rows:
            raise ValueError(f"trace mismatch: {case['name']}")
        sample_count += len(samples)
        max_abs_accumulator = max(max_abs_accumulator,
                                  max(map(abs, accumulators), default=0))
    return {"case_count": len(manifest["cases"]), "sample_count": sample_count,
            "hashes_checked": hashes_checked, "output_mismatches": 0,
            "max_abs_accumulator": max_abs_accumulator,
            "oracle": "independent scatter convolution with fractions.Fraction rounding"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_vectors(arguments.directory)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"VERIFY FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
