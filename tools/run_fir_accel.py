"""Stage and verify the standalone serial Q15 FIR in ModelSim (no CPU bus yet)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from model.fixed_fir import fir_block, to_memory_word
from model.tiny_cpu import run_program
from tools.software_fir import load_fir, fir_inputs, audit_result
from tools.verify_vectors import verify_vectors

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('rtl/fir/fir_serial.vhd', 'sim/tb/tb_fir_serial.vhd',
           'sim/modelsim/compile_fir_accel.do', 'sim/modelsim/fir_accel_helpers.do',
           'sim/modelsim/run_fir_accel_batch.do', 'sim/modelsim/run_fir_accel_gui.do')


def generate_cases(directory):
    """Reuse unchanged step-one fixtures and execute the seven compiled C inputs."""
    verify_vectors(ROOT / 'vectors')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    original = json.loads((ROOT / 'vectors/manifest.json').read_text(encoding='ascii'))
    records = []

    def add(name, x, h, *, protocol=False, stalls=True, software=False):
        expected = fir_block(x, h)
        case_dir = directory / 'cases' / name
        case_dir.mkdir(parents=True, exist_ok=True)
        payloads = {'input.hex': ''.join(to_memory_word(v)+'\n' for v in x),
                    'coefficients.hex': ''.join(to_memory_word(v)+'\n' for v in h),
                    'expected.hex': ''.join(to_memory_word(v)+'\n' for v in expected.outputs),
                    'accumulators.hex': ''.join(f'{v & ((1<<40)-1):010X}\n' for v in expected.accumulators)}
        for filename, text in payloads.items():
            (case_dir / filename).write_text(text, encoding='ascii', newline='\n')
        record = {'name': name, 'sample_count': len(x), 'protocol': protocol, 'stalls': stalls,
                  'outputs': list(expected.outputs), 'accumulators': list(expected.accumulators),
                  'compiled_c_compared': software,
                  'sha256': {f: hashlib.sha256((case_dir/f).read_bytes()).hexdigest() for f in payloads}}
        records.append(record)
        return record

    def read_words(path):
        return tuple(int(w,16) if int(w,16)<(1<<31) else int(w,16)-(1<<32)
                     for w in path.read_text(encoding='ascii').splitlines())

    for case in original['cases']:
        x = read_words(ROOT / 'vectors' / case['files']['inputs']['path'])
        h = read_words(ROOT / 'vectors' / case['files']['coefficients']['path'])
        add(case['name'], x, h)
        # Exact same bytes, including raw 40-bit sums, as the original audited fixtures.
        for filename, key in [('input.hex','inputs'), ('coefficients.hex','coefficients'),
                              ('expected.hex','outputs'), ('accumulators.hex','accumulators')]:
            if (directory/'cases'/case['name']/filename).read_bytes() != (
                    ROOT/'vectors'/case['files'][key]['path']).read_bytes():
                raise ValueError('step-one fixture drift')
    image, manifest = load_fir()
    demo_x = demo_h = None
    for name, memory in fir_inputs().items():
        initial = struct.pack('<256I', *memory)
        x = struct.unpack_from('<8h', initial, manifest['symbols']['samples'])
        h = struct.unpack_from('<32h', initial, manifest['symbols']['coefficients'])
        result = run_program(image.program_words, initial_memory=memory)
        y, a = audit_result(result, memory, manifest)
        record = add(name, x, h, software=True)
        if record['outputs'] != list(y) or record['accumulators'] != list(a):
            raise ValueError('compiled C and accelerator golden differ')
        if name == 'software_fir': demo_x, demo_h = x, h
    add('last_tap', (32767, -32768, 12345, -1)+(0,)*60, (0,)*31+(16384,))
    add('round_boundaries', (-1,-16383,-16384,-16385,-32767,16383,16384,16385), (1,)+(0,)*31)
    add('protocol', demo_x, demo_h, protocol=True)
    add('sustained', demo_x, demo_h, stalls=False)
    rows = ['set fir_serial_cases {']
    for c in records:
        rows.append('    {%s %d %s %s}' % (c['name'], c['sample_count'],
                    str(c['protocol']).lower(), str(c['stalls']).lower()))
    rows.append('}')
    (directory/'fir_serial_cases.tcl').write_text('\n'.join(rows)+'\n',encoding='ascii',newline='\n')
    data = {'contract': 'fir-serial-stream-v1', 'numeric_contract': 'fir-q15-block-v1',
            'case_count': len(records), 'sample_count': sum(c['sample_count'] for c in records),
            'cases': records}
    (directory/'cases.json').write_text(json.dumps(data, indent=2)+'\n',encoding='ascii',newline='\n')
    return data


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for relative in SOURCES:
        text = (ROOT/relative).read_text(encoding='ascii')
        if relative.endswith('run_fir_accel_gui.do'):
            text = f'set fir_accel_directory {{{directory.as_posix()}}}\n'+text
        (directory/Path(relative).name).write_text(text,encoding='ascii',newline='\n')
    return generate_cases(directory)


def simulate(executable, directory, macro='run_fir_accel_batch.do'):
    result = subprocess.run([str(executable), '-c', '-l', 'modelsim.log', '-wlf', 'fir-serial.wlf',
                             '-do', f'do {macro}'], cwd=directory, capture_output=True,
                            text=True, errors='replace', timeout=120)
    log_path = directory/'modelsim.log'
    log = log_path.read_text(encoding='utf-8',errors='replace') if log_path.exists() else result.stdout+result.stderr
    return result.returncode, log


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modelsim-bin',type=Path,default=Path('E:/quartus/modelsim_ase/win32aloem'))
    parser.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/fir_accel'))
    parser.add_argument('--report-dir',type=Path,default=ROOT/'reports/step12-fir-accelerator')
    parser.add_argument('--baseline-only',action='store_true', help='Development check; never reports full validation.')
    args=parser.parse_args()
    executable=(args.modelsim_bin/'vsim.exe').resolve()
    if not executable.is_file(): parser.error('ModelSim not found')
    build=args.build_dir.resolve()
    if not str(build).isascii() or any(c in str(build) for c in '{}\r\n'):
        parser.error('ASCII build path without braces required')
    reports=args.report_dir; reports.mkdir(parents=True,exist_ok=True)
    def write_report(data):
        (reports/'validation.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    write_report({'status':'incomplete','stage':'baseline'})
    baseline=build/'baseline'
    suite=prepare(baseline)
    code,log=simulate(executable,baseline)
    (reports/'modelsim.log').write_text(log,encoding='utf-8',newline='\n')
    matches=re.findall(r'FIR_CASE_PASS name=(\w+) samples=(\d+)',log)
    expected=[(c['name'],str(c['sample_count'])) for c in suite['cases']]
    if (code!=0 or matches!=expected or 'FIR_SERIAL_SUITE_PASS' not in log or
        log.count('FIR_PROTOCOL_PASS')!=1 or any(s in log for s in ('** Error:', '** Failure:', '** Warning:'))):
        write_report({'status':'fail','stage':'baseline','exit_code':code})
        print(log[-10000:]); return 1
    if args.baseline_only:
        write_report({'status':'incomplete','stage':'baseline_passed','case_count':suite['case_count']})
        print('FIR_BASELINE_PASS cases='+str(suite['case_count'])); return 0
    faults = [
        ('truncate_rounding', 'to_unsigned(16384,41)', 'to_unsigned(0,41)', 'positive_ties'),
        ('negative_arithmetic_shift', 'output_data <= quantize(total);',
         'output_data <= resize(shift_right(total,15),16);', 'round_boundaries'),
        ('positive_saturation_wrap', 'return to_signed(32767,16);',
         'return resize(rounded,16);', 'positive_saturation'),
        ('accumulator_32bit', 'total := accumulator + ((partials(0)+partials(1)) + (partials(2)+partials(3)));',
         'total := resize(resize(accumulator,32) + resize(partials(0),32),40);', 'accumulator_extreme'),
        ('product_zero_extended', 'resize(product,40)',
         'signed(resize(unsigned(product),40))', 'negative_ties'),
        ('omit_last_tap', 'output_acc <= total;\n                            output_data <= quantize(total);',
         'output_acc <= accumulator;\n                            output_data <= quantize(accumulator);', 'last_tap'),
        ('reversed_coefficients', 'coefficients(tap_index+lane)', 'coefficients(31-tap_index-lane)', 'impulse'),
        ('ignore_output_backpressure', "if m_ready = '1' then state <= IDLE; end if;",
         'state <= IDLE;', 'software_fir'),
        ('clear_keeps_old_history', "history <= (others => (others => '0')); -- CLEAR_HISTORY",
         'null; -- CLEAR_HISTORY', 'protocol'),
        ('reset_during_mac_ignored', "if rst = '1' then", "if rst = '1' and state /= MAC then", 'protocol'),
        ('reset_only_h0', "coefficients <= (others => (others => '0'));",
         "coefficients(0) <= (others => '0');", 'protocol'),
        ('busy_modifies_coefficients', 'when MAC =>',
         "when MAC =>\n                        if cfg_valid = '1' then coefficients(to_integer(cfg_addr)) <= cfg_data; end if;", 'software_fir'),
    ]
    mutations=[]
    rtl=(ROOT/'rtl/fir/fir_serial.vhd').read_text(encoding='ascii')
    for name,old,new,case_name in faults:
        if rtl.count(old)!=1: raise ValueError('mutation anchor must be unique: '+name)
        with tempfile.TemporaryDirectory(prefix='fir-mutant-',dir=build) as tmp:
            directory=Path(tmp)
            for relative in SOURCES:
                shutil.copyfile(baseline/Path(relative).name,directory/Path(relative).name)
            shutil.copytree(baseline/'cases'/case_name,directory/'cases'/case_name)
            selected=next(c for c in suite['cases'] if c['name']==case_name)
            row='{%s %d %s %s}' % (case_name,selected['sample_count'],
                    str(selected['protocol']).lower(),str(selected['stalls']).lower())
            (directory/'fir_serial_cases.tcl').write_text('set fir_serial_cases {'+row+'}\n',encoding='ascii')
            (directory/'fir_serial.vhd').write_text(rtl.replace(old,new),encoding='ascii',newline='\n')
            rc,mlog=simulate(executable,directory)
            (reports/(name+'.log')).write_text(mlog,encoding='utf-8',newline='\n')
            assertions=re.findall(r'\*\* Failure: (FIR_[^\r\n]+)',mlog)
            killed=rc!=0 and bool(assertions) and '** Error:' not in mlog
            mutations.append({'name':name,'case':case_name,'exit_code':rc,
                              'killed_by_assertion':killed,'assertions':assertions})
            if not killed:
                write_report({'status':'fail','stage':'negative_controls','controls':mutations})
                print(mlog[-8000:]); return 1
    version=subprocess.run([str(executable),'-version'],capture_output=True,text=True,errors='replace',timeout=15)
    additional=('tools/run_fir_accel.py','model/fixed_fir.py','tools/verify_vectors.py',
                'tools/software_fir.py','model/tiny_cpu.py','tools/c_demo.py','tools/elf32.py',
                'programs/c_fir_q15/manifest.json','programs/c_fir_q15/program.elf',
                'programs/c_fir_q15/program.hex','programs/c_fir_q15/initial_memory.txt',
                'vectors/manifest.json','docs/fir-accelerator-contract.md',
                'tests/test_fir_accel_vectors.py')
    details=re.findall(r'FIR_SERIAL_PASS samples=(\d+) stalls=(\d+) protocol_outputs=(\d+)',log)
    if len(details)!=len(suite['cases']): raise ValueError('missing TB result counters')
    report={'status':'pass','contract':suite['contract'],'numeric_contract':suite['numeric_contract'],
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'simulator':(version.stdout+version.stderr).strip(),'language':'VHDL-93',
            'scope':'standalone serial MAC core functional simulation; CPU/MMIO/RAM not connected',
            'case_count':suite['case_count'],'checked_stream_samples':suite['sample_count'],
            'checked_protocol_outputs':sum(int(d[2]) for d in details),
            'output_stall_cycles':sum(int(d[1]) for d in details),
            'mac_edges_per_sample':32,'minimum_input_spacing_edges':34,
            'compiled_c_comparison_cases':7,'cases':suite['cases'],
            'baseline_exit_code':code,'negative_controls':mutations,
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (*SOURCES,*additional)},
            'gui_script':(baseline/'run_fir_accel_gui.do').as_posix(),
            'synthesis':'not_run','timing':'not_run','hardware_programming':'not_run',
            'system_speedup':'not_measured'}
    write_report(report)
    print(json.dumps({k:report[k] for k in ('status','case_count','checked_stream_samples',
                    'checked_protocol_outputs','output_stall_cycles','compiled_c_comparison_cases','gui_script')},indent=2))
    print('FIR_MUTATIONS_KILLED='+str(len(mutations)))
    return 0


if __name__=='__main__': raise SystemExit(main())
