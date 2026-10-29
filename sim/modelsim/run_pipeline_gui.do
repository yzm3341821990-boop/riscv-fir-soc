# Run from the ASCII directory produced by tools.run_pipeline_cpu --prepare-only.
# This macro is stored in the repository; it does not assume the working directory.
catch {quit -sim}
if {![info exists pipeline_directory]} {error "Set pipeline_directory to the prepared ASCII directory first"}
cd $pipeline_directory
if {![info exists pipeline_case_name]} {set pipeline_case_name pipe_load_use}
if {![file exists modelsim.ini]} {vmap -c}
if {![file isdirectory work]} {vlib work}
vmap work work
vcom -93 alu_pkg.vhd alu32.vhd regfile32.vhd mul32.vhd imm_i.vhd imm_s.vhd imm_b.vhd imm_j.vhd imm_u.vhd decode_tiny.vhd data_ram.vhd pipeline_cpu.vhd tb_pipeline_cpu.vhd
quietly set source [open pipeline_cases.do r]
quietly set rows [split [read $source] "\n"]
close $source
quietly set selected {}
foreach row $rows {
    if {[lindex $row 1] eq $pipeline_case_name} {set selected [lindex $row 2]}
}
if {[llength $selected] == 0} {error "Unknown pipeline_case_name"}
vsim -voptargs=+acc {*}$selected work.tb_pipeline_cpu
set ::BreakOnAssertion 3
add wave -divider {Clock and pipeline}
add wave sim:/tb_pipeline_cpu/clk sim:/tb_pipeline_cpu/rst
add wave -radix hexadecimal sim:/tb_pipeline_cpu/imem_addr
add wave sim:/tb_pipeline_cpu/imem_en sim:/tb_pipeline_cpu/stages
add wave sim:/tb_pipeline_cpu/stall sim:/tb_pipeline_cpu/flush
add wave -divider {Ordered retirement}
add wave sim:/tb_pipeline_cpu/commit_valid
add wave -radix hexadecimal sim:/tb_pipeline_cpu/commit_pc sim:/tb_pipeline_cpu/commit_instruction
add wave -radix unsigned sim:/tb_pipeline_cpu/rd
add wave -radix hexadecimal sim:/tb_pipeline_cpu/commit_value sim:/tb_pipeline_cpu/commit_next_pc
add wave -divider {Real RAM transactions}
add wave sim:/tb_pipeline_cpu/req sim:/tb_pipeline_cpu/we sim:/tb_pipeline_cpu/be
add wave -radix hexadecimal sim:/tb_pipeline_cpu/addr sim:/tb_pipeline_cpu/wdata sim:/tb_pipeline_cpu/rdata
add wave sim:/tb_pipeline_cpu/fault sim:/tb_pipeline_cpu/finished
run -all
if {[string tolower [examine sim:/tb_pipeline_cpu/finished]] ne "true"} {error "PIPE_GUI_NOT_FINISHED"}
do pipeline_helpers.do
pipe_check_words cases/$pipeline_case_name/expected_registers.txt sim:/tb_pipeline_cpu/dut/registers/bank 31 1
pipe_check_words cases/$pipeline_case_name/expected_memory.txt sim:/tb_pipeline_cpu/data_memory/bank 256 0
catch {wave zoom range 2550ns 2800ns}
echo "PIPE_GUI_READY case=$pipeline_case_name; inspect stall and commit_valid."
