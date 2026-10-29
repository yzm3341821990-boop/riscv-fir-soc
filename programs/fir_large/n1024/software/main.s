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
	sw	s1, 8(sp)                       # 4-byte Folded Spill
	li	a0, 0
	lui	a1, %hi(bench_data)
	addi	a1, a1, %lo(bench_data)
	lui	a2, 1
	add	a3, a1, a2
	lui	a4, 4
	lui	a5, 8
	addi	a5, a5, -1
	li	a6, 1024
	mv	a7, a1
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	add	t0, t0, a2
	sw	t2, 128(t0)
	addi	a0, a0, 1
	addi	a7, a7, 4
	beq	a0, a6, .LBB0_15
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_5 Depth 2
	li	t0, 31
	mv	t3, a0
	bltu	a0, t0, .LBB0_4
# %bb.3:                                #   in Loop: Header=BB0_2 Depth=1
	li	t3, 31
.LBB0_4:                                #   in Loop: Header=BB0_2 Depth=1
	li	t2, 0
	li	t1, 0
	slli	t0, a0, 2
	add	t0, t0, a1
	slli	t3, t3, 2
	sub	t3, t0, t3
	addi	t3, t3, -4
	mv	t4, a3
	mv	t5, a7
.LBB0_5:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Inner Loop Header: Depth=2
	lw	t6, 0(t5)
	lw	s0, 0(t4)
	mv	s1, t2
	mul	t2, s0, t6
	srai	t6, t2, 31
	add	t2, s1, t2
	sltu	s0, t2, s1
	add	t1, t1, t6
	add	t1, t1, s0
	addi	t5, t5, -4
	addi	t4, t4, 4
	bne	t5, t3, .LBB0_5
# %bb.6:                                #   in Loop: Header=BB0_2 Depth=1
	bltz	t1, .LBB0_8
# %bb.7:                                #   in Loop: Header=BB0_2 Depth=1
	mv	t3, t1
	j	.LBB0_9
.LBB0_8:                                #   in Loop: Header=BB0_2 Depth=1
	snez	t3, t2
	neg	t3, t3
	sub	t3, t3, t1
	neg	t2, t2
.LBB0_9:                                #   in Loop: Header=BB0_2 Depth=1
	add	t4, t2, a4
	sltu	t2, t4, t2
	add	t2, t3, t2
	slli	t2, t2, 17
	srli	t3, t4, 15
	or	t2, t3, t2
	bltz	t1, .LBB0_12
# %bb.10:                               #   in Loop: Header=BB0_2 Depth=1
	bge	t2, a5, .LBB0_13
.LBB0_11:                               #   in Loop: Header=BB0_2 Depth=1
	lui	t1, 1048568
	blt	t1, t2, .LBB0_1
	j	.LBB0_14
.LBB0_12:                               #   in Loop: Header=BB0_2 Depth=1
	neg	t2, t2
	blt	t2, a5, .LBB0_11
.LBB0_13:                               #   in Loop: Header=BB0_2 Depth=1
	mv	t2, a5
	lui	t1, 1048568
	blt	t1, a5, .LBB0_1
.LBB0_14:                               #   in Loop: Header=BB0_2 Depth=1
	lui	t2, 1048568
	j	.LBB0_1
.LBB0_15:
	li	a0, 0
	lw	s0, 12(sp)                      # 4-byte Folded Reload
	lw	s1, 8(sp)                       # 4-byte Folded Reload
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
	lui	a0, 3
	add	s1, s0, a0
	li	a0, 1
	sw	a0, 128(s1)
	#APP
	#NO_APP
	call	run_fir
	li	a0, 0
	#APP
	#NO_APP
	li	a1, 2
	sw	a1, 128(s1)
	lui	a1, 1
	addi	a2, a1, 128
	lui	a1, 2
	#APP
	#NO_APP
	addi	a1, a1, 128
	add	a1, s0, a1
	add	a2, s0, a2
	mv	a3, a1
.LBB1_1:                                # =>This Inner Loop Header: Depth=1
	lw	a4, 0(a2)
	lw	a5, 0(a3)
	xor	a4, a4, a5
	snez	a4, a4
	add	a0, a0, a4
	addi	a2, a2, 4
	addi	a3, a3, 4
	bne	a2, a1, .LBB1_1
# %bb.2:
	lui	a1, %hi(bench_data+12288)
	addi	a1, a1, %lo(bench_data+12288)
	sw	a0, 136(a1)
	li	a2, 1
	sw	a2, 132(a1)
	lw	ra, 12(sp)                      # 4-byte Folded Reload
	lw	s0, 8(sp)                       # 4-byte Folded Reload
	lw	s1, 4(sp)                       # 4-byte Folded Reload
	addi	sp, sp, 16
	ret
.Lfunc_end1:
	.size	main, .Lfunc_end1-main
                                        # -- End function
	.type	bench_data,@object              # @bench_data
	.bss
	.globl	bench_data
	.p2align	2, 0x0
bench_data:
	.zero	12440
	.size	bench_data, 12440

	.ident	"clang version 18.1.6 (https://github.com/ziglang/zig-bootstrap 98bc6bf4fc4009888d33941daf6b600d20a42a56)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym bench_data
