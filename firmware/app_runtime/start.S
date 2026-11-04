.option norvc
.section .text.start,"ax",@progbits
.globl _start, _exit_commit
_start:
    lui sp, %hi(_stack_top)
    addi sp, sp, %lo(_stack_top)
    call main
    lui t0, %hi(job)
    addi t0, t0, %lo(job)
    sw a0, 1040(t0)
    addi t1, zero, 1
    sw t1, 1036(t0)
_exit_commit:
    jal zero, _program_end
.section .job,"aw",@nobits
.globl job
.balign 4
job:
    .space 1304
