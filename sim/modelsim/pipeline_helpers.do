proc pipe_check_words {file_name base expected_count first} {
    set f [open $file_name r]
    set words [split [string trim [read $f]] "\n"]
    close $f
    if {[llength $words] != $expected_count} {error "PIPE_BAD_EXPECTED_WORD_COUNT"}
    set index $first
    foreach word $words {
        if {[scan $word %x expected] != 1} {error "PIPE_BAD_EXPECTED_HEX"}
        set expected [expr {$expected & 0xFFFFFFFF}]
        set actual [examine -radix unsigned [format {%s(%d)} $base $index]]
        if {$actual != $expected} {error "PIPE_FINAL_STATE_MISMATCH $base index=$index expected=$word actual=$actual"}
        incr index
    }
}
proc run_pipeline_case {name options} {
    catch {quit -sim}
    echo "PIPE_CASE_BEGIN name=$name"
    vsim -voptargs=+acc {*}$options work.tb_pipeline_cpu
    set ::BreakOnAssertion 3
    run -all
    if {[string tolower [examine sim:/tb_pipeline_cpu/finished]] ne "true"} {error "PIPE_NOT_FINISHED"}
    pipe_check_words cases/$name/expected_registers.txt sim:/tb_pipeline_cpu/dut/registers/bank 31 1
    pipe_check_words cases/$name/expected_memory.txt sim:/tb_pipeline_cpu/data_memory/bank 256 0
    # Reset after both normal completion and fatal fault, preserving all accepted stores.
    force -freeze sim:/tb_pipeline_cpu/rst 1
    force -freeze sim:/tb_pipeline_cpu/clk 0
    run 5 ns
    force -freeze sim:/tb_pipeline_cpu/clk 1
    run 1 ns
    foreach field {fault commit_valid req imem_en} {
        if {[examine sim:/tb_pipeline_cpu/$field] ne "0"} {error "PIPE_RESET_NOT_QUIET $field"}
    }
    for {set index 1} {$index <= 31} {incr index} {
        if {[examine -radix unsigned [format {sim:/tb_pipeline_cpu/dut/registers/bank(%d)} $index]] != 0} {
            error "PIPE_RESET_REGISTER_MISMATCH"
        }
    }
    pipe_check_words cases/$name/expected_memory.txt sim:/tb_pipeline_cpu/data_memory/bank 256 0
    echo "PIPE_CASE_PASS name=$name"
}
