"""Exercise generation, parameter selection and preservation of compiled work."""
import hashlib
import re
from pathlib import Path
import tempfile
import unittest

from tools.prepare_de2_parallel import prepare


class ParallelProjectTests(unittest.TestCase):
    def test_generates_complete_reproducible_lane_projects(self):
        for lanes in (1,2,4):
            with self.subTest(lanes=lanes),tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp);first=prepare(d,lanes);second=prepare(d,lanes)
                self.assertEqual(first,second)
                self.assertEqual(len(list(d.glob('*.qpf'))),1)
                qsf=(d/(second['project']+'.qsf')).read_text()
                self.assertEqual(re.findall(r'^set_parameter -name FIR_LANES (\d+)$',qsf,re.M),[str(lanes)])
                self.assertEqual(len(re.findall(r'^set_location_assignment ',qsf,re.M)),66)
                self.assertTrue(all((d/n).is_file() for n in re.findall(r'-name VHDL_FILE (\S+)',qsf)))
                self.assertEqual(second['firmware_symbols']['_program_end'],300)
                for name,expected in second['generated_sha256'].items():
                    self.assertEqual(hashlib.sha256((d/name).read_bytes()).hexdigest(),expected,name)

    def test_preserves_compiled_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);prepare(d,4);(d/'output_files').mkdir()
            sof=d/'output_files/example.sof';sof.write_bytes(b'keep this image')
            before=(d/'project-manifest.json').read_bytes()
            with self.assertRaises(FileExistsError):prepare(d,4)
            self.assertEqual(sof.read_bytes(),b'keep this image')
            self.assertEqual((d/'project-manifest.json').read_bytes(),before)

    def test_refuses_unrelated_or_different_lane_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);prepare(d,2)
            with self.assertRaises(FileExistsError):prepare(d,4)
            self.assertTrue((d/'riscv_fir_de2_p2.qpf').is_file())

    def test_refuses_invalid_lane_counts_without_creating_files(self):
        for lanes in (0,3,8,True,'4'):
            with self.subTest(lanes=lanes),tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp)/'not-created'
                with self.assertRaises(ValueError):prepare(d,lanes)
                self.assertFalse(d.exists())


if __name__=='__main__':unittest.main()
