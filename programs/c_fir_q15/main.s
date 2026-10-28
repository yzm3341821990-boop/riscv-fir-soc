	.text
	.attribute	4, 16
	.attribute	5, "rv32i2p1_m2p0"
	.file	"main.c"
	.globl	fir_q15                         # -- Begin function fir_q15
	.p2align	2
	.type	fir_q15,@function
fir_q15:                                # @fir_q15
# %bb.0:
	addi	sp, sp, -16
	sw	s0, 12(sp)                      # 4-byte Folded Spill
	sw	s1, 8(sp)                       # 4-byte Folded Spill
	li	a0, 0
	lui	a1, %hi(samples)
	addi	a1, a1, %lo(samples)
	lui	a2, %hi(coefficients)
	addi	a2, a2, %lo(coefficients)
	lui	a3, %hi(accumulators)
	addi	a3, a3, %lo(accumulators)
	lui	a4, 4
	lui	a5, 8
	addi	a5, a5, -1
	lui	a6, %hi(outputs)
	addi	a6, a6, %lo(outputs)
	li	a7, 8
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	add	t0, a6, t0
	sh	t2, 0(t0)
	addi	a0, a0, 1
	addi	a1, a1, 2
	beq	a0, a7, .LBB0_13
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_3 Depth 2
	li	t2, 0
	li	t1, 0
	slli	t0, a0, 1
	add	t3, t0, a2
	addi	t3, t3, 2
	mv	t4, a1
	mv	t5, a2
.LBB0_3:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Inner Loop Header: Depth=2
	lh	t6, 0(t4)
	lh	s0, 0(t5)
	mv	s1, t2
	mul	t2, s0, t6
	srai	t6, t2, 31
	add	t2, s1, t2
	sltu	s0, t2, s1
	add	t1, t1, t6
	add	t1, t1, s0
	addi	t5, t5, 2
	addi	t4, t4, -2
	bne	t5, t3, .LBB0_3
# %bb.4:                                #   in Loop: Header=BB0_2 Depth=1
	slli	t3, a0, 3
	add	t3, a3, t3
	sw	t1, 4(t3)
	sw	t2, 0(t3)
	bltz	t1, .LBB0_6
# %bb.5:                                #   in Loop: Header=BB0_2 Depth=1
	mv	t3, t1
	j	.LBB0_7
.LBB0_6:                                #   in Loop: Header=BB0_2 Depth=1
	snez	t3, t2
	neg	t3, t3
	sub	t3, t3, t1
	neg	t2, t2
.LBB0_7:                                #   in Loop: Header=BB0_2 Depth=1
	add	t4, t2, a4
	sltu	t2, t4, t2
	add	t2, t3, t2
	slli	t2, t2, 17
	srli	t3, t4, 15
	or	t2, t3, t2
	bltz	t1, .LBB0_10
# %bb.8:                                #   in Loop: Header=BB0_2 Depth=1
	bge	t2, a5, .LBB0_11
.LBB0_9:                                #   in Loop: Header=BB0_2 Depth=1
	lui	t1, 1048568
	blt	t1, t2, .LBB0_1
	j	.LBB0_12
.LBB0_10:                               #   in Loop: Header=BB0_2 Depth=1
	neg	t2, t2
	blt	t2, a5, .LBB0_9
.LBB0_11:                               #   in Loop: Header=BB0_2 Depth=1
	mv	t2, a5
	lui	t1, 1048568
	blt	t1, a5, .LBB0_1
.LBB0_12:                               #   in Loop: Header=BB0_2 Depth=1
	lui	t2, 1048568
	j	.LBB0_1
.LBB0_13:
	lw	s0, 12(sp)                      # 4-byte Folded Reload
	lw	s1, 8(sp)                       # 4-byte Folded Reload
	addi	sp, sp, 16
	ret
.Lfunc_end0:
	.size	fir_q15, .Lfunc_end0-fir_q15
                                        # -- End function
	.globl	main                            # -- Begin function main
	.p2align	2
	.type	main,@function
main:                                   # @main
# %bb.0:
	addi	sp, sp, -16
	sw	ra, 12(sp)                      # 4-byte Folded Spill
	call	fir_q15
	lui	a0, %hi(done)
	li	a1, 1
	sw	a1, %lo(done)(a0)
	lui	a0, %hi(outputs+14)
	lh	a0, %lo(outputs+14)(a0)
	lw	ra, 12(sp)                      # 4-byte Folded Reload
	addi	sp, sp, 16
	ret
.Lfunc_end1:
	.size	main, .Lfunc_end1-main
                                        # -- End function
	.type	samples,@object                 # @samples
	.data
	.globl	samples
	.p2align	1, 0x0
samples:
	.half	16384                           # 0x4000
	.half	32767                           # 0x7fff
	.half	32768                           # 0x8000
	.half	8192                            # 0x2000
	.half	49152                           # 0xc000
	.half	24576                           # 0x6000
	.half	0                               # 0x0
	.half	57344                           # 0xe000
	.size	samples, 16

	.type	coefficients,@object            # @coefficients
	.globl	coefficients
	.p2align	1, 0x0
coefficients:
	.half	16384                           # 0x4000
	.half	57344                           # 0xe000
	.half	4096                            # 0x1000
	.half	2048                            # 0x800
	.zero	56
	.size	coefficients, 64

	.type	accumulators,@object            # @accumulators
	.bss
	.globl	accumulators
	.p2align	3, 0x0
accumulators:
	.zero	64
	.size	accumulators, 64

	.type	outputs,@object                 # @outputs
	.globl	outputs
	.p2align	1, 0x0
outputs:
	.zero	16
	.size	outputs, 16

	.type	done,@object                    # @done
	.globl	done
	.p2align	2, 0x0
done:
	.word	0                               # 0x0
	.size	done, 4

	.ident	"clang version 18.1.6 (https://github.com/ziglang/zig-bootstrap 98bc6bf4fc4009888d33941daf6b600d20a42a56)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym samples
	.addrsig_sym coefficients
	.addrsig_sym accumulators
	.addrsig_sym outputs
	.addrsig_sym done
