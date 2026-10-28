proc load_soc_case {name stalls {never false} {errors 0}} {
    set ::soc_expected_errors $errors
    echo "SOC_CASE_BEGIN name=$name"
    vsim -voptargs=+acc -wlf soc-${name}-[pid].wlf -gINITIAL_FILE=cases/$name/initial_memory.txt \
        -gEND_PC=$::soc_end_pc -gOUTPUT_ADDR=$::soc_output_addr -gSTALL_DMA=$stalls -gNEVER_READY=$never work.tb_fir_soc
    set ::BreakOnAssertion 3
}
proc check_soc_finished {} {
    if {[string tolower [examine sim:/tb_fir_soc/finished]] ne "true"} {error "SOC_CHECK_NOT_FINISHED"}
    foreach pair [list [list done 1] [list errors $::soc_expected_errors] [list hw_written [expr {$::soc_expected_errors ? 0 : 8}]]] {
        lassign $pair name expected
        set word [expr {[dict get $::soc_symbols $name]/4}]
        if {[examine -radix unsigned [format {sim:/tb_fir_soc/dut/shared_memory/bank(%d)} $word]] != $expected} {
            error "SOC_CHECK_C_$name"
        }
    }
}
proc dump_soc_state {name} {
    set out [open cases/$name/final_memory.txt w]
    for {set n 0} {$n < 256} {incr n} {
        puts $out [format %08X [examine -radix unsigned [format {sim:/tb_fir_soc/dut/shared_memory/bank(%d)} $n]]]
    }
    close $out
    set out [open cases/$name/final_registers.txt w]
    puts $out 00000000
    for {set n 1} {$n < 32} {incr n} {
        puts $out [format %08X [examine -radix unsigned [format {sim:/tb_fir_soc/dut/processor/registers/bank(%d)} $n]]]
    }
    close $out
}
