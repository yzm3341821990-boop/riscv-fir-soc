proc load_fir_serial_case {case {stress true}} {
    lassign $case name count protocol stalls
    echo "FIR_CASE_BEGIN name=$name"
    set dir cases/$name
    vsim -voptargs=+acc -wlf fir-${name}-[pid].wlf \
        -gINPUT_FILE=$dir/input.hex -gCOEFF_FILE=$dir/coefficients.hex \
        -gOUTPUT_FILE=$dir/expected.hex -gACC_FILE=$dir/accumulators.hex \
        -gSAMPLE_COUNT=$count -gCHECK_PROTOCOL=$protocol -gUSE_STALLS=$stalls -gSTRESS_BUSY=$stress work.tb_fir_serial
    set ::BreakOnAssertion 3
}
proc check_fir_serial_finished {count} {
    if {[string tolower [examine sim:/tb_fir_serial/finished]] ne "true"} {error "FIR_NOT_FINISHED"}
    if {[examine -radix unsigned sim:/tb_fir_serial/checked_samples] != $count} {error "FIR_BAD_OUTPUT_COUNT"}
}
