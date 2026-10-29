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
	lui	a3, 1
	addi	a3, a3, 128
	add	a2, a2, a3
	sw	a2, 12(a0)
	li	a2, 1024
	sw	a2, 16(a0)
	li	a2, 1
	sw	a2, 0(a0)
	lui	a2, 16
	addi	a3, a2, 255
.LBB0_1:                                # =>This Inner Loop Header: Depth=1
	lw	a2, 4(a0)
	mv	a4, a1
	andi	a5, a2, 1
	addi	a1, a1, 1
	beqz	a5, .LBB0_3
# %bb.2:                                #   in Loop: Header=BB0_1 Depth=1
	bltu	a4, a3, .LBB0_1
.LBB0_3:
	lui	a3, %hi(bench_data+12428)
	addi	a2, a2, -2
	snez	a0, a2
	sw	a1, %lo(bench_data+12428)(a3)
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
	lui	a0, %hi(bench_data+4096)
	addi	a0, a0, %lo(bench_data+4096)
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
	lui	a0, 3
	add	s1, s0, a0
	li	a0, 1
	sw	a0, 128(s1)
	#APP
	#NO_APP
	call	run_fir
	#APP
	#NO_APP
	li	a1, 2
	sw	a1, 128(s1)
	#APP
	#NO_APP
	lui	a1, 262147
	lw	a2, 20(a1)
	sw	a2, 144(s1)
	lw	a1, 24(a1)
	sw	a1, 148(s1)
	lui	a1, 1
	addi	a2, a1, 128
	lui	a1, 2
	addi	a1, a1, 128
	add	a1, s0, a1
	add	a2, s0, a2
	mv	a3, a1
.LBB1_3:                                # =>This Inner Loop Header: Depth=1
	lw	a4, 0(a2)
	lw	a5, 0(a3)
	xor	a4, a4, a5
	snez	a4, a4
	add	a0, a0, a4
	addi	a2, a2, 4
	addi	a3, a3, 4
	bne	a2, a1, .LBB1_3
# %bb.4:
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
