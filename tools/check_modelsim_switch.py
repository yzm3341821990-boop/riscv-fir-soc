"""Exercise GUI loader macros with designs already loaded in one ModelSim process.

Run in console mode to automate loading order; this checks live design switches
and numerical completion, not GUI rendering. Both modules must have run once.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from tools.run_alu import prepare as prepare_alu
from tools.run_regfile import prepare as prepare_regfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path)
    parser.add_argument("--include-cpu", action="store_true",
                        help="also exercise arithmetic, memory, loop, upper-immediate and subword CPU demo loaders")
    arguments = parser.parse_args()
    found = shutil.which("vsim")
    executable = (arguments.modelsim_bin / "vsim.exe" if arguments.modelsim_bin else
                  Path(found) if found else Path("E:/quartus/modelsim_ase/win32aloem/vsim.exe")).resolve()
    if not executable.is_file():
        parser.error("ModelSim not found; pass --modelsim-bin")
    alu_report = json.loads((ROOT / "reports/step2-alu/validation.json").read_text(encoding="utf-8"))
    reg_report = json.loads((ROOT / "reports/step3-regfile/validation.json").read_text(encoding="utf-8"))
    alu_dir, reg_dir = Path(alu_report["gui_script"]).parent, Path(reg_report["gui_script"]).parent
    for directory in (alu_dir, reg_dir):
        if not str(directory).isascii() or any(c in str(directory) for c in "{}\r\n"):
            parser.error("Run the module tools with ASCII-only build directories first")
    prepare_alu(alu_dir)
    prepare_regfile(reg_dir)
    switches = [
        (reg_dir, "run_regfile_gui.do", "tb_regfile32", "ALU -> register file"),
        (alu_dir, "run_alu_gui.do", "tb_alu32", "register file -> ALU"),
        (reg_dir, "run_regfile_gui.do", "tb_regfile32", "ALU -> register file")]
    if arguments.include_cpu:
        from tools.run_cpu import prepare as prepare_cpu
        cpu_report = json.loads((ROOT / "reports/step11-software-fir/validation.json").read_text(encoding="utf-8"))
        cpu_dir = Path(cpu_report["gui_script"]).parent
        if not str(cpu_dir).isascii() or any(c in str(cpu_dir) for c in "{}\r\n"):
            parser.error("Use an ASCII-only CPU build directory")
        prepare_cpu(cpu_dir)
        switches.extend([
            (cpu_dir, "run_cpu_gui.do", "tb_tiny_cpu", "register file -> tiny CPU"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "tiny CPU -> register file"),
            (cpu_dir, "run_cpu_gui.do", "tb_tiny_cpu", "register file -> tiny CPU"),
            (cpu_dir, "run_ops_gui.do", "tb_tiny_cpu", "tiny CPU -> ALU instruction demo"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "ALU instruction demo -> register file"),
            (cpu_dir, "run_ops_gui.do", "tb_tiny_cpu", "register file -> ALU instruction demo"),
            (cpu_dir, "run_memory_gui.do", "tb_tiny_cpu", "ALU instruction demo -> memory demo"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "memory demo -> register file"),
            (cpu_dir, "run_memory_gui.do", "tb_tiny_cpu", "register file -> memory demo"),
            (cpu_dir, "run_loop_gui.do", "tb_tiny_cpu", "memory demo -> loop demo"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "loop demo -> register file"),
            (cpu_dir, "run_loop_gui.do", "tb_tiny_cpu", "register file -> loop demo"),
            (cpu_dir, "run_upper_gui.do", "tb_tiny_cpu", "loop demo -> upper-immediate demo"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "upper-immediate demo -> register file"),
            (cpu_dir, "run_upper_gui.do", "tb_tiny_cpu", "register file -> upper-immediate demo"),
            (cpu_dir, "run_subword_gui.do", "tb_tiny_cpu", "upper-immediate demo -> subword demo"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "subword demo -> register file"),
            (cpu_dir, "run_subword_gui.do", "tb_tiny_cpu", "register file -> subword demo"),
            (cpu_dir, "run_c_gui.do", "tb_tiny_cpu", "subword demo -> compiled C demo"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "compiled C demo -> register file"),
            (cpu_dir, "run_c_gui.do", "tb_tiny_cpu", "register file -> compiled C demo"),
            (cpu_dir, "run_fir_gui.do", "tb_tiny_cpu", "compiled C demo -> software FIR"),
            (reg_dir, "run_regfile_gui.do", "tb_regfile32", "software FIR -> register file"),
            (cpu_dir, "run_fir_gui.do", "tb_tiny_cpu", "register file -> software FIR")])
    script = ["onerror {quit -code 1 -force}", "onbreak {quit -code 1 -force}",
              "do compile_alu.do", "vsim -voptargs=+acc work.tb_alu32", "run -all"]
    for number, (directory, macro, top, description) in enumerate(switches, 1):
        script.extend([
            f"do {{{(directory / macro).as_posix()}}}",
            f'if {{[string tolower [examine sim:/{top}/finished]] ne "true"}} {{error "switch incomplete"}}',
            f'echo "SWITCH_{number}_PASS {top}"',
        ])
    marker = f"MODELSIM_SWITCH_PASS transitions={len(switches)}"
    script.extend([f'echo "{marker}"', "quit -code 0 -force"])
    (alu_dir / "check_switch.do").write_text("\n".join(script) + "\n", encoding="ascii", newline="\n")
    reports = ROOT / "reports/modelsim-switch"
    reports.mkdir(parents=True, exist_ok=True)
    report_path = reports / "validation.json"
    report_path.write_text('{"status": "incomplete"}\n', encoding="ascii")
    process = subprocess.run([str(executable), "-c", "-l", "switch-regression.log",
                              "-do", "do check_switch.do"], cwd=alu_dir, capture_output=True,
                             text=True, errors="replace", timeout=60)
    log_path = alu_dir / "switch-regression.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else process.stdout + process.stderr
    (reports / "modelsim.log").write_text(log, encoding="utf-8", newline="\n")
    # Legacy module compile macros call vmap -c even when a local mapping
    # already exists. Keep that exact informational warning visible; reject
    # other warnings, including WLF collisions or numeric metavalue warnings.
    mapping_warning = "# ** Warning: vmap will not overwrite local modelsim.ini."
    warnings = [line.strip() for line in log.splitlines() if "** Warning:" in line]
    unexpected_warnings = [line for line in warnings if line != mapping_warning]
    passed = (process.returncode == 0 and marker in log
              and all(f"SWITCH_{n}_PASS" in log for n in range(1, len(switches) + 1))
              and "** Error:" not in log and "** Failure:" not in log and not unexpected_warnings)
    source_files = ["sim/modelsim/run_alu_gui.do", "sim/modelsim/run_regfile_gui.do",
                    "sim/modelsim/compile_alu.do", "sim/modelsim/compile_regfile.do",
                    "tools/check_modelsim_switch.py"]
    if arguments.include_cpu:
        source_files.extend(["sim/modelsim/run_cpu_gui.do", "sim/modelsim/run_ops_gui.do",
                             "sim/modelsim/run_memory_gui.do", "sim/modelsim/run_loop_gui.do",
                             "sim/modelsim/run_upper_gui.do",
                             "sim/modelsim/run_subword_gui.do",
                             "sim/modelsim/run_c_gui.do",
                             "sim/modelsim/run_fir_gui.do",
                             "sim/modelsim/compile_cpu.do",
                             "sim/modelsim/cpu_helpers.do"])
    report = {"status": "pass" if passed else "fail", "exit_code": process.returncode,
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "transitions": [item[3] for item in switches],
              "scope": "production GUI loader macros and loaded-design transitions in console mode",
              "gui_rendering": "not_checked_by_this_tool",
              "existing_mapping_warnings": warnings.count(mapping_warning),
              "unexpected_warnings": unexpected_warnings,
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in source_files}}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "transitions": report["transitions"]}, indent=2))
    if not passed:
        print(log[-8000:], file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
