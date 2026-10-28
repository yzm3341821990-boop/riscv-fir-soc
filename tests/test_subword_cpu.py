"""Literal lane/extension expectations and a byte-array memory oracle."""

import random
import tempfile
from pathlib import Path
import unittest
from model import tiny_cpu as cpu


class SubwordCPUTests(unittest.TestCase):
    def test_subword_demo_has_literal_memory_bus_trace(self):
        from tools.generate_cpu_vectors import generate_cpu_vectors
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report = generate_cpu_vectors(directory)
            case = next(c for c in report['cases'] if c['name'] == 'subword_demo')
            self.assertEqual((case['retired_count'], case['memory_count']), (16, 10))
            self.assertEqual((directory / case['memory_trace_file']).read_text(),
                             'W 00000040 80FF817F F\nR 00000041 80FF817F 2\n'
                             'R 00000041 80FF817F 2\nR 00000042 80FF817F C\n'
                             'R 00000042 80FF817F C\nW 00000041 00005500 2\n'
                             'W 00000042 ABCD0000 C\nR 00000040 ABCD557F F\n'
                             'R 00000040 ABCD557F 1\nR 00000043 ABCD557F 8\n')
            values = (directory / case['registers_file']).read_text().splitlines()
            self.assertEqual(values[2:6], ['FFFFFF81','00000081','FFFF80FF','000080FF'])
            self.assertEqual(values[8:11], ['ABCD557F','0000007F','000000AB'])

    def test_load_encodings_are_literal_machine_words(self):
        for name, word in [('LB', 0x00108183), ('LH', 0x00109183), ('LW', 0x0010A183),
                           ('LBU', 0x0010C183), ('LHU', 0x0010D183)]:
            with self.subTest(name=name):
                self.assertEqual(cpu.encode_load(name, 3, 1, 1), word)

    def test_store_encodings_are_literal_machine_words(self):
        for name, word in [('SB', 0xFE208FA3), ('SH', 0xFE209FA3), ('SW', 0xFE20AFA3)]:
            with self.subTest(name=name):
                self.assertEqual(cpu.encode_store(name, 2, 1, -1), word)

    def test_signed_and_unsigned_byte_loads_cover_all_four_lanes(self):
        cases = [(0x00000083, 1, 0x7F, 0, 1), (0x00100083, 1, 0xFFFFFF81, 1, 2),
                 (0x00200083, 1, 0xFFFFFFFF, 2, 4), (0x00300083, 1, 0xFFFFFF80, 3, 8),
                 (0x00004103, 2, 0x7F, 0, 1), (0x00104103, 2, 0x81, 1, 2),
                 (0x00204103, 2, 0xFF, 2, 4), (0x00304103, 2, 0x80, 3, 8)]
        for word, rd, expected, address, be in cases:
            with self.subTest(word=f'{word:08X}'):
                result = cpu.run_program([word], initial_memory=[0x80FF817F])
                self.assertFalse(result.fault)
                self.assertEqual(result.registers[rd], expected)
                self.assertEqual(result.memory[0], 0x80FF817F)
                self.assertEqual([(e.mode, e.address, e.value, e.byte_enable) for e in result.memory_trace],
                                 [('R', address, 0x80FF817F, be)])

    def test_signed_and_unsigned_halfword_loads_cover_both_lanes(self):
        for word, rd, expected, be in [(0x00001183, 3, 0xFFFF817F, 3),
                                       (0x00201183, 3, 0xFFFF80FF, 12),
                                       (0x00005203, 4, 0x817F, 3),
                                       (0x00205203, 4, 0x80FF, 12)]:
            with self.subTest(word=f'{word:08X}'):
                result = cpu.run_program([word], initial_memory=[0x80FF817F])
                self.assertFalse(result.fault)
                self.assertEqual(result.registers[rd], expected)
                self.assertEqual(result.memory_trace[0].byte_enable, be)

    def test_byte_stores_preserve_every_other_byte(self):
        for word, expected, data, be in [(0x00200023, 0x123456FF, 0x000000FF, 1),
                                         (0x002000A3, 0x1234FF78, 0x0000FF00, 2),
                                         (0x00200123, 0x12FF5678, 0x00FF0000, 4),
                                         (0x002001A3, 0xFF345678, 0xFF000000, 8)]:
            with self.subTest(word=f'{word:08X}'):
                result = cpu.run_program([0xFFF00113, word], initial_memory=[0x12345678])
                self.assertFalse(result.fault)
                self.assertEqual(result.memory[0], expected)
                self.assertEqual((result.memory_trace[0].value, result.memory_trace[0].byte_enable), (data, be))
                self.assertEqual((result.trace[-1].rd, result.trace[-1].value), (0, 0))

    def test_halfword_stores_preserve_the_other_half(self):
        for word, expected, data, be in [(0x00201023, 0x1234FFFF, 0x0000FFFF, 3),
                                         (0x00201123, 0xFFFF5678, 0xFFFF0000, 12)]:
            with self.subTest(word=f'{word:08X}'):
                result = cpu.run_program([0xFFF00113, word], initial_memory=[0x12345678])
                self.assertFalse(result.fault)
                self.assertEqual(result.memory[0], expected)
                self.assertEqual((result.memory_trace[0].value, result.memory_trace[0].byte_enable), (data, be))

    def test_alignment_is_specific_to_the_access_width(self):
        for name in ('LH', 'LHU'):
            for address in (1, 3, 1023):
                result = cpu.run_program([cpu.encode_load(name, 1, 0, address)])
                self.assertTrue(result.fault)
                self.assertEqual((result.trace, result.memory_trace), ((), ()))
        for address in (1, 3, 1023):
            result = cpu.run_program([cpu.encode_store('SH', 2, 0, address)], initial_memory=[0x12345678])
            self.assertTrue(result.fault)
            self.assertEqual(result.memory[0], 0x12345678)
            self.assertEqual(result.memory_trace, ())

    def test_last_byte_and_last_halfword_are_legal(self):
        memory = [0] * 255 + [0x80FF817F]
        for name, address, expected in [('LB', 1023, 0xFFFFFF80), ('LBU', 1023, 0x80),
                                         ('LH', 1022, 0xFFFF80FF), ('LHU', 1022, 0x80FF)]:
            result = cpu.run_program([cpu.encode_load(name, 1, 0, address)], initial_memory=memory)
            self.assertFalse(result.fault)
            self.assertEqual(result.registers[1], expected)
        result = cpu.run_program([0xFFF00113, cpu.encode_store('SB', 2, 0, 1023)], initial_memory=memory)
        self.assertEqual(result.memory[-1], 0xFFFF817F)
        result = cpu.run_program([0xFFF00113, cpu.encode_store('SH', 2, 0, 1022)], initial_memory=memory)
        self.assertEqual(result.memory[-1], 0xFFFF817F)

    def test_x0_loads_still_access_memory_and_check_range(self):
        for name in ('LB', 'LBU', 'LH', 'LHU'):
            result = cpu.run_program([cpu.encode_load(name, 0, 0, 0)], initial_memory=[0xFFFFFFFF])
            self.assertFalse(result.fault)
            self.assertEqual((result.trace[0].rd, result.trace[0].value), (0, 0))
            self.assertEqual(len(result.memory_trace), 1)
            for address in (-1, 1024):
                result = cpu.run_program([cpu.encode_load(name, 0, 0, address)])
                self.assertTrue(result.fault)
                self.assertEqual((result.trace, result.memory_trace), ((), ()))

    def test_subword_encoder_validation_and_legacy_wrappers(self):
        self.assertEqual(cpu.encode_load('lw', 1, 2, -4), cpu.encode_lw(1, 2, -4))
        self.assertEqual(cpu.encode_store('sw', 1, 2, -4), cpu.encode_sw(1, 2, -4))
        for func, args, exception in [(cpu.encode_load, ('LD', 1, 0, 0), ValueError),
                                      (cpu.encode_store, ('SD', 1, 0, 0), ValueError),
                                      (cpu.encode_load, (None, 1, 0, 0), TypeError),
                                      (cpu.encode_store, ('SB', True, 0, 0), TypeError),
                                      (cpu.encode_load, ('LB', 32, 0, 0), ValueError),
                                      (cpu.encode_store, ('SH', 1, -1, 0), ValueError),
                                      (cpu.encode_load, ('LB', 1, 0, 2048), ValueError),
                                      (cpu.encode_store, ('SH', 1, 0, -2049), ValueError)]:
            with self.assertRaises(exception):
                func(*args)

    def test_random_mixed_accesses_match_an_independent_byte_array(self):
        rng = random.Random(0xB17E)
        data = bytearray(rng.randrange(256) for _ in range(1024))
        initial = [int.from_bytes(data[i:i+4], 'little') for i in range(0, 1024, 4)]
        program, expected_loads = [], []
        for _ in range(36):
            width = rng.choice((1, 2, 4))
            address = rng.randrange(1024 // width) * width
            value = rng.randrange(1 << 32)
            # Build an arbitrary raw word without depending on upper encoders.
            upper, lower = ((value + 2048) >> 12) & 0xFFFFF, value & 0xFFF
            lower = lower - 4096 if lower >= 2048 else lower
            program += [cpu.encode_lui(2, upper), cpu.encode_addi(2, 2, lower)]
            program.append(cpu.encode_store({1:'SB', 2:'SH', 4:'SW'}[width], 2, 0, address))
            data[address:address+width] = value.to_bytes(4, 'little')[:width]
            name = rng.choice({1:('LB','LBU'),2:('LH','LHU'),4:('LW',)}[width])
            program.append(cpu.encode_load(name, 3, 0, address))
            expected_loads.append(int.from_bytes(data[address:address+width], 'little', signed=name in ('LB','LH')) & 0xFFFFFFFF)
        result = cpu.run_program(program, initial_memory=initial)
        self.assertFalse(result.fault)
        self.assertEqual([result.trace[n].value for n in range(3, len(program), 4)], expected_loads)
        self.assertEqual(result.memory, tuple(int.from_bytes(data[i:i+4], 'little') for i in range(0, 1024, 4)))


if __name__ == '__main__':
    unittest.main()
