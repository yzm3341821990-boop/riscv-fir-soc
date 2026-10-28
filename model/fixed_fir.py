"""32-tap Q15 FIR reference, using only Python's standard library.

The filter is a functional reference, not a clock-cycle/performance model.
See docs/numeric-contract.md for bit widths, rounding and block boundaries.
"""

from dataclasses import dataclass
from math import floor, isfinite
from numbers import Real
from typing import Iterable

TAPS = 32
FRAC_BITS = 15
SAMPLE_MIN = -32768
SAMPLE_MAX = 32767
ACC_BITS = 40


def _integer(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not {type(value).__name__}")
    return value


def _sample(value: int, name: str) -> int:
    value = _integer(value, name)
    if not SAMPLE_MIN <= value <= SAMPLE_MAX:
        raise ValueError(f"{name}={value} is outside signed 16-bit range")
    return value


def round_shift(value: int, shift: int = FRAC_BITS) -> int:
    """Divide by 2**shift, nearest integer, ties away from zero."""
    value = _integer(value, "value")
    shift = _integer(shift, "shift")
    if shift < 0:
        raise ValueError("shift must be nonnegative")
    if shift == 0:
        return value
    magnitude = (abs(value) + (1 << (shift - 1))) >> shift
    return -magnitude if value < 0 else magnitude


def saturate_i16(value: int) -> int:
    """Clip an integer to the signed 16-bit output range."""
    value = _integer(value, "value")
    return min(SAMPLE_MAX, max(SAMPLE_MIN, value))


def accumulator_to_q15(accumulator: int) -> int:
    """Check signed 40-bit range, round Q30 to Q15, then saturate."""
    accumulator = _integer(accumulator, "accumulator")
    if not -(1 << (ACC_BITS - 1)) <= accumulator < (1 << (ACC_BITS - 1)):
        raise OverflowError("accumulator is outside signed 40-bit range")
    return saturate_i16(round_shift(accumulator, FRAC_BITS))


def quantize_q15(value: Real) -> int:
    """Quantize a finite real value to signed Q15, with explicit clipping."""
    if not isinstance(value, Real) or isinstance(value, bool):
        raise TypeError("value must be a real number")
    if not isfinite(value):
        raise ValueError("value must be finite")
    if value >= 1:
        return SAMPLE_MAX
    if value <= -1:
        return SAMPLE_MIN
    magnitude = floor(abs(value) * (1 << FRAC_BITS) + 0.5)
    return saturate_i16(-magnitude if value < 0 else magnitude)


@dataclass(frozen=True)
class FIRResult:
    """Immutable sample results and pre-rounding Q30 accumulators."""

    outputs: tuple[int, ...]
    accumulators: tuple[int, ...]


def fir_block(samples: Iterable[int], coefficients: Iterable[int]) -> FIRResult:
    """Causal FIR, h[0] multiplies x[n]; zero history on every call.

    Both operands are raw signed 16-bit integers. Exactly 32 coefficients
    are required. Return N outputs for N inputs, without the FIR tail.
    No intermediate product is rounded and no state survives a call.
    """
    data = tuple(_sample(value, f"samples[{i}]")
                 for i, value in enumerate(samples))
    taps = tuple(_sample(value, f"coefficients[{i}]")
                 for i, value in enumerate(coefficients))
    if len(taps) != TAPS:
        raise ValueError(f"exactly {TAPS} coefficients are required")
    outputs, accumulators = [], []
    for n in range(len(data)):
        accumulator = 0
        for k, coefficient in enumerate(taps):
            if k <= n:
                accumulator += coefficient * data[n - k]
        accumulators.append(accumulator)
        outputs.append(accumulator_to_q15(accumulator))
    return FIRResult(tuple(outputs), tuple(accumulators))


def to_memory_word(value: int) -> str:
    """One raw Q15 sample sign-extended to a 32-bit, eight-hex-digit word."""
    value = _sample(value, "sample")
    return f"{value & 0xFFFFFFFF:08X}"


def from_memory_word(word: str) -> int:
    """Parse a 32-bit word, rejecting incorrect 16-to-32 sign extension."""
    if not isinstance(word, str):
        raise TypeError("word must be a string")
    if len(word) != 8 or any(c not in "0123456789abcdefABCDEF" for c in word):
        raise ValueError("word must contain exactly eight hexadecimal digits")
    raw = int(word, 16)
    signed = raw if raw < 0x80000000 else raw - 0x100000000
    return _sample(signed, "decoded sample")
