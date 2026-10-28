"""Independent literal expectations for the RV32I ALU teaching CPU."""

import importlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest


class TinyCPUModelTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("model.tiny_cpu"),
                             "the CPU reference is not implemented")
        self.cpu = importlib.import_module("model.tiny_cpu")

    def test_demo_encodings_match_fixed_machine_words(self):
        self.assertEqual(self.cpu.encode_addi(1, 0, 5), 0x00500093)
        self.assertEqual(self.cpu.encode_addi(2, 0, 7), 0x00700113)
        self.assertEqual(self.cpu.encode_add(3, 1, 2), 0x002081B3)
        self.assertEqual(self.cpu.encode_sub(3, 1, 2), 0x402081B3)

    def test_upper_encoders_match_independent_literal_words(self):
        self.assertEqual(self.cpu.encode_lui(1, 0x12345), 0x123450B7)
        self.assertEqual(self.cpu.encode_lui(31, 0xFFFFF), 0xFFFFFFB7)
        self.assertEqual(self.cpu.encode_auipc(3, 0), 0x00000197)
        self.assertEqual(self.cpu.encode_auipc(31, 0x80000), 0x80000F97)
        self.assertEqual(self.cpu.encode_auipc(rd=2, imm20=0xABCDE), 0xABCDE117)

    def test_upper_encoders_reject_out_of_range_fields_and_registers(self):
        for name in ("encode_lui", "encode_auipc"):
            for arguments in ((-1, 0), (32, 0), (1, -1), (1, 0x100000)):
                with self.subTest(name=name, arguments=arguments), self.assertRaises(ValueError):
                    getattr(self.cpu, name)(*arguments)

    def test_upper_encoders_reject_non_integer_fields_and_registers(self):
        for name in ("encode_lui", "encode_auipc"):
            for arguments in ((True, 0), (1.0, 0), (1, True), (1, 1.0), (1, "1")):
                with self.subTest(name=name, arguments=arguments), self.assertRaises(TypeError):
                    getattr(self.cpu, name)(*arguments)

    def test_lui_literal_boundaries_and_all_immediate_fields_are_legal(self):
        # No funct3/rs1/rs2 fields exist in U format: all bits 31:12 are data.
        result = self.cpu.run_program([0x000000B7, 0x80000137, 0xFFFFF1B7, 0xABCDE237])
        self.assertFalse(result.fault)
        self.assertEqual([entry.value for entry in result.trace],
                         [0, 0x80000000, 0xFFFFF000, 0xABCDE000])
        self.assertEqual([entry.rd for entry in result.trace], [1, 2, 3, 4])

    def test_lui_ignores_dirty_register_matching_immediate_bit_positions(self):
        # 0x12345 in the U field makes instruction[19:15] equal x8.
        result = self.cpu.run_program([0x06300413, 0x123450B7])
        self.assertFalse(result.fault)
        self.assertEqual(result.registers[8], 99)
        self.assertEqual(result.registers[1], 0x12345000)

    def test_auipc_uses_current_pc_and_ignores_encoded_rs1_bits(self):
        result = self.cpu.run_program([0x06300413, 0x12345117, 0x80000F97, 0xFFFFF197])
        self.assertFalse(result.fault)
        self.assertEqual([(entry.pc, entry.rd, entry.value) for entry in result.trace],
                         [(0, 8, 99), (4, 2, 0x12345004),
                          (8, 31, 0x80000008), (12, 3, 0xFFFFF00C)])
        self.assertEqual(result.pc, 16)

    def test_auipc_uses_redirected_pc_rather_than_execution_count(self):
        result = self.cpu.run_program([0x00C0006F, 0, 0, 0x00000097, 0x00001117])
        self.assertFalse(result.fault)
        self.assertEqual([(entry.pc, entry.value) for entry in result.trace],
                         [(0, 0), (12, 12), (16, 0x1010)])

    def test_upper_writes_to_x0_commit_but_discard_the_result(self):
        result = self.cpu.run_program([0x80000037, 0xFFFFF017, 0x00700093])
        self.assertFalse(result.fault)
        self.assertEqual([(entry.rd, entry.value) for entry in result.trace], [(0, 0), (0, 0), (1, 7)])
        self.assertEqual(result.registers[0], 0)
        self.assertEqual(result.pc, 12)

    def test_lui_plus_negative_addi_constructs_constant_with_carry_adjustment(self):
        result = self.cpu.run_program([0x123460B7, 0xABC08093])
        self.assertFalse(result.fault)
        self.assertEqual([entry.value for entry in result.trace], [0x12346000, 0x12345ABC])

    def test_upper_values_feed_existing_wrapping_arithmetic(self):
        result = self.cpu.run_program([0xFFFFF0B7, 0x00001137, 0x002081B3])
        self.assertFalse(result.fault)
        self.assertEqual([entry.value for entry in result.trace], [0xFFFFF000, 0x1000, 0])

    def test_upper_demo_constructs_constant_and_skips_destructive_store(self):
        words = [0x123450B7, 0x67808093, 0x04102023, 0x04002103, 0x00000197,
                 0x01018193, 0x00018267, 0x04002023, 0x04002283]
        result = self.cpu.run_program(words)
        self.assertFalse(result.fault)
        self.assertEqual([(entry.pc, entry.rd, entry.value, entry.next_pc) for entry in result.trace],
                         [(0, 1, 0x12345000, 4), (4, 1, 0x12345678, 8), (8, 0, 0, 12),
                          (12, 2, 0x12345678, 16), (16, 3, 16, 20), (20, 3, 32, 24),
                          (24, 4, 28, 32), (32, 5, 0x12345678, 36)])
        self.assertEqual(result.registers, (0, 0x12345678, 0x12345678, 32, 28, 0x12345678) + (0,) * 26)
        self.assertEqual(result.memory, (0,) * 16 + (0x12345678,) + (0,) * 239)
        self.assertEqual([(event.mode, event.address, event.value) for event in result.memory_trace],
                         [("W", 64, 0x12345678), ("R", 64, 0x12345678), ("R", 64, 0x12345678)])

    def test_immediate_boundaries_have_independent_encodings(self):
        self.assertEqual(self.cpu.encode_addi(1, 0, -2048), 0x80000093)
        self.assertEqual(self.cpu.encode_addi(31, 1, 2047), 0x7FF08F93)
        self.assertEqual(self.cpu.encode_addi(2, 1, -1), 0xFFF08113)

    def test_addi_accepts_the_documented_imm_keyword(self):
        self.assertEqual(self.cpu.encode_addi(rd=1, rs1=0, imm=5), 0x00500093)

    def test_assembler_rejects_registers_outside_five_bits(self):
        for function, arguments in [
                ("encode_addi", (32, 0, 0)), ("encode_addi", (1, -1, 0)),
                ("encode_add", (0, 32, 0)), ("encode_add", (0, 0, -1)),
                ("encode_sub", (-1, 0, 0)), ("encode_sub", (0, 0, 32))]:
            with self.subTest(function=function, arguments=arguments):
                with self.assertRaises(ValueError):
                    getattr(self.cpu, function)(*arguments)

    def test_assembler_rejects_immediates_outside_signed_twelve_bits(self):
        for immediate in (-2049, 2048):
            with self.subTest(immediate=immediate), self.assertRaises(ValueError):
                self.cpu.encode_addi(1, 0, immediate)

    def test_assembler_rejects_non_integer_operands(self):
        for function, arguments in [
                ("encode_addi", (True, 0, 0)), ("encode_addi", (1, 0, 1.0)),
                ("encode_add", (1, "2", 3)), ("encode_sub", (1, 2, None))]:
            with self.subTest(function=function, arguments=arguments):
                with self.assertRaises(TypeError):
                    getattr(self.cpu, function)(*arguments)

    def test_demo_commits_exact_pc_words_destinations_and_values(self):
        result = self.cpu.run_program([0x00500093, 0x00700113, 0x002081B3])
        self.assertEqual([(t.pc, t.instruction, t.rd, t.value) for t in result.trace],
                         [(0, 0x00500093, 1, 5), (4, 0x00700113, 2, 7),
                          (8, 0x002081B3, 3, 12)])
        self.assertEqual(result.registers, (0, 5, 7, 12) + (0,) * 28)
        self.assertEqual(result.pc, 12)
        self.assertFalse(result.fault)
        self.assertEqual(result.fault_pc, 0)

    def test_negative_immediates_are_sign_extended(self):
        result = self.cpu.run_program([0xFFF00093, 0xFFE08113])
        self.assertEqual([t.value for t in result.trace], [0xFFFFFFFF, 0xFFFFFFFD])
        self.assertEqual(result.registers[1:3], (0xFFFFFFFF, 0xFFFFFFFD))

    def test_immediate_extremes_and_back_to_back_dependencies(self):
        result = self.cpu.run_program([0x80000093, 0x7FF08113, 0x00110193])
        self.assertEqual([t.value for t in result.trace], [0xFFFFF800, 0xFFFFFFFF, 0])
        self.assertEqual(result.registers[1:4], (0xFFFFF800, 0xFFFFFFFF, 0))

    def test_add_wraps_at_thirty_two_bits(self):
        result = self.cpu.run_program([0xFFF00093, 0x00100113, 0x002081B3,
                                       0x00108233])
        self.assertEqual([t.value for t in result.trace],
                         [0xFFFFFFFF, 1, 0, 0xFFFFFFFE])
        self.assertEqual(result.registers[3:5], (0, 0xFFFFFFFE))

    def test_subtract_wraps_and_reads_the_new_previous_destination(self):
        result = self.cpu.run_program([0x00100093, 0x40100133, 0x402081B3,
                                       0x401181B3])
        self.assertEqual([t.value for t in result.trace], [1, 0xFFFFFFFF, 2, 1])
        self.assertEqual(result.registers[1:4], (1, 0xFFFFFFFF, 1))

    def test_x0_write_is_ignored_and_committed_value_is_zero(self):
        result = self.cpu.run_program([0x00500013, 0x00100093, 0x00108033,
                                       0x40100033, 0x00000133])
        self.assertEqual([t.value for t in result.trace], [0, 1, 0, 0, 0])
        self.assertEqual(result.registers, (0, 1) + (0,) * 30)

    def test_register_thirty_one_is_readable_and_writable(self):
        result = self.cpu.run_program([0xFF900F93, 0x004F8F93, 0x41F00F33])
        self.assertEqual([t.value for t in result.trace],
                         [0xFFFFFFF9, 0xFFFFFFFD, 3])
        self.assertEqual(result.registers[30:], (3, 0xFFFFFFFD))

    def test_empty_program_finishes_with_reset_state(self):
        result = self.cpu.run_program([])
        self.assertEqual(result.trace, ())
        self.assertEqual(result.registers, (0,) * 32)
        self.assertEqual(result.pc, 0)
        self.assertFalse(result.fault)

    def test_illegal_opcode_reserved_fields_and_system_do_not_commit(self):
        for instruction in (0x00000000, 0x02101093, 0x402091B3,
                            0x042081B3, 0x00000073,
                            0x00100073, 0x00002067):
            with self.subTest(instruction=f"{instruction:08X}"):
                result = self.cpu.run_program([instruction, 0x00500093])
                self.assertTrue(result.fault)
                self.assertEqual(result.fault_pc, 0)
                self.assertEqual(result.pc, 0)
                self.assertEqual(result.trace, ())
                self.assertEqual(result.registers, (0,) * 32)

    def test_addi_upper_immediate_bits_are_not_misread_as_funct7(self):
        result = self.cpu.run_program([0x40200093])
        self.assertFalse(result.fault)
        self.assertEqual(result.registers[1], 1026)
        self.assertEqual(len(result.trace), 1)

    def test_fault_after_valid_prefix_preserves_pc_and_registers(self):
        result = self.cpu.run_program([0x00500093, 0x00700113, 0x002081B3,
                                       0x042081B3, 0x06300093])
        self.assertTrue(result.fault)
        self.assertEqual((result.pc, result.fault_pc), (12, 12))
        self.assertEqual(len(result.trace), 3)
        self.assertEqual(result.registers, (0, 5, 7, 12) + (0,) * 28)

    def test_program_rejects_non_words_and_excess_rom_depth(self):
        for words, error in [([True], TypeError), ([1.5], TypeError),
                              ([-1], ValueError), ([1 << 32], ValueError),
                              ([0x00000013] * 257, ValueError)]:
            with self.subTest(words_count=len(words), error=error):
                with self.assertRaises(error):
                    self.cpu.run_program(words)

    def test_all_register_alu_operations_have_independent_literal_results(self):
        for word, expected in [(0x002081B3, 0xFFFFFFFD), (0x402081B3, 0xFFFFFFF3),
                               (0x002091B3, 0xFFFFFF00), (0x0020A1B3, 1),
                               (0x0020B1B3, 0), (0x0020C1B3, 0xFFFFFFFD),
                               (0x0020D1B3, 0x07FFFFFF), (0x4020D1B3, 0xFFFFFFFF),
                               (0x0020E1B3, 0xFFFFFFFD), (0x0020F1B3, 0)]:
            with self.subTest(word=f"{word:08X}"):
                result = self.cpu.run_program([0xFF800093, 0x00500113, word])
                self.assertFalse(result.fault)
                self.assertEqual(len(result.trace), 3)
                self.assertEqual(result.registers[3], expected)
                self.assertEqual(result.trace[-1].value, expected)

    def test_nonshift_immediates_sign_extend_for_comparison_and_logic(self):
        for word, expected in [(0xFFF08193, 0xFFFFFFF7), (0xFFF0A193, 1),
                               (0xFFF0B193, 1), (0xFFF0C193, 7),
                               (0xFFF0E193, 0xFFFFFFFF), (0xFFF0F193, 0xFFFFFFF8),
                               (0x8000E193, 0xFFFFFFF8)]:
            with self.subTest(word=f"{word:08X}"):
                result = self.cpu.run_program([0xFF800093, word])
                self.assertFalse(result.fault)
                self.assertEqual(result.registers[3], expected)

    def test_immediate_shift_zero_one_and_thirty_one(self):
        for word, expected in [(0x00009193, 0xFFFFFFF8), (0x00109193, 0xFFFFFFF0),
                               (0x01F09193, 0), (0x0000D193, 0xFFFFFFF8),
                               (0x0010D193, 0x7FFFFFFC), (0x01F0D193, 1),
                               (0x4000D193, 0xFFFFFFF8), (0x4010D193, 0xFFFFFFFC),
                               (0x41F0D193, 0xFFFFFFFF)]:
            with self.subTest(word=f"{word:08X}"):
                result = self.cpu.run_program([0xFF800093, word])
                self.assertFalse(result.fault)
                self.assertEqual(result.registers[3], expected)

    def test_register_shift_amount_uses_low_five_bits(self):
        for amount_word, expectations in [
                (0x02000113, [(0x002091B3, 0xFFFFFFF8),
                              (0x0020D1B3, 0xFFFFFFF8), (0x4020D1B3, 0xFFFFFFF8)]),
                (0xFFF00113, [(0x002091B3, 0),
                              (0x0020D1B3, 1), (0x4020D1B3, 0xFFFFFFFF)])]:
            for word, expected in expectations:
                with self.subTest(amount_word=amount_word, word=word):
                    result = self.cpu.run_program([0xFF800093, amount_word, word])
                    self.assertFalse(result.fault)
                    self.assertEqual(result.registers[3], expected)

    def test_signed_minimum_and_positive_arithmetic_shifts(self):
        for words, expected in [([0x00100093, 0x01F09093, 0x41F0D193], 0xFFFFFFFF),
                                ([0x00700093, 0x4010D193], 3),
                                ([0x00100093, 0x01F09193], 0x80000000)]:
            with self.subTest(words=words):
                result = self.cpu.run_program(words)
                self.assertFalse(result.fault)
                self.assertEqual(result.registers[3], expected)

    def test_unsigned_immediate_compare_uses_sign_extended_negative_operand(self):
        for first, expected in [(0x00000093, 1), (0x00100093, 1),
                                (0xFFF00093, 0), (0xFF800093, 1)]:
            with self.subTest(first=first):
                result = self.cpu.run_program([first, 0xFFF0B193])
                self.assertFalse(result.fault)
                self.assertEqual(result.registers[3], expected)

    def test_all_reserved_r_funct7_combinations_fault_without_commit(self):
        for funct7 in range(1, 128):
            for funct3 in range(8):
                if (funct7 == 0x20 and funct3 in (0, 5)) or (funct7 == 1 and funct3 == 0):
                    continue
                word = 0x002081B3 | (funct7 << 25) | (funct3 << 12)
                with self.subTest(funct7=funct7, funct3=funct3):
                    result = self.cpu.run_program([word])
                    self.assertTrue(result.fault)
                    self.assertEqual((result.pc, result.fault_pc), (0, 0))
                    self.assertEqual(result.trace, ())
                    self.assertEqual(result.registers, (0,) * 32)

    def test_all_reserved_immediate_shift_high_bits_fault(self):
        for funct3 in (1, 5):
            for funct7 in range(128):
                if funct7 == 0 or (funct3 == 5 and funct7 == 0x20):
                    continue
                word = 0x00100093 | (funct3 << 12) | (funct7 << 25)
                with self.subTest(funct3=funct3, funct7=funct7):
                    result = self.cpu.run_program([word, 0x00500093])
                    self.assertTrue(result.fault)
                    self.assertEqual(result.trace, ())
                    self.assertEqual(result.pc, 0)
                    self.assertEqual(result.registers, (0,) * 32)

    def test_generic_and_named_register_encoders_match_fixed_machine_words(self):
        for name, expected in [("ADD", 0x002081B3), ("SUB", 0x402081B3),
                               ("SLL", 0x002091B3), ("SLT", 0x0020A1B3),
                               ("SLTU", 0x0020B1B3), ("XOR", 0x0020C1B3),
                               ("SRL", 0x0020D1B3), ("SRA", 0x4020D1B3),
                               ("OR", 0x0020E1B3), ("AND", 0x0020F1B3)]:
            with self.subTest(name=name):
                self.assertEqual(self.cpu.encode_op(name, 3, 1, 2), expected)
                self.assertEqual(getattr(self.cpu, "encode_" + name.lower())(3, 1, 2), expected)

    def test_generic_and_named_immediate_encoders_match_fixed_machine_words(self):
        for name, expected in [("ADDI", 0x00508193), ("SLTI", 0x0050A193),
                               ("SLTIU", 0x0050B193), ("XORI", 0x0050C193),
                               ("ORI", 0x0050E193), ("ANDI", 0x0050F193),
                               ("SLLI", 0x00509193), ("SRLI", 0x0050D193),
                               ("SRAI", 0x4050D193)]:
            with self.subTest(name=name):
                self.assertEqual(self.cpu.encode_op_imm(name, 3, 1, 5), expected)
                self.assertEqual(getattr(self.cpu, "encode_" + name.lower())(3, 1, 5), expected)

    def test_new_encoders_validate_mnemonics_and_shift_width(self):
        for name in ("SLLI", "SRLI", "SRAI"):
            for amount in (-1, 32):
                with self.subTest(name=name, amount=amount), self.assertRaises(ValueError):
                    self.cpu.encode_op_imm(name, 3, 1, amount)
        for function, operands in [("encode_op", ("DIV", 1, 2, 3)),
                                   ("encode_op_imm", ("LUI", 1, 2, 3)),
                                   ("encode_op", ("AND", 32, 1, 2)),
                                   ("encode_op_imm", ("XORI", 1, 0, -2049))]:
            with self.subTest(function=function, operands=operands), self.assertRaises(ValueError):
                getattr(self.cpu, function)(*operands)

    def test_new_alu_operations_cannot_write_x0(self):
        for word in (0x002091B3, 0x0020A1B3, 0x0020B1B3, 0x0020C1B3,
                     0x0020D1B3, 0x4020D1B3, 0x0020E1B3, 0x0020F1B3,
                     0xFFF0A193, 0xFFF0B193, 0xFFF0C193, 0xFFF0E193,
                     0xFFF0F193, 0x00109193, 0x0010D193, 0x4010D193):
            with self.subTest(word=word):
                result = self.cpu.run_program([0xFF800093, 0x00500113, word & ~0xF80])
                self.assertFalse(result.fault)
                self.assertEqual(result.trace[-1].rd, 0)
                self.assertEqual(result.trace[-1].value, 0)
                self.assertEqual(result.registers[0], 0)

    def test_load_store_encoders_match_fixed_i_and_split_s_words(self):
        for function, operands, expected in [
                ("encode_lw", (3, 1, 0), 0x0000A183),
                ("encode_lw", (3, 1, -4), 0xFFC0A183),
                ("encode_lw", (3, 1, -2048), 0x8000A183),
                ("encode_lw", (3, 1, 2047), 0x7FF0A183),
                ("encode_sw", (2, 1, 0), 0x0020A023),
                ("encode_sw", (2, 1, 4), 0x0020A223),
                ("encode_sw", (2, 1, -4), 0xFE20AE23),
                ("encode_sw", (2, 1, -2048), 0x8020A023),
                ("encode_sw", (2, 1, 2047), 0x7E20AFA3)]:
            with self.subTest(function=function, operands=operands):
                self.assertEqual(getattr(self.cpu, function)(*operands), expected)

    def test_load_store_encoders_reject_invalid_registers_and_offsets(self):
        for function in ("encode_lw", "encode_sw"):
            for operands in ((32, 0, 0), (1, -1, 0), (1, 0, -2049), (1, 0, 2048)):
                with self.subTest(function=function, operands=operands), self.assertRaises(ValueError):
                    getattr(self.cpu, function)(*operands)
            with self.assertRaises(TypeError):
                getattr(self.cpu, function)(1, 0, True)

    def test_memory_demo_has_literal_commits_data_and_bus_events(self):
        words = [0x04000093, 0x00C00113, 0x0020A023, 0x0000A183,
                 0x00518213, 0x0040A223, 0x0040A283, 0x40328333]
        result = self.cpu.run_program(words)
        self.assertFalse(result.fault)
        self.assertEqual([(t.rd, t.value) for t in result.trace],
                         [(1, 64), (2, 12), (0, 0), (3, 12),
                          (4, 17), (0, 0), (5, 17), (6, 5)])
        self.assertEqual(result.memory, (0,) * 16 + (12, 17) + (0,) * 238)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace],
                         [("W", 64, 12), ("R", 64, 12), ("W", 68, 17), ("R", 68, 17)])

    def test_negative_s_offset_writes_rs2_and_loads_same_byte_address(self):
        result = self.cpu.run_program([0x04400093, 0x00C00113, 0xFE20AE23, 0xFFC0A183])
        self.assertFalse(result.fault)
        self.assertEqual(result.memory[16], 12)
        self.assertEqual(result.registers[3], 12)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace],
                         [("W", 64, 12), ("R", 64, 12)])

    def test_effective_address_wraps_to_zero_before_range_check(self):
        result = self.cpu.run_program([0xFFC00093, 0x00C00113, 0x0020A223, 0x0040A183])
        self.assertFalse(result.fault)
        self.assertEqual(result.memory[0], 12)
        self.assertEqual(result.registers[3], 12)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace],
                         [("W", 0, 12), ("R", 0, 12)])

    def test_signed_offset_extremes_can_reach_zero_with_suitable_base(self):
        for words in ([0x40000093, 0x40008093, 0x00C00113, 0x8020A023, 0x8000A183],
                      [0x80100093, 0x00C00113, 0x7E20AFA3, 0x7FF0A183]):
            with self.subTest(words=words):
                result = self.cpu.run_program(words)
                self.assertFalse(result.fault)
                self.assertEqual(result.memory[0], 12)
                self.assertEqual(result.registers[3], 12)

    def test_last_aligned_ram_word_is_accessible(self):
        result = self.cpu.run_program([0x3FC00093, 0x00C00113, 0x0020A023, 0x0000A183])
        self.assertFalse(result.fault)
        self.assertEqual(result.memory[255], 12)
        self.assertEqual(result.registers[3], 12)
        self.assertEqual([t.address for t in result.memory_trace], [1020, 1020])

    def test_load_destination_can_equal_its_base_register(self):
        memory = [0] * 256
        memory[16] = 128
        result = self.cpu.run_program([0x04000093, 0x0000A083], initial_memory=memory)
        self.assertFalse(result.fault)
        self.assertEqual(result.registers[1], 128)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace], [("R", 64, 128)])
        self.assertEqual(memory[16], 128)

    def test_store_base_can_equal_store_data_register(self):
        result = self.cpu.run_program([0x04000093, 0x0010A023])
        self.assertFalse(result.fault)
        self.assertEqual(result.memory[16], 64)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace], [("W", 64, 64)])

    def test_store_overwrite_is_seen_by_the_next_load(self):
        result = self.cpu.run_program([0x04000093, 0x00100113, 0x0020A023,
                                       0x00200113, 0x0020A023, 0x0000A183])
        self.assertFalse(result.fault)
        self.assertEqual(result.memory[16], 2)
        self.assertEqual(result.registers[3], 2)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace],
                         [("W", 64, 1), ("W", 64, 2), ("R", 64, 2)])

    def test_load_x0_still_reads_data_and_store_x0_clears_ram(self):
        result = self.cpu.run_program([0x00002003, 0x00002023], initial_memory=[0xDEADBEEF])
        self.assertFalse(result.fault)
        self.assertEqual([(t.rd, t.value) for t in result.trace], [(0, 0), (0, 0)])
        self.assertEqual(result.memory[0], 0)
        self.assertEqual(result.registers[0], 0)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace],
                         [("R", 0, 0xDEADBEEF), ("W", 0, 0)])

    def test_bad_load_store_addresses_fault_without_commit_or_bus_request(self):
        for word in (0x00202183, 0x00202123, 0x40002183, 0x40202023,
                     0xFFC02183, 0xFE202E23, 0x00202003, 0x7FF02183, 0x7E202FA3):
            with self.subTest(word=f"{word:08X}"):
                result = self.cpu.run_program([0x00700113, word, 0x00202023], initial_memory=[9])
                self.assertTrue(result.fault)
                self.assertEqual((result.pc, result.fault_pc), (4, 4))
                self.assertEqual(len(result.trace), 1)
                self.assertEqual(result.registers[2], 7)
                self.assertEqual(result.registers[3], 0)
                self.assertEqual(result.memory, (9,) + (0,) * 255)
                self.assertEqual(result.memory_trace, ())

    def test_reserved_load_store_encodings_are_rejected(self):
        for base, reserved in ((0x00000183, (3, 6, 7)), (0x00200023, (3, 4, 5, 6, 7))):
            for funct3 in reserved:
                with self.subTest(funct3=funct3, base=base):
                    result = self.cpu.run_program([base | (funct3 << 12)], initial_memory=[9])
                    self.assertTrue(result.fault)
                    self.assertEqual(result.trace, ())
                    self.assertEqual(result.memory_trace, ())
                    self.assertEqual(result.memory[0], 9)

    def test_reset_reference_clears_registers_and_keeps_initial_memory(self):
        warmup = self.cpu.run_program([0x00C00093, 0x00102023])
        result = self.cpu.run_program([0x00002103], initial_memory=warmup.memory)
        self.assertFalse(result.fault)
        self.assertEqual(result.registers[1:3], (0, 12))
        self.assertEqual(result.memory, warmup.memory)
        self.assertEqual([(t.mode, t.address, t.value) for t in result.memory_trace], [("R", 0, 12)])

    def test_initial_ram_is_copied_padded_and_validated(self):
        memory = [0x12345678]
        result = self.cpu.run_program([0x00002083], initial_memory=memory)
        self.assertEqual(result.registers[1], 0x12345678)
        self.assertEqual(result.memory, (0x12345678,) + (0,) * 255)
        self.assertEqual(memory, [0x12345678])
        for initial, error in [([0] * 257, ValueError), ([-1], ValueError),
                               ([1 << 32], ValueError), ([True], TypeError), ([0.5], TypeError)]:
            with self.subTest(error=error, initial_length=len(initial)), self.assertRaises(error):
                self.cpu.run_program([], initial_memory=initial)

    def test_branch_and_jump_encoders_match_literal_scattered_fields(self):
        for name, expected in [("BEQ", 0x00208463), ("BNE", 0x00209463),
                               ("BLT", 0x0020C463), ("BGE", 0x0020D463),
                               ("BLTU", 0x0020E463), ("BGEU", 0x0020F463)]:
            with self.subTest(name=name):
                self.assertEqual(self.cpu.encode_branch(name, 1, 2, 8), expected)
                self.assertEqual(getattr(self.cpu, "encode_" + name.lower())(1, 2, 8), expected)
        self.assertEqual(self.cpu.encode_branch("BLT", 1, 2, -8), 0xFE20CCE3)
        self.assertEqual(self.cpu.encode_beq(1, 2, -4096), 0x80208063)
        self.assertEqual(self.cpu.encode_beq(1, 2, 4094), 0x7E208FE3)
        for offset, expected in [(8, 0x008000EF), (-4, 0xFFDFF0EF),
                                  (-1048576, 0x800000EF), (1048574, 0x7FFFF0EF)]:
            with self.subTest(offset=offset):
                self.assertEqual(self.cpu.encode_jal(1, offset), expected)
        self.assertEqual(self.cpu.encode_jalr(1, 2, -4), 0xFFC100E7)

    def test_control_encoders_reject_odd_offsets_and_out_of_range_fields(self):
        for offset in (-4098, 4096, -1, 1):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.cpu.encode_beq(1, 2, offset)
        for offset in (-1048578, 1048576, -1, 1):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.cpu.encode_jal(1, offset)
        for function, operands in [("encode_branch", ("BAL", 1, 2, 0)),
                                   ("encode_branch", ("BEQ", 32, 2, 0)),
                                   ("encode_jal", (32, 0)), ("encode_jalr", (1, 0, 2048))]:
            with self.subTest(function=function), self.assertRaises(ValueError):
                getattr(self.cpu, function)(*operands)

    def test_trace_records_fallthrough_next_pc(self):
        result = self.cpu.run_program([0x00500093, 0x00700113, 0x002081B3])
        self.assertEqual([entry.next_pc for entry in result.trace], [4, 8, 12])

    def test_six_branch_conditions_distinguish_signed_and_unsigned_operands(self):
        for word, taken in [(0x00208463, False), (0x00209463, True),
                            (0x0020C463, True), (0x0020D463, False),
                            (0x0020E463, False), (0x0020F463, True)]:
            with self.subTest(word=word):
                result = self.cpu.run_program([0xFFF00093, 0x00100113, word,
                                               0x06300193, 0x00700193])
                self.assertFalse(result.fault)
                self.assertEqual([entry.pc for entry in result.trace],
                                 [0, 4, 8, 16] if taken else [0, 4, 8, 12, 16])
                self.assertEqual((result.trace[2].rd, result.trace[2].value), (0, 0))
                self.assertEqual(result.trace[2].next_pc, 16 if taken else 12)
                self.assertEqual(result.registers[1:3], (0xFFFFFFFF, 1))

    def test_branch_signed_minimum_comparison_does_not_use_subtraction_sign(self):
        result = self.cpu.run_program([0x00100093, 0x01F09093, 0x00100113,
                                       0x0020C463, 0x00000000, 0x00700193])
        self.assertFalse(result.fault)
        self.assertEqual([entry.pc for entry in result.trace], [0, 4, 8, 12, 20])
        self.assertEqual(result.registers[3], 7)

    def test_loop_demo_executes_ten_rounds_and_sums_one_through_ten(self):
        result = self.cpu.run_program([0x00100093, 0x00B00113, 0x00000193,
                                       0x001181B3, 0x00108093, 0xFE20CCE3,
                                       0x04302023, 0x04002203])
        self.assertFalse(result.fault)
        self.assertEqual(len(result.trace), 35)
        self.assertEqual([entry.pc for entry in result.trace],
                         [0, 4, 8] + [12, 16, 20] * 10 + [24, 28])
        self.assertEqual([entry.next_pc for entry in result.trace if entry.pc == 20], [12] * 9 + [24])
        self.assertEqual(result.registers[1:5], (11, 11, 55, 55))
        self.assertEqual(result.memory[16], 55)
        self.assertEqual([(e.mode, e.address, e.value) for e in result.memory_trace],
                         [("W", 64, 55), ("R", 64, 55)])

    def test_untaken_halfword_target_is_ignored_but_taken_target_faults(self):
        untaken = self.cpu.run_program([0x00001163, 0x00700093])
        self.assertFalse(untaken.fault)
        self.assertEqual([entry.next_pc for entry in untaken.trace], [4, 8])
        taken = self.cpu.run_program([0x00000163, 0x00700093])
        self.assertTrue(taken.fault)
        self.assertEqual(taken.trace, ())
        self.assertEqual(taken.pc, 0)

    def test_jal_writes_pc_plus_four_and_skips_an_illegal_instruction_or_store(self):
        for skipped in (0x00000000, 0x00102023):
            with self.subTest(skipped=skipped):
                result = self.cpu.run_program([0x008000EF, skipped, 0x00700113])
                self.assertFalse(result.fault)
                self.assertEqual([(e.pc, e.next_pc) for e in result.trace], [(0, 8), (8, 12)])
                self.assertEqual(result.registers[1:3], (4, 7))
                self.assertEqual(result.memory_trace, ())

    def test_negative_jal_offset_uses_current_pc_and_link_is_not_target(self):
        result = self.cpu.run_program([0x0080006F, 0x0080016F, 0xFFDFF0EF, 0x00700193])
        self.assertFalse(result.fault)
        self.assertEqual([entry.pc for entry in result.trace], [0, 8, 4, 12])
        self.assertEqual(result.registers[1:4], (12, 8, 7))

    def test_jalr_clears_bit_zero_uses_old_base_and_discards_x0_link(self):
        for setup, jump, register, link in [(0x00D00093, 0x00008167, 2, 8),
                                           (0x00C00093, 0x000080E7, 1, 8),
                                           (0x00D00093, 0x00008067, 0, 0)]:
            with self.subTest(jump=jump):
                result = self.cpu.run_program([setup, jump, 0x00000000, 0x00700193])
                self.assertFalse(result.fault)
                self.assertEqual([entry.pc for entry in result.trace], [0, 4, 12])
                self.assertEqual(result.registers[register], link)
                self.assertEqual(result.registers[3], 7)

    def test_jalr_negative_offset_and_thirty_two_bit_target_wrap(self):
        for setup, jump in [(0x01000113, 0xFFC100E7), (0xFFC00113, 0x010100E7)]:
            with self.subTest(setup=setup):
                result = self.cpu.run_program([setup, jump, 0x00000000, 0x00700193])
                self.assertFalse(result.fault)
                self.assertEqual(result.registers[1], 8)
                self.assertEqual([entry.pc for entry in result.trace], [0, 4, 12])

    def test_bad_control_targets_fault_without_link_or_memory_side_effects(self):
        for words, pc, saved_x1 in [([0x002000EF], 0, 0), ([0x400000EF], 0, 0),
                                    ([0xFFDFF0EF], 0, 0), ([0x40000063], 0, 0),
                                    ([0xFE000EE3], 0, 0),
                                    ([0x00300093, 0x000080E7], 4, 3),
                                    ([0x40000093, 0x000080E7], 4, 1024)]:
            with self.subTest(words=words):
                result = self.cpu.run_program(words, initial_memory=[9])
                self.assertTrue(result.fault)
                self.assertEqual((result.pc, result.fault_pc), (pc, pc))
                self.assertEqual(result.registers[1], saved_x1)
                self.assertEqual(result.memory[0], 9)
                self.assertEqual(result.memory_trace, ())
                self.assertEqual(len(result.trace), 1 if pc else 0)

    def test_jump_and_branch_can_reach_last_rom_word_in_two_commits(self):
        for first in (0x3FC000EF, 0x3E000E63):
            with self.subTest(first=first):
                result = self.cpu.run_program([first] + [0x00000013] * 254 + [0x00700113])
                self.assertFalse(result.fault)
                self.assertEqual([entry.pc for entry in result.trace], [0, 1020])
                self.assertEqual(result.pc, 1024)
                self.assertEqual(result.registers[2], 7)

    def test_fault_pc_after_jump_is_the_executed_pc_not_retired_times_four(self):
        result = self.cpu.run_program([0x0080006F, 0x00000013, 0x00000163])
        self.assertTrue(result.fault)
        self.assertEqual(len(result.trace), 1)
        self.assertEqual((result.pc, result.fault_pc), (8, 8))

    def test_reserved_branch_and_jalr_funct3_are_illegal(self):
        for word in [0x00002063, 0x00003063] + [0x00000067 | (f3 << 12) for f3 in range(1, 8)]:
            with self.subTest(word=word):
                result = self.cpu.run_program([word])
                self.assertTrue(result.fault)
                self.assertEqual(result.trace, ())
                self.assertEqual(result.pc, 0)

    def test_step_limit_detects_loops_and_allows_exact_finite_completion(self):
        with self.assertRaises(RuntimeError):
            self.cpu.run_program([0x0000006F], max_steps=3)
        result = self.cpu.run_program([0x0040006F], max_steps=1)
        self.assertFalse(result.fault)
        self.assertEqual(result.pc, 4)
        for limit, error in [(0, ValueError), (-1, ValueError), (True, TypeError)]:
            with self.subTest(limit=limit), self.assertRaises(error):
                self.cpu.run_program([], max_steps=limit)


class TinyCPUVectorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("tools.generate_cpu_vectors"),
                             "the CPU vector generator is not implemented")
        self.generator = importlib.import_module("tools.generate_cpu_vectors")

    def test_demo_files_have_literal_expected_values(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            demo = next(case for case in report["cases"] if case["name"] == "demo")
            self.assertEqual((directory / demo["program_file"]).read_text(),
                             "00500093\n00700113\n002081B3\n")
            self.assertEqual((directory / demo["trace_file"]).read_text(),
                             "00000000 00500093 1 00000005 00000004\n"
                             "00000004 00700113 2 00000007 00000008\n"
                             "00000008 002081B3 3 0000000C 0000000C\n")
            self.assertEqual((directory / demo["registers_file"]).read_text(),
                             "00000005\n00000007\n0000000C\n" + "00000000\n" * 28)
            self.assertEqual(demo["retired_count"], 3)
            self.assertFalse(demo["expect_fault"])

    def test_json_and_tcl_describe_bounded_and_parseable_cases(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            metadata = json.loads((directory / "cpu_cases.json").read_text())
            self.assertEqual(metadata, report)
            self.assertEqual(report["case_count"], len(report["cases"]))
            self.assertEqual(report["instruction_count"],
                             sum(case["retired_count"] for case in report["cases"]))
            names = [case["name"] for case in report["cases"]]
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue({"demo", "alu_demo", "shift_immediate", "register_shifts",
                             "logic_immediate", "logic_register", "sltiu_negative_immediate",
                             "reset_during_fetch", "reset_after_write"}.issubset(names))
            tcl = (directory / "cpu_cases.tcl").read_text()
            self.assertTrue(tcl.startswith("set tiny_cpu_cases {\n"))
            self.assertTrue(tcl.endswith("}\n"))
            for case in report["cases"]:
                self.assertIsInstance(case["expect_fault"], bool)
                self.assertIsInstance(case["inject_reset"], bool)
                self.assertEqual(case["fault_pc"] % 4, 0)
                for key in ("program_file", "trace_file", "registers_file", "memory_file", "memory_trace_file"):
                    relative = Path(case[key])
                    self.assertFalse(relative.is_absolute())
                    self.assertNotIn("\\", case[key])
                    self.assertTrue((directory / relative).is_file())
                program = (directory / case["program_file"]).read_text().splitlines()
                self.assertTrue(1 <= len(program) <= 256)
                self.assertTrue(all(re.fullmatch(r"[0-9A-F]{8}", line) for line in program))
                trace = (directory / case["trace_file"]).read_text().splitlines()
                self.assertEqual(len(trace), case["retired_count"])
                self.assertTrue(all(re.fullmatch(r"[0-9A-F]{8} [0-9A-F]{8} [0-9]+ [0-9A-F]{8} [0-9A-F]{8}",
                                                  line) for line in trace))
                registers = (directory / case["registers_file"]).read_text().splitlines()
                self.assertEqual(len(registers), 31)
                memory = (directory / case["memory_file"]).read_text().splitlines()
                self.assertEqual(len(memory), 256)
                self.assertTrue(all(re.fullmatch(r"[0-9A-F]{8}", line) for line in memory))
                memory_trace = (directory / case["memory_trace_file"]).read_text().splitlines()
                self.assertEqual(len(memory_trace), case["memory_count"])
                self.assertIsInstance(case["reset_during_load"], bool)
                expected_row = (f"  {{{case['name']} {case['program_file']} "
                                f"{case['trace_file']} {case['registers_file']} "
                                f"{case['retired_count']} {str(case['expect_fault']).lower()} "
                                f"{case['fault_pc']} {str(case['inject_reset']).lower()} "
                                f"{case['memory_file']} {case['memory_trace_file']} "
                                f"{str(case['reset_during_load']).lower()}}}")
                self.assertIn(expected_row, tcl.splitlines())

    def test_reset_case_restarts_the_same_demo_and_fault_case_excludes_bad_word(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            cases = {case["name"]: case for case in report["cases"]}
            reset, demo = cases["reset_during_fetch"], cases["demo"]
            self.assertTrue(reset["inject_reset"])
            self.assertEqual(reset["retired_count"], 3)
            for key in ("program_file", "trace_file", "registers_file"):
                self.assertEqual((directory / reset[key]).read_bytes(),
                                 (directory / demo[key]).read_bytes())
            fault = cases["prefix_then_fault"]
            self.assertTrue(fault["expect_fault"])
            self.assertEqual(fault["fault_pc"], 12)
            self.assertEqual(fault["retired_count"], 3)
            self.assertEqual((directory / fault["trace_file"]).read_bytes(),
                             (directory / demo["trace_file"]).read_bytes())

    def test_fixed_seed_random_vectors_and_metadata_are_reproducible(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            first, second = Path(temporary) / "first", Path(temporary) / "second"
            report = self.generator.generate_cpu_vectors(first)
            self.generator.generate_cpu_vectors(second)
            random_case = next(case for case in report["cases"] if case["name"] == "random_legal")
            self.assertTrue(32 <= random_case["retired_count"] <= 64)
            self.assertFalse(random_case["expect_fault"])
            self.assertIsInstance(report["seed"], int)
            first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
            second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
            self.assertEqual(first_files, second_files)
            for relative in first_files:
                self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes())

    def test_reset_after_write_has_cold_trace_for_a_dirty_register_dependency(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            cases = {case["name"]: case for case in report["cases"]}
            self.assertIn("reset_after_write", cases)
            case = cases["reset_after_write"]
            self.assertTrue(case["inject_reset"])
            self.assertFalse(case["expect_fault"])
            self.assertEqual(case["retired_count"], 3)
            self.assertEqual((directory / case["program_file"]).read_text(),
                             "00128093\n00900293\n005081B3\n")
            # The second commit dirties x5 to 9.  A reset that leaves registers
            # dirty would make the restarted first/third results 10 and 19.
            self.assertEqual((directory / case["trace_file"]).read_text(),
                             "00000000 00128093 1 00000001 00000004\n"
                             "00000004 00900293 5 00000009 00000008\n"
                             "00000008 005081B3 3 0000000A 0000000C\n")
            self.assertEqual((directory / case["registers_file"]).read_text(),
                             "00000001\n00000000\n0000000A\n00000000\n00000009\n"
                             + "00000000\n" * 26)

    def test_alu_demo_is_seven_fixed_instructions_and_shift_case_runs_early(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            self.assertEqual([case["name"] for case in report["cases"][:3]],
                             ["demo", "alu_demo", "shift_immediate"])
            case = report["cases"][1]
            self.assertEqual((directory / case["program_file"]).read_text(),
                             "FF800093\n00100113\n0020D1B3\n4020D233\n"
                             "0020A2B3\n0020B333\n00F0F393\n")
            self.assertEqual((directory / case["trace_file"]).read_text(),
                             "00000000 FF800093 1 FFFFFFF8 00000004\n"
                             "00000004 00100113 2 00000001 00000008\n"
                             "00000008 0020D1B3 3 7FFFFFFC 0000000C\n"
                             "0000000C 4020D233 4 FFFFFFFC 00000010\n"
                             "00000010 0020A2B3 5 00000001 00000014\n"
                             "00000014 0020B333 6 00000000 00000018\n"
                             "00000018 00F0F393 7 00000008 0000001C\n")
            self.assertEqual(case["retired_count"], 7)

    def test_metadata_and_random_program_cover_all_nineteen_alu_instructions(self):
        register_names = {(0, 0): "ADD", (0x20, 0): "SUB", (0, 1): "SLL",
                          (0, 2): "SLT", (0, 3): "SLTU", (0, 4): "XOR",
                          (0, 5): "SRL", (0x20, 5): "SRA", (0, 6): "OR", (0, 7): "AND"}
        immediate_names = {0: "ADDI", 2: "SLTI", 3: "SLTIU", 4: "XORI", 6: "ORI", 7: "ANDI"}
        expected = {"ADD", "SUB", "SLL", "SLT", "SLTU", "XOR", "SRL", "SRA", "OR", "AND",
                    "ADDI", "SLTI", "SLTIU", "XORI", "ORI", "ANDI", "SLLI", "SRLI", "SRAI"}
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            self.assertEqual(report["contract"], "tiny-cpu-rv32i-mul-v7")
            self.assertEqual(set(report["supported_instructions"]), expected | {"LW", "SW", "BEQ", "BNE", "BLT",
                                                                              "BGE", "BLTU", "BGEU", "JAL", "JALR",
                                                                              "LUI", "AUIPC", "LB", "LH", "LBU", "LHU", "SB", "SH", "MUL"})
            case = next(case for case in report["cases"] if case["name"] == "random_legal")
            observed = set()
            for line in (directory / case["program_file"]).read_text().splitlines():
                word = int(line, 16)
                opcode, funct3, funct7 = word & 0x7F, (word >> 12) & 7, word >> 25
                if opcode == 0x33:
                    observed.add(register_names[(funct7, funct3)])
                elif funct3 == 1:
                    self.assertEqual(funct7, 0)
                    observed.add("SLLI")
                elif funct3 == 5:
                    self.assertIn(funct7, (0, 0x20))
                    observed.add("SRAI" if funct7 == 0x20 else "SRLI")
                else:
                    observed.add(immediate_names[funct3])
            self.assertEqual(observed, expected)

    def test_memory_demo_files_use_byte_addresses_and_store_commits_are_zero(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            cases = {case["name"]: case for case in report["cases"]}
            self.assertIn("memory_demo", cases)
            case = cases["memory_demo"]
            self.assertEqual((directory / case["program_file"]).read_text(),
                             "04000093\n00C00113\n0020A023\n0000A183\n"
                             "00518213\n0040A223\n0040A283\n40328333\n")
            self.assertEqual((directory / case["memory_trace_file"]).read_text(),
                             "W 00000040 0000000C F\nR 00000040 0000000C F\n"
                             "W 00000044 00000011 F\nR 00000044 00000011 F\n")
            self.assertEqual((directory / case["memory_file"]).read_text(),
                             "00000000\n" * 16 + "0000000C\n00000011\n" + "00000000\n" * 238)
            self.assertEqual((case["retired_count"], case["memory_count"]), (8, 4))
            trace = (directory / case["trace_file"]).read_text().splitlines()
            self.assertEqual(trace[2], "00000008 0020A023 0 00000000 0000000C")
            self.assertEqual(trace[5], "00000014 0040A223 0 00000000 00000018")

    def test_pending_load_reset_case_replays_from_preserved_ram(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            cases = {case["name"]: case for case in report["cases"]}
            self.assertIn("reset_pending_load", cases)
            case = cases["reset_pending_load"]
            self.assertTrue(case["inject_reset"])
            self.assertTrue(case["reset_during_load"])
            self.assertEqual((directory / case["program_file"]).read_text(),
                             "00C00093\n00102023\n00002103\n00110193\n")
            self.assertEqual((directory / case["trace_file"]).read_text(),
                             "00000000 00C00093 1 0000000C 00000004\n"
                             "00000004 00102023 0 00000000 00000008\n"
                             "00000008 00002103 2 0000000C 0000000C\n"
                             "0000000C 00110193 3 0000000D 00000010\n")
            self.assertEqual((directory / case["memory_trace_file"]).read_text(),
                             "W 00000000 0000000C F\nR 00000000 0000000C F\n")
            self.assertEqual((case["retired_count"], case["memory_count"]), (4, 2))
            for name in ("reset_during_fetch", "reset_after_write"):
                self.assertFalse(cases[name]["reset_during_load"])

    def test_loop_demo_metadata_uses_dynamic_count_and_nonsequential_next_pc(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            cases = {case["name"]: case for case in report["cases"]}
            self.assertIn("loop_demo", cases)
            case = cases["loop_demo"]
            self.assertEqual((directory / case["program_file"]).read_text(),
                             "00100093\n00B00113\n00000193\n001181B3\n"
                             "00108093\nFE20CCE3\n04302023\n04002203\n")
            self.assertEqual((case["retired_count"], case["memory_count"]), (35, 2))
            rows = (directory / case["trace_file"]).read_text().splitlines()
            self.assertEqual(rows[5], "00000014 FE20CCE3 0 00000000 0000000C")
            self.assertEqual(rows[-3], "00000014 FE20CCE3 0 00000000 00000018")
            self.assertEqual((directory / case["memory_trace_file"]).read_text(),
                             "W 00000040 00000037 F\nR 00000040 00000037 F\n")

    def test_upper_demo_metadata_preserves_skipped_store_and_pc_relative_target(self):
        with tempfile.TemporaryDirectory(prefix="tiny-cpu-") as temporary:
            directory = Path(temporary)
            report = self.generator.generate_cpu_vectors(directory)
            case = next(case for case in report["cases"] if case["name"] == "upper_demo")
            self.assertEqual((directory / case["program_file"]).read_text(),
                             "123450B7\n67808093\n04102023\n04002103\n00000197\n"
                             "01018193\n00018267\n04002023\n04002283\n")
            self.assertEqual((case["retired_count"], case["memory_count"]), (8, 3))
            rows = (directory / case["trace_file"]).read_text().splitlines()
            self.assertEqual(rows[4], "00000010 00000197 3 00000010 00000014")
            self.assertEqual(rows[6], "00000018 00018267 4 0000001C 00000020")
            self.assertEqual(rows[7], "00000020 04002283 5 12345678 00000024")
            self.assertEqual((directory / case["memory_trace_file"]).read_text(),
                             "W 00000040 12345678 F\nR 00000040 12345678 F\nR 00000040 12345678 F\n")


if __name__ == "__main__":
    unittest.main()
