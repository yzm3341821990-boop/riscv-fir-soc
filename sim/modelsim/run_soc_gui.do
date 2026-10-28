# Generated copies prepend soc_directory.
onerror {abort}
onbreak {echo "FIR_SOC_STOPPED: inspect Transcript"; abort}
if {![info exists soc_directory]} {set soc_directory [pwd]}
catch {quit -sim}
cd $soc_directory
do compile_soc.do
source soc_config.tcl
source soc_helpers.do
load_soc_case hardware_fir true
view wave
delete wave *
add wave -divider "CPU runs the compiled C driver"
foreach name {clk rst host_active} {add wave sim:/tb_fir_soc/$name}
add wave -label PC -radix hexadecimal sim:/tb_fir_soc/pc
add wave sim:/tb_fir_soc/commit_valid
add wave -radix unsigned sim:/tb_fir_soc/retired_count
foreach name {cpu_req cpu_we} {add wave sim:/tb_fir_soc/$name}
add wave -radix hexadecimal sim:/tb_fir_soc/cpu_addr
add wave -radix hexadecimal sim:/tb_fir_soc/cpu_wdata
add wave -divider "MMIO START -> DMA reads -> FIR MAC -> accepted RAM writes -> DONE"
add wave -label FIR_STATUS -radix unsigned sim:/tb_fir_soc/dut/accelerator/status_word
add wave sim:/tb_fir_soc/dut/accelerator/state
add wave -label HW_cycles -radix unsigned sim:/tb_fir_soc/dut/accelerator/cycles
add wave -label HW_written -radix unsigned sim:/tb_fir_soc/dut/accelerator/written
foreach name {dma_req dma_ready dma_we} {add wave sim:/tb_fir_soc/$name}
add wave -radix unsigned sim:/tb_fir_soc/dma_addr
add wave -radix decimal sim:/tb_fir_soc/dma_wdata
add wave -divider "Actual shared RAM: signed Q15 output words"
for {set n 0} {$n < 8} {incr n} {
    add wave -label y$n -radix decimal [format {sim:/tb_fir_soc/dut/shared_memory/bank(%d)} [expr {$soc_output_addr/4+$n}]]
}
foreach name {done errors polls} {
    add wave -label C_$name -radix unsigned [format {sim:/tb_fir_soc/dut/shared_memory/bank(%d)} [expr {[dict get $soc_symbols $name]/4}]]
}
add wave sim:/tb_fir_soc/finished
run -all
check_soc_finished
dump_soc_state hardware_fir
configure wave -timelineunits ns
WaveRestoreCursors [list {Cursor 1} $now 0]
wave zoom full
echo "FIR_SOC_GUI_READY C_done=1 C_errors=0 HW_written=8."
