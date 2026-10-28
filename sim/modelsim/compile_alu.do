# Run inside the generated ASCII-only simulation directory.
catch {quit -sim}
vmap -c
if {![file isdirectory work]} {vlib work}
vmap work work
vcom -93 -work work alu_pkg.vhd alu32.vhd tb_alu32.vhd
