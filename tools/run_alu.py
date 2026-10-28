"""Compile and test VHDL ALU in ModelSim, including a real RTL negative control."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from tools.generate_alu_vectors import generate_alu_vectors

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("rtl/cpu/alu_pkg.vhd", "rtl/cpu/alu32.vhd", "sim/tb/tb_alu32.vhd",
           "sim/modelsim/compile_alu.do", "sim/modelsim/run_alu_batch.do",
           "sim/modelsim/run_alu_gui.do")


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for relative in SOURCES:
        shutil.copyfile(ROOT / relative, directory / Path(relative).name)
    gui = directory / "run_alu_gui.do"
    template = (ROOT / "sim/modelsim/run_alu_gui.do").read_text(encoding="ascii")
    gui.write_text(f"set alu_directory {{{directory.as_posix()}}}\n" + template,
                   encoding="ascii", newline="\n")
    return generate_alu_vectors(directory)


def simulate(executable, directory):
    process = subprocess.run([str(executable), "-c", "-l", "modelsim.log", "-wlf", "alu32.wlf",
                              "-do", "do run_alu_batch.do"], cwd=directory,
                             capture_output=True, text=True, errors="replace", timeout=60)
    log_path = directory / "modelsim.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    if not log:
        log = process.stdout + process.stderr
    return process.returncode, log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports/step2-alu")
    arguments = parser.parse_args()
    executable = arguments.modelsim_bin / "vsim.exe" if arguments.modelsim_bin else None
    if executable is None:
        found = shutil.which("vsim")
        executable = Path(found) if found else Path("E:/quartus/modelsim_ase/win32aloem/vsim.exe")
    executable = executable.resolve()
    if not executable.is_file():
        parser.error("ModelSim not found; pass --modelsim-bin with the directory containing vsim")
    key = hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:8]
    build = (arguments.build_dir or Path(tempfile.gettempdir()) / f"riscv-fir-alu32-{key}").resolve()
    if not str(build).isascii() or any(c in str(build) for c in "{}\r\n"):
        parser.error("Use an ASCII-only --build-dir without braces for this legacy simulator")
    reports = arguments.report_dir
    reports.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()

    def save_status(status, stage):
        (reports / "validation.json").write_text(json.dumps({
            "status": status, "stage": stage, "started_at_utc": started,
            "scope": "ALU RTL functional simulation"}, indent=2) + "\n", encoding="utf-8")

    # Invalidate a prior PASS before any compile/log changes in this run.
    save_status("incomplete", "baseline")
    baseline = build / "baseline"
    vectors = prepare(baseline)
    code, log = simulate(executable, baseline)
    (reports / "modelsim.log").write_text(log, encoding="utf-8", newline="\n")
    marker = re.search(r"ALU32_PASS vectors=\s*(\d+)", log)
    if code != 0 or not marker or int(marker.group(1)) != vectors["vector_count"]:
        save_status("fail", "baseline")
        print(log[-10000:], file=sys.stderr)
        print(f"ALU simulation failed (exit={code}); see {reports / 'modelsim.log'}", file=sys.stderr)
        return 1
    source = (ROOT / "rtl/cpu/alu32.vhd").read_text(encoding="utf-8")
    anchor = "shift_right(signed(a), shift_amount)"
    if source.count(anchor) != 1:
        save_status("fail", "mutation_setup")
        print("SRA mutation anchor missing or ambiguous", file=sys.stderr)
        return 1
    # The temporary mutant lives inside the explicit build root, never in rtl/.
    with tempfile.TemporaryDirectory(prefix="mutant-", dir=build) as temporary:
        mutant = Path(temporary).resolve()
        if not mutant.is_relative_to(build):
            raise RuntimeError("unexpected mutation-directory location")
        prepare(mutant)
        (mutant / "alu32.vhd").write_text(source.replace(
            anchor, "shift_right(unsigned(a), shift_amount)", 1), encoding="ascii", newline="\n")
        mutant_code, mutant_log = simulate(executable, mutant)
    (reports / "mutation-sra.log").write_text(mutant_log, encoding="utf-8", newline="\n")
    killed = mutant_code != 0 and "ALU32_MISMATCH" in mutant_log and "ALU32_PASS" not in mutant_log
    if not killed:
        save_status("fail", "negative_control")
        print("Controlled SRA fault was not rejected by a result assertion", file=sys.stderr)
        return 1
    version = subprocess.run([str(executable), "-version"], capture_output=True,
                             text=True, errors="replace", timeout=15)
    hashes = {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
              for relative in (*SOURCES, "model/alu.py", "tools/generate_alu_vectors.py", "tools/run_alu.py")}
    report = {"status": "pass", "contract": "alu32-rv32i-v1",
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "simulator": (version.stdout + version.stderr).strip(),
              "language": "VHDL-93", "vector_count": int(marker.group(1)),
              "vector_seed": vectors["seed"], "vector_sha256": vectors["sha256"],
              "baseline_exit_code": code,
              "negative_control": {"name": "SRA changed to logical right shift", "killed": killed,
                                   "exit_code": mutant_code},
              "source_sha256": hashes, "gui_script": (baseline / "run_alu_gui.do").as_posix(),
              "scope": "ALU RTL functional simulation", "synthesis": "not_run",
              "timing": "not_run", "hardware_programming": "not_run"}
    (reports / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                            encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("status", "vector_count", "negative_control", "gui_script")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
