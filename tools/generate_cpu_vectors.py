"""Reproducible program ROMs and architectural checks for the tiny CPU."""

import argparse
import hashlib
import json
from pathlib import Path
import random

from model.tiny_cpu import (ALU_INSTRUCTIONS, MEMORY_INSTRUCTIONS, SUPPORTED_INSTRUCTIONS,
                            encode_addi, encode_add, encode_sub, encode_lw, encode_sw,
                            encode_op, encode_op_imm, encode_branch, encode_jal, encode_jalr,
                            encode_lui, encode_auipc, encode_load, encode_store, run_program)

ROOT = Path(__file__).resolve().parents[1]
SEED = 0xC0DE32


def _multiply_programs():
    def load(rd,value):
        low=value&0xFFF
        return [encode_lui(rd,((value+2048)>>12)&0xFFFFF),encode_addi(rd,rd,low-4096 if low>=2048 else low)]
    edges=[(0,0),(0,0xFFFFFFFF),(7,9),(0xFFFFFFF9,9),(0xFFFFFFFF,0xFFFFFFFF),
           (0x80000000,0xFFFFFFFF),(0x7FFFFFFF,2),(0x10001,0x10001),(0x8000,0x8000),
           (0xDEADBEEF,0x12345678),(0x80000000,0x80000000),(0xFFFF,0x10001)]
    edge_words=[]
    for a,b in edges:edge_words+=load(1,a)+load(2,b)+[encode_op('MUL',3,1,2)]
    rng=random.Random(SEED^0x4D554C);random_words=[]
    for _ in range(40):random_words+=load(1,rng.randrange(1<<32))+load(2,rng.randrange(1<<32))+[encode_op('MUL',3,1,2)]
    cases=[('multiply_edges',edge_words,False),('multiply_random',random_words,False)]
    for rd in (0,1,2,31):
        cases.append((f'multiply_alias_{rd}',[encode_addi(1,0,-7),encode_addi(2,0,9),
                     encode_op('MUL',rd,1,2),encode_addi(3,rd,1)],False))
    cases.extend([
        ('multiply_then_memory',[encode_addi(1,0,-7),encode_addi(2,0,9),encode_op('MUL',3,1,2),
                                 encode_sw(3,0,0),encode_lw(4,0,0),encode_sub(5,4,1)],False),
        ('multiply_zero',load(1,0xDEADBEEF)+[encode_op('MUL',3,1,0)],False),
        ('multiply_reset',[encode_addi(1,0,7),encode_addi(2,0,-9),encode_op('MUL',3,1,2)],True),
    ])
    for funct3 in range(1,8):cases.append((f'multiply_unimplemented_m_{funct3}',[0x022081B3|(funct3<<12)],False))
    return cases


def _fir_programs():
    from tools.software_fir import load_fir,fir_inputs
    image,_=load_fir()
    return [(name,list(image.program_words),False) for name in fir_inputs()]


def _subword_programs() -> list[tuple[str, list[int], bool]]:
    a, l, s = encode_addi, encode_load, encode_store
    prefix = [encode_lui(2, 0x80FF8), a(2, 2, 0x17F), encode_sw(2, 0, 0)]
    cases = [("subword_demo", [a(1, 0, 64), encode_lui(2, 0x80FF8), a(2, 2, 0x17F),
                               encode_sw(2, 1, 0), l('LB', 3, 1, 1), l('LBU', 4, 1, 1),
                               l('LH', 5, 1, 2), l('LHU', 6, 1, 2), a(7, 0, 0x55), s('SB', 7, 1, 1),
                               encode_lui(8, 0x1234B), a(8, 8, -0x433), s('SH', 8, 1, 2),
                               encode_lw(9, 1, 0), l('LB', 10, 1, 0), l('LBU', 11, 1, 3)], False)]
    for lane in range(4):
        cases.append((f"subword_byte_lane_{lane}", prefix + [a(2, 0, -1), s('SB', 2, 0, lane),
                      l('LB', 3, 0, lane), l('LBU', 4, 0, lane), encode_lw(5, 0, 0)], False))
    for lane in (0, 2):
        cases.append((f"subword_half_lane_{lane}", prefix + [a(2, 0, -129), s('SH', 2, 0, lane),
                      l('LH', 3, 0, lane), l('LHU', 4, 0, lane), encode_lw(5, 0, 0)], False))
    for value in (0, 0x7FFF7F7F, 0x80008080, 0xFFFFFFFF):
        upper, low = ((value + 2048) >> 12) & 0xFFFFF, value & 0xFFF
        low = low - 4096 if low >= 2048 else low
        cases.append((f"subword_sign_edges_{value:08x}", [encode_lui(1, upper), a(1, 1, low),
                      encode_sw(1, 0, 0), l('LB', 2, 0, 0), l('LBU', 3, 0, 0),
                      l('LH', 4, 0, 2), l('LHU', 5, 0, 2)], False))
    for name in ('LB', 'LBU', 'LH', 'LHU'):
        address = 1023 if name in ('LB', 'LBU') else 1022
        store = 'SB' if address == 1023 else 'SH'
        cases.append((f"subword_boundary_{name.lower()}", [a(1, 0, -128), s(store, 1, 0, address),
                      l(name, 31, 0, address)], False))
        cases.append((f"subword_x0_{name.lower()}", prefix + [l(name, 0, 0, 0)], False))
        for address in (-1, 1024):
            suffix = 'negative' if address < 0 else 'range'
            cases.append((f"subword_{name.lower()}_{suffix}_fault", [l(name, 0, 0, address)], False))
    for name in ('SB', 'SH'):
        for address in (-1, 1024):
            suffix = 'negative' if address < 0 else 'range'
            cases.append((f"subword_{name.lower()}_{suffix}_fault", prefix + [s(name, 2, 0, address)], False))
    for name in ('LH', 'LHU'):
        for address in (1, 3, 1023):
            cases.append((f"subword_{name.lower()}_odd_{address}_fault", [l(name, 1, 0, address)], False))
    for address in (1, 3, 1023):
        cases.append((f"subword_sh_odd_{address}_fault", prefix + [s('SH', 2, 0, address)], False))
    for funct3 in (6, 7):
        cases.append((f"subword_reserved_load_{funct3}", [0x00000083 | (funct3 << 12)], False))
    for funct3 in (4, 5, 6, 7):
        cases.append((f"subword_reserved_store_{funct3}", [0x00100023 | (funct3 << 12)], False))
    cases.extend([
        ('subword_negative_offset', [a(1, 0, 67), a(2, 0, -127), s('SB', 2, 1, -2), l('LB', 3, 1, -2)], False),
        ('subword_wrap_to_zero', [a(1, 0, -1), a(2, 0, -128), s('SB', 2, 1, 1), l('LBU', 3, 1, 1)], False),
        ('subword_load_base_alias', [a(1, 0, 65), a(2, 0, -127), s('SB', 2, 1, 0), l('LB', 1, 1, 0)], False),
        ('subword_store_base_alias', [a(1, 0, 65), s('SB', 1, 1, 0), l('LBU', 2, 1, 0)], False),
        ('reset_pending_lb', [a(1, 0, -128), s('SB', 1, 0, 1), l('LB', 2, 0, 1), l('LBU', 3, 0, 1)], True),
        ('reset_pending_lh', [a(1, 0, -128), s('SH', 1, 0, 2), l('LH', 2, 0, 2), l('LHU', 3, 0, 2)], True),
    ])
    rng = random.Random(SEED ^ 0xB17E)
    mixed = []
    for _ in range(32):
        width = rng.choice((1, 2, 4))
        address = rng.randrange(1024 // width) * width
        value = rng.randrange(1 << 32)
        upper, low = ((value + 2048) >> 12) & 0xFFFFF, value & 0xFFF
        low = low - 4096 if low >= 2048 else low
        load = rng.choice({1:('LB','LBU'), 2:('LH','LHU'), 4:('LW',)}[width])
        mixed.extend([encode_lui(2, upper), a(2, 2, low),
                      s({1:'SB',2:'SH',4:'SW'}[width], 2, 0, address), l(load, 3, 0, address)])
    cases.append(('subword_random_legal', mixed, False))
    return cases


def _upper_programs() -> list[tuple[str, list[int], bool]]:
    a, lui, auipc = encode_addi, encode_lui, encode_auipc
    cases = [
        ("upper_demo", [lui(1, 0x12345), a(1, 1, 0x678), encode_sw(1, 0, 64), encode_lw(2, 0, 64),
                         auipc(3, 0), a(3, 3, 16), encode_jalr(4, 3, 0),
                         encode_sw(0, 0, 64), encode_lw(5, 0, 64)], False),
        ("lui_boundaries", [lui(1, 0), lui(2, 0x80000), lui(31, 0xFFFFF)], False),
        ("lui_dirty_pseudo_rs1", [a(8, 0, 99), lui(1, 0x12345)], False),
        ("auipc_nonzero_pc", [a(8, 0, 99), auipc(2, 0x12345), auipc(3, 0), auipc(31, 0xFFFFF)], False),
        ("auipc_after_jump", [encode_jal(0, 12), 0, 0, auipc(1, 0), auipc(2, 1)], False),
        ("upper_x0", [lui(0, 0xABCDE), auipc(0, 0xFFFFF), a(1, 0, 7)], False),
        ("upper_rd31", [lui(31, 0x80000), auipc(31, 1), encode_add(1, 31, 31)], False),
        ("upper_negative_addi_constant", [lui(1, 0x12346), a(1, 1, -0x544)], False),
        ("upper_arithmetic_wrap", [lui(1, 0xFFFFF), lui(2, 1), encode_add(3, 1, 2)], False),
        ("upper_address_to_ram", [lui(1, 0), a(1, 1, 1020), lui(2, 0x80000),
                                  encode_sw(2, 1, 0), encode_lw(3, 1, 0)], False),
        ("upper_auipc_jalr_alias", [auipc(1, 0), encode_jalr(1, 1, 12), 0, auipc(2, 0)], False),
        ("upper_target_fault", [lui(1, 1), encode_jalr(2, 1, 0)], False),
    ]
    # U bits 14:12 are data, so exercise every apparent funct3 in both opcodes.
    cases.append(("upper_all_low_fields", [encoder(index + 1, 0x55550 | index)
                                           for encoder in (lui, auipc) for index in range(8)], False))
    rng = random.Random(SEED ^ 0x55505045)
    random_program = []
    for index in range(20):
        rd = index % 30 + 1
        encoder = lui if index % 2 == 0 else auipc
        random_program.extend([encoder(rd, rng.randrange(1 << 20)), a(rd, rd, rng.randint(-2048, 2047)),
                               encode_sw(rd, 0, (index % 16) * 4), encode_lw(31, 0, (index % 16) * 4)])
    cases.append(("upper_random_legal", random_program, False))
    return cases


def _control_programs() -> list[tuple[str, list[int], bool]]:
    a, b, j, jr = encode_addi, encode_branch, encode_jal, encode_jalr
    nop = a(0, 0, 0)
    cases = [("loop_demo", [a(1, 0, 1), a(2, 0, 11), a(3, 0, 0),
                             encode_add(3, 3, 1), a(1, 1, 1), b("BLT", 1, 2, -8),
                             encode_sw(3, 0, 64), encode_lw(4, 0, 64)], False)]
    comparisons = {
        "BEQ": ((1, 1), (1, 2)), "BNE": ((1, 2), (1, 1)),
        "BLT": ((-1, 1), (1, -1)), "BGE": ((1, -1), (-1, 1)),
        "BLTU": ((1, -1), (-1, 1)), "BGEU": ((-1, 1), (1, -1)),
    }
    for name, pairs in comparisons.items():
        for outcome, (first, second) in zip(("taken", "untaken"), pairs):
            cases.append((f"branch_{name.lower()}_{outcome}",
                          [a(1, 0, first), a(2, 0, second), b(name, 1, 2, 8),
                           a(3, 0, 99), a(4, 0, 7)], False))
    cases.extend([
        ("branch_signed_min", [a(1, 0, 1), encode_op_imm("SLLI", 1, 1, 31), a(2, 0, 1),
                                b("BLT", 1, 2, 8), 0, a(3, 0, 7)], False),
        ("branch_equal_edges", [a(1, 0, -1), a(2, 0, -1), b("BLT", 1, 2, 8),
                                 a(3, 0, 1), b("BGE", 1, 2, 8), 0,
                                 b("BLTU", 1, 2, 8), a(4, 0, 1),
                                 b("BGEU", 1, 2, 8), 0, a(5, 0, 1)], False),
        ("branch_skip_store", [a(1, 0, 9), b("BEQ", 0, 0, 8),
                                encode_sw(1, 0, 0), encode_lw(2, 0, 0)], False),
        ("branch_untaken_halfword", [b("BNE", 0, 0, 2), a(1, 0, 7)], False),
        ("branch_taken_halfword_fault", [b("BEQ", 0, 0, 2)], False),
        ("branch_target_range_fault", [b("BEQ", 0, 0, 1024)], False),
        ("branch_target_negative_fault", [b("BEQ", 0, 0, -4)], False),
        ("branch_rom_boundary", [b("BEQ", 0, 0, 1020)] + [nop] * 254 + [a(2, 0, 7)], False),
        ("jal_link_skip_illegal", [j(1, 8), 0, a(2, 0, 7)], False),
        ("jal_skip_store", [a(1, 0, 9), j(2, 8), encode_sw(1, 0, 0), encode_lw(3, 0, 0)], False),
        ("jal_negative_offset", [j(0, 8), j(2, 8), j(1, -4), a(3, 0, 7)], False),
        ("jal_x0_link", [j(0, 8), 0, a(2, 0, 7)], False),
        ("jal_halfword_fault", [j(1, 2)], False),
        ("jal_range_fault", [j(1, 1024)], False),
        ("jal_negative_fault", [j(1, -4)], False),
        ("jal_rom_boundary", [j(1, 1020)] + [nop] * 254 + [a(2, 0, 7)], False),
        ("jalr_clear_bit_zero", [a(1, 0, 13), jr(2, 1, 0), 0, a(3, 0, 7)], False),
        ("jalr_base_alias", [a(1, 0, 12), jr(1, 1, 0), 0, a(3, 0, 7)], False),
        ("jalr_x0_link", [a(1, 0, 13), jr(0, 1, 0), 0, a(3, 0, 7)], False),
        ("jalr_negative_offset", [a(2, 0, 16), jr(1, 2, -4), 0, a(3, 0, 7)], False),
        ("jalr_target_wrap", [a(2, 0, -4), jr(1, 2, 16), 0, a(3, 0, 7)], False),
        ("jalr_bit_one_fault", [a(1, 0, 3), jr(1, 1, 0)], False),
        ("jalr_range_fault", [a(1, 0, 1024), jr(1, 1, 0)], False),
        ("jalr_negative_fault", [jr(1, 0, -4)], False),
        ("jalr_rom_boundary", [a(1, 0, 1021), jr(31, 1, 0)] + [nop] * 253 + [a(2, 0, 7)], False),
        ("illegal_branch_funct3_2", [0x00002063], False),
        ("illegal_branch_funct3_3", [0x00003063], False),
        ("illegal_jalr_funct3", [0x00001067], False),
        ("control_fault_pc_after_jump", [j(0, 8), nop, b("BEQ", 0, 0, 2)], False),
    ])
    # Forward-only blocks guarantee termination while mixing all six branch
    # conditions, JAL links, JALR bit-zero clearing and skipped side effects.
    rng = random.Random(SEED ^ 0x4252414E)
    random_program = []
    branch_names = list(comparisons) + [rng.choice(tuple(comparisons)) for _ in range(6)]
    for name in branch_names:
        next_block = (len(random_program) + 10) * 4
        first, second = rng.choice((-8, -1, 0, 1, 7)), rng.choice((-8, -1, 0, 1, 7))
        random_program.extend([a(1, 0, first), a(2, 0, second), b(name, 1, 2, 8),
                               a(3, 3, 1), a(3, 3, rng.randint(1, 5)), j(4, 8),
                               encode_sw(3, 0, 0), a(5, 0, next_block + 1), jr(6, 5, 0), 0])
    cases.append(("control_random_legal", random_program, False))
    return cases


def _programs() -> list[tuple[str, list[int], bool]]:
    demo = [0x00500093, 0x00700113, 0x002081B3]
    r, i = encode_op, encode_op_imm
    alu_demo = [i("ADDI", 1, 0, -8), i("ADDI", 2, 0, 1),
                r("SRL", 3, 1, 2), r("SRA", 4, 1, 2),
                r("SLT", 5, 1, 2), r("SLTU", 6, 1, 2), i("ANDI", 7, 1, 15)]
    shift_immediate = [i("ADDI", 1, 0, -8), i("SRAI", 2, 1, 1),
                       i("SRLI", 3, 1, 1), i("SLLI", 4, 1, 0),
                       i("SRLI", 5, 1, 0), i("SRAI", 6, 1, 0),
                       i("SLLI", 7, 1, 31), i("SRLI", 8, 1, 31),
                       i("SRAI", 9, 1, 31), i("ADDI", 10, 0, 1),
                       i("SLLI", 11, 10, 31)]
    x0_writes = [i("ADDI", 1, 0, -8), i("ADDI", 2, 0, 1)]
    x31 = [i("ADDI", 30, 0, -8), i("ADDI", 29, 0, 1)]
    for operation in ALU_INSTRUCTIONS:
        if operation in ("SLLI", "SRLI", "SRAI"):
            x0_writes.append(i(operation, 0, 1, 31))
            x31.append(i(operation, 31, 31, 1))
        elif operation in ("ADDI", "SLTI", "SLTIU", "XORI", "ORI", "ANDI"):
            x0_writes.append(i(operation, 0, 1, -1))
            x31.append(i(operation, 31, 31, 1))
        else:
            x0_writes.append(r(operation, 0, 1, 2))
            x31.append(r(operation, 31, 30, 29))
    # Reach both unsigned and signed wrap boundaries using only the supported
    # instructions: doubling 1 thirty-one times constructs 0x80000000.
    add_wrap = [encode_addi(1, 0, -1), encode_addi(2, 0, 1),
                encode_add(3, 1, 2), encode_add(4, 1, 1), encode_addi(5, 0, 1)]
    add_wrap.extend(encode_add(5, 5, 5) for _ in range(31))
    add_wrap.extend([encode_sub(6, 5, 2), encode_add(7, 6, 2)])
    rng = random.Random(SEED)
    # Include each operation at least once before adding more mixed operations;
    # shuffle the whole list so instruction coverage does not rely on chance.
    operations = list(ALU_INSTRUCTIONS)
    operations.extend(rng.choice(ALU_INSTRUCTIONS) for _ in range(48 - len(operations)))
    rng.shuffle(operations)
    random_legal = []
    for operation in operations:
        rd, rs1 = rng.randrange(32), rng.randrange(32)
        if operation in ("SLLI", "SRLI", "SRAI"):
            word = i(operation, rd, rs1, rng.randrange(32))
        elif operation in ("ADDI", "SLTI", "SLTIU", "XORI", "ORI", "ANDI"):
            word = i(operation, rd, rs1, rng.randint(-2048, 2047))
        else:
            word = r(operation, rd, rs1, rng.randrange(32))
        random_legal.append(word)
    memory_demo = [i("ADDI", 1, 0, 64), i("ADDI", 2, 0, 12),
                   encode_sw(2, 1, 0), encode_lw(3, 1, 0), i("ADDI", 4, 3, 5),
                   encode_sw(4, 1, 4), encode_lw(5, 1, 4), r("SUB", 6, 5, 3)]
    # x31 is reserved as a stable base.  All generated offsets select aligned
    # words in the complete RAM range, and every supported instruction occurs.
    memory_rng = random.Random(SEED ^ 0x4D454D)
    memory_random = [i("ADDI", 31, 0, 512), i("ADDI", 1, 0, -9),
                     encode_sw(1, 31, 0), encode_lw(2, 31, 0)]
    memory_operations = list(MEMORY_INSTRUCTIONS)
    memory_operations.extend(memory_rng.choice(MEMORY_INSTRUCTIONS)
                             for _ in range(60 - len(memory_operations)))
    memory_rng.shuffle(memory_operations)
    for operation in memory_operations:
        rd, rs1 = memory_rng.randrange(31), memory_rng.randrange(32)
        if operation == "LW":
            word = encode_lw(rd, 31, memory_rng.randrange(256) * 4 - 512)
        elif operation == "SW":
            word = encode_sw(memory_rng.randrange(32), 31, memory_rng.randrange(256) * 4 - 512)
        elif operation in ("SLLI", "SRLI", "SRAI"):
            word = i(operation, rd, rs1, memory_rng.randrange(32))
        elif operation in ("ADDI", "SLTI", "SLTIU", "XORI", "ORI", "ANDI"):
            word = i(operation, rd, rs1, memory_rng.randint(-2048, 2047))
        else:
            word = r(operation, rd, rs1, memory_rng.randrange(32))
        memory_random.append(word)
    return [
        ("demo", demo, False),
        ("alu_demo", alu_demo, False),
        ("shift_immediate", shift_immediate, False),
        ("negative_immediates", [encode_addi(1, 0, -1), encode_addi(2, 1, -2),
                                 encode_addi(3, 2, 1), encode_addi(4, 3, -17),
                                 encode_addi(5, 4, 19)], False),
        ("immediate_limits", [encode_addi(1, 0, -2048), encode_addi(2, 1, 2047),
                              encode_addi(3, 2, 1), encode_addi(4, 0, 2047),
                              encode_addi(5, 4, -2048), encode_addi(6, 0, 1026)], False),
        ("add_wrap", add_wrap, False),
        ("sub_wrap", [encode_addi(1, 0, 1), encode_sub(2, 0, 1),
                       encode_sub(3, 1, 2), encode_sub(3, 3, 1),
                       encode_sub(4, 2, 1), encode_sub(5, 0, 4)], False),
        ("dependencies", [encode_addi(1, 0, 3), encode_add(1, 1, 1),
                           encode_add(2, 1, 1), encode_sub(2, 2, 1),
                           encode_addi(2, 2, -1), encode_sub(3, 1, 2),
                           encode_add(3, 3, 3), encode_sub(3, 3, 3)], False),
        ("x0_writes", x0_writes, False),
        ("x31", x31, False),
        ("register_shifts", [i("ADDI", 1, 0, -8), i("ADDI", 2, 0, 32),
                              r("SLL", 3, 1, 2), r("SRL", 4, 1, 2), r("SRA", 5, 1, 2),
                              i("ADDI", 2, 0, -1), r("SLL", 6, 1, 2),
                              r("SRL", 7, 1, 2), r("SRA", 8, 1, 2)], False),
        ("compare_signed_unsigned", [i("ADDI", 1, 0, -1), i("ADDI", 2, 0, 1),
                                      r("SLT", 3, 1, 2), r("SLTU", 4, 1, 2),
                                      r("SLT", 5, 2, 1), r("SLTU", 6, 2, 1),
                                      r("SLT", 7, 1, 1), r("SLTU", 8, 1, 1),
                                      i("SLTI", 9, 1, -1), i("SLTI", 10, 1, 0),
                                      i("SLTI", 11, 2, -1)], False),
        ("logic_register", [i("ADDI", 1, 0, 0x555), i("ADDI", 2, 0, 0x333),
                             r("XOR", 3, 1, 2), r("OR", 4, 1, 2), r("AND", 5, 1, 2),
                             i("ADDI", 6, 0, -1), r("XOR", 7, 1, 6),
                             r("AND", 8, 2, 6), r("OR", 9, 1, 6)], False),
        ("logic_immediate", [i("ADDI", 1, 0, -8), i("XORI", 2, 1, -1),
                              i("ORI", 3, 0, -2048), i("ANDI", 4, 1, -1),
                              i("ANDI", 5, 1, 15), i("XORI", 6, 1, 2047),
                              i("ORI", 7, 2, -1), i("ANDI", 8, 7, -2048)], False),
        ("sltiu_negative_immediate", [i("ADDI", 1, 0, -8), i("SLTIU", 2, 1, -1),
                                      i("SLTIU", 3, 1, -2048), i("SLTIU", 4, 0, -1),
                                      i("ADDI", 5, 0, -1), i("SLTIU", 6, 5, -1),
                                      i("SLTIU", 7, 0, 0), i("SLTIU", 8, 0, 1)], False),
        ("shift_positive", [i("ADDI", 1, 0, 7), i("SRAI", 2, 1, 1),
                             i("SRAI", 3, 1, 31), i("SRLI", 4, 1, 1),
                             i("ADDI", 5, 0, 1), r("SRA", 6, 1, 5),
                             i("SLLI", 7, 5, 31), i("SRAI", 8, 7, 31)], False),
        ("illegal_opcode", [0x00000000], False),
        ("illegal_slli_funct7", [0x02101093], False),
        ("illegal_r_funct7", [0x042081B3], False),
        ("illegal_system", [0x00000073], False),
        ("illegal_slli_bit30", [0x40101093], False),
        ("illegal_srli_funct7", [0x02105093], False),
        ("illegal_srai_reserved", [0x42105093], False),
        ("illegal_r_reserved_shift", [0x402091B3], False),
        ("illegal_r_reserved_logic", [0x4020F1B3], False),
        ("prefix_then_fault", demo + [0x042081B3, encode_addi(1, 0, 99)], False),
        ("random_legal", random_legal, False),
        ("reset_during_fetch", demo, True),
        # x5 is zero only after reset.  After the first two commits it is nine,
        # so a restarted core that omitted register-file reset produces 10/19.
        ("reset_after_write", [encode_addi(1, 5, 1), encode_addi(5, 0, 9),
                                encode_add(3, 1, 5)], True),
        ("memory_demo", memory_demo, False),
        ("memory_negative_offset", [i("ADDI", 1, 0, 68), i("ADDI", 2, 0, 12),
                                     encode_sw(2, 1, -4), encode_lw(3, 1, -4)], False),
        ("memory_s_imm_min", [i("ADDI", 1, 0, 1024), i("ADDI", 1, 1, 1024),
                               i("ADDI", 2, 0, -17), encode_sw(2, 1, -2048),
                               encode_lw(3, 1, -2048)], False),
        ("memory_s_imm_max_wrap", [i("ADDI", 1, 0, -2047), i("ADDI", 2, 0, 19),
                                    encode_sw(2, 1, 2047), encode_lw(3, 1, 2047)], False),
        ("memory_wrap_to_zero", [i("ADDI", 1, 0, -4), i("ADDI", 2, 0, 23),
                                  encode_sw(2, 1, 4), encode_lw(3, 1, 4)], False),
        ("memory_boundary", [i("ADDI", 1, 0, 1020), i("ADDI", 2, 0, 31),
                              encode_sw(2, 1, 0), encode_lw(3, 1, 0),
                              encode_sw(3, 0, 0), encode_lw(4, 0, 0)], False),
        ("memory_load_base_alias", [i("ADDI", 1, 0, 64), i("ADDI", 2, 0, 128),
                                     encode_sw(2, 1, 0), encode_lw(1, 1, 0)], False),
        ("memory_store_base_alias", [i("ADDI", 1, 0, 64), encode_sw(1, 1, 0),
                                      encode_lw(2, 1, 0)], False),
        ("memory_overwrite", [i("ADDI", 1, 0, 64), i("ADDI", 2, 0, 1),
                               encode_sw(2, 1, 0), i("ADDI", 2, 0, 2),
                               encode_sw(2, 1, 0), encode_lw(3, 1, 0)], False),
        ("memory_x0", [i("ADDI", 1, 0, -1), encode_sw(1, 0, 0), encode_lw(0, 0, 0),
                        encode_sw(0, 0, 0), encode_lw(2, 0, 0)], False),
        ("memory_x31", [i("ADDI", 31, 0, -7), encode_sw(31, 0, 4),
                         i("ADDI", 31, 0, 0), encode_lw(31, 0, 4)], False),
        ("memory_lw_alignment_fault", [encode_lw(1, 0, 2)], False),
        ("memory_sw_alignment_fault", [i("ADDI", 2, 0, 9), encode_sw(2, 0, 2)], False),
        ("memory_lw_range_fault", [encode_lw(1, 0, 1024)], False),
        ("memory_sw_range_fault", [i("ADDI", 2, 0, 9), encode_sw(2, 0, 1024)], False),
        ("memory_lw_negative_fault", [encode_lw(1, 0, -4)], False),
        ("memory_sw_negative_fault", [i("ADDI", 2, 0, 9), encode_sw(2, 0, -4)], False),
        ("memory_offset_max_fault", [i("ADDI", 2, 0, 9), encode_sw(2, 0, 2047)], False),
        ("memory_offset_min_fault", [i("ADDI", 2, 0, 9), encode_sw(2, 0, -2048)], False),
        ("memory_lw_x0_fault", [encode_lw(0, 0, 2)], False),
        ("illegal_load_funct3_3", [0x00003083], False),
        ("illegal_store_funct3_3", [0x00203023], False),
        ("memory_prefix_then_fault", [i("ADDI", 1, 0, 7), encode_sw(1, 0, 0),
                                       encode_lw(2, 0, 0), encode_sw(1, 0, 2),
                                       encode_sw(0, 0, 0)], False),
        ("memory_random_legal", memory_random, False),
        ("reset_pending_load", [i("ADDI", 1, 0, 12), encode_sw(1, 0, 0),
                                 encode_lw(2, 0, 0), i("ADDI", 3, 2, 1)], True),
    ] + _control_programs() + _upper_programs() + _subword_programs() + _c_programs() + _multiply_programs() + _fir_programs()


def _c_programs():
    from tools.c_demo import load_demo
    image, _ = load_demo()
    return [("c_array_sum", list(image.program_words), False)]


def generate_cpu_vectors(directory: Path) -> dict:
    """Write relative-path JSON/Tcl metadata and one directory per program."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for name, program, inject_reset in _programs():
        relative = Path("cases") / name
        case_directory = directory / relative
        case_directory.mkdir(parents=True, exist_ok=True)
        initial_memory_file = None
        initial_memory = None
        if name == "c_array_sum":
            from tools.c_demo import load_demo
            image, _ = load_demo()
            initial_memory = image.memory_words
            initial_memory_file = relative / "initial_memory.txt"
            (directory/initial_memory_file).write_text(''.join(f'{word:08X}\n' for word in initial_memory),
                                                       encoding='ascii', newline='\n')
        elif name.startswith("software_fir"):
            from tools.software_fir import load_fir,fir_inputs
            initial_memory=fir_inputs()[name]
            initial_memory_file=relative / "initial_memory.txt"
            (directory/initial_memory_file).write_text(''.join(f'{word:08X}\n' for word in initial_memory),
                                                       encoding='ascii',newline='\n')
        result = run_program(program, initial_memory=initial_memory)
        fir_evidence=None
        if name.startswith("software_fir"):
            from tools.software_fir import audit_result
            _,firmware=load_fir()
            outputs,accumulators=audit_result(result,initial_memory,firmware)
            fir_evidence={"outputs":list(outputs),"accumulators":list(accumulators),
                          "multiply_commits":sum(t.instruction&0xFE00707F==0x02000033 for t in result.trace)}
        program_file = relative / "program.hex"
        trace_file = relative / "expected_trace.txt"
        registers_file = relative / "expected_registers.txt"
        memory_file = relative / "expected_memory.txt"
        memory_trace_file = relative / "expected_memory_trace.txt"
        (directory / program_file).write_text("".join(f"{word:08X}\n" for word in program),
                                               encoding="ascii", newline="\n")
        (directory / trace_file).write_text(
            "".join(f"{entry.pc:08X} {entry.instruction:08X} {entry.rd} {entry.value:08X} {entry.next_pc:08X}\n"
                    for entry in result.trace), encoding="ascii", newline="\n")
        (directory / registers_file).write_text(
            "".join(f"{word:08X}\n" for word in result.registers[1:]),
            encoding="ascii", newline="\n")
        (directory / memory_file).write_text(
            "".join(f"{word:08X}\n" for word in result.memory), encoding="ascii", newline="\n")
        (directory / memory_trace_file).write_text(
            "".join(f"{event.mode} {event.address:08X} {event.value:08X} {event.byte_enable:X}\n"
                    for event in result.memory_trace), encoding="ascii", newline="\n")
        cases.append({"name": name, "program_file": program_file.as_posix(),
                      "trace_file": trace_file.as_posix(),
                      "registers_file": registers_file.as_posix(),
                      "retired_count": len(result.trace), "expect_fault": result.fault,
                      "fault_pc": result.fault_pc, "inject_reset": inject_reset,
                      "memory_file": memory_file.as_posix(),
                      "memory_trace_file": memory_trace_file.as_posix(),
                      "memory_count": len(result.memory_trace),
                      "multiply_count": sum(t.instruction&0xFE00707F==0x02000033 for t in result.trace),
                      "reset_during_load": name.startswith("reset_pending_")})
        if initial_memory_file is not None:
            cases[-1]["initial_memory_file"] = initial_memory_file.as_posix()
            cases[-1]["loader_words"] = 256
        if fir_evidence is not None:cases[-1]["fir_reference"]=fir_evidence
    report = {"contract": "tiny-cpu-rv32i-mul-v7", "seed": SEED,
              "supported_instructions": list(SUPPORTED_INSTRUCTIONS),
              "case_count": len(cases), "cases": cases,
              "instruction_count": sum(case["retired_count"] for case in cases),
              "memory_count": sum(case["memory_count"] for case in cases),
              "source_sha256": {
                  relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                  for relative in ("model/tiny_cpu.py", "tools/generate_cpu_vectors.py")}}
    (directory / "cpu_cases.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                               encoding="ascii", newline="\n")
    tcl_rows = ["set tiny_cpu_cases {\n"]
    for case in cases:
        tcl_rows.append(f"  {{{case['name']} {case['program_file']} {case['trace_file']} "
                        f"{case['registers_file']} {case['retired_count']} "
                        f"{str(case['expect_fault']).lower()} {case['fault_pc']} "
                        f"{str(case['inject_reset']).lower()} {case['memory_file']} "
                        f"{case['memory_trace_file']} {str(case['reset_during_load']).lower()}}}\n")
    tcl_rows.append("}\n")
    (directory / "cpu_cases.tcl").write_text("".join(tcl_rows), encoding="ascii", newline="\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "sim/vectors/tiny_cpu")
    print(json.dumps(generate_cpu_vectors(parser.parse_args().output), indent=2))
