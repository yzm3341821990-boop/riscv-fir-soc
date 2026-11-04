"""RV32 M arithmetic semantics. Returns unsigned 32-bit register bit patterns."""
OPERATIONS = ('MUL', 'MULH', 'MULHSU', 'MULHU', 'DIV', 'DIVU', 'REM', 'REMU')
MASK = (1 << 32) - 1


def signed(word: int) -> int:
    word &= MASK
    return word if word < 1 << 31 else word - (1 << 32)


def evaluate(operation: str, first: int, second: int) -> int:
    if operation not in OPERATIONS:
        raise ValueError('Unsupported RV32M operation: ' + str(operation))
    a, b = first & MASK, second & MASK
    if operation == 'MUL':
        return (a * b) & MASK
    if operation in ('MULH', 'MULHSU', 'MULHU'):
        product = (signed(a) if operation != 'MULHU' else a) * (
            signed(b) if operation == 'MULH' else b)
        return (product >> 32) & MASK
    if b == 0:
        return MASK if operation in ('DIV', 'DIVU') else a
    if operation in ('DIVU', 'REMU'):
        return a // b if operation == 'DIVU' else a % b
    x, y = signed(a), signed(b)
    quotient = abs(x) // abs(y)
    if (x < 0) != (y < 0):
        quotient = -quotient
    return (quotient if operation == 'DIV' else x - quotient*y) & MASK
