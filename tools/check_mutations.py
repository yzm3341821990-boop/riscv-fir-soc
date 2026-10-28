"""Run three controlled model faults in isolated Python processes.

The real source is never rewritten. Each mutant must trigger assertion
failures in the numerical tests, with no import/runtime errors.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check_mutations() -> dict:
    path = ROOT / "model/fixed_fir.py"
    source = path.read_text(encoding="utf-8")
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    faults = [
        ("truncate_instead_of_round",
         "magnitude = (abs(value) + (1 << (shift - 1))) >> shift",
         "magnitude = abs(value) >> shift",
         "test_positive_rounding_around_half_lsb"),
        ("wrap_instead_of_saturate",
         "return saturate_i16(round_shift(accumulator, FRAC_BITS))",
         "return ((round_shift(accumulator, FRAC_BITS) + 32768) & 0xFFFF) - 32768",
         "test_accumulator_conversion_rounds_then_saturates"),
        ("reverse_coefficient_order",
         "for k, coefficient in enumerate(taps):",
         "for k, coefficient in enumerate(reversed(taps)):",
         "test_hand_computed_causal_convolution"),
    ]
    records = []
    for name, original, replacement, confirming_test in faults:
        if source.count(original) != 1:
            raise ValueError(f"mutation anchor is ambiguous or missing: {name}")
        mutated = source.replace(original, replacement, 1)
        script = (
            "import unittest\nimport model.fixed_fir as model\n"
            f"exec(compile({mutated!r}, '<controlled-mutant>', 'exec'), model.__dict__)\n"
            "suite = unittest.defaultTestLoader.discover('tests', pattern='test_fixed_fir.py')\n"
            "result = unittest.TextTestRunner(verbosity=1).run(suite)\n"
            "raise SystemExit(0 if result.wasSuccessful() else 1)\n"
        )
        process = subprocess.run([sys.executable, "-X", "utf8", "-c", script],
                                 cwd=ROOT, capture_output=True, encoding="utf-8", timeout=30)
        log = process.stdout + process.stderr
        ran = re.search(r"Ran (\d+) tests?", log)
        failures = re.search(r"failures=(\d+)", log)
        errors = re.search(r"errors=(\d+)", log)
        tests_run = int(ran.group(1)) if ran else 0
        failure_count = int(failures.group(1)) if failures else 0
        error_count = int(errors.group(1)) if errors else 0
        killed = (process.returncode == 1 and tests_run > 0 and failure_count > 0
                  and error_count == 0 and confirming_test in log and "ERROR:" not in log)
        records.append({"name": name, "killed": killed, "tests_run": tests_run,
                        "failure_count": failure_count, "error_count": error_count,
                        "confirming_test": confirming_test, "log": log})
    if hashlib.sha256(path.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError("the production source changed during mutation checking")
    return {"source_sha256": source_hash, "killed_count": sum(r["killed"] for r in records),
            "mutations": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = check_mutations()
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"killed_count": report["killed_count"],
                      "total": len(report["mutations"])}))
    return 0 if all(item["killed"] for item in report["mutations"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
