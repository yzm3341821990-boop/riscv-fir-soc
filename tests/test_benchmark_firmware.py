"""The paired benchmark must preserve inputs, layout and CPU capability."""
import json
from pathlib import Path
import struct
import unittest

from model.fixed_fir import fir_block
from model.tiny_cpu import run_program
from tools.c_demo import load_demo

ROOT = Path(__file__).resolve().parents[1]
MODES = ('software', 'hardware_cold', 'hardware_resident')
LAYOUT = {'bench_data': 512, 'samples': 512, 'coefficients': 544, 'outputs': 672,
          'marker': 704, 'done': 708, 'errors': 712, 'polls': 716,
          'hw_cycles': 720, 'hw_written': 724, '_stack_top': 1024}


class BenchmarkFirmwareTests(unittest.TestCase):
    def artifact(self, mode):
        folder = ROOT/'programs/fir_benchmark'/mode
        self.assertTrue((folder/'manifest.json').is_file(),
                        'the three matched benchmark compiler artifacts are required')
        return load_demo(folder, expected_contract='c-fir-benchmark-v1')

    def test_all_three_modes_export_the_same_data_addresses(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                image, manifest = self.artifact(mode)
                for name, expected in LAYOUT.items():
                    self.assertEqual(image.symbols[name], expected)
                self.assertEqual(manifest['mode'], mode)
                self.assertLessEqual(4*len(image.program_words), 512)

    def test_initial_ram_is_byte_identical_across_modes(self):
        images = [self.artifact(mode)[0] for mode in MODES]
        self.assertEqual(images[0].memory_words, images[1].memory_words)
        self.assertEqual(images[1].memory_words, images[2].memory_words)
        raw = struct.pack('<256I', *images[0].memory_words)
        self.assertEqual(struct.unpack_from('<8i', raw, 512),
                         (16384,32767,-32768,8192,-16384,24576,0,-8192))
        self.assertEqual(struct.unpack_from('<32i', raw, 544),
                         (16384,-8192,4096,2048)+(0,)*28)
        self.assertEqual(raw[672:728], bytes(56))

    def test_compiler_flags_and_multiplier_capability_match(self):
        manifests = [self.artifact(mode)[1] for mode in MODES]
        self.assertTrue(all(m['compiler_flags']==manifests[0]['compiler_flags'] for m in manifests))
        self.assertTrue(all(m['compiler_cpu']=='generic_rv32+m' and m['abi']=='ilp32' for m in manifests))
        for mode in MODES:
            image,_ = self.artifact(mode)
            self.assertFalse(any(w&127==0x33 and w>>25==1 and (w>>12)&7!=0 for w in image.program_words))

    def test_instruction_audit_rejects_other_m_and_system_instructions(self):
        from tools.build_fir_benchmark import validate_instructions
        validate_instructions([0x02000033, 0x00000013])
        for word in (0x02001033, 0x02004033, 0x00000073, 0x0000000f):
            with self.subTest(word=word):
                with self.assertRaisesRegex(ValueError, 'unsupported instruction'):
                    validate_instructions([word])

    def test_software_uses_runtime_inputs_and_matches_literal_result(self):
        image,_ = self.artifact('software')
        result = run_program(image.program_words, initial_memory=image.memory_words)
        self.assertFalse(result.fault)
        self.assertEqual(tuple((v-(1<<32) if v&(1<<31) else v) for v in result.memory[168:176]),
                         (8192,12288,-22528,17408,-12288,15360,-7680,-2048))
        self.assertEqual(result.memory[176:179], (2,1,0))
        self.assertEqual(result.registers[2], 1024)

    def test_software_keeps_rounding_saturation_and_signed64_accumulation(self):
        image,_ = self.artifact('software')
        cases = [([1,-1,3,-3,32767,-32768,0,2], [16384]+[0]*31),
                 ([-32768]*8, [-32768]*32), ([-32768]*8,[32767]*32),
                 ([0]*8,[32767,-32768]*16),
                 ([32767]+[0]*7,[16384,-8192,4096,2048]+[0]*28)]
        for x,h in cases:
            with self.subTest(samples=x, first_coefficient=h[0]):
                memory=list(image.memory_words)
                memory[128:136]=[v&0xffffffff for v in x]
                memory[136:168]=[v&0xffffffff for v in h]
                r=run_program(image.program_words,initial_memory=memory)
                self.assertFalse(r.fault)
                self.assertEqual(tuple(v-(1<<32) if v&(1<<31) else v for v in r.memory[168:176]),
                                 fir_block(x,h).outputs)


if __name__=='__main__': unittest.main()
