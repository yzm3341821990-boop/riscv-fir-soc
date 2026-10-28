# Generated copies receive an absolute cpu_directory assignment.
onerror {abort}
onbreak {echo "TINYCPU_STOPPED: inspect Transcript"; abort}
if {![info exists cpu_directory]} {set cpu_directory [pwd]}
catch {quit -sim}
cd $cpu_directory
do compile_cpu.do
source cpu_helpers.do
source cpu_cases.tcl
source fir_gui_config.tcl
set demo_case {}
foreach candidate $tiny_cpu_cases {
    if {[lindex $candidate 0] eq "software_fir"} {set demo_case $candidate; break}
}
if {[llength $demo_case] != 11} {error "software_fir case not found"}
load_cpu_case $demo_case
view wave
delete wave *
add wave -divider "C FIR execution"
add wave sim:/tb_tiny_cpu/clk
add wave sim:/tb_tiny_cpu/rst
add wave sim:/tb_tiny_cpu/initial_memory_ready
add wave -label PC -radix hexadecimal sim:/tb_tiny_cpu/debug_pc
add wave sim:/tb_tiny_cpu/commit_valid
add wave -radix unsigned sim:/tb_tiny_cpu/retired_count
add wave -label MUL_operations -radix unsigned sim:/tb_tiny_cpu/multiply_count
add wave -divider "Actual RAM outputs (signed Q15 raw integers)"
for {set n 0} {$n < 8} {incr n} {
    set word [expr {$fir_outputs_word + $n/2}]
    set low [expr {16*($n%2)}]
    set path [format {sim:/tb_tiny_cpu/data_memory/bank(%d)(%d downto %d)} $word [expr {$low+15}] $low]
    add wave -label y$n -radix decimal $path
}
add wave -label C_done -radix unsigned [format {sim:/tb_tiny_cpu/data_memory/bank(%d)} $fir_done_word]
add wave -label sp -radix unsigned {sim:/tb_tiny_cpu/dut/registers/bank(2)}
add wave -label a0_return -radix decimal {sim:/tb_tiny_cpu/dut/registers/bank(10)}
add wave sim:/tb_tiny_cpu/dmem_req
add wave sim:/tb_tiny_cpu/dmem_we
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_addr
add wave -radix hexadecimal sim:/tb_tiny_cpu/dmem_wdata
add wave sim:/tb_tiny_cpu/finished
run -all
check_cpu_finished
check_cpu_registers [lindex $demo_case 3]
check_cpu_memory [lindex $demo_case 8]
if {[examine -radix unsigned sim:/tb_tiny_cpu/multiply_count] != $fir_multiply_count} {error "FIR_MUL_COUNT_MISMATCH"}
configure wave -timelineunits ns
WaveRestoreCursors [list {Cursor 1} "$fir_finish_ns ns" 0]
quietly wave cursor active 1
WaveRestoreZoom {2560 ns} "[expr {$fir_finish_ns + 100}] ns"
echo "TINYCPU_FIR_GUI_READY outputs=[join $fir_expected_outputs ,] done=1 retired=$fir_retired_count multiplications=$fir_multiply_count."
