catch {quit -sim}
vmap -c
if {![file isdirectory work]} {vlib work}
vmap work work
vcom -93 -work work regfile32.vhd tb_regfile32.vhd
