"""Bit-vector reference for alu32-rv32i-v1; operands are raw port values."""

MASK = 0xFFFFFFFF


def alu_result(a: int, b: int, operation: int) -> int:
    for name, value, upper in (("a", a, MASK), ("b", b, MASK), ("operation", operation, 15)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer")
        if not 0 <= value <= upper:
            raise ValueError(f"{name} does not fit its port width")
    signed_a = a - (1 << 32) if a & 0x80000000 else a
    signed_b = b - (1 << 32) if b & 0x80000000 else b
    shift = b & 31
    if operation == 0:
        result = a + b
    elif operation == 1:
        result = a - b
    elif operation == 2:
        result = a & b
    elif operation == 3:
        result = a | b
    elif operation == 4:
        result = a ^ b
    elif operation == 5:
        result = a << shift
    elif operation == 6:
        result = a >> shift
    elif operation == 7:
        result = signed_a >> shift
    elif operation == 8:
        result = int(signed_a < signed_b)
    elif operation == 9:
        result = int(a < b)
    else:
        result = 0
    return result & MASK
