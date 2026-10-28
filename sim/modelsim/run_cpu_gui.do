# Generated copies receive an absolute cpu_directory assignment.
onerror {abort}
onbreak {echo "TINYCPU_STOPPED: inspect Transcript"; abort}
if {![info exists cpu_directory]} {set cpu_directory [pwd]}
catch {quit -sim}
cd $cpu_directory
do compile_cpu.do
source cpu_helpers.do
source cpu_cases.tcl
set demo_case [lindex $tiny_cpu_cases 0]
load_cpu_case $demo_case
view wave
delete wave *
add wave -divider "Clock and instruction"
add wave sim:/tb_tiny_cpu/clk
add wave sim:/tb_tiny_cpu/rst
add wave -label PC -radix hexadecimal sim:/tb_tiny_cpu/debug_pc
add wave -label instruction -radix hexadecimal sim:/tb_tiny_cpu/debug_instruction
add wave -label state -radix unsigned sim:/tb_tiny_cpu/debug_state
add wave -divider "Completed instruction"
add wave sim:/tb_tiny_cpu/commit_valid
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_pc
add wave -radix unsigned sim:/tb_tiny_cpu/commit_rd
add wave -radix hexadecimal sim:/tb_tiny_cpu/commit_value
add wave -divider "Registers: actual saved data"
add wave -label x1 -radix hexadecimal {sim:/tb_tiny_cpu/dut/registers/bank(1)}
add wave -label x2 -radix hexadecimal {sim:/tb_tiny_cpu/dut/registers/bank(2)}
add wave -label x3 -radix hexadecimal {sim:/tb_tiny_cpu/dut/registers/bank(3)}
add wave sim:/tb_tiny_cpu/finished
run -all
check_cpu_finished
check_cpu_registers [lindex $demo_case 3]
check_cpu_memory [lindex $demo_case 8]
configure wave -timelineunits ns
WaveRestoreCursors {{Cursor 1} {105500 ps} 0}
quietly wave cursor active 1
WaveRestoreZoom {0 ns} {115 ns}
echo "TINYCPU_GUI_READY x1=5 x2=7 x3=12: inspect commits at 45, 75 and 105 ns."
