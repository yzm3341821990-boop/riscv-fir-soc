"""Run the complete standard-library-only step-one verification gate."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

from tools.check_mutations import check_mutations
from tools.demo_data import make_demo_data
from tools.generate_vectors import generate_vectors
from tools.verify_vectors import verify_vectors

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports/step1")
    arguments = parser.parse_args()
    directory = arguments.report_dir
    directory.mkdir(parents=True, exist_ok=True)
    process = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", "discover",
                              "-s", "tests", "-v"], cwd=ROOT, capture_output=True,
                             encoding="utf-8", timeout=60)
    log = process.stdout + process.stderr
    (directory / "unit-tests.log").write_text(log, encoding="utf-8", newline="\n")
    ran = re.search(r"Ran (\d+) tests?", log)
    if process.returncode != 0 or not ran:
        print(log, file=sys.stderr)
        return 1
    generated = ROOT / "build/step1-vectors"
    generate_vectors(generated)
    committed = ROOT / "vectors"
    expected_files = {path.relative_to(generated) for path in generated.rglob("*") if path.is_file()}
    committed_files = {path.relative_to(committed) for path in committed.rglob("*") if path.is_file()}
    if expected_files != committed_files:
        print("Fixture file set differs; run python -m tools.generate_vectors", file=sys.stderr)
        return 1
    changed = [str(relative) for relative in sorted(expected_files)
               if (generated / relative).read_bytes() != (committed / relative).read_bytes()]
    if changed:
        print(f"Stale fixtures; regenerate and review: {changed}", file=sys.stderr)
        return 1
    vectors = verify_vectors(committed)
    mutations = check_mutations()
    (directory / "mutations.json").write_text(json.dumps(mutations, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
    if mutations["killed_count"] != len(mutations["mutations"]):
        print("A controlled mutation survived or failed without a valid assertion", file=sys.stderr)
        return 1
    sources = {}
    for folder in ("model", "tools", "tests"):
        for path in sorted((ROOT / folder).glob("*.py")):
            sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {
        "status": "pass", "scope": "Python reference model and fixtures only",
        "contract": "fir-q15-block-v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "unit_tests": {"count": int(ran.group(1)), "failures": 0, "errors": 0},
        "vectors": vectors, "vectors_regenerate_identically": True,
        "mutations": {"killed": mutations["killed_count"], "total": len(mutations["mutations"]),
                      "names": [item["name"] for item in mutations["mutations"]]},
        "demo_metrics": make_demo_data()["metrics"], "source_sha256": sources,
        "rtl_simulation": "not_run", "synthesis": "not_run", "timing": "not_run",
        "hardware_programming": "not_run", "hardware_performance": "not_measured",
    }
    (directory / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                               encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("status", "unit_tests", "vectors", "mutations")},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
