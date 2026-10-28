	.text
	.attribute	4, 16
	.attribute	5, "rv32i2p1"
	.file	"main.c"
	.globl	sum_samples                     # -- Begin function sum_samples
	.p2align	2
	.type	sum_samples,@function
sum_samples:                            # @sum_samples
# %bb.0:
	li	a2, 0
	beqz	a1, .LBB0_2
.LBB0_1:                                # =>This Inner Loop Header: Depth=1
	lh	a3, 0(a0)
	add	a2, a2, a3
	addi	a1, a1, -1
	addi	a0, a0, 2
	bnez	a1, .LBB0_1
.LBB0_2:
	mv	a0, a2
	ret
.Lfunc_end0:
	.size	sum_samples, .Lfunc_end0-sum_samples
                                        # -- End function
	.globl	main                            # -- Begin function main
	.p2align	2
	.type	main,@function
main:                                   # @main
# %bb.0:
	addi	sp, sp, -16
	sw	ra, 12(sp)                      # 4-byte Folded Spill
	lui	a0, %hi(samples)
	addi	a0, a0, %lo(samples)
	li	a1, 8
	call	sum_samples
	lui	a1, %hi(result)
	sw	a0, %lo(result)(a1)
	lui	a0, %hi(done)
	li	a2, 1
	sw	a2, %lo(done)(a0)
	lw	a0, %lo(result)(a1)
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
	.half	12                              # 0xc
	.half	65533                           # 0xfffd
	.half	25                              # 0x19
	.half	65526                           # 0xfff6
	.half	7                               # 0x7
	.half	65534                           # 0xfffe
	.half	30                              # 0x1e
	.half	65532                           # 0xfffc
	.size	samples, 16

	.type	result,@object                  # @result
	.bss
	.globl	result
	.p2align	2, 0x0
result:
	.word	0                               # 0x0
	.size	result, 4

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
	.addrsig_sym result
	.addrsig_sym done
