"""Verify register-file VHDL with ModelSim and two real RTL negative controls."""

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

from tools.generate_regfile_vectors import generate_regfile_vectors

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("rtl/cpu/regfile32.vhd", "sim/tb/tb_regfile32.vhd",
           "sim/modelsim/compile_regfile.do", "sim/modelsim/run_regfile_batch.do",
           "sim/modelsim/run_regfile_gui.do")


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for relative in SOURCES:
        shutil.copyfile(ROOT / relative, directory / Path(relative).name)
    template = (ROOT / "sim/modelsim/run_regfile_gui.do").read_text(encoding="ascii")
    (directory / "run_regfile_gui.do").write_text(
        f"set regfile_directory {{{directory.as_posix()}}}\n" + template,
        encoding="ascii", newline="\n")
    return generate_regfile_vectors(directory)


def simulate(executable, directory):
    process = subprocess.run([str(executable), "-c", "-l", "modelsim.log", "-wlf", "regfile32.wlf",
                              "-do", "do run_regfile_batch.do"], cwd=directory,
                             capture_output=True, text=True, errors="replace", timeout=60)
    logfile = directory / "modelsim.log"
    log = logfile.read_text(encoding="utf-8", errors="replace") if logfile.is_file() else ""
    return process.returncode, log or process.stdout + process.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports/step3-regfile")
    arguments = parser.parse_args()
    found = shutil.which("vsim")
    executable = (arguments.modelsim_bin / "vsim.exe" if arguments.modelsim_bin else
                  Path(found) if found else Path("E:/quartus/modelsim_ase/win32aloem/vsim.exe")).resolve()
    if not executable.is_file():
        parser.error("ModelSim not found; pass --modelsim-bin")
    key = hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:8]
    build = (arguments.build_dir or Path(tempfile.gettempdir()) / f"riscv-fir-regfile-{key}").resolve()
    if not str(build).isascii() or any(c in str(build) for c in "{}\r\n"):
        parser.error("Use an ASCII-only --build-dir without braces")
    reports = arguments.report_dir
    reports.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()

    def save_status(status, stage):
        (reports / "validation.json").write_text(json.dumps({"status": status, "stage": stage,
            "started_at_utc": started, "scope": "register-file RTL functional simulation"},
            indent=2) + "\n", encoding="utf-8")

    save_status("incomplete", "baseline")
    baseline = build / "baseline"
    vectors = prepare(baseline)
    code, log = simulate(executable, baseline)
    (reports / "modelsim.log").write_text(log, encoding="utf-8", newline="\n")
    marker = re.search(r"REGFILE32_PASS cycles=\s*(\d+) value_checks=\s*(\d+)", log)
    if (code != 0 or not marker or int(marker.group(1)) != vectors["cycle_count"]
            or int(marker.group(2)) != vectors["value_checks"]):
        save_status("fail", "baseline")
        print(log[-10000:], file=sys.stderr)
        return 1
    source_path = ROOT / "rtl/cpu/regfile32.vhd"
    source = source_path.read_text(encoding="utf-8")
    original_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    faults = [
        ("write_on_falling_edge", "rising_edge(clk)", "falling_edge(clk)", "before"),
        ("reset_loses_write_priority", "if rst = '1' then",
         "if rst = '1' and we = '0' then", "after"),
    ]
    mutations = []
    for name, anchor, replacement, phase in faults:
        if source.count(anchor) != 1:
            save_status("fail", "mutation_setup")
            print(f"Mutation anchor missing or ambiguous: {name}", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory(prefix="mutant-", dir=build) as temporary:
            mutant = Path(temporary).resolve()
            if not mutant.is_relative_to(build):
                raise RuntimeError("unexpected mutation-directory location")
            prepare(mutant)
            (mutant / "regfile32.vhd").write_text(source.replace(anchor, replacement, 1),
                                                 encoding="ascii", newline="\n")
            mutant_code, mutant_log = simulate(executable, mutant)
        (reports / f"mutation-{name}.log").write_text(mutant_log, encoding="utf-8", newline="\n")
        killed = (mutant_code != 0 and "REGFILE32_MISMATCH" in mutant_log
                  and f"phase={phase}" in mutant_log and "REGFILE32_PASS" not in mutant_log)
        mutations.append({"name": name, "killed": killed, "exit_code": mutant_code,
                          "expected_failure_phase": phase})
        if not killed:
            save_status("fail", "negative_control")
            print(f"Controlled fault not rejected by the intended assertion: {name}", file=sys.stderr)
            return 1
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != original_hash:
        save_status("fail", "source_identity")
        raise RuntimeError("production RTL changed during negative controls")
    version = subprocess.run([str(executable), "-version"], capture_output=True,
                             text=True, errors="replace", timeout=15)
    hashes = {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
              for relative in (*SOURCES, "model/regfile.py", "tools/generate_regfile_vectors.py",
                               "tools/run_regfile.py")}
    report = {"status": "pass", "contract": "regfile32-rv32i-v1",
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "simulator": (version.stdout + version.stderr).strip(), "language": "VHDL-93",
              "cycles": int(marker.group(1)), "value_checks": int(marker.group(2)),
              "vector_seed": vectors["seed"], "vector_sha256": vectors["sha256"],
              "baseline_exit_code": code, "negative_controls": mutations,
              "source_sha256": hashes,
              "gui_script": (baseline / "run_regfile_gui.do").as_posix(),
              "scope": "register-file RTL functional simulation", "synthesis": "not_run",
              "timing": "not_run", "hardware_programming": "not_run"}
    (reports / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                            encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("status", "cycles", "value_checks",
                     "negative_controls", "gui_script")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
