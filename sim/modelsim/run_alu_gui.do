# Open this generated script from the ModelSim Transcript using: do {full/path}
onerror {abort}
onbreak {echo "ALU32_STOPPED: inspect the assertion in Transcript"; abort}
# The generated copy gets an absolute alu_directory assignment from Python.
if {![info exists alu_directory]} {set alu_directory [pwd]}
# Unload before changing directories when switching from another design.
catch {quit -sim}
cd $alu_directory
do compile_alu.do
source vector_count.tcl
vsim -voptargs=+acc -gEXPECTED_COUNT=$alu_expected_count work.tb_alu32
set BreakOnAssertion 3
view wave
add wave -radix unsigned sim:/tb_alu32/test_index
add wave -radix hexadecimal sim:/tb_alu32/alu_op
add wave -radix hexadecimal sim:/tb_alu32/a
add wave -radix hexadecimal sim:/tb_alu32/b
add wave -radix hexadecimal sim:/tb_alu32/expected
add wave -radix hexadecimal sim:/tb_alu32/result
add wave sim:/tb_alu32/finished
run -all
if {[string tolower [examine sim:/tb_alu32/finished]] ne "true"} {
    error "ALU32_NOT_FINISHED"
}
WaveRestoreZoom {0 ns} {16 ns}
echo "ALU32_GUI_READY: first 16 hand-derived vectors are visible."
