# Generated copies receive an absolute cpu_directory assignment.
onerror {abort}
onbreak {echo "TINYCPU_STOPPED: inspect Transcript"; abort}
if {![info exists cpu_directory]} {set cpu_directory [pwd]}
catch {quit -sim}
cd $cpu_directory
do compile_cpu.do
source cpu_helpers.do
source cpu_cases.tcl
set demo_case {}
foreach candidate $tiny_cpu_cases {
    if {[lindex $candidate 0] eq "c_array_sum"} {set demo_case $candidate; break}
}
if {[llength $demo_case] != 11} {error "c_array_sum case not found"}
load_cpu_case $demo_case
view wave
delete wave *
add wave -divider "C execution after initialized RAM loading"
add wave sim:/tb_tiny_cpu/clk
add wave sim:/tb_tiny_cpu/rst
add wave sim:/tb_tiny_cpu/initial_memory_ready
add wave -label PC -radix hexadecimal sim:/tb_tiny_cpu/debug_pc
add wave sim:/tb_tiny_cpu/commit_valid
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_pc
add wave -radix unsigned sim:/tb_tiny_cpu/commit_rd
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_value
add wave -radix unsigned sim:/tb_tiny_cpu/retired_count
add wave -divider "Calling convention and C globals"
add wave -label ra -radix hexadecimal {sim:/tb_tiny_cpu/dut/registers/bank(1)}
add wave -label sp -radix unsigned {sim:/tb_tiny_cpu/dut/registers/bank(2)}
add wave -label a0_return -radix decimal {sim:/tb_tiny_cpu/dut/registers/bank(10)}
add wave -label C_result -radix decimal {sim:/tb_tiny_cpu/data_memory/bank(132)}
add wave -label C_done -radix unsigned {sim:/tb_tiny_cpu/data_memory/bank(133)}
add wave -label samples_0_1 -radix hexadecimal {sim:/tb_tiny_cpu/data_memory/bank(128)}
add wave -divider "CPU memory requests (loader writes excluded)"
add wave sim:/tb_tiny_cpu/dmem_req
add wave sim:/tb_tiny_cpu/dmem_we
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_addr
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_wdata
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_rdata
add wave sim:/tb_tiny_cpu/finished
run -all
check_cpu_finished
check_cpu_registers [lindex $demo_case 3]
check_cpu_memory [lindex $demo_case 8]
configure wave -timelineunits ns
WaveRestoreCursors {{Cursor 1} {4596000 ps} 0}
quietly wave cursor active 1
WaveRestoreZoom {2560 ns} {4620 ns}
echo {TINYCPU_C_GUI_READY result=55 done=1 sp=1024 retired=64.}
