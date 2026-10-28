onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
# ModelSim 'do' does not set Tcl's [info script] to the macro filename.
# The command-line runner starts this process in its simulation directory.
set alu_directory [pwd]
do compile_alu.do
source vector_count.tcl
vsim -voptargs=+acc -gEXPECTED_COUNT=$alu_expected_count work.tb_alu32
set BreakOnAssertion 3
run -all
if {[string tolower [examine sim:/tb_alu32/finished]] ne "true"} {
    echo "ALU32_NOT_FINISHED"
    quit -code 1 -force
}
quit -code 0 -force
