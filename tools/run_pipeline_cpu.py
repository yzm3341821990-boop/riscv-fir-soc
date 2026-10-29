"""Prepare/run the independent five-stage, fixed-latency-memory CPU regression."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from model.tiny_cpu import (encode_addi as a, encode_add as add, encode_op,
                            encode_lw as lw, encode_sw as sw, encode_branch as b,
                            encode_jal as j, encode_jalr as jr, run_program)
from tools.generate_cpu_vectors import generate_cpu_vectors

ROOT = Path(__file__).resolve().parents[1]
RTL = ('alu_pkg', 'alu32', 'regfile32', 'mul32', 'imm_i', 'imm_s', 'imm_b',
       'imm_j', 'imm_u', 'decode_tiny', 'data_ram', 'pipeline_cpu')


def directed_programs():
    """Hazard cases have independently specified timing, in addition to ISA traces."""
    nop = a(0, 0, 0)
    return [
        ('pipe_throughput', [a(i, 0, i) for i in range(1, 21)], 24, 0),
        ('pipe_mem_forward', [a(1, 0, 7), add(2, 1, 1), add(3, 2, 1)], 7, 0),
        ('pipe_wb_forward', [a(1, 0, 7), nop, add(2, 1, 1)], 7, 0),
        ('pipe_wb_id', [a(1, 0, 7), nop, nop, add(2, 1, 1)], 8, 0),
        ('pipe_forward_priority', [a(1, 0, 2), a(1, 1, 3), add(2, 1, 1)], 7, 0),
        ('pipe_load_use', [a(1, 0, 7), sw(1, 0, 0), lw(2, 0, 0), add(3, 2, 2)], 9, 1),
        ('pipe_load_store_data', [lw(1, 0, 0), sw(1, 0, 4), lw(2, 0, 4)], 8, 1),
        ('pipe_load_store_base', [lw(1, 0, 0), sw(0, 1, 0)], 7, 1),
        ('pipe_load_branch', [lw(1, 0, 0), b('BEQ', 1, 0, 12), sw(0, 0, 4),
                              0xFFFFFFFF, a(2, 0, 9)], 10, 1),
        ('pipe_alu_branch', [a(1, 0, 7), b('BNE', 1, 0, 12), sw(0, 0, 4),
                             0xFFFFFFFF, a(2, 0, 9)], 9, 0),
        ('pipe_jal_wrong_path', [j(1, 12), sw(0, 0, 0), 0xFFFFFFFF, add(2, 1, 1)], 8, 0),
        ('pipe_jalr_forward', [a(1, 0, 16), jr(1, 1, 0), sw(0, 0, 4),
                               0xFFFFFFFF, add(2, 1, 1)], 9, 0),
        ('pipe_load_jalr', [a(1, 0, 24), sw(1, 0, 0), lw(2, 0, 0), jr(3, 2, 0),
                            sw(0, 0, 0), 0xFFFFFFFF, add(4, 3, 3)], 12, 1),
        ('pipe_no_false_immediate_hazard', [lw(1, 0, 0), a(2, 0, 1)], 6, 0),
        ('pipe_no_x0_hazard', [lw(0, 0, 0), add(1, 0, 0)], 6, 0),
        ('pipe_mul_forward', [a(1, 0, -7), a(2, 0, 9), encode_op('MUL', 3, 1, 2),
                              sw(3, 0, 0), lw(4, 0, 0)], 9, 0),
        ('pipe_fault_drain', [a(1, 0, 7), sw(1, 0, 0), 0xFFFFFFFF, sw(0, 0, 0)], 0, 0),
        ('pipe_load_fault_drain', [a(1, 0, 9), sw(1, 0, 0), lw(2, 0, 0),
                                   sw(0, 0, 2), sw(0, 0, 0)], 0, 0),
    ]


def write_case(directory, name, program, cycles=0, stalls=-1):
    result = run_program(program)
    case_dir = directory / 'cases' / name
    case_dir.mkdir(parents=True, exist_ok=True)
    files = {
        'program.hex': ''.join(f'{w:08X}\n' for w in program),
        'expected_trace.txt': ''.join(f'{t.pc:08X} {t.instruction:08X} {t.rd} {t.value:08X} {t.next_pc:08X}\n' for t in result.trace),
        'expected_memory_trace.txt': ''.join(f'{t.mode} {t.address:08X} {t.value:08X} {t.byte_enable:X}\n' for t in result.memory_trace),
        'expected_registers.txt': ''.join(f'{w:08X}\n' for w in result.registers[1:]),
        'expected_memory.txt': ''.join(f'{w:08X}\n' for w in result.memory),
    }
    for filename, data in files.items():
        (case_dir / filename).write_text(data, encoding='ascii')
    return dict(name=name, retired_count=len(result.trace), expect_fault=result.fault,
                fault_pc=result.fault_pc, memory_count=len(result.memory_trace),
                expected_cycles=cycles, expected_stalls=stalls)


def prepare(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    legacy = generate_cpu_vectors(directory)
    cases = legacy['cases'] + [write_case(directory, *p) for p in directed_programs()]
    boundary = write_case(directory, 'pipe_sequential_rom_fault',
                          [j(0,1020)]+[a(0,0,0)]*254+[a(1,0,7)])
    boundary.update(expect_fault=True,fault_pc=1024)
    cases.append(boundary)
    # Restart during IF/ID/EX/MEM/WB and pending read; prefix stores are idempotent.
    for cycle in range(1, 10):
        case = write_case(directory, f'pipe_reset_{cycle}',
                          [a(1,0,7), sw(1,0,0), lw(2,0,0), add(3,2,2), a(4,0,11)])
        case['reset_at_cycle'] = cycle
        cases.append(case)
    for name in RTL:
        shutil.copyfile(ROOT / f'rtl/cpu/{name}.vhd', directory / f'{name}.vhd')
    shutil.copyfile(ROOT/'sim/tb/tb_pipeline_cpu.vhd', directory/'tb_pipeline_cpu.vhd')
    shutil.copyfile(ROOT/'sim/modelsim/pipeline_helpers.do', directory/'pipeline_helpers.do')
    lines = []
    for case in cases:
        name = case['name']
        prefix = f'cases/{name}'
        options = [f'-gPROGRAM_FILE={prefix}/program.hex', f'-gTRACE_FILE={prefix}/expected_trace.txt',
                   f'-gMEMORY_TRACE_FILE={prefix}/expected_memory_trace.txt',
                   f'-gEXPECTED_COUNT={case["retired_count"]}',
                   f'-gEXPECT_FAULT={str(case["expect_fault"]).lower()}', f'-gFAULT_PC={case["fault_pc"]}',
                   f'-gEXPECT_CYCLES={case.get("expected_cycles",0)}',
                   f'-gEXPECT_STALLS={case.get("expected_stalls",-1)}',
                   f'-gRESET_AT_CYCLE={case.get("reset_at_cycle",0)}']
        if case.get('initial_memory_file'):
            options.append(f'-gINITIAL_MEMORY_FILE={case["initial_memory_file"]}')
        lines.append(f'run_pipeline_case {name} {{{" ".join(options)}}}\n')
    (directory/'pipeline_cases.do').write_text(''.join(lines), encoding='ascii')
    (directory/'run_pipeline_batch.do').write_text(
        'onerror {quit -code 1 -f}\nonbreak {quit -code 1 -f}\n'
        'if {![file exists modelsim.ini]} {vmap -c}\n'
        'if {![file isdirectory work]} {vlib work}\nvmap work work\n'
        f'vcom -93 {" ".join(n+".vhd" for n in RTL)} tb_pipeline_cpu.vhd\n'
        'do pipeline_helpers.do\ndo pipeline_cases.do\necho PIPE_SUITE_PASS\nquit -code 0 -f\n', encoding='ascii')
    (directory/'pipeline_cases.json').write_text(json.dumps(cases, indent=2)+'\n', encoding='utf-8')
    return cases


def simulate(executable, directory):
    process = subprocess.run([str(executable), '-c', '-l', 'modelsim.log',
                              '-do', 'do run_pipeline_batch.do'], cwd=directory,
                             capture_output=True, text=True, errors='replace', timeout=600)
    path = directory/'modelsim.log'
    log = path.read_text(encoding='utf-8', errors='replace') if path.exists() else process.stdout+process.stderr
    (directory/'process-output.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
    if process.returncode and process.stdout not in log:
        log += '\nPROCESS OUTPUT:\n'+process.stdout+process.stderr
    return process.returncode, log


def negative_controls(executable, build, reports):
    source = (ROOT/'rtl/cpu/pipeline_cpu.vhd').read_text(encoding='ascii')
    faults = [
        ('missing_mem_forward', 'pipe_mem_forward',
         'if mem.valid = \'1\' and mem.load = \'0\' and mem.rd /= "00000" then', 'if false then'),
        ('missing_wb_forward', 'pipe_wb_forward',
         'if wb.valid = \'1\' and wb.rd /= "00000" then', 'if false then'),
        ('old_producer_wins', 'pipe_forward_priority',
         'if mem.valid = \'1\' and mem.load = \'0\' and mem.rd /= "00000" then',
         'if mem.valid = \'1\' and mem.load = \'0\' and mem.rd /= "00000" and mem.rd /= wb.rd then'),
        ('missing_wb_id_bypass', 'pipe_wb_id',
         "capture_first <= wb_value when rf_we = '1' and wb.rd = id_rs1 else id_first;",
         'capture_first <= id_first;'),
        ('missing_load_use_stall', 'pipe_load_use',
         "elsif hazard = '1' then", 'elsif false then'),
        ('wrong_path_survives', 'pipe_jal_wrong_path',
         "fetch_pc <= target; id_valid <= '0'; ex <= EMPTY_EX;",
         "fetch_pc <= target; id_valid <= '0'; ex.valid <= id_valid; ex.pc <= id_pc; ex.instruction <= imem_rdata;"),
        ('fault_drops_older_instruction', 'pipe_fault_drain',
         "stopped <= '1'; fault_address <= ex.pc; ex <= EMPTY_EX; id_valid <= '0';",
         "stopped <= '1'; fault_address <= ex.pc; ex <= EMPTY_EX; id_valid <= '0'; wb <= EMPTY_LATER;"),
        ('wrong_store_data', 'pipe_mul_forward',
         'mem.store_data <= second;', 'mem.store_data <= ex.second;'),
        ('reset_keeps_pending_load', 'pipe_reset_6',
         "if rst = '1' then", "if rst = '1' and wb.load /= '1' then"),
        ('false_immediate_dependency', 'pipe_no_false_immediate_hazard',
         '(ex_rd = id_rs1 or ex_rd = id_rs2)', '(ex_rd = id_rs1 or ex_rd = imem_rdata(24 downto 20))'),
    ]
    rows = (build/'pipeline_cases.do').read_text(encoding='ascii').splitlines()
    controls = []
    for name, case, anchor, replacement in faults:
        if source.count(anchor) != 1:
            raise RuntimeError(f'Ambiguous mutation anchor: {name}')
        directory = build/'mutations'/name
        directory.mkdir(parents=True, exist_ok=True)
        for path in build.glob('*.vhd'):
            shutil.copyfile(path, directory/path.name)
        for filename in ('run_pipeline_batch.do','pipeline_helpers.do'):
            shutil.copyfile(build/filename,directory/filename)
        shutil.copytree(build/'cases'/case, directory/'cases'/case, dirs_exist_ok=True)
        selected = [line for line in rows if line.startswith(f'run_pipeline_case {case} ')]
        if len(selected) != 1: raise RuntimeError(f'Missing mutation case {case}')
        (directory/'pipeline_cases.do').write_text(selected[0]+'\n',encoding='ascii')
        (directory/'pipeline_cpu.vhd').write_text(source.replace(anchor,replacement,1),encoding='ascii')
        code, log = simulate(executable,directory)
        (reports/f'mutation-{name}.log').write_text(log,encoding='utf-8')
        failures = re.findall(r'\*\* Failure: (PIPE_\w+)',log)
        killed = code != 0 and bool(failures) and '** Error:' not in log
        controls.append(dict(name=name,case=case,exit_code=code,killed=killed,assertions=failures))
        if not killed: break
    return controls, len(faults)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modelsim-bin', type=Path, default=Path('E:/quartus/modelsim_ase/win32aloem'))
    parser.add_argument('--build-dir', type=Path, default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/pipeline_cpu'))
    parser.add_argument('--report-dir', type=Path, default=ROOT/'reports/step17-pipeline')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--case', help='Run one named case for diagnosis (no mutation campaign)')
    args = parser.parse_args()
    build = args.build_dir.resolve()
    if not str(build).isascii() or any(c in str(build) for c in '{}\r\n'):
        parser.error('Use an ASCII build directory without braces/newlines')
    cases = prepare(build)
    if args.case:
        cases = [c for c in cases if c['name'] == args.case]
        if not cases: parser.error('Unknown --case')
        rows = (build/'pipeline_cases.do').read_text(encoding='ascii').splitlines()
        (build/'pipeline_cases.do').write_text(''.join(line+'\n' for line in rows if
            line.startswith(f'run_pipeline_case {args.case} ')),encoding='ascii')
    if args.prepare_only:
        print(f'Prepared {len(cases)} cases in {build}')
        return 0
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.report_dir/'validation.json'
    report = dict(status='incomplete', contract='pipeline-fixed-memory-v1',
                  generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  synthesis='not_run', timing='not_run', hardware='not_run')
    report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    code, log = simulate(args.modelsim_bin/'vsim.exe', build)
    (args.report_dir/'modelsim.log').write_text(log,encoding='utf-8')
    passed = re.findall(r'PIPE_CASE_PASS name=(\w+)', log)
    ok = code == 0 and passed == [c['name'] for c in cases] and 'PIPE_SUITE_PASS' in log
    ok = ok and not any(s in log for s in ('** Error:', '** Failure:', '** Warning:'))
    measurements = re.findall(r'PIPE_PASS retired=(\d+) cycles=(\d+) requests=(\d+) stalls=(\d+) flushes=(\d+)',log)
    ok = ok and len(measurements) == len(cases)
    report.update(status='pass' if ok else 'fail', baseline_exit_code=code,
                  case_count=len(cases), legacy_cases=sum(not c['name'].startswith('pipe_') for c in cases),
                  measurements=[dict(name=c['name'], **dict(zip(
                      ('retired','cycles','requests','stalls','flushes'),map(int,m))))
                                for c,m in zip(cases,measurements)],
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                    [f'rtl/cpu/{n}.vhd' for n in RTL]+['sim/tb/tb_pipeline_cpu.vhd',
                    'sim/modelsim/pipeline_helpers.do','tools/run_pipeline_cpu.py',
                    'tools/generate_cpu_vectors.py','model/tiny_cpu.py','docs/pipeline-cpu-contract.md']})
    if ok and not args.case:
        controls, total = negative_controls(args.modelsim_bin/'vsim.exe',build,args.report_dir)
        report['negative_controls'] = controls
        ok = len(controls) == total and all(c['killed'] for c in controls)
        report['status'] = 'pass' if ok else 'fail'
        version = subprocess.run([str(args.modelsim_bin/'vsim.exe'),'-version'],capture_output=True,
                                 text=True,errors='replace',timeout=15)
        report['simulator'] = (version.stdout+version.stderr).strip()
        report['language'] = 'VHDL-93'
        report['program_commits'] = sum(c['retired_count'] for c in cases)
        report['memory_requests'] = sum(c['memory_count'] for c in cases)
        report['reset_in_flight_cases'] = 9
        report['postreset_memory_word_checks'] = 256*len(cases)
        report['legacy_reset_flags_reused'] = False
        report['vector_sha256'] = {p.relative_to(build).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((build/'cases').rglob('*')) if p.is_file()}
    report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'Pipeline: {report["status"]}; {len(passed)}/{len(cases)} cases; {report_path}')
    if not ok: print(log[-5000:])
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
