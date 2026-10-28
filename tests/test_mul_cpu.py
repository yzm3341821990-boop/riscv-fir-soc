"""MUL low-word results, using literals and an independent bitwise oracle."""
import random
import unittest
from model import tiny_cpu as cpu


def load32(rd, value):
    high=((value+2048)>>12)&0xFFFFF
    low=value&0xFFF
    return [cpu.encode_lui(rd,high),cpu.encode_addi(rd,rd,low-4096 if low>=2048 else low)]


class MultiplyTests(unittest.TestCase):
    def test_encoding_is_the_standard_mul_word(self):
        self.assertEqual(cpu.encode_op('MUL',3,1,2),0x022081B3)

    def test_literal_sign_overflow_and_high_input_bits(self):
        for a,b,expected in [(0,0xFFFFFFFF,0),(7,9,63),(0xFFFFFFF9,9,0xFFFFFFC1),
                             (0xFFFFFFFF,0xFFFFFFFF,1),(0x80000000,0xFFFFFFFF,0x80000000),
                             (0x7FFFFFFF,2,0xFFFFFFFE),(0x10001,0x10001,0x20001),
                             (0x8000,0x8000,0x40000000)]:
            with self.subTest(a=a,b=b):
                r=cpu.run_program(load32(1,a)+load32(2,b)+[0x022081B3])
                self.assertFalse(r.fault)
                self.assertEqual(r.registers[3],expected)

    def test_random_products_match_shift_add_oracle(self):
        rng=random.Random(0x4D554C)
        for _ in range(96):
            a,b=rng.randrange(1<<32),rng.randrange(1<<32)
            expected=sum(a<<bit for bit in range(32) if (b>>bit)&1)&0xFFFFFFFF
            r=cpu.run_program(load32(1,a)+load32(2,b)+[0x022081B3])
            self.assertFalse(r.fault)
            self.assertEqual(r.registers[3],expected)

    def test_destination_alias_x0_and_dependency(self):
        for rd in (0,1,2,31):
            words=[cpu.encode_addi(1,0,-7),cpu.encode_addi(2,0,9),cpu.encode_op('MUL',rd,1,2)]
            r=cpu.run_program(words+[cpu.encode_addi(3,rd,1)])
            self.assertFalse(r.fault)
            self.assertEqual(r.trace[2].value,0 if rd==0 else 0xFFFFFFC1)
            self.assertEqual(r.registers[3],1 if rd==0 else 0xFFFFFFC2)

    def test_remaining_m_instructions_still_fault_without_side_effects(self):
        for funct3 in range(1,8):
            r=cpu.run_program([0x022081B3|(funct3<<12)])
            self.assertTrue(r.fault)
            self.assertEqual((r.trace,r.memory_trace),((),()))


if __name__=='__main__':unittest.main()
