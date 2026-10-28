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
    if {[lindex $candidate 0] eq "upper_demo"} {set demo_case $candidate; break}
}
if {[llength $demo_case] != 11} {error "upper_demo case not found"}
load_cpu_case $demo_case
view wave
delete wave *
add wave -divider "Clock and instruction path"
add wave sim:/tb_tiny_cpu/clk
add wave sim:/tb_tiny_cpu/rst
add wave -label PC -radix hexadecimal sim:/tb_tiny_cpu/debug_pc
add wave -label instruction -radix hexadecimal sim:/tb_tiny_cpu/debug_instruction
add wave -label state -radix unsigned sim:/tb_tiny_cpu/debug_state
add wave -label immediate -radix hexadecimal sim:/tb_tiny_cpu/debug_imm
add wave -divider "Completed instruction"
add wave sim:/tb_tiny_cpu/commit_valid
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_pc
add wave -radix unsigned sim:/tb_tiny_cpu/commit_rd
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_value
add wave -radix unsigned sim:/tb_tiny_cpu/retired_count
add wave -divider "32-bit constant, readback, target and return address"
foreach number {1 2 3 4 5} {
    add wave -label x$number -radix hexadecimal sim:/tb_tiny_cpu/dut/registers/bank($number)
}
add wave -divider "Actual data RAM and interface"
add wave -label RAM_byte64 -radix hexadecimal {sim:/tb_tiny_cpu/data_memory/bank(16)}
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
WaveRestoreCursors {{Cursor 1} {276000 ps} 0}
quietly wave cursor active 1
WaveRestoreZoom {0 ns} {300 ns}
echo {TINYCPU_UPPER_GUI_READY constant=12345678 RAM_byte64=12345678 x5=12345678 retired=8.}
