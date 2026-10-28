catch {quit -sim}
if {![file exists modelsim.ini]} {vmap -c}
if {![file isdirectory work]} {vlib work}
vmap work work
vcom -93 -work work fir_serial.vhd tb_fir_serial.vhd
