	.text
	.attribute	4, 16
	.attribute	5, "rv32i2p1"
	.file	"main.c"
	.globl	main                            # -- Begin function main
	.p2align	2
	.type	main,@function
main:                                   # @main
# %bb.0:
	lui	a1, 262147
	li	a0, 2
	sw	a0, 0(a1)
	lui	a0, %hi(coefficients)
	addi	a0, a0, %lo(coefficients)
	addi	a1, a1, 256
	addi	a2, a0, 128
.LBB0_1:                                # =>This Inner Loop Header: Depth=1
	lw	a3, 0(a0)
	sw	a3, 0(a1)
	addi	a0, a0, 4
	addi	a1, a1, 4
	bne	a0, a2, .LBB0_1
# %bb.2:
	lui	a0, %hi(samples)
	addi	a1, a0, %lo(samples)
	lui	a0, 262147
	sw	a1, 8(a0)
	lui	a1, %hi(outputs)
	addi	a1, a1, %lo(outputs)
	sw	a1, 12(a0)
	li	a1, 8
	sw	a1, 16(a0)
	li	a1, 1
	sw	a1, 0(a0)
	lui	a1, %hi(polls)
	li	a2, 64
.LBB0_3:                                # =>This Inner Loop Header: Depth=1
	lw	a3, 4(a0)
	lw	a4, %lo(polls)(a1)
	addi	a4, a4, 1
	andi	a5, a3, 1
	sw	a4, %lo(polls)(a1)
	beqz	a5, .LBB0_5
# %bb.4:                                #   in Loop: Header=BB0_3 Depth=1
	lw	a4, %lo(polls)(a1)
	bltu	a4, a2, .LBB0_3
.LBB0_5:
	li	a0, 2
	bne	a3, a0, .LBB0_10
# %bb.6:
	lui	a0, %hi(expected)
	addi	a0, a0, %lo(expected)
	lui	a1, %hi(outputs)
	addi	a1, a1, %lo(outputs)
	addi	a2, a0, 32
	lui	a3, %hi(errors)
	j	.LBB0_8
.LBB0_7:                                #   in Loop: Header=BB0_8 Depth=1
	addi	a0, a0, 4
	addi	a1, a1, 4
	beq	a0, a2, .LBB0_11
.LBB0_8:                                # =>This Inner Loop Header: Depth=1
	lw	a4, 0(a1)
	lw	a5, 0(a0)
	beq	a4, a5, .LBB0_7
# %bb.9:                                #   in Loop: Header=BB0_8 Depth=1
	lw	a4, %lo(errors)(a3)
	addi	a4, a4, 1
	sw	a4, %lo(errors)(a3)
	j	.LBB0_7
.LBB0_10:
	lui	a1, %hi(errors)
	li	a0, 1
	sw	a0, %lo(errors)(a1)
	lui	a1, %hi(done)
	sw	a0, %lo(done)(a1)
	ret
.LBB0_11:
	lui	a0, 262147
	lw	a1, 20(a0)
	lui	a2, %hi(hw_cycles)
	sw	a1, %lo(hw_cycles)(a2)
	lw	a0, 24(a0)
	lui	a1, %hi(hw_written)
	sw	a0, %lo(hw_written)(a1)
	lui	a0, %hi(done)
	li	a1, 1
	sw	a1, %lo(done)(a0)
	lui	a0, %hi(errors)
	lw	a0, %lo(errors)(a0)
	ret
.Lfunc_end0:
	.size	main, .Lfunc_end0-main
                                        # -- End function
	.type	samples,@object                 # @samples
	.data
	.globl	samples
	.p2align	2, 0x0
samples:
	.word	16384                           # 0x4000
	.word	32767                           # 0x7fff
	.word	4294934528                      # 0xffff8000
	.word	8192                            # 0x2000
	.word	4294950912                      # 0xffffc000
	.word	24576                           # 0x6000
	.word	0                               # 0x0
	.word	4294959104                      # 0xffffe000
	.size	samples, 32

	.type	coefficients,@object            # @coefficients
	.globl	coefficients
	.p2align	2, 0x0
coefficients:
	.word	16384                           # 0x4000
	.word	4294959104                      # 0xffffe000
	.word	4096                            # 0x1000
	.word	2048                            # 0x800
	.zero	112
	.size	coefficients, 128

	.type	expected,@object                # @expected
	.globl	expected
	.p2align	2, 0x0
expected:
	.word	8192                            # 0x2000
	.word	12288                           # 0x3000
	.word	4294944768                      # 0xffffa800
	.word	17408                           # 0x4400
	.word	4294955008                      # 0xffffd000
	.word	15360                           # 0x3c00
	.word	4294959616                      # 0xffffe200
	.word	4294965248                      # 0xfffff800
	.size	expected, 32

	.type	outputs,@object                 # @outputs
	.bss
	.globl	outputs
	.p2align	2, 0x0
outputs:
	.zero	32
	.size	outputs, 32

	.type	polls,@object                   # @polls
	.globl	polls
	.p2align	2, 0x0
polls:
	.word	0                               # 0x0
	.size	polls, 4

	.type	errors,@object                  # @errors
	.globl	errors
	.p2align	2, 0x0
errors:
	.word	0                               # 0x0
	.size	errors, 4

	.type	done,@object                    # @done
	.globl	done
	.p2align	2, 0x0
done:
	.word	0                               # 0x0
	.size	done, 4

	.type	hw_cycles,@object               # @hw_cycles
	.globl	hw_cycles
	.p2align	2, 0x0
hw_cycles:
	.word	0                               # 0x0
	.size	hw_cycles, 4

	.type	hw_written,@object              # @hw_written
	.globl	hw_written
	.p2align	2, 0x0
hw_written:
	.word	0                               # 0x0
	.size	hw_written, 4

	.ident	"clang version 18.1.6 (https://github.com/ziglang/zig-bootstrap 98bc6bf4fc4009888d33941daf6b600d20a42a56)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym samples
	.addrsig_sym coefficients
	.addrsig_sym expected
	.addrsig_sym outputs
	.addrsig_sym polls
	.addrsig_sym errors
	.addrsig_sym done
	.addrsig_sym hw_cycles
	.addrsig_sym hw_written
