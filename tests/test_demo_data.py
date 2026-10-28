"""Check the signal demonstration against declared numerical behavior."""

import cmath
import math
import unittest

from tools import demo_data


class DemoDataTests(unittest.TestCase):
    demo = demo_data

    def test_lowpass_coefficients_are_symmetric_and_near_unity_dc_gain(self):
        data = self.demo.make_demo_data()
        coefficients = data["coefficients"]
        self.assertEqual(len(coefficients), 32)
        self.assertEqual(coefficients, list(reversed(coefficients)))
        self.assertLessEqual(abs(sum(coefficients) - 32768), 8)

    def test_fixed_output_is_within_half_lsb_of_same_operand_float_reference(self):
        data = self.demo.make_demo_data()
        self.assertEqual(len(data["input"]), 4096)
        self.assertEqual(len(data["output"]), 4096)
        self.assertEqual(data["metrics"]["saturated_samples"], 0)
        self.assertLessEqual(data["metrics"]["max_rounding_error_lsb"], 0.5 + 1e-9)

    def test_example_keeps_low_tone_and_attenuates_high_tone(self):
        data = self.demo.make_demo_data()
        self.assertLess(abs(data["metrics"]["low_tone_gain_db"]), 0.5)
        self.assertGreater(data["metrics"]["high_tone_rejection_db"], 30)

    def test_measured_rejection_agrees_with_quantized_filter_response(self):
        # Catches a demo at an accidental exact notch or a wrong amplitude estimator.
        data = self.demo.make_demo_data()
        frequency = data["input_frequencies_hz"][1]
        response = abs(sum((coefficient / 32768) * cmath.exp(
            -2j * math.pi * frequency * k / data["sample_rate_hz"])
            for k, coefficient in enumerate(data["coefficients"])))
        predicted = -20 * math.log10(response)
        self.assertLess(abs(data["metrics"]["high_tone_rejection_db"] - predicted), 1.0)


if __name__ == "__main__":
    unittest.main()
