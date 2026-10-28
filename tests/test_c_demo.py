"""Independent firmware expectations, including data loading and stack use."""
import importlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from model.tiny_cpu import run_program

ROOT = Path(__file__).resolve().parents[1]


class CDemoTests(unittest.TestCase):
    def load(self, directory=None):
        return importlib.import_module('tools.c_demo').load_demo(directory)

    def test_compiled_c_uses_eight_signed_loads_and_restores_stack(self):
        image, manifest = self.load()
        self.assertEqual(len(image.program_words), 29)
        result = run_program(image.program_words, initial_memory=image.memory_words)
        self.assertFalse(result.fault)
        self.assertEqual((len(result.trace), result.pc), (64,116))
        self.assertEqual((result.registers[1], result.registers[2], result.registers[10]), (12,1024,55))
        self.assertEqual(result.memory[132:134], (55,1))
        self.assertEqual([t.value for t in result.trace if t.instruction & 0x707F == 0x1003],
                         [12,0xFFFFFFFD,25,0xFFFFFFF6,7,0xFFFFFFFE,30,0xFFFFFFFC])
        self.assertEqual([(e.mode,e.value) for e in result.memory_trace if e.address==1020],
                         [('W',12),('R',12)])
        self.assertEqual(manifest['abi'],'ilp32')

    def test_the_c_result_depends_on_loader_supplied_ram_data(self):
        image, _ = self.load()
        result = run_program(image.program_words)
        self.assertFalse(result.fault)
        self.assertEqual(result.memory[132:134],(0,1))

    def test_changed_export_is_rejected_before_it_can_be_used(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            for p in (ROOT/'programs/c_array_sum').iterdir(): shutil.copyfile(p,directory/p.name)
            path=directory/'program.hex'
            path.write_text('00000013\n'+path.read_text().split('\n',1)[1])
            with self.assertRaises(ValueError): self.load(directory)

    def test_generator_provides_initial_memory_without_changing_legacy_cases(self):
        from tools.generate_cpu_vectors import generate_cpu_vectors
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            report=generate_cpu_vectors(directory)
            case=next(c for c in report['cases'] if c['name']=='c_array_sum')
            self.assertEqual((case['retired_count'],case['memory_count'],case['loader_words']),(64,13,256))
            initial=(directory/case['initial_memory_file']).read_text().splitlines()
            self.assertEqual(initial[128:134],['FFFD000C','FFF60019','FFFE0007','FFFC001E','00000000','00000000'])
            legacy=[c for c in report['cases'] if c['name']!='c_array_sum' and not c['name'].startswith('software_fir')]
            self.assertTrue(all('initial_memory_file' not in c for c in legacy))


if __name__=='__main__': unittest.main()
