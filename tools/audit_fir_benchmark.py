"""Validate matched FIR call timing against accepted CPU and DMA events.

This checker measures the interval between two accepted stores to a reserved
RAM word. It does not treat the accelerator's internal cycle counter as the
whole software call, and it rejects timing regions that omit required work.
"""
from dataclasses import dataclass
import re

from model.fixed_fir import fir_block
from model.tiny_cpu import run_program
from tools.audit_soc_trace import audit as audit_hardware_trace

BASE = 0x40003000
SAMPLES = 8
TAPS = 32
MASK = (1 << 32) - 1
MODES = ('software', 'hardware_cold', 'hardware_resident')
_BUS = re.compile(
    r'SOC_BUS mode=([RW]) addr=([0-9A-Fa-f]{8}) data=([0-9A-Fa-f]{8}) '
    r'be=([0-9A-Fa-f]{8}) cycle=(\d+)')
_DMA = re.compile(
    r'SOC_DMA mode=([RW]) addr=([0-9A-Fa-f]{8}) data=([0-9A-Fa-f]{8}) cycle=(\d+)')
_COMMIT = re.compile(
    r'SOC_COMMIT pc=([0-9A-Fa-f]{8}) insn=([0-9A-Fa-f]{8}) rd=(\d+) '
    r'value=([0-9A-Fa-f]{8}) next=([0-9A-Fa-f]{8})')


@dataclass(frozen=True)
class Event:
    line: int
    kind: str
    mode: str
    address: int
    data: int
    byte_enable: int
    cycle: int


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _signed(value):
    return value - (1 << 32) if value & (1 << 31) else value


def _events(log):
    events = []
    for number, line in enumerate(log.splitlines()):
        if 'SOC_BUS ' in line:
            match = _BUS.search(line)
            _need(match is not None, 'malformed accepted CPU bus event')
            events.append(Event(number, 'BUS', match[1], int(match[2], 16),
                                int(match[3], 16), int(match[4], 16), int(match[5])))
        elif 'SOC_DMA ' in line:
            match = _DMA.search(line)
            _need(match is not None, 'malformed accepted DMA event')
            events.append(Event(number, 'DMA', match[1], int(match[2], 16),
                                int(match[3], 16), 15, int(match[4])))
    _need(all(a.cycle <= b.cycle for a, b in zip(events, events[1:])),
          'accepted event cycles are not monotonic within one benchmark run')
    return events


def _commits(log):
    result = []
    for line in log.splitlines():
        if 'SOC_COMMIT ' not in line:
            continue
        match = _COMMIT.search(line)
        _need(match is not None, 'malformed CPU commit event')
        result.append((int(match[1], 16), int(match[2], 16), int(match[3]),
                       int(match[4], 16), int(match[5], 16)))
    return result


def _check_mode(mode):
    _need(mode in MODES, 'unknown benchmark mode: ' + str(mode))


def _check_symbols(symbols):
    for name, length in (('samples', 4*SAMPLES), ('coefficients', 4*TAPS),
                         ('outputs', 4*SAMPLES), ('marker', 4)):
        _need(name in symbols and type(symbols[name]) is int,
              'missing integer benchmark symbol: ' + name)
        _need(0 <= symbols[name] <= 1024-length and symbols[name] % 4 == 0,
              'benchmark buffer outside aligned 1 KiB RAM: ' + name)
    spans = [(symbols[n], symbols[n]+length) for n, length in
             (('samples', 4*SAMPLES), ('coefficients', 4*TAPS),
              ('outputs', 4*SAMPLES), ('marker', 4))]
    for n, (first, last) in enumerate(spans):
        _need(all(last <= other_first or other_last <= first
                  for other_first, other_last in spans[n+1:]),
              'benchmark input, coefficients, output and marker spans overlap')


def measure_interval(log, mode, symbols):
    """Return accepted-edge call cycles and enforce mode-specific boundaries.

    Begin/end are full-word CPU writes of 1/2 to ``symbols['marker']``.
    The cycle difference excludes initialization and common output checking;
    cold hardware includes all coefficient/configuration/start/poll overhead.
    Resident hardware may preload exactly 32 coefficients before begin.
    """
    _check_mode(mode)
    _check_symbols(symbols)
    events = _events(log)
    bus = [e for e in events if e.kind == 'BUS']
    dma = [e for e in events if e.kind == 'DMA']
    markers = [e for e in bus if e.address == symbols['marker']]
    _need(len(markers) == 2, 'benchmark requires exactly two marker writes')
    begin, end = markers
    _need(all(e.mode == 'W' and e.byte_enable == 15 for e in markers),
          'benchmark markers must be accepted full-word stores')
    _need((begin.data, end.data) == (1, 2) and begin.cycle < end.cycle,
          'benchmark marker payload/order/cycles are invalid')

    def inside(event):
        return begin.line < event.line < end.line and begin.cycle < event.cycle < end.cycle

    result = {
        'mode': mode, 'cycles': end.cycle-begin.cycle,
        'begin_cycle': begin.cycle, 'end_cycle': end.cycle,
        'marker_address': symbols['marker'], 'marker_writes': 2,
        'cpu_requests_in_interval': sum(inside(e) for e in bus),
        'coefficient_writes_before_interval': 0,
        'coefficient_writes_in_interval': 0,
        'output_stores_in_interval': 0,
        'dma_reads_in_interval': 0, 'dma_writes_in_interval': 0,
        'status_polls_in_interval': 0, 'diagnostic_reads_after_interval': 0,
        'timing_boundary': 'end accepted marker store cycle minus begin accepted marker store cycle',
    }
    mmio = [e for e in bus if e.address >= 1024]
    if mode == 'software':
        _need(not mmio, 'software benchmark must not access MMIO')
        _need(not dma, 'software benchmark must not issue DMA transactions')
        output_words = {symbols['outputs']+4*n for n in range(SAMPLES)}
        stores = [e for e in bus if e.mode == 'W' and
                  symbols['outputs'] <= e.address < symbols['outputs']+4*SAMPLES]
        _need(len(stores) == SAMPLES and {e.address for e in stores} == output_words and
              all(e.byte_enable == 15 and inside(e) for e in stores),
              'software must perform exactly eight full-word output stores inside the interval')
        result['output_stores_in_interval'] = SAMPLES
        return result

    _need(all(BASE <= e.address < BASE+4096 and e.address % 4 == 0 and
              e.byte_enable == 15 for e in mmio), 'invalid benchmark MMIO address/width')
    coefficient_writes = [e for e in mmio if e.mode == 'W' and
                          BASE+256 <= e.address <= BASE+380]
    coefficient_addresses = {BASE+256+4*k for k in range(TAPS)}
    _need(len(coefficient_writes) == TAPS and
          {e.address for e in coefficient_writes} == coefficient_addresses,
          'benchmark must write all 32 unique coefficient registers exactly once')
    for event in coefficient_writes:
        value = event.data & 65535
        encoded = value if value < 32768 else value | 0xffff0000
        _need(event.data == encoded, 'benchmark coefficient word is not signed16 extended')
    before = [e for e in coefficient_writes if e.line < begin.line and e.cycle < begin.cycle]
    during = [e for e in coefficient_writes if inside(e)]
    if mode == 'hardware_cold':
        _need(len(during) == TAPS and not before,
              'cold benchmark coefficient loading must be inside its measured interval')
    else:
        _need(len(before) == TAPS and not during,
              'resident benchmark coefficient loading must precede its measured interval')

    starts = [e for e in mmio if e.mode == 'W' and e.address == BASE and e.data == 1]
    _need(len(starts) == 1 and inside(starts[0]),
          'benchmark requires one START inside the measured interval')
    start = starts[0]
    _need(all(e.line < start.line and e.cycle < start.cycle for e in coefficient_writes),
          'all coefficient writes must precede START')
    setup = ((BASE, 2), (BASE+8, symbols['samples']),
             (BASE+12, symbols['outputs']), (BASE+16, SAMPLES))
    setup_events = []
    for address, value in setup:
        selected = [e for e in mmio if e.mode == 'W' and e.address == address and
                    (address != BASE or e.data != 1)]
        _need(len(selected) == 1 and selected[0].data == value and inside(selected[0]) and
              selected[0].line < start.line and selected[0].cycle < start.cycle,
              'ACK/SRC/DST/COUNT configuration must be inside the interval before START')
        setup_events.extend(selected)

    expected_dma = []
    for n in range(SAMPLES):
        expected_dma += [('R', symbols['samples']+4*n), ('W', symbols['outputs']+4*n)]
    _need([(e.mode, e.address) for e in dma] == expected_dma and
          all(inside(e) and e.line > start.line and e.cycle > start.cycle for e in dma),
          'all eight ordered DMA reads/writes must complete inside the interval after START')
    last_write = dma[-1]
    polls = [e for e in mmio if e.mode == 'R' and e.address == BASE+4]
    _need(polls and all(inside(e) and e.line > start.line and e.cycle > start.cycle
                       and e.data in (1, 2) for e in polls),
          'all STATUS polls must be successful busy/completion reads inside the interval')
    complete = [e for e in polls if e.data == 2]
    _need(complete and all(e.line > last_write.line and e.cycle > last_write.cycle
                          for e in complete),
          'a completion STATUS poll after the last accepted DMA write is required')
    _need(all(e.data == 2 for e in polls if e.line >= complete[0].line),
          'STATUS returned to busy after a completion poll')
    diagnostics = [e for e in mmio if e.mode == 'R' and e.address in (BASE+20, BASE+24)]
    _need(len(diagnostics) == 2 and {e.address for e in diagnostics} == {BASE+20, BASE+24} and
          all(e.line > end.line and e.cycle > end.cycle for e in diagnostics),
          'CYCLES/WRITTEN diagnostic reads must each occur only after the end marker')
    accounted = set(coefficient_writes + starts + setup_events + polls + diagnostics)
    _need(all(e in accounted for e in mmio), 'unexpected MMIO event outside the benchmark contract')
    # CPU writes cannot replace the accelerator's result stores.
    _need(not any(e.mode == 'W' and symbols['outputs'] <= e.address <
                  symbols['outputs']+4*SAMPLES for e in bus),
          'hardware benchmark CPU must not write the output buffer')
    result.update({
        'coefficient_writes_before_interval': len(before),
        'coefficient_writes_in_interval': len(during),
        'dma_reads_in_interval': SAMPLES, 'dma_writes_in_interval': SAMPLES,
        'status_polls_in_interval': len(polls),
        'diagnostic_reads_after_interval': len(diagnostics),
        'start_cycle': start.cycle, 'last_dma_write_cycle': last_write.cycle,
        'completion_poll_cycle': complete[0].cycle,
        'hardware_cycle_register': next(e.data for e in diagnostics if e.address == BASE+20),
        'hardware_written_register': next(e.data for e in diagnostics if e.address == BASE+24),
    })
    return result


def audit_benchmark(log, image, initial_memory, manifest, final_memory, final_registers, mode=None):
    """Validate complete execution and the measured call, returning JSON metrics.

    Hardware uses the unchanged Step 13 ISA/RAM/MMIO replay. Software uses the
    standalone ISA model, then separately checks Q15 outputs from runtime inputs.
    All modes require a successful C result, restored stack and complete evidence.
    """
    mode = mode if mode is not None else manifest.get('mode', manifest.get('benchmark_mode'))
    _check_mode(mode)
    symbols = manifest['symbols']
    measurement = measure_interval(log, mode, symbols)
    commits = _commits(log)
    _need(commits, 'benchmark has no CPU commit evidence')
    if mode == 'software':
        try:
            expected = run_program(image.program_words, initial_memory=initial_memory, max_steps=16384)
        except RuntimeError as error:
            raise ValueError('software benchmark exceeded the reference instruction bound') from error
        _need(not expected.fault and expected.pc == symbols['_program_end'],
              'software reference did not reach the program-end sentinel')
        reference_commits = [(t.pc, t.instruction, t.rd, t.value, t.next_pc) for t in expected.trace]
        _need(commits == reference_commits, 'software CPU commits differ from the independent ISA trace')
        actual_bus = [(e.mode, e.address, e.data, e.byte_enable)
                      for e in _events(log) if e.kind == 'BUS']
        reference_bus = [(e.mode, e.address, e.value, e.byte_enable) for e in expected.memory_trace]
        _need(actual_bus == reference_bus, 'software accepted RAM transactions differ from the ISA trace')
        _need(list(final_memory) == list(expected.memory), 'software final complete RAM differs from ISA replay')
        _need(list(final_registers) == list(expected.registers), 'software final registers differ from ISA replay')
        _need(expected.registers[2] == 1024 and expected.registers[10] == 0,
              'software C calling convention or return status failed')
        samples = [_signed(initial_memory[symbols['samples']//4+n]) for n in range(SAMPLES)]
        coefficients = [_signed(initial_memory[symbols['coefficients']//4+k]) for k in range(TAPS)]
        golden = fir_block(samples, coefficients)
        outputs = [_signed(final_memory[symbols['outputs']//4+n]) for n in range(SAMPLES)]
        _need(outputs == list(golden.outputs), 'software output differs from original Q15 reference')
        _need(final_memory[symbols['done']//4] == 1 and final_memory[symbols['errors']//4] == 0,
              'software C done/errors status is not successful')
        metrics = {
            'checked_commits': len(commits), 'cpu_requests': len(actual_bus),
            'dma_reads': 0, 'dma_writes': 0, 'hardware_cycles': 0,
            'polls': final_memory[symbols['polls']//4], 'outputs': outputs,
            'complete_ram_words_checked': 256, 'registers_checked': 32,
        }
    else:
        metrics = audit_hardware_trace(log, image, initial_memory, manifest,
                                       final_memory, final_registers)
        _need(measurement['hardware_cycle_register'] == metrics['hardware_cycles'] and
              measurement['hardware_written_register'] == SAMPLES,
              'benchmark diagnostic register evidence disagrees with hardware replay')
    loads = sum((instruction & 0x7f) == 3 for _, instruction, _, _, _ in commits)
    multiply = sum((instruction & 0xfe00707f) == 0x02000033
                   for _, instruction, _, _, _ in commits)
    return {**measurement, **metrics, 'mode': mode,
            'multiply_commits': multiply, 'load_commits': loads,
            'total_execution_edges': 3*len(commits)+loads}
