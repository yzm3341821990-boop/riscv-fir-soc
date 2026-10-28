proc load_benchmark_case {case} {
    lassign $case name mode initial end_pc waits expects_dma
    echo "BENCH_CASE_BEGIN name=$name"
    vsim -voptargs=+acc -wlf bench-${name}-[pid].wlf \
        -gPROGRAM_FILE=images/$mode/program.hex -gINITIAL_FILE=$initial \
        -gEND_PC=$end_pc -gOUTPUT_ADDR=672 -gSTALL_DMA=$waits -gEXPECT_DMA=$expects_dma work.tb_fir_benchmark
    set ::BreakOnAssertion 3
}
proc check_benchmark_finished {} {
    if {[string tolower [examine sim:/tb_fir_benchmark/finished]] ne "true"} {error "BENCH_CHECK_NOT_FINISHED"}
    foreach pair {{176 2} {177 1} {178 0}} {
        lassign $pair word expected
        if {[examine -radix unsigned [format {sim:/tb_fir_benchmark/dut/shared_memory/bank(%d)} $word]] != $expected} {
            error "BENCH_CHECK_FLAG_$word"
        }
    }
}
proc dump_benchmark_state {name} {
    set out [open results/$name-memory.txt w]
    for {set n 0} {$n < 256} {incr n} {
        puts $out [format %08X [examine -radix unsigned [format {sim:/tb_fir_benchmark/dut/shared_memory/bank(%d)} $n]]]
    }
    close $out
    set out [open results/$name-registers.txt w]
    puts $out 00000000
    for {set n 1} {$n < 32} {incr n} {
        puts $out [format %08X [examine -radix unsigned [format {sim:/tb_fir_benchmark/dut/processor/registers/bank(%d)} $n]]]
    }
    close $out
}
