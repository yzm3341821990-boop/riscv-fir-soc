onerror {quit -code 1 -f}
onbreak {quit -code 1 -f}
do compile_soc.do
source soc_config.tcl
source soc_helpers.do
foreach case $guard_cases {
    lassign $case name word base enabled expected_fault
    vsim -voptargs=+acc -wlf guard-${name}-[pid].wlf -gMEM_WORD=$word -gLUI_WORD=$base \
        -gENABLE_MMIO=$enabled -gEXPECT_FAULT=$expected_fault work.tb_cpu_mmio_guard
    set BreakOnAssertion 3
    run -all
    if {[string tolower [examine sim:/tb_cpu_mmio_guard/finished]] ne "true"} {error "GUARD_CHECK_INCOMPLETE"}
    echo "GUARD_CASE_PASS name=$name"
    quit -sim
}
foreach case $mmio_cases {
    lassign $case name count protocol
    echo "MMIO_CASE_BEGIN name=$name"
    vsim -voptargs=+acc -wlf mmio-${name}-[pid].wlf \
        -gINPUT_FILE=mmio/$name/input.hex -gCOEFF_FILE=mmio/$name/coefficients.hex \
        -gOUTPUT_FILE=mmio/$name/expected.hex -gSAMPLE_COUNT=$count -gCHECK_PROTOCOL=$protocol work.tb_fir_mmio
    set BreakOnAssertion 3
    run -all
    if {[string tolower [examine sim:/tb_fir_mmio/finished]] ne "true"} {error "MMIO_CHECK_INCOMPLETE"}
    echo "MMIO_CASE_PASS name=$name"
    quit -sim
}
foreach case $soc_cases {
    lassign $case name stalls never errors
    load_soc_case $name $stalls $never $errors
    run -all
    check_soc_finished
    dump_soc_state $name
    echo "SOC_CASE_PASS name=$name"
    quit -sim
}
echo "FIR_SOC_SUITE_PASS"
quit -code 0 -f
