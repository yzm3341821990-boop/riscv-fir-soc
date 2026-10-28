# Generated copies prepend benchmark_directory.
onerror {abort}
onbreak {echo "FIR_BENCHMARK_STOPPED: inspect Transcript"; abort}
if {![info exists benchmark_directory]} {set benchmark_directory [pwd]}
catch {quit -sim}
cd $benchmark_directory
do compile_benchmark.do
source benchmark_cases.tcl
source benchmark_helpers.do
set demo {}
foreach case $benchmark_cases {
    if {[lindex $case 0] eq "base_hardware_cold_none"} {set demo $case; break}
}
if {[llength $demo]!=6} {error "BENCH_DEMO_NOT_FOUND"}
load_benchmark_case $demo
view wave
delete wave *
add wave -divider "Cold invocation: marker 1 -> all setup -> START -> poll -> marker 2"
foreach name {clk rst host_active} {add wave sim:/tb_fir_benchmark/$name}
add wave -label PC -radix hexadecimal sim:/tb_fir_benchmark/pc
add wave -label marker -radix unsigned {sim:/tb_fir_benchmark/dut/shared_memory/bank(176)}
add wave -label accepted_clock_count -radix unsigned sim:/tb_fir_benchmark/cycles
add wave -label FIR_STATUS -radix unsigned sim:/tb_fir_benchmark/dut/accelerator/status_word
add wave -label kernel_cycles -radix unsigned sim:/tb_fir_benchmark/dut/accelerator/cycles
add wave -label written -radix unsigned sim:/tb_fir_benchmark/dut/accelerator/written
foreach name {cpu_req cpu_we} {add wave sim:/tb_fir_benchmark/$name}
add wave -radix hexadecimal sim:/tb_fir_benchmark/cpu_addr
add wave -radix hexadecimal sim:/tb_fir_benchmark/cpu_wdata
foreach name {dma_req dma_ready dma_we} {add wave sim:/tb_fir_benchmark/$name}
add wave -divider "Actual RAM outputs"
for {set n 0} {$n < 8} {incr n} {
    add wave -label y$n -radix decimal [format {sim:/tb_fir_benchmark/dut/shared_memory/bank(%d)} [expr {168+$n}]]
}
add wave -label done -radix unsigned {sim:/tb_fir_benchmark/dut/shared_memory/bank(177)}
add wave -label errors -radix unsigned {sim:/tb_fir_benchmark/dut/shared_memory/bank(178)}
add wave sim:/tb_fir_benchmark/finished
run -all
check_benchmark_finished
dump_benchmark_state base_hardware_cold_none
configure wave -timelineunits ns
WaveRestoreCursors [list {Cursor 1} $now 0]
wave zoom full
source benchmark_summary.tcl
echo "FIR_BENCHMARK_GUI_READY $benchmark_summary"
