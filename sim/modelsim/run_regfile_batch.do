onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
do compile_regfile.do
source vector_count.tcl
vsim -voptargs=+acc -gEXPECTED_COUNT=$regfile_expected_count work.tb_regfile32
set BreakOnAssertion 3
run -all
if {[string tolower [examine sim:/tb_regfile32/finished]] ne "true"} {
    echo "REGFILE32_NOT_FINISHED"
    quit -code 1 -force
}
quit -code 0 -force
