import importlib
import importlib.util
from fractions import Fraction
import random
import unittest


class RV32MReferenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('model.rv32m'),
                             'RV32M reference model has not been implemented')
        self.m = importlib.import_module('model.rv32m')

    def test_operation_encoding(self):
        self.assertEqual(self.m.OPERATIONS,
                         ('MUL', 'MULH', 'MULHSU', 'MULHU', 'DIV', 'DIVU', 'REM', 'REMU'))

    def test_low_multiply_wrap(self):
        for a, b, answer in [(7, 3, 21), (0xffffffff, 2, 0xfffffffe),
                             (0x80000000, 2, 0), (0x80000000, 0xffffffff, 0x80000000)]:
            self.assertEqual(self.m.evaluate('MUL', a, b), answer)

    def test_high_multiply_signedness(self):
        for op, a, b, answer in [
            ('MULH', 0xfffffffe, 3, 0xffffffff),
            ('MULH', 0x80000000, 0x80000000, 0x40000000),
            ('MULHSU', 1, 0xffffffff, 0),
            ('MULHSU', 0xffffffff, 0xffffffff, 0xffffffff),
            ('MULHSU', 0x80000000, 0xffffffff, 0x80000000),
            ('MULHU', 0xffffffff, 0xffffffff, 0xfffffffe),
        ]:
            self.assertEqual(self.m.evaluate(op, a, b), answer, (op, a, b))

    def test_signed_division_truncates_towards_zero(self):
        for a, b, q, rem in [(-7, 3, -2, -1), (7, -3, -2, 1),
                              (-7, -3, 2, -1), (1, 2, 0, 1)]:
            self.assertEqual(self.m.evaluate('DIV', a, b), q & 0xffffffff)
            self.assertEqual(self.m.evaluate('REM', a, b), rem & 0xffffffff)

    def test_division_by_zero(self):
        for a in [0, 1, 7, 0xffffffff, 0x80000000]:
            for op in ['DIV', 'DIVU']:
                self.assertEqual(self.m.evaluate(op, a, 0), 0xffffffff)
            for op in ['REM', 'REMU']:
                self.assertEqual(self.m.evaluate(op, a, 0), a)

    def test_signed_overflow(self):
        self.assertEqual(self.m.evaluate('DIV', 0x80000000, 0xffffffff), 0x80000000)
        self.assertEqual(self.m.evaluate('REM', 0x80000000, 0xffffffff), 0)

    def test_unsigned_division(self):
        self.assertEqual(self.m.evaluate('DIVU', 0xffffffff, 2), 0x7fffffff)
        self.assertEqual(self.m.evaluate('REMU', 0xffffffff, 2), 1)
        self.assertEqual(self.m.evaluate('DIVU', 0x80000000, 0xffffffff), 0)
        self.assertEqual(self.m.evaluate('REMU', 0x80000000, 0xffffffff), 0x80000000)

    def test_division_against_independent_fraction_oracle(self):
        rng = random.Random(2301)
        for _ in range(1500):
            raw_a, raw_b = rng.getrandbits(32), rng.getrandbits(32)
            if raw_b == 0:
                continue
            a = raw_a if raw_a < 2**31 else raw_a - 2**32
            b = raw_b if raw_b < 2**31 else raw_b - 2**32
            q = int(Fraction(a, b))
            self.assertEqual(self.m.evaluate('DIV', raw_a, raw_b), q & 0xffffffff)
            self.assertEqual(self.m.evaluate('REM', raw_a, raw_b), (a - q*b) & 0xffffffff)
            self.assertEqual(self.m.evaluate('DIVU', raw_a, raw_b), raw_a // raw_b)
            self.assertEqual(self.m.evaluate('REMU', raw_a, raw_b), raw_a % raw_b)

    def test_operands_are_word_sized(self):
        self.assertEqual(self.m.evaluate('MUL', 2**32 + 7, -1), 0xfffffff9)

    def test_invalid_operation_rejected(self):
        with self.assertRaises(ValueError):
            self.m.evaluate('DIVW', 7, 3)


if __name__ == '__main__':
    unittest.main()
