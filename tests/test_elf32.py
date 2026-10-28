"""Hand-built ELF headers test the bounded teaching-board image loader."""
import importlib
import struct
import unittest


def fixture():
    data = bytearray(0x500)
    ident = b'\x7fELF\x01\x01\x01' + b'\0' * 9
    struct.pack_into('<16sHHIIIIIHHHHHH', data, 0, ident, 2, 243, 1, 0, 52, 0x400, 0,
                     52, 32, 2, 40, 3, 0)
    struct.pack_into('<IIIIIIII', data, 52, 1, 0x100, 0, 0, 8, 8, 5, 4)
    struct.pack_into('<IIIIIIII', data, 84, 1, 0x108, 512, 512, 4, 12, 6, 4)
    struct.pack_into('<III', data, 0x100, 0x00500093, 0x0040006F, 0xDEADBEEF)
    strings = b'\0samples\0result\0done\0_program_end\0_stack_top\0'
    data[0x200:0x200+len(strings)] = strings
    for index, (name, value, size) in enumerate((('samples',512,4),('result',516,4),
                                                ('done',520,4),('_program_end',8,0),('_stack_top',1024,0)), 1):
        struct.pack_into('<IIIBBH', data, 0x300+index*16, strings.index(name.encode()+b'\0'),
                         value, size, 0x11, 0, 1)
    struct.pack_into('<IIIIIIIIII', data, 0x428, 0, 3, 0, 0, 0x200, len(strings), 0, 0, 1, 0)
    struct.pack_into('<IIIIIIIIII', data, 0x450, 0, 2, 0, 0, 0x300, 96, 1, 0, 4, 16)
    return data


class ELF32Tests(unittest.TestCase):
    def load(self, data):
        return importlib.import_module('tools.elf32').read_elf(bytes(data))

    def test_loads_code_data_bss_and_named_addresses(self):
        image = self.load(fixture())
        self.assertEqual(image.program_words, (0x00500093, 0x0040006F))
        self.assertEqual(len(image.memory_words), 256)
        self.assertEqual(image.memory_words[128:131], (0xDEADBEEF, 0, 0))
        self.assertEqual(image.symbols['result'], 516)
        self.assertEqual(image.symbols['_program_end'], 8)

    def test_rejects_wrong_machine_class_endian_entry_and_abi(self):
        for offset, fmt, value in ((4,'B',2),(5,'B',2),(18,'H',62),(24,'I',4),(36,'I',1)):
            data=fixture(); struct.pack_into('<'+fmt,data,offset,value)
            with self.subTest(offset=offset), self.assertRaises(ValueError): self.load(data)

    def test_rejects_truncated_segments_and_file_larger_than_memory(self):
        with self.assertRaises(ValueError): self.load(fixture()[:0x104])
        data=fixture(); struct.pack_into('<I',data,52+20,4)
        with self.assertRaises(ValueError): self.load(data)

    def test_rejects_rom_ram_bounds_overlap_and_partial_instructions(self):
        for offset,value in ((52+8,512),(84+8,0),(84+8,1020),(52+16,7)):
            data=fixture(); struct.pack_into('<I',data,offset,value)
            with self.subTest(offset=offset,value=value), self.assertRaises(ValueError): self.load(data)

    def test_rejects_bad_symbol_table_bounds(self):
        data=fixture(); struct.pack_into('<I',data,0x450+16,0x4F8)
        with self.assertRaises(ValueError): self.load(data)

    def test_ignores_local_symbols_with_the_same_name_as_a_global(self):
        data=fixture()
        struct.pack_into('<IIIBBH',data,0x300,1,123,0,0,0,1)
        self.assertEqual(self.load(data).symbols['samples'],512)


if __name__ == '__main__': unittest.main()
