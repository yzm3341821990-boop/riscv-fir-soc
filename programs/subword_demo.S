# Little-endian byte/halfword loads and writes that preserve adjacent bytes.
addi x1, x0, 64
lui  x2, 0x80FF8
addi x2, x2, 0x17F
sw   x2, 0(x1)       # RAM[64..67] = 7F 81 FF 80.
lb   x3, 1(x1)       # -127, sign-extended.
lbu  x4, 1(x1)       # 129, zero-extended.
lh   x5, 2(x1)       # 0x80FF, sign-extended.
lhu  x6, 2(x1)       # 0x80FF, zero-extended.
addi x7, x0, 0x55
sb   x7, 1(x1)       # Only byte 65 changes; word is 80FF557F.
lui  x8, 0x1234B
addi x8, x8, -1075   # x8=1234ABCD; SH uses only its low 16 bits.
sh   x8, 2(x1)       # Only bytes 66/67 change; word is ABCD557F.
lw   x9, 0(x1)
lb   x10, 0(x1)      # Neighbouring low byte remains 7F.
lbu  x11, 3(x1)
