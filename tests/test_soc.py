"""Replay a source-bound actual RTL trace and reject independently corrupted evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from tools.audit_soc_trace import audit
from tools.run_soc import load_firmware,prepare

ROOT=Path(__file__).resolve().parents[1]


class SoCTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image,cls.manifest=load_firmware()
        cls.fixture=json.loads((ROOT/'sim/fixtures/c-fir-accel-trace.json').read_text())

    def check_trace(self,*,events=None,memory=None,registers=None):
        f=self.fixture
        return audit(f['events'] if events is None else events,self.image,f['initial_memory'],self.manifest,
                     f['final_memory'] if memory is None else memory,
                     f['final_registers'] if registers is None else registers)

    def test_actual_trace_is_bound_to_the_compiled_elf(self):
        self.assertEqual(self.fixture['program_elf_sha256'],self.manifest['artifact_sha256']['program.elf'])
        result=self.check_trace()
        self.assertEqual(result['outputs'],[8192,12288,-22528,17408,-12288,15360,-7680,-2048])
        self.assertEqual((result['dma_reads'],result['dma_writes']),(8,8))
        self.assertEqual(result['registers_checked'],32)
        self.assertEqual(result['complete_ram_words_checked'],256)

    def test_wrong_dma_result_is_not_hidden_by_the_cpu_trace(self):
        old='SOC_DMA mode=W addr=000002C0 data=00002000'
        self.assertIn(old,self.fixture['events'])
        with self.assertRaisesRegex(ValueError,'original Q15'):
            self.check_trace(events=self.fixture['events'].replace(old,old[:-1]+'1',1))

    def test_wrong_mmio_response_is_rejected_independently(self):
        old='SOC_BUS mode=R addr=40003004 data=00000001'
        self.assertIn(old,self.fixture['events'])
        with self.assertRaisesRegex(ValueError,'MMIO read mismatch'):
            self.check_trace(events=self.fixture['events'].replace(old,old[:-1]+'3',1))

    def test_store_bus_must_match_register_operand(self):
        old='SOC_BUS mode=W addr=40003000 data=00000002'
        self.assertIn(old,self.fixture['events'])
        with self.assertRaises(ValueError):
            self.check_trace(events=self.fixture['events'].replace(old,old[:-1]+'0',1))

    def test_next_pc_must_follow_the_independent_isa_replay(self):
        with self.assertRaisesRegex(ValueError,'CPU writeback/next PC'):
            self.check_trace(events=self.fixture['events'].replace('next=00000004','next=00000008',1))

    def test_full_ram_comparison_detects_unrelated_damage(self):
        memory=list(self.fixture['final_memory']);memory[7]^=1
        with self.assertRaisesRegex(ValueError,'complete RAM'):
            self.check_trace(memory=memory)

    def test_register_file_comparison_detects_silent_damage(self):
        registers=list(self.fixture['final_registers']);registers[31]^=1
        with self.assertRaisesRegex(ValueError,'register file'):
            self.check_trace(registers=registers)

    def test_staging_covers_mmio_guards_and_timeout_without_a_compiler(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite,image,manifest=prepare(Path(tmp))
            self.assertEqual(len(suite['soc_cases']),9)
            self.assertEqual(len(suite['guard_cases']),11)
            self.assertEqual(len(suite['mmio_cases']),20)
            self.assertEqual(sum(bool(c.get('timeout')) for c in suite['soc_cases']),1)
            self.assertEqual(image,self.image)
            self.assertEqual(manifest,self.manifest)


if __name__=='__main__': unittest.main()
