"""Compiled FIR compared with literal outputs and the original Q15 contract."""
import importlib
import struct
import unittest
from model.tiny_cpu import run_program


class SoftwareFIRTests(unittest.TestCase):
    def api(self):return importlib.import_module('tools.software_fir')

    def test_demo_outputs_and_raw_accumulators_are_literal(self):
        api=self.api();image,manifest=api.load_fir()
        r=run_program(image.program_words,initial_memory=image.memory_words)
        y,acc=api.audit_result(r,image.memory_words,manifest)
        self.assertEqual(y,(8192,12288,-22528,17408,-12288,15360,-7680,-2048))
        self.assertEqual(acc,(268435456,402636800,-738189312,570421248,-402655232,503316480,-251658240,-67108864))
        self.assertEqual(r.registers[2],1024)
        self.assertEqual(sum(t.instruction&0xFE00707F==0x02000033 for t in r.trace),36)

    def test_ties_round_away_from_zero(self):
        api=self.api();im,m=api.load_fir();memory=api.fir_inputs()['software_fir_ties']
        y,_=api.audit_result(run_program(im.program_words,initial_memory=memory),memory,m)
        self.assertEqual(y,(1,-1,2,-2,16384,-16384,0,1))

    def test_positive_accumulation_crosses_32_bits_before_saturation(self):
        api=self.api();im,m=api.load_fir();memory=api.fir_inputs()['software_fir_positive_extreme']
        y,acc=api.audit_result(run_program(im.program_words,initial_memory=memory),memory,m)
        self.assertEqual(y,(32767,)*8)
        self.assertEqual(acc[-1],1<<33)

    def test_negative_accumulation_crosses_32_bits_before_saturation(self):
        api=self.api();im,m=api.load_fir();memory=api.fir_inputs()['software_fir_negative_extreme']
        y,acc=api.audit_result(run_program(im.program_words,initial_memory=memory),memory,m)
        self.assertEqual(y,(-32767,)+(-32768,)*7)
        self.assertEqual(acc[-1],8*(-32768)*32767)

    def test_impulse_and_zero_cases_are_not_constant_folded(self):
        api=self.api();im,m=api.load_fir()
        expected={'software_fir_impulse':(16384,-8192,4096,2048,0,0,0,0),
                  'software_fir_zero':(0,)*8,'software_fir_zero_coefficients':(0,)*8}
        for name,y_expected in expected.items():
            memory=api.fir_inputs()[name]
            y,_=api.audit_result(run_program(im.program_words,initial_memory=memory),memory,m)
            self.assertEqual(y,y_expected)


if __name__=='__main__':unittest.main()
