"""Read this project's static RV32I/ILP32 ELF layout using only the stdlib.

This is a bounded loader: text at 0..511, data/BSS at 512..1023.
It does not relocate files or implement a general-purpose ELF loader.
"""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class FirmwareImage:
    program_words: tuple[int, ...]
    memory_words: tuple[int, ...]
    symbols: dict[str, int]


def read_elf(data: bytes) -> FirmwareImage:
    def region(offset, size):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise ValueError('ELF file range is truncated')
        return data[offset:offset+size]

    def unpack(fmt, offset):
        return struct.unpack(fmt, region(offset, struct.calcsize(fmt)))

    (ident, kind, machine, version, entry, phoff, shoff, flags, ehsize,
     phsize, phnum, shsize, shnum, _) = unpack('<16sHHIIIIIHHHHHH', 0)
    if (ident[:7] != b'\x7fELF\x01\x01\x01' or kind != 2 or machine != 243 or
            version != 1 or entry != 0 or flags != 0 or ehsize != 52 or phsize != 32):
        raise ValueError('expected static little-endian RV32I/ILP32 ELF32 at entry zero, without RVC')
    text = None
    memory = bytearray(1024)
    occupied = set()
    for i in range(phnum):
        ptype, offset, addr, physical, filesz, memsz, pflags, align = unpack('<IIIIIIII', phoff+i*phsize)
        if ptype != 1:
            continue
        if filesz > memsz or physical != addr:
            raise ValueError('unsupported load-segment size or physical mapping')
        payload = region(offset, filesz)
        if pflags & 1:
            if text is not None or addr != 0 or not filesz or filesz != memsz or filesz % 4 or filesz > 512:
                raise ValueError('text must be one aligned segment at zero within 512 bytes')
            text = payload
        else:
            if addr < 512 or addr + memsz > 1024:
                raise ValueError('data/BSS outside the firmware RAM region')
            addresses = set(range(addr, addr+memsz))
            if occupied & addresses:
                raise ValueError('overlapping RAM segments')
            occupied |= addresses
            memory[addr:addr+filesz] = payload
    if text is None:
        raise ValueError('no executable segment')
    words = struct.unpack('<'+'I'*(len(text)//4), text)
    if any(word & 3 != 3 for word in words):
        raise ValueError('compressed or partial instruction in RV32I text')
    symbols = {}
    if shnum:
        if shsize != 40:
            raise ValueError('unsupported section-header size')
        sections = [unpack('<IIIIIIIIII', shoff+i*shsize) for i in range(shnum)]
        for section in sections:
            _, stype, _, _, offset, size, link, _, _, entsize = section
            if stype != 2:
                continue
            if entsize != 16 or size % 16 or link >= len(sections) or sections[link][1] != 3:
                raise ValueError('bad symbol-table layout')
            strings = region(sections[link][4], sections[link][5])
            region(offset, size)
            for pos in range(offset, offset+size, 16):
                name, value, _, info, _, index = unpack('<IIIBBH', pos)
                if not name or not index or info >> 4 not in (1, 2):
                    continue
                end = strings.find(b'\0', name)
                if name >= len(strings) or end < 0:
                    raise ValueError('bad symbol name')
                name = strings[name:end].decode('ascii')
                if name in symbols and symbols[name] != value:
                    raise ValueError('ambiguous symbol')
                symbols[name] = value
    return FirmwareImage(tuple(words), struct.unpack('<256I', memory), symbols)
