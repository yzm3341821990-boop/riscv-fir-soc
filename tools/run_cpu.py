"""Run the RV32I ALU, memory and control-flow subset in ModelSim."""

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

from tools.generate_cpu_vectors import generate_cpu_vectors

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("rtl/cpu/alu_pkg.vhd", "rtl/cpu/alu32.vhd", "rtl/cpu/regfile32.vhd", "rtl/cpu/mul32.vhd",
           "rtl/cpu/imm_i.vhd", "rtl/cpu/imm_s.vhd", "rtl/cpu/imm_b.vhd", "rtl/cpu/imm_j.vhd",
           "rtl/cpu/imm_u.vhd",
           "rtl/cpu/decode_tiny.vhd",
           "rtl/cpu/tiny_cpu.vhd", "rtl/cpu/data_ram.vhd", "sim/tb/tb_tiny_cpu.vhd",
           "sim/modelsim/compile_cpu.do", "sim/modelsim/cpu_helpers.do",
           "sim/modelsim/run_cpu_batch.do", "sim/modelsim/run_cpu_gui.do",
           "sim/modelsim/run_ops_gui.do", "sim/modelsim/run_memory_gui.do", "sim/modelsim/run_loop_gui.do",
           "sim/modelsim/run_upper_gui.do", "sim/modelsim/run_subword_gui.do", "sim/modelsim/run_c_gui.do", "sim/modelsim/run_fir_gui.do")


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for relative in SOURCES:
        shutil.copyfile(ROOT / relative, directory / Path(relative).name)
    for macro in ("run_cpu_gui.do", "run_ops_gui.do", "run_memory_gui.do", "run_loop_gui.do", "run_upper_gui.do", "run_subword_gui.do", "run_c_gui.do", "run_fir_gui.do"):
        template = (ROOT / "sim/modelsim" / macro).read_text(encoding="ascii")
        (directory / macro).write_text(f"set cpu_directory {{{directory.as_posix()}}}\n" + template,
                                      encoding="ascii", newline="\n")
    firmware=json.loads((ROOT/'programs/c_fir_q15/manifest.json').read_text(encoding='utf-8'))
    config=(f"set fir_outputs_word {firmware['symbols']['outputs']//4}\n"
            f"set fir_done_word {firmware['symbols']['done']//4}\n"
            f"set fir_finish_ns {firmware['simulation_finish_ns']}\n"
            f"set fir_expected_outputs {{{' '.join(map(str,firmware['expected_outputs']))}}}\n"
            f"set fir_retired_count {firmware['dynamic_commits']}\n"
            f"set fir_multiply_count {firmware['multiply_commits']}\n")
    (directory/'fir_gui_config.tcl').write_text(config,encoding='ascii',newline='\n')
    return generate_cpu_vectors(directory)


def simulate(executable, directory):
    process = subprocess.run([str(executable), "-c", "-l", "modelsim.log", "-wlf", "tiny_cpu.wlf",
                              "-do", "do run_cpu_batch.do"], cwd=directory, capture_output=True,
                             text=True, errors="replace", timeout=180)
    path = directory / "modelsim.log"
    log = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    return process.returncode, log or process.stdout + process.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports/step11-software-fir")
    arguments = parser.parse_args()
    found = shutil.which("vsim")
    executable = (arguments.modelsim_bin / "vsim.exe" if arguments.modelsim_bin else
                  Path(found) if found else Path("E:/quartus/modelsim_ase/win32aloem/vsim.exe")).resolve()
    if not executable.is_file():
        parser.error("ModelSim not found; pass --modelsim-bin")
    key = hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:8]
    build = (arguments.build_dir or Path(tempfile.gettempdir()) / f"riscv-fir-tiny-cpu-{key}").resolve()
    if not str(build).isascii() or any(c in str(build) for c in "{}\r\n"):
        parser.error("Use an ASCII-only --build-dir without braces")
    reports = arguments.report_dir
    reports.mkdir(parents=True, exist_ok=True)

    def save_status(status, stage):
        (reports / "validation.json").write_text(json.dumps({"status": status, "stage": stage,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "37 RV32I instructions plus MUL and compiled Q15 software FIR RTL functional simulation"}, indent=2) + "\n", encoding="utf-8")

    save_status("incomplete", "baseline")
    baseline = build / "baseline"
    cases = prepare(baseline)
    code, log = simulate(executable, baseline)
    (reports / "modelsim.log").write_text(log, encoding="utf-8", newline="\n")
    passed_names = re.findall(r"TINYCPU_CASE_PASS name=(\w+) retired=(\d+)", log)
    expected = [(case["name"], str(case["retired_count"])) for case in cases["cases"]]
    checked_commits = log.count("TINYCPU_COMMIT pc=")
    warmup_commits = 2 * sum(case["inject_reset"] for case in cases["cases"])
    memory_passed = re.findall(r"TINYCPU_MEMORY_PASS requests=(\d+) warmup_requests=(\d+)", log)
    expected_memory = [(str(case["memory_count"]), "2" if case["reset_during_load"] else "0")
                       for case in cases["cases"]]
    memory_requests = sum(case["memory_count"] for case in cases["cases"])
    warmup_memory_requests = 2 * sum(case["reset_during_load"] for case in cases["cases"])
    if (code != 0 or passed_names != expected or
            checked_commits != cases["instruction_count"] + warmup_commits or
            memory_passed != expected_memory or
            re.findall(r"TINYCPU_MULTIPLY_PASS operations=(\d+)",log) !=
                [str(case['multiply_count']) for case in cases['cases']] or
            log.count("TINYCPU_MEMORY_REQUEST mode=") != memory_requests + warmup_memory_requests or
            log.count("TINYCPU_RESET_PRESERVES_MEMORY_PASS") != cases["case_count"] or
            log.count("TINYCPU_MEMORY_STATE_PASS words=256") != 2 * cases["case_count"] or
            log.count("TINYCPU_INITIAL_MEMORY_PASS words=256") !=
                sum(bool(case.get("initial_memory_file")) for case in cases["cases"]) or
            f"TINYCPU_SUITE_PASS cases={cases['case_count']}" not in log or
            "** Error:" in log or "** Failure:" in log or "** Warning:" in log):
        save_status("fail", "baseline")
        print(log[-16000:], file=sys.stderr)
        return 1
    faults = [
        ("pc_step_eight", "rtl/cpu/tiny_cpu.vhd",
         "sequential_pc <= std_logic_vector(unsigned(pc_reg) + 4);",
         "sequential_pc <= std_logic_vector(unsigned(pc_reg) + 8);", "demo"),
        ("addi_zero_extension", "rtl/cpu/imm_i.vhd",
         "resize(signed(instruction(31 downto 20)), 32)",
         "resize(unsigned(instruction(31 downto 20)), 32)", "alu_demo"),
        ("srai_as_srli", "rtl/cpu/decode_tiny.vhd",
         "chosen_op := ALU_SRA; -- SRAI", "chosen_op := ALU_SRL; -- SRAI", "shift_immediate"),
        ("store_uses_immediate", "rtl/cpu/tiny_cpu.vhd",
         "dmem_wdata <= store_data;", "dmem_wdata <= immediate;", "memory_demo"),
        ("load_returns_address", "rtl/cpu/tiny_cpu.vhd",
         "load_value when state = LOAD_WRITEBACK", "alu_value when state = LOAD_WRITEBACK", "memory_demo"),
        ("store_zero_extension", "rtl/cpu/imm_s.vhd",
         "resize(signed(offset_bits), 32)", "resize(unsigned(offset_bits), 32)", "memory_negative_offset"),
        ("reset_during_load_ignored", "rtl/cpu/tiny_cpu.vhd",
         "if rst = '1' then", "if rst = '1' and state /= LOAD_WRITEBACK then", "reset_pending_load"),
        ("branch_falls_through", "rtl/cpu/tiny_cpu.vhd",
         "if take_branch then", "if false then", "loop_demo"),
        ("jal_link_uses_target", "rtl/cpu/tiny_cpu.vhd",
         "sequential_pc when jump_instruction = '1' else alu_value;",
         "next_pc when jump_instruction = '1' else alu_value;", "jal_link_skip_illegal"),
        ("jalr_keeps_bit_zero", "rtl/cpu/tiny_cpu.vhd",
         "target(0) := '0';", "null;", "jalr_clear_bit_zero"),
        ("invalid_jump_writes_link", "rtl/cpu/tiny_cpu.vhd",
         "and control_target_valid = '1' and", "and", "jal_halfword_fault"),
        ("blt_compares_unsigned", "rtl/cpu/tiny_cpu.vhd",
         'when "100" => take_branch := signed(rs1_data) < signed(rs2_data);',
         'when "100" => take_branch := unsigned(rs1_data) < unsigned(rs2_data);', "branch_blt_taken"),
        ("lui_missing_shift", "rtl/cpu/imm_u.vhd",
         'instruction(31 downto 12) & x"000"', 'x"000" & instruction(31 downto 12)', "upper_demo"),
        ("auipc_uses_pc_plus_four", "rtl/cpu/tiny_cpu.vhd",
         "alu_a <= pc_reg when upper_pc_relative = '1' else rs1_data;",
         "alu_a <= sequential_pc when upper_pc_relative = '1' else rs1_data;", "auipc_nonzero_pc"),
        ("lui_reads_immediate_as_rs1", "rtl/cpu/decode_tiny.vhd",
         'and instruction(6 downto 0) /= "0110111"', '', "lui_dirty_pseudo_rs1"),
        ("lb_zero_extends", "rtl/cpu/tiny_cpu.vhd",
         'when "000" => load_value <= std_logic_vector(resize(signed(shifted(7 downto 0)), 32));',
         'when "000" => load_value <= std_logic_vector(resize(shifted(7 downto 0), 32));', "subword_demo"),
        ("lh_zero_extends", "rtl/cpu/tiny_cpu.vhd",
         'when "001" => load_value <= std_logic_vector(resize(signed(shifted(15 downto 0)), 32));',
         'when "001" => load_value <= std_logic_vector(resize(shifted(15 downto 0), 32));', "subword_demo"),
        ("ram_ignores_byte_enable", "rtl/cpu/data_ram.vhd",
         "if byte_enable(lane) = '1' then", "if true then", "subword_demo"),
        ("load_ignores_lane", "rtl/cpu/tiny_cpu.vhd",
         "shift_right(unsigned(dmem_rdata), 8*to_integer(unsigned(alu_value(1 downto 0))))",
         "shift_right(unsigned(dmem_rdata), 0)", "subword_demo"),
        ("halfword_requires_word_alignment", "rtl/cpu/tiny_cpu.vhd",
         'instruction_reg(13 downto 12) = "01" and alu_value(0) = \'0\'',
         'instruction_reg(13 downto 12) = "01" and alu_value(1 downto 0) = "00"', "subword_demo"),
        ("store_reverses_byte_lane", "rtl/cpu/tiny_cpu.vhd",
         "lane := to_integer(unsigned(alu_value(1 downto 0)));",
         "lane := 3 - to_integer(unsigned(alu_value(1 downto 0)));", "subword_demo"),
        ("c_initializer_corrupted", "programs/c_array_sum/initial_memory.txt",
         "FFFD000C", "00000000", "c_array_sum"),
        ("c_stack_not_initialized", "programs/c_array_sum/program.hex",
         "40010113", "00010113", "c_array_sum"),
        ("mul_returns_sum", "rtl/cpu/mul32.vhd",
         "result <= std_logic_vector(product(31 downto 0));",
         "result <= std_logic_vector(unsigned(a) + unsigned(b));", "multiply_edges"),
        ("mul_uses_upper_half", "rtl/cpu/mul32.vhd",
         "product(31 downto 0)", "product(63 downto 32)", "multiply_edges"),
        ("mul_truncates_operands", "rtl/cpu/mul32.vhd",
         "unsigned(a) * unsigned(b)", "resize(unsigned(a(15 downto 0)) * unsigned(b(15 downto 0)), 64)", "multiply_edges"),
    ]
    mutations = []
    for name, relative, anchor, replacement, case_name in faults:
        source = (ROOT / relative).read_text(encoding="utf-8")
        if source.count(anchor) != 1:
            save_status("fail", "mutation_setup")
            print(f"Mutation anchor missing or ambiguous: {name}", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory(prefix="mutant-", dir=build) as temporary:
            mutant = Path(temporary).resolve()
            if not mutant.is_relative_to(build):
                raise RuntimeError("unexpected mutation-directory location")
            mutant_cases = prepare(mutant)
            if not any(case["name"] == case_name for case in mutant_cases["cases"]):
                raise RuntimeError(f"Unknown mutation test case: {case_name}")
            # Each negative control runs one named baseline case. The clean
            # implementation above still runs the entire regression suite.
            with (mutant / "cpu_cases.tcl").open("a", encoding="ascii", newline="\n") as case_file:
                case_file.write('\nset selected_cases {}\nforeach candidate $tiny_cpu_cases {\n'
                                f'    if {{[lindex $candidate 0] eq "{case_name}"}} {{lappend selected_cases $candidate}}\n'
                                '}\nif {[llength $selected_cases] != 1} {error "mutation case missing"}\n'
                                'set tiny_cpu_cases $selected_cases\n')
            target = (mutant / "cases/c_array_sum" / Path(relative).name
                      if relative.startswith("programs/c_array_sum/") else mutant / Path(relative).name)
            target.write_text(source.replace(anchor, replacement, 1), encoding="ascii", newline="\n")
            if name == "c_stack_not_initialized":
                # Keep the trace's instruction identity consistent with the
                # intentionally changed program. Its required SP value stays
                # 1024, so rejection must come from the execution comparison.
                trace = mutant / "cases/c_array_sum/expected_trace.txt"
                expected = trace.read_text(encoding="ascii")
                old_field, new_field = f" {anchor} ", f" {replacement} "
                if expected.count(old_field) != 1:
                    raise RuntimeError("ambiguous stack-setup trace instruction")
                trace.write_text(expected.replace(old_field, new_field, 1), encoding="ascii", newline="\n")
            mutant_code, mutant_log = simulate(executable, mutant)
        (reports / f"mutation-{name}.log").write_text(mutant_log, encoding="utf-8", newline="\n")
        detected = [marker for marker in ("TINYCPU_MISMATCH", "TINYCPU_REGISTER_MISMATCH",
                                          "TINYCPU_MEMORY_MISMATCH") if marker in mutant_log]
        killed = (mutant_code != 0 and bool(detected)
                  and "TINYCPU_SUITE_PASS" not in mutant_log)
        mutations.append({"name": name, "case": case_name, "killed": killed,
                          "exit_code": mutant_code, "detected_assertions": detected,
                          "category": "firmware_initialization" if name.startswith("c_") else "rtl"})
        if not killed:
            save_status("fail", "negative_control")
            print(f"Controlled fault not rejected by an execution assertion: {name}", file=sys.stderr)
            return 1
    version = subprocess.run([str(executable), "-version"], capture_output=True,
                             text=True, errors="replace", timeout=15)
    source_files = (*SOURCES, "model/tiny_cpu.py", "tools/generate_cpu_vectors.py", "tools/run_cpu.py",
                    "tests/test_tiny_cpu_model.py", "tests/test_subword_cpu.py",
                    "tests/test_elf32.py", "tests/test_c_demo.py", "tools/elf32.py", "tools/c_demo.py",
                    "tools/build_c_demo.py", "firmware/c_array_sum/main.c", "firmware/c_array_sum/start.S",
                    "firmware/c_array_sum/link.ld", "programs/c_array_sum/program.elf",
                    "programs/c_array_sum/program.hex", "programs/c_array_sum/initial_memory.txt",
                    "programs/c_array_sum/main.s", "programs/c_array_sum/manifest.json",
                    "firmware/c_fir_q15/main.c", "tools/build_fir_demo.py", "tools/software_fir.py",
                    "tests/test_mul_cpu.py", "tests/test_software_fir.py", "model/fixed_fir.py",
                    "programs/c_fir_q15/program.elf", "programs/c_fir_q15/program.hex",
                    "programs/c_fir_q15/main.s", "programs/c_fir_q15/initial_memory.txt",
                    "programs/c_fir_q15/manifest.json")
    report = {"status": "pass", "contract": cases["contract"],
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "simulator": (version.stdout + version.stderr).strip(), "language": "VHDL-93",
              "case_count": cases["case_count"], "program_commits": cases["instruction_count"],
              "supported_instructions": cases["supported_instructions"],
              "warmup_commits": warmup_commits, "checked_commits": checked_commits,
              "memory_requests": memory_requests, "warmup_memory_requests": warmup_memory_requests,
              "checked_memory_requests": memory_requests + warmup_memory_requests,
              "initial_memory_loader_writes": sum(case.get("loader_words", 0) for case in cases["cases"]),
              "c_firmware": json.loads((ROOT / "programs/c_array_sum/manifest.json").read_text(encoding="utf-8")),
              "fir_firmware": json.loads((ROOT / "programs/c_fir_q15/manifest.json").read_text(encoding="utf-8")),
              "multiply_commits": sum(case['multiply_count'] for case in cases['cases']),
              "software_fir_cases": [{"name":case['name'],**case['fir_reference']} for case in cases['cases'] if 'fir_reference' in case],
              "reset_preserves_memory_checks": log.count("TINYCPU_RESET_PRESERVES_MEMORY_PASS"),
              "final_and_postreset_ram_word_checks": 2 * cases["case_count"] * 256,
              "fault_reset_checks": log.count("TINYCPU_FAULT_RESET_PASS"),
              "cases": [{"name": name, "commits": int(count)} for name, count in passed_names],
              "baseline_exit_code": code, "negative_controls": mutations,
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in source_files},
              "gui_script": (baseline / "run_cpu_gui.do").as_posix(),
              "ops_gui_script": (baseline / "run_ops_gui.do").as_posix(),
              "memory_gui_script": (baseline / "run_memory_gui.do").as_posix(),
              "loop_gui_script": (baseline / "run_loop_gui.do").as_posix(),
              "upper_gui_script": (baseline / "run_upper_gui.do").as_posix(),
              "subword_gui_script": (baseline / "run_subword_gui.do").as_posix(),
              "c_gui_script": (baseline / "run_c_gui.do").as_posix(),
              "fir_gui_script": (baseline / "run_fir_gui.do").as_posix(),
              "scope": "38 instructions (37 RV32I plus MUL), compiled C Q15 FIR, and 1 KiB synchronous RAM",
              "synthesis": "not_run", "timing": "not_run", "hardware_programming": "not_run"}
    (reports / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                            encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("status", "case_count", "program_commits",
                     "checked_memory_requests", "fault_reset_checks", "negative_controls", "fir_gui_script")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
