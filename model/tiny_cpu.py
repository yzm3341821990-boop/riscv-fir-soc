"""Architectural reference for 37 RV32I instructions plus the M-extension MUL.

This is deliberately a small RV32I instruction subset.  Programs start from
reset state (PC zero and every register zero), and normal runs stop when the
provided words are exhausted.  Hardware testbenches stop after the same number
of commits; the remaining ROM slots contain ADDI x0, x0, 0.
"""

from dataclasses import dataclass
from typing import Iterable

MASK = 0xFFFFFFFF
ROM_WORDS = 256
RAM_WORDS = 256
REGISTER_OPERATIONS = {
    "ADD": (0, 0), "SUB": (0x20, 0), "SLL": (0, 1), "SLT": (0, 2),
    "SLTU": (0, 3), "XOR": (0, 4), "SRL": (0, 5), "SRA": (0x20, 5),
    "OR": (0, 6), "AND": (0, 7), "MUL": (1, 0),
}
IMMEDIATE_OPERATIONS = {"ADDI": 0, "SLTI": 2, "SLTIU": 3,
                        "XORI": 4, "ORI": 6, "ANDI": 7}
SHIFT_IMMEDIATE_OPERATIONS = {"SLLI": (0, 1), "SRLI": (0, 5), "SRAI": (0x20, 5)}
ALU_INSTRUCTIONS = tuple(n for n in REGISTER_OPERATIONS if n != "MUL") + tuple(IMMEDIATE_OPERATIONS) + tuple(SHIFT_IMMEDIATE_OPERATIONS)
MEMORY_INSTRUCTIONS = ALU_INSTRUCTIONS + ("LW", "SW")
LOAD_OPERATIONS = {"LB": 0, "LH": 1, "LW": 2, "LBU": 4, "LHU": 5}
STORE_OPERATIONS = {"SB": 0, "SH": 1, "SW": 2}
BRANCH_OPERATIONS = {"BEQ": 0, "BNE": 1, "BLT": 4, "BGE": 5, "BLTU": 6, "BGEU": 7}
UPPER_IMMEDIATE_OPERATIONS = {"LUI": 0x37, "AUIPC": 0x17}
SUPPORTED_INSTRUCTIONS = (MEMORY_INSTRUCTIONS + tuple(BRANCH_OPERATIONS) + ("JAL", "JALR")
                          + tuple(UPPER_IMMEDIATE_OPERATIONS) + ("LB", "LH", "LBU", "LHU", "SB", "SH", "MUL"))


def _integer(value: int, lower: int, upper: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")
    return value


def encode_op(operation: str, rd: int, rs1: int, rs2: int) -> int:
    """Assemble a base integer register operation or MUL."""
    if not isinstance(operation, str):
        raise TypeError("operation must be a mnemonic string")
    operation = operation.upper()
    if operation not in REGISTER_OPERATIONS:
        raise ValueError(f"unsupported register operation: {operation}")
    _integer(rd, 0, 31, "rd")
    _integer(rs1, 0, 31, "rs1")
    _integer(rs2, 0, 31, "rs2")
    funct7, funct3 = REGISTER_OPERATIONS[operation]
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0x33


def encode_op_imm(operation: str, rd: int, rs1: int, imm: int) -> int:
    """Assemble a signed immediate ALU operation or a shift by zero to 31."""
    if not isinstance(operation, str):
        raise TypeError("operation must be a mnemonic string")
    operation = operation.upper()
    _integer(rd, 0, 31, "rd")
    _integer(rs1, 0, 31, "rs1")
    if operation in SHIFT_IMMEDIATE_OPERATIONS:
        _integer(imm, 0, 31, "shift amount")
        funct7, funct3 = SHIFT_IMMEDIATE_OPERATIONS[operation]
        immediate_bits = (funct7 << 5) | imm
    elif operation in IMMEDIATE_OPERATIONS:
        _integer(imm, -2048, 2047, "immediate")
        funct3, immediate_bits = IMMEDIATE_OPERATIONS[operation], imm & 0xFFF
    else:
        raise ValueError(f"unsupported immediate operation: {operation}")
    return (immediate_bits << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0x13


def encode_addi(rd: int, rs1: int, imm: int) -> int:
    return encode_op_imm("ADDI", rd, rs1, imm)


def encode_lui(rd: int, imm20: int) -> int:
    """Assemble LUI from an unsigned raw twenty-bit upper field."""
    _integer(rd, 0, 31, "rd")
    _integer(imm20, 0, 0xFFFFF, "imm20")
    return (imm20 << 12) | (rd << 7) | 0x37


def encode_auipc(rd: int, imm20: int) -> int:
    """Assemble AUIPC; its U field has the same raw format as LUI."""
    _integer(rd, 0, 31, "rd")
    _integer(imm20, 0, 0xFFFFF, "imm20")
    return (imm20 << 12) | (rd << 7) | 0x17


def encode_add(rd: int, rs1: int, rs2: int) -> int:
    """Assemble ADD rd, rs1, rs2."""
    return encode_op("ADD", rd, rs1, rs2)


def encode_sub(rd: int, rs1: int, rs2: int) -> int:
    """Assemble SUB rd, rs1, rs2."""
    return encode_op("SUB", rd, rs1, rs2)


def encode_sll(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("SLL", rd, rs1, rs2)


def encode_slt(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("SLT", rd, rs1, rs2)


def encode_sltu(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("SLTU", rd, rs1, rs2)


def encode_xor(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("XOR", rd, rs1, rs2)


def encode_srl(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("SRL", rd, rs1, rs2)


def encode_sra(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("SRA", rd, rs1, rs2)


def encode_or(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("OR", rd, rs1, rs2)


def encode_and(rd: int, rs1: int, rs2: int) -> int:
    return encode_op("AND", rd, rs1, rs2)


def encode_slti(rd: int, rs1: int, imm: int) -> int:
    return encode_op_imm("SLTI", rd, rs1, imm)


def encode_sltiu(rd: int, rs1: int, imm: int) -> int:
    return encode_op_imm("SLTIU", rd, rs1, imm)


def encode_xori(rd: int, rs1: int, imm: int) -> int:
    return encode_op_imm("XORI", rd, rs1, imm)


def encode_ori(rd: int, rs1: int, imm: int) -> int:
    return encode_op_imm("ORI", rd, rs1, imm)


def encode_andi(rd: int, rs1: int, imm: int) -> int:
    return encode_op_imm("ANDI", rd, rs1, imm)


def encode_slli(rd: int, rs1: int, shamt: int) -> int:
    return encode_op_imm("SLLI", rd, rs1, shamt)


def encode_srli(rd: int, rs1: int, shamt: int) -> int:
    return encode_op_imm("SRLI", rd, rs1, shamt)


def encode_srai(rd: int, rs1: int, shamt: int) -> int:
    return encode_op_imm("SRAI", rd, rs1, shamt)


def encode_load(name: str, rd: int, rs1: int, offset: int) -> int:
    """Assemble a load with a signed twelve-bit byte offset."""
    if not isinstance(name, str):
        raise TypeError("load name must be a mnemonic string")
    name = name.upper()
    if name not in LOAD_OPERATIONS:
        raise ValueError(f"unsupported load: {name}")
    _integer(rd, 0, 31, "rd")
    _integer(rs1, 0, 31, "rs1")
    _integer(offset, -2048, 2047, "offset")
    return ((offset & 0xFFF) << 20) | (rs1 << 15) | (LOAD_OPERATIONS[name] << 12) | (rd << 7) | 0x03


def encode_store(name: str, rs2: int, rs1: int, offset: int) -> int:
    """Assemble a store, including both split S-type offset fields."""
    if not isinstance(name, str):
        raise TypeError("store name must be a mnemonic string")
    name = name.upper()
    if name not in STORE_OPERATIONS:
        raise ValueError(f"unsupported store: {name}")
    _integer(rs2, 0, 31, "rs2")
    _integer(rs1, 0, 31, "rs1")
    _integer(offset, -2048, 2047, "offset")
    immediate = offset & 0xFFF
    return ((immediate >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (STORE_OPERATIONS[name] << 12) | ((immediate & 31) << 7) | 0x23


def encode_lw(rd: int, rs1: int, offset: int) -> int:
    return encode_load("LW", rd, rs1, offset)


def encode_sw(rs2: int, rs1: int, offset: int) -> int:
    return encode_store("SW", rs2, rs1, offset)


def _even_offset(offset: int, lower: int, upper: int) -> int:
    _integer(offset, lower, upper, "offset")
    if offset & 1:
        raise ValueError("control offset must be an even byte count")
    return offset


def encode_branch(name: str, rs1: int, rs2: int, offset: int) -> int:
    """Assemble a conditional branch with a signed, even B-type offset."""
    if not isinstance(name, str):
        raise TypeError("branch name must be a mnemonic string")
    name = name.upper()
    if name not in BRANCH_OPERATIONS:
        raise ValueError(f"unsupported branch: {name}")
    _integer(rs1, 0, 31, "rs1")
    _integer(rs2, 0, 31, "rs2")
    immediate = _even_offset(offset, -4096, 4094) & 0x1FFF
    return (((immediate >> 12) << 31) | (((immediate >> 5) & 63) << 25)
            | (rs2 << 20) | (rs1 << 15) | (BRANCH_OPERATIONS[name] << 12)
            | (((immediate >> 1) & 15) << 8) | (((immediate >> 11) & 1) << 7) | 0x63)


def encode_beq(rs1: int, rs2: int, offset: int) -> int:
    return encode_branch("BEQ", rs1, rs2, offset)


def encode_bne(rs1: int, rs2: int, offset: int) -> int:
    return encode_branch("BNE", rs1, rs2, offset)


def encode_blt(rs1: int, rs2: int, offset: int) -> int:
    return encode_branch("BLT", rs1, rs2, offset)


def encode_bge(rs1: int, rs2: int, offset: int) -> int:
    return encode_branch("BGE", rs1, rs2, offset)


def encode_bltu(rs1: int, rs2: int, offset: int) -> int:
    return encode_branch("BLTU", rs1, rs2, offset)


def encode_bgeu(rs1: int, rs2: int, offset: int) -> int:
    return encode_branch("BGEU", rs1, rs2, offset)


def encode_jal(rd: int, offset: int) -> int:
    """Assemble JAL with a signed, even J-type offset."""
    _integer(rd, 0, 31, "rd")
    immediate = _even_offset(offset, -1048576, 1048574) & 0x1FFFFF
    return (((immediate >> 20) << 31) | (((immediate >> 1) & 0x3FF) << 21)
            | (((immediate >> 11) & 1) << 20) | (immediate & 0xFF000) | (rd << 7) | 0x6F)


def encode_jalr(rd: int, rs1: int, offset: int) -> int:
    """Assemble JALR with a signed twelve-bit offset and funct3 zero."""
    _integer(rd, 0, 31, "rd")
    _integer(rs1, 0, 31, "rs1")
    _integer(offset, -2048, 2047, "offset")
    return ((offset & 0xFFF) << 20) | (rs1 << 15) | (rd << 7) | 0x67


def _alu(operation: str, first: int, second: int) -> int:
    signed_first = first - (1 << 32) if first & 0x80000000 else first
    signed_second = second - (1 << 32) if second & 0x80000000 else second
    shift = second & 31
    if operation == "ADD":
        return first + second
    if operation == "SUB":
        return first - second
    if operation == "MUL":
        return first * second
    if operation == "SLL":
        return first << shift
    if operation == "SLT":
        return int(signed_first < signed_second)
    if operation == "SLTU":
        return int(first < second)
    if operation == "XOR":
        return first ^ second
    if operation == "SRL":
        return first >> shift
    if operation == "SRA":
        return signed_first >> shift
    if operation == "OR":
        return first | second
    return first & second


@dataclass(frozen=True)
class TraceEntry:
    pc: int
    instruction: int
    rd: int
    value: int
    next_pc: int = 0


@dataclass(frozen=True)
class MemoryEvent:
    mode: str
    address: int
    value: int
    byte_enable: int = 15


@dataclass(frozen=True)
class ExecutionResult:
    trace: tuple[TraceEntry, ...]
    registers: tuple[int, ...]
    pc: int
    fault: bool
    fault_pc: int
    memory: tuple[int, ...] = (0,) * RAM_WORDS
    memory_trace: tuple[MemoryEvent, ...] = ()


def run_program(words: Iterable[int], initial_memory: Iterable[int] | None = None,
                max_steps: int = 4096) -> ExecutionResult:
    """Run from reset until ROM exhaustion or the first illegal instruction.

    A legal instruction targeting x0 commits a trace value of zero.  An illegal
    word neither commits nor changes PC or any register, and no following word
    executes.  The caller receives the exact state at that fault boundary.
    RAM is a copied, zero-padded array of at most 256 raw words.  Passing a prior
    result's memory models a CPU reset that clears registers while retaining RAM.
    Control targets must be aligned and inside the fixed 256-word ROM.  Reaching
    an unprovided word ends this bounded reference run normally.  A still-running
    program that exhausts max_steps raises RuntimeError, rather than a CPU fault.
    """
    program = tuple(words)
    if len(program) > ROM_WORDS:
        raise ValueError(f"program exceeds the {ROM_WORDS}-word instruction ROM")
    for word in program:
        _integer(word, 0, MASK, "instruction")
    if not isinstance(max_steps, int) or isinstance(max_steps, bool):
        raise TypeError("max_steps must be an integer")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    memory = list(initial_memory) if initial_memory is not None else []
    if len(memory) > RAM_WORDS:
        raise ValueError(f"initial memory exceeds {RAM_WORDS} words")
    for word in memory:
        _integer(word, 0, MASK, "memory word")
    memory.extend([0] * (RAM_WORDS - len(memory)))
    memory_trace = []
    registers, trace = [0] * 32, []
    pc = 0
    while pc // 4 < len(program):
        if len(trace) >= max_steps:
            raise RuntimeError(f"program exceeded max_steps={max_steps} at PC {pc:08X}")
        instruction = program[pc // 4]
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 31
        funct3 = (instruction >> 12) & 7
        rs1 = (instruction >> 15) & 31
        rs2 = (instruction >> 20) & 31
        funct7 = instruction >> 25
        operation = None
        next_pc = (pc + 4) & MASK
        if opcode == 0x37:
            operation, value = "LUI", instruction & 0xFFFFF000
        elif opcode == 0x17:
            operation, value = "AUIPC", (pc + (instruction & 0xFFFFF000)) & MASK
        elif opcode == 0x63:
            name = next((name for name, encoding in BRANCH_OPERATIONS.items() if encoding == funct3), None)
            if name is not None:
                first, second = registers[rs1], registers[rs2]
                signed_first = first - (1 << 32) if first & 0x80000000 else first
                signed_second = second - (1 << 32) if second & 0x80000000 else second
                taken = {0: first == second, 1: first != second,
                         4: signed_first < signed_second, 5: signed_first >= signed_second,
                         6: first < second, 7: first >= second}[funct3]
                immediate = (((instruction >> 31) << 12) | (((instruction >> 7) & 1) << 11)
                             | (((instruction >> 25) & 63) << 5) | (((instruction >> 8) & 15) << 1))
                if immediate & 0x1000:
                    immediate -= 0x2000
                target = (pc + immediate) & MASK
                if not taken or (target % 4 == 0 and target < ROM_WORDS * 4):
                    operation, rd, value = name, 0, 0
                    if taken:
                        next_pc = target
        elif opcode == 0x6F:
            immediate = (((instruction >> 31) << 20) | (instruction & 0xFF000)
                         | (((instruction >> 20) & 1) << 11) | (((instruction >> 21) & 0x3FF) << 1))
            if immediate & 0x100000:
                immediate -= 0x200000
            target = (pc + immediate) & MASK
            if target % 4 == 0 and target < ROM_WORDS * 4:
                operation, value, next_pc = "JAL", next_pc, target
        elif opcode == 0x67 and funct3 == 0:
            immediate = instruction >> 20
            if immediate & 0x800:
                immediate -= 0x1000
            target = ((registers[rs1] + immediate) & MASK) & ~1
            if target % 4 == 0 and target < ROM_WORDS * 4:
                operation, value, next_pc = "JALR", next_pc, target
        elif opcode in (0x03, 0x23):
            if opcode == 0x03:
                immediate = instruction >> 20
            else:
                immediate = ((instruction >> 25) << 5) | ((instruction >> 7) & 31)
            if immediate & 0x800:
                immediate -= 0x1000
            address = (registers[rs1] + immediate) & MASK
            # Validate the full wrapped byte address before accessing RAM or
            # adding a bus event, including loads whose destination is x0.
            valid_width = funct3 in (LOAD_OPERATIONS.values() if opcode == 0x03 else STORE_OPERATIONS.values())
            width = 1 << (funct3 & 3) if valid_width else 0
            if valid_width and address % width == 0 and address + width <= RAM_WORDS * 4:
                lane = address % 4
                byte_enable = ((1 << width) - 1) << lane
                if opcode == 0x03:
                    raw_word = memory[address // 4]
                    value = (raw_word >> (8 * lane)) & ((1 << (8 * width)) - 1)
                    if funct3 in (0, 1) and value & (1 << (8 * width - 1)):
                        value -= 1 << (8 * width)
                    memory_trace.append(MemoryEvent("R", address, raw_word, byte_enable))
                    operation = next(name for name, code in LOAD_OPERATIONS.items() if code == funct3)
                else:
                    mask = ((1 << (8 * width)) - 1) << (8 * lane)
                    bus_data = (registers[rs2] << (8 * lane)) & mask
                    memory[address // 4] = (memory[address // 4] & ~mask) | bus_data
                    memory_trace.append(MemoryEvent("W", address, bus_data, byte_enable))
                    operation, rd, value = next(name for name, code in STORE_OPERATIONS.items() if code == funct3), 0, 0
        elif opcode == 0x33:
            operation = next((name for name, encoding in REGISTER_OPERATIONS.items()
                              if encoding == (funct7, funct3)), None)
            operand = registers[rs2]
        elif opcode == 0x13:
            if funct3 in (1, 5):
                name = next((name for name, encoding in SHIFT_IMMEDIATE_OPERATIONS.items()
                             if encoding == (funct7, funct3)), None)
                operation = name[:-1] if name else None
                operand = rs2
            else:
                name = next((name for name, encoding in IMMEDIATE_OPERATIONS.items()
                             if encoding == funct3), None)
                operation = "SLTU" if name == "SLTIU" else name[:-1] if name else None
                immediate = instruction >> 20
                if immediate & 0x800:
                    immediate -= 0x1000
                operand = immediate & MASK
        if operation is None:
            return ExecutionResult(tuple(trace), tuple(registers), pc, True, pc,
                                   tuple(memory), tuple(memory_trace))
        if opcode not in (0x03, 0x23, 0x63, 0x6F, 0x67, 0x37, 0x17):
            value = _alu(operation, registers[rs1], operand)
        value = (value & MASK) if rd else 0
        if rd:
            registers[rd] = value
        trace.append(TraceEntry(pc, instruction, rd, value, next_pc))
        pc = next_pc
    return ExecutionResult(tuple(trace), tuple(registers), pc, False, 0,
                           tuple(memory), tuple(memory_trace))
