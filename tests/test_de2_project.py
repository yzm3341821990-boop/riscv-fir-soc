"""The reference Quartus kit must be complete and bound to the audited firmware."""
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest


class DE2ProjectTests(unittest.TestCase):
    def test_gui_default_root_partition_can_be_collected(self):
        from tools.collect_de2_build import canonical_project_text
        base='set_global_assignment -name DEVICE EP4CE115F29C7\n'
        additions='\n'.join((
            'set_instance_assignment -name PARTITION_HIERARCHY root_partition -to | -section_id Top',
            'set_global_assignment -name PARTITION_NETLIST_TYPE SOURCE -section_id Top',
            'set_global_assignment -name PARTITION_FITTER_PRESERVATION_LEVEL PLACEMENT_AND_ROUTING -section_id Top',
            'set_global_assignment -name PARTITION_COLOR 16764057 -section_id Top'))
        self.assertEqual(canonical_project_text('board.qsf',base),
                         canonical_project_text('board.qsf',base+additions+'\n'))

    def test_gui_tolerance_does_not_hide_changed_device_pin_or_netlist(self):
        from tools.collect_de2_build import canonical_project_text
        base='set_global_assignment -name DEVICE EP4CE115F29C7\n'
        for text in (base.replace('C7','C9'),base+'set_location_assignment PIN_G19 -to RESET_N\n',
                     base+'set_global_assignment -name PARTITION_NETLIST_TYPE POST_FIT -section_id Top\n'):
            with self.subTest(text=text):
                self.assertNotEqual(canonical_project_text('board.qsf',base),
                                    canonical_project_text('board.qsf',text))

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.prepare_de2_project'),
                             'a reproducible Quartus project preparer is required')
        from tools.prepare_de2_project import prepare
        return prepare

    def test_staged_project_has_real_rtl_and_correct_reference_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); report=self.api()(p)
            self.assertTrue((p/'riscv_fir_de2_115.qpf').is_file())
            qsf=(p/'riscv_fir_de2_115.qsf').read_text()
            self.assertIn('EP4CE115F29C7',qsf)
            self.assertIn('de2_115_top',qsf)
            self.assertNotIn('-to {LEDR',qsf)
            for pin,bit in [('G19',0),('F19',1),('E19',2),('F21',3)]:
                self.assertIn(f'set_location_assignment PIN_{pin} -to LEDR[{bit}]',qsf)
            self.assertTrue((p/'fir_soc.vhd').is_file())
            self.assertTrue((p/'board_images_pkg.vhd').is_file())
            self.assertEqual(report['physical_board_verified'],False)
            self.assertEqual(report['system_clock_mhz'],25)

    def test_rom_export_contains_all_256_seed_words_and_firmware_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); r=self.api()(p)
            self.assertEqual(r['ram_seed_words'],256)
            self.assertEqual(r['program_words'],75)
            self.assertEqual(r['firmware_symbols']['outputs'],704)
            self.assertEqual(r['firmware_symbols']['done'],744)
            self.assertEqual(json.loads((p/'project-manifest.json').read_text())['firmware_symbols'],r['firmware_symbols'])

    def test_entire_rom_and_ram_exports_match_the_verified_firmware(self):
        from tools.run_soc import load_firmware
        image,_=load_firmware()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); self.api()(p)
            for file,expected in [('ram_seed.mif',list(image.memory_words)),
                                  ('program.mif',list(image.program_words)+[0x13]*(256-len(image.program_words)))]:
                words=re.findall(r'^([0-9A-F]{2}) : ([0-9A-F]{8});$',(p/file).read_text(),re.MULTILINE)
                self.assertEqual([int(a,16) for a,_ in words],list(range(256)))
                self.assertEqual([int(v,16) for _,v in words],expected)


if __name__=='__main__': unittest.main()
