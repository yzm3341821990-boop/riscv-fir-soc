import unittest
from model.dsp_peripheral import Peripheral,BASE,MARKER
from model.fixed_fir import fir_block

class DSPOracle(unittest.TestCase):
    def configured(self):
        p=Peripheral();p.memory=[0]*8192
        h=[-32768,32767]+[0]*30
        for i,v in enumerate(h):p.write(BASE+256+4*i,v&0xffffffff)
        p.write(BASE+8,4096);p.write(BASE+12,8192);p.write(BASE+16,4)
        p.memory[1024:1028]=[v&0xffffffff for v in [-32768,32767,-1,0]]
        return p,h
    def test_bitexact_saturation_and_cold_history(self):
        p,h=self.configured();p.write(BASE,1)
        self.assertEqual(p.memory[2048:2052],[v&0xffffffff for v in fir_block([-32768,32767,-1,0],h).outputs])
        p.write(BASE,2);p.write(BASE,1);self.assertEqual(p.starts,2);self.assertEqual(p.read(BASE+4),2)
    def test_reject_overlapping_or_high_dma_pointer(self):
        for dst in (4096,0x10002000):
            p,_=self.configured();p.write(BASE+12,dst)
            with self.assertRaisesRegex(ValueError,'configuration'):p.write(BASE,1)
    def test_incomplete_coefficients_and_bad_sign(self):
        p,_=self.configured();p.mask.remove(31)
        with self.assertRaisesRegex(ValueError,'configuration'):p.write(BASE,1)
        with self.assertRaisesRegex(ValueError,'signed16'):p.write(BASE+256,65535)
    def test_marker_order_and_no_reference_clock_values(self):
        p=Peripheral();p.write(MARKER,1);p.write(MARKER,0);self.assertEqual(p.intervals,[1,0,0])
        with self.assertRaisesRegex(ValueError,'ordering'):p.write(MARKER,0)
        with self.assertRaisesRegex(ValueError,'Timing'):p.read(BASE+20)

if __name__=='__main__':unittest.main()
