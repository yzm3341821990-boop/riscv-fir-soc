# Sum 1..10 with a conditional loop, then save and read back the sum.
addi x1, x0, 1
addi x2, x0, 11
addi x3, x0, 0
loop:
add  x3, x3, x1
addi x1, x1, 1
blt  x1, x2, loop
sw   x3, 64(x0)
lw   x4, 64(x0)
