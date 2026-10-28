onerror {quit -code 1 -f}
onbreak {quit -code 1 -f}
if {![file exists modelsim.ini]} {vmap -c}
if {![file isdirectory work]} {vlib work}
vmap work work
vcom -93 board_images_pkg.vhd alu_pkg.vhd alu32.vhd regfile32.vhd mul32.vhd imm_i.vhd imm_s.vhd imm_b.vhd imm_j.vhd imm_u.vhd decode_tiny.vhd tiny_cpu.vhd fir_serial.vhd fir_mmio.vhd shared_ram.vhd fir_soc.vhd de2_115_top.vhd hex7seg.vhd de2_115_display_top.vhd tb_de2_display.vhd
if {[info exists expected_error] && $expected_error} {
    vsim -voptargs=+acc -wlf display-[pid].wlf work.tb_de2_display -gEXPECT_ERROR=true
} else {
    vsim -voptargs=+acc -wlf display-[pid].wlf work.tb_de2_display
}
set BreakOnAssertion 3
run -all
if {[string tolower [examine sim:/tb_de2_display/finished]] ne "true"} {error "DISPLAY_NOT_FINISHED"}
set runs 4
if {[info exists expected_error] && $expected_error} {set runs 1}
if {[examine -radix unsigned sim:/tb_de2_display/completed_runs] != $runs} {error "DISPLAY_RESTART_COUNT"}
echo "DISPLAY_SUITE_PASS"
quit -code 0 -f
