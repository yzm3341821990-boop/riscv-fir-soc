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
    if {[lindex $candidate 0] eq "subword_demo"} {set demo_case $candidate; break}
}
if {[llength $demo_case] != 11} {error "subword_demo case not found"}
load_cpu_case $demo_case
view wave
delete wave *
add wave -divider "Clock and completed instruction"
add wave sim:/tb_tiny_cpu/clk
add wave sim:/tb_tiny_cpu/rst
add wave -label PC -radix hexadecimal sim:/tb_tiny_cpu/debug_pc
add wave sim:/tb_tiny_cpu/commit_valid
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_pc
add wave -radix unsigned sim:/tb_tiny_cpu/commit_rd
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_value
add wave -radix unsigned sim:/tb_tiny_cpu/retired_count
add wave -divider "Signed and unsigned loads"
foreach number {3 4 5 6 9 10 11} {
    add wave -label x$number -radix hexadecimal sim:/tb_tiny_cpu/dut/registers/bank($number)
}
add wave -label LB_signed -radix decimal {sim:/tb_tiny_cpu/dut/registers/bank(3)}
add wave -label LBU_unsigned -radix unsigned {sim:/tb_tiny_cpu/dut/registers/bank(4)}
add wave -divider "Partial writes preserve neighbouring bytes"
add wave -label RAM_byte64 -radix hexadecimal {sim:/tb_tiny_cpu/data_memory/bank(16)}
add wave sim:/tb_tiny_cpu/dmem_req
add wave sim:/tb_tiny_cpu/dmem_we
add wave -label byte_enable -radix binary sim:/tb_tiny_cpu/dmem_be
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_addr
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_wdata
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_rdata
add wave sim:/tb_tiny_cpu/finished
run -all
check_cpu_finished
check_cpu_registers [lindex $demo_case 3]
check_cpu_memory [lindex $demo_case 8]
configure wave -timelineunits ns
WaveRestoreCursors {{Cursor 1} {566000 ps} 0}
quietly wave cursor active 1
WaveRestoreZoom {0 ns} {600 ns}
echo {TINYCPU_SUBWORD_GUI_READY LB=FFFFFF81 LBU=00000081 LH=FFFF80FF LHU=000080FF RAM_byte64=ABCD557F retired=16.}
