.option norvc
.option norelax
.section .text.start,"ax",@progbits
.globl _start
_start:
    lui  sp, %hi(_stack_top)
    addi sp, sp, %lo(_stack_top)
    jal  ra, main
    jal  zero, _program_end
