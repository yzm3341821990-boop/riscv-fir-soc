	.text
	.attribute	4, 16
	.attribute	5, "rv32i2p1_m2p0"
	.file	"main.c"
	.globl	run_fir                         # -- Begin function run_fir
	.p2align	2
	.type	run_fir,@function
run_fir:                                # @run_fir
# %bb.0:
	addi	sp, sp, -16
	sw	s0, 12(sp)                      # 4-byte Folded Spill
	li	a0, 0
	lui	a1, %hi(bench_data)
	addi	a1, a1, %lo(bench_data)
	addi	a2, a1, 32
	lui	a3, 4
	lui	a4, 8
	addi	a4, a4, -1
	li	a5, 8
	mv	a6, a1
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	sw	t1, 160(a7)
	addi	a0, a0, 1
	addi	a6, a6, 4
	beq	a0, a5, .LBB0_13
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_3 Depth 2
	li	t1, 0
	li	t0, 0
	slli	a7, a0, 2
	add	a7, a7, a1
	addi	t2, a7, 36
	mv	t3, a6
	mv	t4, a2
.LBB0_3:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Inner Loop Header: Depth=2
	lw	t5, 0(t3)
	lw	t6, 0(t4)
	mv	s0, t1
	mul	t1, t6, t5
	srai	t5, t1, 31
	add	t1, s0, t1
	sltu	t6, t1, s0
	add	t0, t0, t5
	add	t0, t0, t6
	addi	t4, t4, 4
	addi	t3, t3, -4
	bne	t4, t2, .LBB0_3
# %bb.4:                                #   in Loop: Header=BB0_2 Depth=1
	bltz	t0, .LBB0_6
# %bb.5:                                #   in Loop: Header=BB0_2 Depth=1
	mv	t2, t0
	j	.LBB0_7
.LBB0_6:                                #   in Loop: Header=BB0_2 Depth=1
	snez	t2, t1
	neg	t2, t2
	sub	t2, t2, t0
	neg	t1, t1
.LBB0_7:                                #   in Loop: Header=BB0_2 Depth=1
	add	t3, t1, a3
	sltu	t1, t3, t1
	add	t1, t2, t1
	slli	t1, t1, 17
	srli	t2, t3, 15
	or	t1, t2, t1
	bltz	t0, .LBB0_10
# %bb.8:                                #   in Loop: Header=BB0_2 Depth=1
	bge	t1, a4, .LBB0_11
.LBB0_9:                                #   in Loop: Header=BB0_2 Depth=1
	lui	t0, 1048568
	blt	t0, t1, .LBB0_1
	j	.LBB0_12
.LBB0_10:                               #   in Loop: Header=BB0_2 Depth=1
	neg	t1, t1
	blt	t1, a4, .LBB0_9
.LBB0_11:                               #   in Loop: Header=BB0_2 Depth=1
	mv	t1, a4
	lui	t0, 1048568
	blt	t0, a4, .LBB0_1
.LBB0_12:                               #   in Loop: Header=BB0_2 Depth=1
	lui	t1, 1048568
	j	.LBB0_1
.LBB0_13:
	li	a0, 0
	lw	s0, 12(sp)                      # 4-byte Folded Reload
	addi	sp, sp, 16
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
	#APP
	#NO_APP
	lui	a0, %hi(bench_data)
	addi	s0, a0, %lo(bench_data)
	li	s1, 1
	sw	s1, 192(s0)
	#APP
	#NO_APP
	call	run_fir
	sw	zero, 200(s0)
	#APP
	#NO_APP
	li	a0, 2
	sw	a0, 192(s0)
	#APP
	#NO_APP
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
