import importlib.util
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class UpgradeContract(unittest.TestCase):
    def test_new_dsp_profile_is_separate(self):
        self.assertTrue((ROOT/'rtl/board/de2_115_dsp_core.vhd').exists(), 'DSP6 core is not implemented')
        self.assertTrue((ROOT/'rtl/cpu/pipeline_dsp_cpu.vhd').exists())
    def test_reference_peripheral_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec('model.dsp_peripheral'), 'DSP peripheral oracle is not implemented')
    def test_physical_large_review_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.review_long_signal'), 'physical long-signal evidence review is missing')

if __name__=='__main__':unittest.main()
