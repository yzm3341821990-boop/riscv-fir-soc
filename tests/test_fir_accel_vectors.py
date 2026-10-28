"""Golden-vector provenance and literal corner cases for the serial RTL gate."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.run_fir_accel import generate_cases


class FIRAcceleratorVectorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.suite = generate_cases(cls.directory)
        cls.cases = {c['name']: c for c in cls.suite['cases']}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_case_and_sample_counts_include_empty_and_long_blocks(self):
        self.assertEqual(self.suite['case_count'],24)
        self.assertEqual(self.suite['sample_count'],1855)
        self.assertEqual(self.cases['empty_block']['outputs'],[])
        self.assertEqual(self.cases['random_1024']['sample_count'],1024)

    def test_compiled_c_results_have_seven_independent_input_images(self):
        compared=[c for c in self.suite['cases'] if c['compiled_c_compared']]
        self.assertEqual(len(compared),7)
        self.assertEqual(self.cases['software_fir']['outputs'],
                         [8192,12288,-22528,17408,-12288,15360,-7680,-2048])

    def test_farthest_tap_has_31_initial_zeros_then_signed_impulse(self):
        case=self.cases['last_tap']
        self.assertEqual(case['outputs'],[0]*31+[16384,-16384,6173,-1]+[0]*29)
        self.assertEqual(case['accumulators'][31:35],
                         [32767*16384,-32768*16384,12345*16384,-16384])

    def test_negative_subhalf_rounding_and_signed40_extreme_are_literal(self):
        self.assertEqual(self.cases['round_boundaries']['outputs'],[0,0,-1,-1,-1,0,1,1])
        self.assertEqual(self.cases['accumulator_extreme']['accumulators'][-1],1<<35)
        self.assertEqual(self.cases['accumulator_extreme']['outputs'][-1],32767)

    def test_export_reproduces_identically_in_another_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            other=Path(tmp)
            self.assertEqual(generate_cases(other),self.suite)
            def hashes(folder):
                return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in folder.rglob('*') if p.is_file()}
            self.assertEqual(hashes(other),hashes(self.directory))


if __name__=='__main__': unittest.main()
