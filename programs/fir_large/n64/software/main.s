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
	addi	a2, a1, 256
	lui	a3, 4
	lui	a4, 8
	addi	a4, a4, -1
	li	a5, 64
	mv	a6, a1
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	sw	t1, 384(a7)
	addi	a0, a0, 1
	addi	a6, a6, 4
	beq	a0, a5, .LBB0_15
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_5 Depth 2
	li	a7, 31
	mv	t2, a0
	bltu	a0, a7, .LBB0_4
# %bb.3:                                #   in Loop: Header=BB0_2 Depth=1
	li	t2, 31
.LBB0_4:                                #   in Loop: Header=BB0_2 Depth=1
	li	t1, 0
	li	t0, 0
	slli	a7, a0, 2
	add	a7, a7, a1
	slli	t2, t2, 2
	sub	t2, a7, t2
	addi	t2, t2, -4
	mv	t3, a2
	mv	t4, a6
.LBB0_5:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Inner Loop Header: Depth=2
	lw	t5, 0(t4)
	lw	t6, 0(t3)
	mv	s0, t1
	mul	t1, t6, t5
	srai	t5, t1, 31
	add	t1, s0, t1
	sltu	t6, t1, s0
	add	t0, t0, t5
	add	t0, t0, t6
	addi	t4, t4, -4
	addi	t3, t3, 4
	bne	t4, t2, .LBB0_5
# %bb.6:                                #   in Loop: Header=BB0_2 Depth=1
	bltz	t0, .LBB0_8
# %bb.7:                                #   in Loop: Header=BB0_2 Depth=1
	mv	t2, t0
	j	.LBB0_9
.LBB0_8:                                #   in Loop: Header=BB0_2 Depth=1
	snez	t2, t1
	neg	t2, t2
	sub	t2, t2, t0
	neg	t1, t1
.LBB0_9:                                #   in Loop: Header=BB0_2 Depth=1
	add	t3, t1, a3
	sltu	t1, t3, t1
	add	t1, t2, t1
	slli	t1, t1, 17
	srli	t2, t3, 15
	or	t1, t2, t1
	bltz	t0, .LBB0_12
# %bb.10:                               #   in Loop: Header=BB0_2 Depth=1
	bge	t1, a4, .LBB0_13
.LBB0_11:                               #   in Loop: Header=BB0_2 Depth=1
	lui	t0, 1048568
	blt	t0, t1, .LBB0_1
	j	.LBB0_14
.LBB0_12:                               #   in Loop: Header=BB0_2 Depth=1
	neg	t1, t1
	blt	t1, a4, .LBB0_11
.LBB0_13:                               #   in Loop: Header=BB0_2 Depth=1
	mv	t1, a4
	lui	t0, 1048568
	blt	t0, a4, .LBB0_1
.LBB0_14:                               #   in Loop: Header=BB0_2 Depth=1
	lui	t1, 1048568
	j	.LBB0_1
.LBB0_15:
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
	#APP
	#NO_APP
	lui	a0, %hi(bench_data)
	addi	s0, a0, %lo(bench_data)
	li	a0, 1
	sw	a0, 896(s0)
	#APP
	#NO_APP
	call	run_fir
	#APP
	#NO_APP
	li	a0, 2
	sw	a0, 896(s0)
	#APP
	#NO_APP
	li	a0, 0
	addi	a1, s0, 640
	addi	a2, s0, 896
.LBB1_1:                                # =>This Inner Loop Header: Depth=1
	lw	a3, -256(a1)
	lw	a4, 0(a1)
	xor	a3, a3, a4
	snez	a3, a3
	addi	a1, a1, 4
	add	a0, a0, a3
	bne	a1, a2, .LBB1_1
# %bb.2:
	lui	a1, %hi(bench_data)
	addi	a1, a1, %lo(bench_data)
	sw	a0, 904(a1)
	li	a2, 1
	sw	a2, 900(a1)
	lw	ra, 12(sp)                      # 4-byte Folded Reload
	lw	s0, 8(sp)                       # 4-byte Folded Reload
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
	.zero	920
	.size	bench_data, 920

	.ident	"clang version 18.1.6 (https://github.com/ziglang/zig-bootstrap 98bc6bf4fc4009888d33941daf6b600d20a42a56)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym bench_data
