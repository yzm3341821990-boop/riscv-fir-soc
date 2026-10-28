"""Literal state transitions for the register-file contract."""

from pathlib import Path
import tempfile
import unittest

from model import regfile
from tools import generate_regfile_vectors


class RegisterFileTests(unittest.TestCase):
    def setUp(self):
        self.registers = regfile.RegisterFileReference()

    def test_x0_is_zero_before_reset(self):
        self.assertEqual(self.registers.read(0), 0)

    def test_ordinary_power_on_contents_are_not_assumed(self):
        with self.assertRaises(RuntimeError):
            self.registers.read(1)

    def test_reset_clears_every_register(self):
        self.registers.edge(1, 0, 0, 0)
        self.assertEqual([self.registers.read(i) for i in range(32)], [0] * 32)

    def test_writes_preserve_other_addresses(self):
        self.registers.edge(1, 0, 0, 0)
        self.registers.edge(0, 1, 1, 5)
        self.registers.edge(0, 1, 2, 7)
        self.assertEqual(self.registers.read(1), 5)
        self.assertEqual(self.registers.read(2), 7)
        self.assertEqual(self.registers.read(3), 0)

    def test_disabled_write_holds_old_data(self):
        self.registers.edge(1, 0, 0, 0)
        self.registers.edge(0, 1, 1, 5)
        self.registers.edge(0, 0, 1, 0xDEADBEEF)
        self.assertEqual(self.registers.read(1), 5)

    def test_x0_cannot_be_written(self):
        self.registers.edge(1, 0, 0, 0)
        self.registers.edge(0, 1, 1, 5)
        self.registers.edge(0, 1, 0, 0xFFFFFFFF)
        self.assertEqual(self.registers.read(0), 0)
        self.assertEqual(self.registers.read(1), 5)

    def test_overwrite_and_highest_address(self):
        self.registers.edge(1, 0, 0, 0)
        self.registers.edge(0, 1, 31, 0xFFFFFFFF)
        self.assertEqual(self.registers.read(31), 0xFFFFFFFF)
        self.registers.edge(0, 1, 31, 0x80000000)
        self.assertEqual(self.registers.read(31), 0x80000000)

    def test_reset_has_priority_over_write(self):
        self.registers.edge(1, 0, 0, 0)
        self.registers.edge(0, 1, 1, 9)
        self.registers.edge(0, 1, 2, 7)
        self.registers.edge(1, 1, 1, 0xDEADBEEF)
        self.assertEqual([self.registers.read(i) for i in range(32)], [0] * 32)

    def test_illegal_port_values_are_rejected(self):
        for address in (-1, 32):
            with self.subTest(address=address), self.assertRaises(ValueError):
                self.registers.read(address)
        for values in [(2, 0, 0, 0), (0, 2, 0, 0), (0, 1, 32, 0), (0, 1, 1, 1 << 32)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.registers.edge(*values)
        with self.assertRaises(TypeError):
            self.registers.read(1.0)

    def test_vectors_have_literal_before_and_after_values(self):
        with tempfile.TemporaryDirectory(prefix="regfile-vectors-") as temporary:
            first, second = Path(temporary) / "a", Path(temporary) / "b"
            report = generate_regfile_vectors.generate_regfile_vectors(first)
            generate_regfile_vectors.generate_regfile_vectors(second)
            text = (first / "regfile_vectors.txt").read_text()
            self.assertEqual(report["cycle_count"], 1610)
            self.assertEqual(len(text.splitlines()), 1610)
            self.assertEqual(text.splitlines()[1],
                             "0 1 1 00000005 1 0 00000000 00000000 00000005 00000000")
            self.assertEqual(text.splitlines()[6],
                             "1 1 1 DEADBEEF 1 2 00000009 00000007 00000000 00000000")
            for name in ("regfile_vectors.txt", "regfile_vectors.json", "regfile_trace.csv", "vector_count.tcl"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
