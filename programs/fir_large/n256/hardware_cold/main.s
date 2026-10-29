	.text
	.attribute	4, 16
	.attribute	5, "rv32i2p1_m2p0"
	.file	"main.c"
	.globl	run_fir                         # -- Begin function run_fir
	.p2align	2
	.type	run_fir,@function
run_fir:                                # @run_fir
# %bb.0:
	lui	a2, 262147
	li	a0, 2
	sw	a0, 0(a2)
	lui	a0, %hi(bench_data+1024)
	addi	a0, a0, %lo(bench_data+1024)
	addi	a1, a2, 256
	addi	a2, a2, 384
.LBB0_1:                                # =>This Inner Loop Header: Depth=1
	lw	a3, 0(a0)
	sw	a3, 0(a1)
	addi	a1, a1, 4
	addi	a0, a0, 4
	bne	a1, a2, .LBB0_1
# %bb.2:
	li	a1, 0
	lui	a0, %hi(bench_data)
	addi	a2, a0, %lo(bench_data)
	lui	a0, 262147
	sw	a2, 8(a0)
	addi	a2, a2, 1152
	sw	a2, 12(a0)
	li	a2, 256
	sw	a2, 16(a0)
	li	a2, 1
	sw	a2, 0(a0)
	lui	a2, 4
	addi	a3, a2, 255
.LBB0_3:                                # =>This Inner Loop Header: Depth=1
	lw	a2, 4(a0)
	mv	a4, a1
	andi	a5, a2, 1
	addi	a1, a1, 1
	beqz	a5, .LBB0_5
# %bb.4:                                #   in Loop: Header=BB0_3 Depth=1
	bltu	a4, a3, .LBB0_3
.LBB0_5:
	lui	a3, %hi(bench_data+3212)
	addi	a2, a2, -2
	snez	a0, a2
	sw	a1, %lo(bench_data+3212)(a3)
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
	lui	a0, %hi(bench_data+2047)
	addi	s0, a0, %lo(bench_data+2047)
	li	a0, 1
	sw	a0, 1153(s0)
	#APP
	#NO_APP
	call	run_fir
	#APP
	#NO_APP
	li	a1, 2
	sw	a1, 1153(s0)
	#APP
	#NO_APP
	lui	a1, 262147
	lw	a2, 20(a1)
	sw	a2, 1169(s0)
	lw	a1, 24(a1)
	sw	a1, 1173(s0)
	addi	a1, s0, 129
	addi	a2, s0, 1153
.LBB1_1:                                # =>This Inner Loop Header: Depth=1
	lw	a3, -1024(a1)
	lw	a4, 0(a1)
	xor	a3, a3, a4
	snez	a3, a3
	addi	a1, a1, 4
	add	a0, a0, a3
	bne	a1, a2, .LBB1_1
# %bb.2:
	lui	a1, %hi(bench_data+2047)
	addi	a1, a1, %lo(bench_data+2047)
	sw	a0, 1161(a1)
	li	a2, 1
	sw	a2, 1157(a1)
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
	.zero	3224
	.size	bench_data, 3224

	.ident	"clang version 18.1.6 (https://github.com/ziglang/zig-bootstrap 98bc6bf4fc4009888d33941daf6b600d20a42a56)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym bench_data
