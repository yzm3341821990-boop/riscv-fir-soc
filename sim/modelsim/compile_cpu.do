catch {quit -sim}
if {![file exists modelsim.ini]} {vmap -c}
if {![file isdirectory work]} {vlib work}
vmap work work
vcom -93 -work work alu_pkg.vhd alu32.vhd regfile32.vhd mul32.vhd imm_i.vhd imm_s.vhd imm_b.vhd imm_j.vhd imm_u.vhd decode_tiny.vhd tiny_cpu.vhd data_ram.vhd tb_tiny_cpu.vhd
