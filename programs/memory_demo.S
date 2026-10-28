# Addresses are byte addresses; each SW/LW transfers one 32-bit word.
addi x1, x0, 64
addi x2, x0, 12
sw   x2, 0(x1)
lw   x3, 0(x1)
addi x4, x3, 5
sw   x4, 4(x1)
lw   x5, 4(x1)
sub  x6, x5, x3
