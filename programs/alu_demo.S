# RV32I ALU subset: each instruction retires after three clock cycles.
# Run by loading the matching alu_demo.hex into the simulation ROM.
addi x1, x0, -8
addi x2, x0, 1
srl  x3, x1, x2
sra  x4, x1, x2
slt  x5, x1, x2
sltu x6, x1, x2
andi x7, x1, 15
