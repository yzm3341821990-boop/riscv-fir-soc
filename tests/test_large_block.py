"""Exercise expanded ELF limits and audit real traces with intentional damage."""
import json,struct,tempfile,unittest
from pathlib import Path
from tools.large_elf import read_large_elf
from tools.audit_large_trace import audit
from tools.build_large_firmware import layout,dataset

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'sim/fixtures/large-soc-smoke'


class LargeFirmwareTests(unittest.TestCase):
    def test_long_layout_has_full_nonoverlapping_arrays(self):
        m=layout(1024)
        self.assertEqual([m[k] for k in ['samples','coefficients','outputs','expected','marker','_stack_top']],
                         [2048,6144,6272,10368,14464,32768])
        self.assertEqual(layout(64)['marker'],2944)

    def test_lengths_use_matching_signal_prefix_and_coefficients(self):
        short,h,y=dataset(64);long,h2,y2=dataset(1024)
        self.assertEqual(short,long[:64]);self.assertEqual(h,h2);self.assertEqual(y,y2[:64])

    def test_elf_accepts_32k_layout_and_zero_fills_bss(self):
        image=read_large_elf((ROOT/'programs/fir_large/n1024/software/program.elf').read_bytes())
        self.assertEqual(len(image.memory_words),8192)
        self.assertEqual(image.symbols['_stack_top'],32768)
        self.assertEqual(image.symbols['expected'],10368)
        self.assertEqual(image.memory_words[512:],(0,)*(8192-512))

    def test_elf_rejects_out_of_bounds_data_segment(self):
        data=bytearray((ROOT/'programs/fir_large/n1024/software/program.elf').read_bytes())
        offset=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
        for k in range(count):
            base=offset+size*k;kind=struct.unpack_from('<I',data,base)[0];flags=struct.unpack_from('<I',data,base+24)[0]
            if kind==1 and not flags&1:
                struct.pack_into('<II',data,base+8,32764,32764);break
        with self.assertRaisesRegex(ValueError,'outside'):read_large_elf(bytes(data))


class LargeTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda name:[int(v,16) for v in (FIXTURE/name).read_text().split()]
        cls.program=read('program.hex');cls.initial=read('initial_memory.txt')
        cls.memory=read('final-memory.txt');cls.registers=read('final-registers.txt')
        cls.manifest=json.loads((FIXTURE/'manifest.json').read_text())
        cls.trace=(FIXTURE/'trace.txt').read_text()

    def replay(self,trace=None,memory=None,registers=None):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.txt';path.write_text(self.trace if trace is None else trace)
            return audit(path,self.program,self.initial,self.manifest,
                         self.memory if memory is None else memory,self.registers if registers is None else registers)

    def test_real_execution_checks_all_ram_registers_and_samples(self):
        result=self.replay()
        self.assertEqual((result['cycles'],result['outputs_checked'],result['checked_commits']), (1126,64,1293))
        self.assertEqual(result['complete_ram_words_checked'],8192)

    def test_detects_corrupt_last_dma_output(self):
        lines=self.trace.splitlines();index=max(i for i,s in enumerate(lines) if s.startswith('D W '))
        fields=lines[index].split();fields[3]=f'{int(fields[3],16)^1:08X}';lines[index]=' '.join(fields)
        with self.assertRaisesRegex(ValueError,'numerical'):self.replay('\n'.join(lines))

    def test_detects_missing_last_dma_write(self):
        lines=self.trace.splitlines();index=max(i for i,s in enumerate(lines) if s.startswith('D W '));del lines[index]
        with self.assertRaises(ValueError):self.replay('\n'.join(lines))

    def test_detects_wrong_instruction_commit(self):
        lines=self.trace.splitlines();index=next(i for i,s in enumerate(lines) if s.startswith('I '))
        fields=lines[index].split();fields[5]='00000008';lines[index]=' '.join(fields)
        with self.assertRaisesRegex(ValueError,'next PC'):self.replay('\n'.join(lines))

    def test_detects_ghost_write_at_last_ram_word(self):
        memory=self.memory.copy();memory[-1]^=1
        with self.assertRaisesRegex(ValueError,'complete 32 KiB RAM'):self.replay(memory=memory)

    def test_detects_wrong_actual_register_file(self):
        registers=self.registers.copy();registers[31]^=1
        with self.assertRaisesRegex(ValueError,'register file'):self.replay(registers=registers)

    def test_detects_nonmonotonic_event_clock(self):
        lines=self.trace.splitlines();fields=lines[-1].split();fields[-1]='0';lines[-1]=' '.join(fields)
        with self.assertRaisesRegex(ValueError,'nonmonotonic'):self.replay('\n'.join(lines))


if __name__=='__main__':unittest.main()
