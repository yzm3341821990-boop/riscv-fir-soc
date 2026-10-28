onerror {quit -code 1 -f}
onbreak {quit -code 1 -f}
if {![file exists modelsim.ini]} {vmap -c}
if {![file isdirectory work]} {vlib work}
vmap work work
vcom -93 board_images_pkg.vhd alu_pkg.vhd alu32.vhd regfile32.vhd mul32.vhd imm_i.vhd imm_s.vhd imm_b.vhd imm_j.vhd imm_u.vhd decode_tiny.vhd tiny_cpu.vhd fir_serial.vhd fir_mmio.vhd shared_ram.vhd fir_soc.vhd de2_115_top.vhd tb_de2_boot.vhd
vsim -voptargs=+acc -wlf de2-boot-[pid].wlf work.tb_de2_boot
set BreakOnAssertion 3
run -all
if {[string tolower [examine sim:/tb_de2_boot/finished]] ne "true"} {error "DE2_BOOT_NOT_FINISHED"}
if {[examine -radix unsigned sim:/tb_de2_boot/completed_runs] != 4} {error "DE2_BOOT_RESTART_COUNT"}
echo "DE2_BOOT_SUITE_PASS"
quit -code 0 -f
