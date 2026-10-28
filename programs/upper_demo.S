# Build a full 32-bit constant, preserve it in RAM, then jump relative to PC.
lui   x1, 0x12345
addi  x1, x1, 0x678
sw    x1, 64(x0)
lw    x2, 64(x0)
auipc x3, 0
addi  x3, x3, 16
jalr  x4, x3, 0
sw    x0, 64(x0)      # Skipped: the RAM must keep 0x12345678.
lw    x5, 64(x0)
