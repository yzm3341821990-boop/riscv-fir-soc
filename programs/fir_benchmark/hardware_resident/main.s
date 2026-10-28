	.text
	.attribute	4, 16
	.attribute	5, "rv32i2p1_m2p0"
	.file	"main.c"
	.globl	run_fir                         # -- Begin function run_fir
	.p2align	2
	.type	run_fir,@function
run_fir:                                # @run_fir
# %bb.0:
	li	a1, 0
	lui	a0, 262147
	li	a2, 2
	sw	a2, 0(a0)
	lui	a2, %hi(bench_data)
	addi	a2, a2, %lo(bench_data)
	sw	a2, 8(a0)
	addi	a2, a2, 160
	sw	a2, 12(a0)
	li	a2, 8
	sw	a2, 16(a0)
	li	a2, 1
	sw	a2, 0(a0)
	li	a3, 63
.LBB0_1:                                # =>This Inner Loop Header: Depth=1
	lw	a2, 4(a0)
	mv	a4, a1
	andi	a5, a2, 1
	addi	a1, a1, 1
	beqz	a5, .LBB0_3
# %bb.2:                                #   in Loop: Header=BB0_1 Depth=1
	bltu	a4, a3, .LBB0_1
.LBB0_3:
	lui	a3, %hi(bench_data+204)
	addi	a2, a2, -2
	snez	a0, a2
	sw	a1, %lo(bench_data+204)(a3)
	ret
.Lfunc_end0:
	.size	run_fir, .Lfunc_end0-run_fir
                                        # -- End function
	.globl	main                            # -- Begin function main
	.p2align	2
	.type	main,@function
main:                                   # @main
# %bb.0:
	addi	sp, sp, -16
	sw	ra, 12(sp)                      # 4-byte Folded Spill
	sw	s0, 8(sp)                       # 4-byte Folded Spill
	sw	s1, 4(sp)                       # 4-byte Folded Spill
	lui	a0, %hi(bench_data+32)
	addi	a0, a0, %lo(bench_data+32)
	lui	a2, 262147
	addi	a1, a2, 256
	addi	a2, a2, 384
.LBB1_1:                                # =>This Inner Loop Header: Depth=1
	lw	a3, 0(a0)
	sw	a3, 0(a1)
	addi	a1, a1, 4
	addi	a0, a0, 4
	bne	a1, a2, .LBB1_1
# %bb.2:
	#APP
	#NO_APP
	lui	a0, %hi(bench_data)
	addi	s0, a0, %lo(bench_data)
	li	s1, 1
	sw	s1, 192(s0)
	#APP
	#NO_APP
	call	run_fir
	sw	a0, 200(s0)
	#APP
	#NO_APP
	li	a0, 2
	sw	a0, 192(s0)
	#APP
	#NO_APP
	lui	a0, 262147
	lw	a1, 20(a0)
	sw	a1, 208(s0)
	lw	a0, 24(a0)
	sw	a0, 212(s0)
	sw	s1, 196(s0)
	lw	a0, 200(s0)
	lw	ra, 12(sp)                      # 4-byte Folded Reload
	lw	s0, 8(sp)                       # 4-byte Folded Reload
	lw	s1, 4(sp)                       # 4-byte Folded Reload
	addi	sp, sp, 16
	ret
.Lfunc_end1:
	.size	main, .Lfunc_end1-main
                                        # -- End function
	.type	bench_data,@object              # @bench_data
	.data
	.globl	bench_data
	.p2align	2, 0x0
bench_data:
	.word	16384                           # 0x4000
	.word	32767                           # 0x7fff
	.word	4294934528                      # 0xffff8000
	.word	8192                            # 0x2000
	.word	4294950912                      # 0xffffc000
	.word	24576                           # 0x6000
	.word	0                               # 0x0
	.word	4294959104                      # 0xffffe000
	.word	16384                           # 0x4000
	.word	4294959104                      # 0xffffe000
	.word	4096                            # 0x1000
	.word	2048                            # 0x800
	.zero	112
	.zero	32
	.word	0                               # 0x0
	.word	0                               # 0x0
	.word	0                               # 0x0
	.word	0                               # 0x0
	.word	0                               # 0x0
	.word	0                               # 0x0
	.size	bench_data, 216

	.ident	"clang version 18.1.6 (https://github.com/ziglang/zig-bootstrap 98bc6bf4fc4009888d33941daf6b600d20a42a56)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym bench_data
