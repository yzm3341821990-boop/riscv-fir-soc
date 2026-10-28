"""The display project must preserve the old board and use all documented pins."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


class DisplayProjectTests(unittest.TestCase):
    def test_complete_separate_project_and_voltage_groups(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.prepare_de2_display'))
        from tools.prepare_de2_display import prepare, PINS
        self.assertEqual(len(PINS),66)
        self.assertEqual(len({v['pin'] for v in PINS.values()}),66)
        self.assertEqual(PINS['HEX0[0]'],{'pin':'G18','standard':'2.5 V'})
        self.assertEqual(PINS['HEX3[1]']['standard'],'2.5 V')
        self.assertEqual(PINS['HEX3[2]'],{'pin':'AB20','standard':'3.3-V LVTTL'})
        self.assertEqual(PINS['HEX7[6]'],{'pin':'AA14','standard':'3.3-V LVTTL'})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=prepare(p)
            self.assertEqual(r['contract'],'de2-display-v1')
            self.assertEqual(r['system_clock_mhz'],25)
            self.assertTrue((p/'riscv_fir_de2_display.qpf').is_file())
            qsf=(p/'riscv_fir_de2_display.qsf').read_text()
            self.assertIn('TOP_LEVEL_ENTITY de2_115_display_top',qsf)
            self.assertIn('hex7seg.vhd',qsf)
            for name,v in PINS.items():
                self.assertIn('PIN_'+v['pin']+' -to '+name,qsf)
                self.assertIn('"'+v['standard']+'" -to '+name,qsf)
            self.assertIn('sw_meta',(p/'display.sdc').read_text())


if __name__=='__main__': unittest.main()
