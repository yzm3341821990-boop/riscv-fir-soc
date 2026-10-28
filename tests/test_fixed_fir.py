"""Numerical-contract tests; expectations never call the model under test."""

import math
import random
import unittest
from fractions import Fraction

from model import fixed_fir


def rational_oracle(samples, coefficients):
    """Independent scatter convolution followed by rational rounding."""
    accumulators = [0] * len(samples)
    for source_index, sample in enumerate(samples):
        for delay, coefficient in enumerate(coefficients):
            target_index = source_index + delay
            if target_index < len(samples):
                accumulators[target_index] += sample * coefficient
    outputs = []
    for accumulator in accumulators:
        value = Fraction(accumulator, 32768)
        lower = abs(value.numerator) // value.denominator
        remainder = abs(value) - lower
        magnitude = lower + int(remainder >= Fraction(1, 2))
        rounded = -magnitude if value < 0 else magnitude
        outputs.append(min(32767, max(-32768, rounded)))
    return tuple(accumulators), tuple(outputs)


class FixedFIRTests(unittest.TestCase):
    fir = fixed_fir

    def test_positive_rounding_around_half_lsb(self):
        for accumulator, expected in [(0, 0), (16383, 0), (16384, 1),
                                      (16385, 1), (49151, 1), (49152, 2)]:
            with self.subTest(accumulator=accumulator):
                self.assertEqual(self.fir.round_shift(accumulator), expected)

    def test_negative_rounding_around_half_lsb(self):
        # Catches arithmetic-shift truncation and ties-to-even rounding.
        for accumulator, expected in [(-16383, 0), (-16384, -1),
                                      (-16385, -1), (-49151, -1), (-49152, -2)]:
            with self.subTest(accumulator=accumulator):
                self.assertEqual(self.fir.round_shift(accumulator), expected)

    def test_rounding_other_shifts_and_large_integers(self):
        self.assertEqual(self.fir.round_shift(-7, 0), -7)
        self.assertEqual(self.fir.round_shift(-5, 1), -3)
        self.assertEqual(self.fir.round_shift((1 << 70) + 16384), (1 << 55) + 1)

    def test_rounding_rejects_invalid_shift_or_value(self):
        with self.assertRaises(ValueError):
            self.fir.round_shift(1, -1)
        for value in [1.5, True, "1"]:
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.fir.round_shift(value)
        with self.assertRaises(TypeError):
            self.fir.round_shift(1, 1.5)

    def test_saturation_clips_instead_of_wrapping(self):
        for value, expected in [(-10**9, -32768), (-32769, -32768),
                                (-32768, -32768), (0, 0), (32767, 32767),
                                (32768, 32767), (10**9, 32767)]:
            with self.subTest(value=value):
                self.assertEqual(self.fir.saturate_i16(value), expected)
        with self.assertRaises(TypeError):
            self.fir.saturate_i16(1.0)

    def test_accumulator_conversion_rounds_then_saturates(self):
        for accumulator, expected in [(16384, 1), (-16384, -1),
                                      (32767 * 32768 + 16384, 32767),
                                      (-32768 * 32768 - 16384, -32768),
                                      ((1 << 39) - 1, 32767),
                                      (-(1 << 39), -32768)]:
            with self.subTest(accumulator=accumulator):
                self.assertEqual(self.fir.accumulator_to_q15(accumulator), expected)

    def test_accumulator_overflow_is_rejected(self):
        for value in [1 << 39, -(1 << 39) - 1]:
            with self.subTest(value=value), self.assertRaises(OverflowError):
                self.fir.accumulator_to_q15(value)

    def test_float_quantization_is_explicit_and_saturating(self):
        for value, expected in [(0, 0), (0.5, 16384), (-0.5, -16384),
                                (1 / 65536, 1), (-1 / 65536, -1),
                                (1, 32767), (-1, -32768),
                                (1e300, 32767), (-1e300, -32768)]:
            with self.subTest(value=value):
                self.assertEqual(self.fir.quantize_q15(value), expected)

    def test_quantization_rejects_nonfinite_and_non_numeric(self):
        for value in [math.nan, math.inf, -math.inf]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.fir.quantize_q15(value)
        for value in [True, "0.5", complex(1, 1)]:
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.fir.quantize_q15(value)

    def test_zero_input_and_output_length(self):
        result = self.fir.fir_block([0] * 64, [32767] * 32)
        self.assertEqual(result.outputs, (0,) * 64)
        self.assertEqual(result.accumulators, (0,) * 64)

    def test_empty_block_has_no_output(self):
        result = self.fir.fir_block([], [0] * 32)
        self.assertEqual(result.outputs, ())
        self.assertEqual(result.accumulators, ())

    def test_half_scale_impulse_preserves_coefficient_order(self):
        coefficients = [1024, -2048, 4096, 8192] + [0] * 28
        result = self.fir.fir_block([16384] + [0] * 35, coefficients)
        self.assertEqual(result.outputs, (512, -1024, 2048, 4096) + (0,) * 32)

    def test_hand_computed_causal_convolution(self):
        coefficients = [16384, -8192, 4096] + [0] * 29
        result = self.fir.fir_block([16384, 8192, -8192, 0], coefficients)
        self.assertEqual(result.accumulators,
                         (268435456, 0, -134217728, 100663296))
        self.assertEqual(result.outputs, (8192, 0, -4096, 3072))

    def test_step_builds_from_zero_history(self):
        result = self.fir.fir_block([16384] * 5,
                                   [16384, 8192, -4096] + [0] * 29)
        self.assertEqual(result.outputs, (8192, 12288, 10240, 10240, 10240))

    def test_positive_and_negative_saturation_in_real_filter(self):
        positive = self.fir.fir_block([32767] * 33, [32767] * 32)
        negative = self.fir.fir_block([-32768] * 33, [32767] * 32)
        self.assertEqual(positive.outputs[:2], (32766, 32767))
        self.assertEqual(negative.outputs[:2], (-32767, -32768))

    def test_negative_extrema_need_more_than_signed_36_bits(self):
        result = self.fir.fir_block([-32768] * 32, [-32768] * 32)
        self.assertEqual(result.accumulators[-1], 34359738368)
        self.assertEqual(result.outputs[-1], 32767)

    def test_calls_reset_history(self):
        coefficients = [16384] * 32
        self.fir.fir_block([32767] * 32, coefficients)
        self.assertEqual(self.fir.fir_block([0] * 4, coefficients).outputs,
                         (0, 0, 0, 0))

    def test_input_containers_are_unchanged(self):
        samples, coefficients = [1, 2, 3], [16384] + [0] * 31
        self.fir.fir_block(samples, coefficients)
        self.assertEqual(samples, [1, 2, 3])
        self.assertEqual(coefficients, [16384] + [0] * 31)

    def test_iterable_inputs_are_supported(self):
        result = self.fir.fir_block(iter([1, -1, 3, -3]),
                                   iter([16384] + [0] * 31))
        self.assertEqual(result.outputs, (1, -1, 2, -2))

    def test_wrong_number_of_coefficients_is_rejected(self):
        for count in [0, 1, 31, 33]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.fir.fir_block([1], [0] * count)

    def test_out_of_range_samples_and_coefficients_are_rejected(self):
        for value in [-32769, 32768]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.fir.fir_block([value], [0] * 32)
                with self.assertRaises(ValueError):
                    self.fir.fir_block([0], [value] + [0] * 31)

    def test_float_and_boolean_raw_samples_are_rejected(self):
        for value in [0.5, True, "3"]:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.fir.fir_block([value], [0] * 32)
                with self.assertRaises(TypeError):
                    self.fir.fir_block([0], [value] + [0] * 31)

    def test_random_blocks_against_independent_rational_oracle(self):
        rng = random.Random(0xC0DE)
        for length in [0, 1, 7, 31, 32, 33, 64, 256, 1024]:
            samples = [rng.randint(-32768, 32767) for _ in range(length)]
            coefficients = [rng.randint(-8192, 8192) for _ in range(32)]
            expected_accumulators, expected_outputs = rational_oracle(
                samples, coefficients)
            with self.subTest(length=length):
                result = self.fir.fir_block(samples, coefficients)
                self.assertEqual(result.accumulators, expected_accumulators)
                self.assertEqual(result.outputs, expected_outputs)

    def test_memory_words_sign_extend_to_32_bits(self):
        for value, expected in [(0, "00000000"), (1, "00000001"),
                                (-1, "FFFFFFFF"), (-32768, "FFFF8000"),
                                (32767, "00007FFF")]:
            with self.subTest(value=value):
                self.assertEqual(self.fir.to_memory_word(value), expected)
                self.assertEqual(self.fir.from_memory_word(expected), value)

    def test_memory_word_parser_rejects_invalid_sign_extension(self):
        for word in ["0000FFFF", "00008000", "FFFF0001", "7FFF8000",
                     "FFFF", "0x000001", "GGGGGGGG", "000000000"]:
            with self.subTest(word=word), self.assertRaises(ValueError):
                self.fir.from_memory_word(word)
        with self.assertRaises(ValueError):
            self.fir.to_memory_word(32768)

    def test_memory_word_parser_accepts_lowercase(self):
        self.assertEqual(self.fir.from_memory_word("ffff8000"), -32768)


if __name__ == "__main__":
    unittest.main()
