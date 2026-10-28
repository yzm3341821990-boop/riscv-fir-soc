"""Independent literal checks for the future ALU's 32-bit semantics."""

from pathlib import Path
import tempfile
import unittest

from model import alu
from tools import generate_alu_vectors


class ALUModelTests(unittest.TestCase):
    model = alu

    def test_add_and_subtract_wrap_to_32_bits(self):
        for operation, a, b, expected in [
                (0, 0xFFFFFFFF, 1, 0), (0, 0x7FFFFFFF, 1, 0x80000000),
                (1, 0, 1, 0xFFFFFFFF), (1, 0x80000000, 1, 0x7FFFFFFF)]:
            with self.subTest(operation=operation, a=a, b=b):
                self.assertEqual(self.model.alu_result(a, b, operation), expected)

    def test_complementary_bit_patterns(self):
        self.assertEqual(self.model.alu_result(0x55AA55AA, 0xAA55AA55, 2), 0)
        self.assertEqual(self.model.alu_result(0x55AA55AA, 0xAA55AA55, 3), 0xFFFFFFFF)
        self.assertEqual(self.model.alu_result(0x55AA55AA, 0xAA55AA55, 4), 0xFFFFFFFF)

    def test_signed_and_logical_right_shifts_differ(self):
        self.assertEqual(self.model.alu_result(0x80000000, 1, 6), 0x40000000)
        self.assertEqual(self.model.alu_result(0x80000000, 1, 7), 0xC0000000)
        self.assertEqual(self.model.alu_result(0x80000001, 31, 5), 0x80000000)
        self.assertEqual(self.model.alu_result(0x80000001, 31, 7), 0xFFFFFFFF)

    def test_shift_amount_uses_only_low_five_bits(self):
        for operation in (5, 6, 7):
            with self.subTest(operation=operation):
                self.assertEqual(self.model.alu_result(0x89ABCDEF, 32, operation), 0x89ABCDEF)
                self.assertEqual(self.model.alu_result(0x80000000, 0xFFFFFFE1, operation),
                                 self.model.alu_result(0x80000000, 1, operation))

    def test_signed_unsigned_and_equal_comparisons(self):
        for operation, a, b, expected in [
                (8, 0xFFFFFFFF, 1, 1), (9, 0xFFFFFFFF, 1, 0),
                (8, 0x80000000, 0, 1), (9, 0x80000000, 0, 0),
                (8, 0x80000000, 0x80000000, 0), (9, 7, 7, 0)]:
            with self.subTest(operation=operation, a=a, b=b):
                self.assertEqual(self.model.alu_result(a, b, operation), expected)

    def test_unassigned_binary_opcodes_return_zero(self):
        for operation in range(10, 16):
            with self.subTest(operation=operation):
                self.assertEqual(self.model.alu_result(0xFFFFFFFF, 0xFFFFFFFF, operation), 0)

    def test_reference_rejects_values_outside_port_widths(self):
        for a, b, operation in [(-1, 0, 0), (1 << 32, 0, 0),
                                (0, 1 << 32, 0), (0, 0, 16)]:
            with self.subTest(a=a, b=b, operation=operation), self.assertRaises(ValueError):
                self.model.alu_result(a, b, operation)
        with self.assertRaises(TypeError):
            self.model.alu_result(True, 0, 0)

    def test_vectors_are_reproducible_and_contain_literal_sra_case(self):
        with tempfile.TemporaryDirectory(prefix="alu-vectors-") as temporary:
            first, second = Path(temporary) / "a", Path(temporary) / "b"
            report = generate_alu_vectors.generate_alu_vectors(first)
            generate_alu_vectors.generate_alu_vectors(second)
            self.assertEqual(report["vector_count"], 4880)
            text = (first / "alu_vectors.txt").read_text()
            self.assertIn("7 80000000 00000001 C0000000\n", text)
            self.assertEqual(len(text.splitlines()), 4880)
            for name in ("alu_vectors.txt", "alu_vectors.json", "vector_count.tcl"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
