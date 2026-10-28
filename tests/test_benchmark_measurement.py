"""Independent accepted-edge timing boundaries for the paired FIR benchmark."""
import importlib
from pathlib import Path
import unittest

BASE = 0x40003000
SYMBOLS = {'samples': 512, 'coefficients': 544, 'outputs': 672, 'marker': 704}


def bus(cycle, address, data, mode='W', be=15):
    return f'SOC_BUS mode={mode} addr={address:08X} data={data & 0xffffffff:08X} be={be:08X} cycle={cycle}'


def dma(cycle, address, data=0, mode='R'):
    return f'SOC_DMA mode={mode} addr={address:08X} data={data & 0xffffffff:08X} cycle={cycle}'


def hardware_events(resident=False):
    events = [(100, bus(100, 704, 1))]
    first = 1 if resident else 101
    for k in range(32):
        cycle = first + k
        events.append((cycle, bus(cycle, BASE + 256 + 4*k, 16384 if k == 0 else 0)))
    first = 101 if resident else 133
    for n, (offset, value) in enumerate(((0, 2), (8, 512), (12, 672), (16, 8), (0, 1))):
        cycle = first + n
        events.append((cycle, bus(cycle, BASE + offset, value)))
    start = first + 4
    for n in range(8):
        events.append((start + 1 + 38*n, dma(start + 1 + 38*n, 512 + 4*n)))
        events.append((start + 37 + 38*n, dma(start + 37 + 38*n, 672 + 4*n, mode='W')))
    last = start + 37 + 38*7
    events.append((start + 3, bus(start + 3, BASE + 4, 1, mode='R')))
    events.append((last + 2, bus(last + 2, BASE + 4, 2, mode='R')))
    end = last + 4
    events += [(end, bus(end, 704, 2)),
               (end + 2, bus(end + 2, BASE + 20, last - start, mode='R')),
               (end + 3, bus(end + 3, BASE + 24, 8, mode='R'))]
    return '\n'.join(text for _, text in sorted(events)) + '\n'


def software_events():
    return '\n'.join([bus(100, 704, 1)] +
                     [bus(101+n, 672+4*n, n) for n in range(8)] + [bus(110, 704, 2)]) + '\n'


class BenchmarkMeasurementTests(unittest.TestCase):
    def api(self):
        path = Path(__file__).resolve().parents[1] / 'tools/audit_fir_benchmark.py'
        self.assertTrue(path.is_file(), 'benchmark measurement implementation is missing')
        return importlib.import_module('tools.audit_fir_benchmark')

    def test_software_uses_accepted_marker_edges_and_eight_output_stores(self):
        result = self.api().measure_interval(software_events(), 'software', SYMBOLS)
        self.assertEqual(result['cycles'], 10)
        self.assertEqual((result['begin_cycle'], result['end_cycle']), (100, 110))
        self.assertEqual(result['output_stores_in_interval'], 8)

    def test_cold_hardware_includes_all_coefficient_configuration(self):
        result = self.api().measure_interval(hardware_events(), 'hardware_cold', SYMBOLS)
        self.assertEqual(result['coefficient_writes_in_interval'], 32)
        self.assertEqual(result['coefficient_writes_before_interval'], 0)
        self.assertEqual(result['dma_reads_in_interval'], 8)
        self.assertEqual(result['dma_writes_in_interval'], 8)
        self.assertLess(result['last_dma_write_cycle'], result['completion_poll_cycle'])
        self.assertLess(result['completion_poll_cycle'], result['end_cycle'])

    def test_resident_hardware_preloads_coefficients_before_begin(self):
        result = self.api().measure_interval(hardware_events(True), 'hardware_resident', SYMBOLS)
        self.assertEqual(result['coefficient_writes_before_interval'], 32)
        self.assertEqual(result['coefficient_writes_in_interval'], 0)

    def test_cold_cannot_hide_coefficient_loading_before_timer(self):
        with self.assertRaisesRegex(ValueError, 'coefficient'):
            self.api().measure_interval(hardware_events(True), 'hardware_cold', SYMBOLS)

    def test_resident_cannot_load_coefficients_inside_timer(self):
        with self.assertRaisesRegex(ValueError, 'coefficient'):
            self.api().measure_interval(hardware_events(), 'hardware_resident', SYMBOLS)

    def test_missing_duplicate_reversed_or_partial_markers_are_rejected(self):
        source = software_events()
        bad = [source.replace(bus(110, 704, 2)+'\n', ''),
               source + bus(111, 704, 2)+'\n',
               source.replace('data=00000001', 'data=00000002', 1),
               source.replace(bus(100, 704, 1), bus(100, 704, 1, be=3)),
               source.replace(bus(100, 704, 1), bus(110, 704, 1))]
        for log in bad:
            with self.subTest(log=log), self.assertRaises(ValueError):
                self.api().measure_interval(log, 'software', SYMBOLS)

    def test_hardware_end_cannot_precede_the_last_dma_write(self):
        source = hardware_events()
        end = next(line for line in source.splitlines() if 'addr=000002C0 data=00000002' in line)
        log = source.replace(end, bus(150, 704, 2))
        with self.assertRaises(ValueError):
            self.api().measure_interval(log, 'hardware_cold', SYMBOLS)

    def test_completion_poll_is_required_inside_interval(self):
        source = hardware_events()
        log = '\n'.join(line for line in source.splitlines()
                        if not ('addr=40003004 data=00000002' in line))+'\n'
        with self.assertRaisesRegex(ValueError, 'completion|STATUS|poll'):
            self.api().measure_interval(log, 'hardware_cold', SYMBOLS)

    def test_hardware_diagnostic_reads_must_follow_end_marker(self):
        source = hardware_events()
        old = next(line for line in source.splitlines() if 'addr=40003014' in line)
        log = source.replace(old, bus(200, BASE + 20, 303, mode='R'))
        with self.assertRaises(ValueError):
            self.api().measure_interval(log, 'hardware_cold', SYMBOLS)

    def test_software_cannot_skip_output_stores_or_access_mmio(self):
        log = software_events().replace(bus(104, 684, 3)+'\n', '')
        with self.assertRaisesRegex(ValueError, 'output'):
            self.api().measure_interval(log, 'software', SYMBOLS)
        with self.assertRaisesRegex(ValueError, 'MMIO'):
            self.api().measure_interval(software_events()+bus(120, BASE+4, 2, mode='R'), 'software', SYMBOLS)

    def test_unknown_modes_and_bad_marker_payload_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'mode'):
            self.api().measure_interval(software_events(), 'fastest', SYMBOLS)
        with self.assertRaises(ValueError):
            self.api().measure_interval(software_events().replace('data=00000002', 'data=00000003'), 'software', SYMBOLS)


if __name__ == '__main__':
    unittest.main()
