"""Check nine-bank provenance and fair input identity without vendor tools."""
import hashlib,json,shutil,struct,tempfile,unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from tools import prepare_de2_benchmark as packer

ROOT=Path(__file__).resolve().parents[1]


class BoardBenchmarkImagesTests(unittest.TestCase):
    @contextmanager
    def isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shutil.copytree(ROOT/'programs/fir_large',root/'programs/fir_large')
            m=json.loads((ROOT/'programs/fir_large/n64/software/manifest.json').read_text())
            for name in m['input_sha256']:
                (root/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,root/name)
            with patch.object(packer,'ROOT',root):yield root

    def test_profiles_follow_declared_switch_order(self):
        profiles,_,_,_=packer.load_profiles()
        self.assertEqual([(p['sample_count'],p['mode']) for p in profiles],
            [(64,'software'),(64,'hardware_cold'),(64,'hardware_resident'),
             (256,'software'),(256,'hardware_cold'),(256,'hardware_resident'),
             (1024,'software'),(1024,'hardware_cold'),(1024,'hardware_resident')])

    def test_every_rom_bank_contains_exact_compiled_instructions(self):
        profiles,programs,_,_=packer.load_profiles();self.assertEqual(len(programs),2304)
        for p in profiles:
            path=ROOT/'programs/fir_large'/f"n{p['sample_count']}"/p['mode']/'program.hex'
            words=[int(v,16) for v in path.read_text().split()];bank=programs[256*p['index']:256*(p['index']+1)]
            self.assertEqual(bank[:len(words)],words);self.assertEqual(bank[len(words):],[0x13]*(256-len(words)))

    def test_lengths_share_one_seed_bank_across_three_modes(self):
        _,_,seeds,_=packer.load_profiles();self.assertEqual(len(seeds),24576)
        for bank,n in enumerate([64,256,1024]):
            words=[int(v,16) for v in (ROOT/'programs/fir_large'/f'n{n}'/'software/initial_memory.txt').read_text().split()]
            self.assertEqual(seeds[8192*bank:8192*(bank+1)],words)

    def test_marker_addresses_follow_linked_c_objects(self):
        profiles,_,_,_=packer.load_profiles()
        self.assertEqual([p['symbols']['marker'] for p in profiles],[2944]*3+[5248]*3+[14464]*3)
        self.assertEqual([p['symbols']['outputs'] for p in profiles],[2432]*3+[3200]*3+[6272]*3)

    def test_changed_instruction_image_is_rejected(self):
        with self.isolated() as root:
            p=root/'programs/fir_large/n64/hardware_cold/program.hex';p.write_text('00000013\n'+p.read_text())
            with self.assertRaisesRegex(ValueError,'stale firmware artifact'):packer.load_profiles()

    def test_different_unused_ram_word_is_still_unfair(self):
        with self.isolated() as root:
            folder=root/'programs/fir_large/n64/hardware_resident';p=folder/'initial_memory.txt'
            words=[int(v,16) for v in p.read_text().split()];words[-1]=0x1234;p.write_text(''.join(f'{v:08X}\n' for v in words))
            m=json.loads((folder/'manifest.json').read_text());m['artifact_sha256']['initial_memory.txt']=hashlib.sha256(p.read_bytes()).hexdigest()
            m['initial_memory_sha256']=hashlib.sha256(struct.pack('<8192I',*words)).hexdigest();(folder/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'mode-dependent initial RAM'):packer.load_profiles()

    def test_mismatched_compiler_flags_are_rejected(self):
        with self.isolated() as root:
            p=root/'programs/fir_large/n256/software/manifest.json';m=json.loads(p.read_text());m['compiler_flags'].append('-O0');p.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'nonmatching comparison conditions'):packer.load_profiles()

    def test_changed_c_source_cannot_reuse_old_elf_provenance(self):
        with self.isolated() as root:
            p=root/'firmware/fir_large/main.c';p.write_bytes(p.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'stale firmware source'):packer.load_profiles()


if __name__=='__main__':unittest.main()
