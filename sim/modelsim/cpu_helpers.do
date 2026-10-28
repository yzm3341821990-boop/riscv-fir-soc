proc load_cpu_case {case} {
    lassign $case name program trace registers count expect_fault fault_pc inject_reset memory memory_trace reset_load
    echo "TINYCPU_CASE_BEGIN name=$name"
    set initial_options {}
    set initial_file [file join [file dirname $program] initial_memory.txt]
    if {[file exists $initial_file]} {lappend initial_options -gINITIAL_MEMORY_FILE=$initial_file}
    vsim {*}$initial_options -voptargs=+acc -wlf cpu-${name}-[pid].wlf -gPROGRAM_FILE=$program -gTRACE_FILE=$trace \
        -gEXPECTED_COUNT=$count -gEXPECT_FAULT=$expect_fault -gFAULT_PC=$fault_pc \
        -gINJECT_RESET=$inject_reset -gMEMORY_TRACE_FILE=$memory_trace \
        -gRESET_DURING_LOAD=$reset_load work.tb_tiny_cpu
    set ::BreakOnAssertion 3
}

proc check_cpu_finished {} {
    if {[string tolower [examine sim:/tb_tiny_cpu/finished]] ne "true"} {
        error "TINYCPU_NOT_FINISHED"
    }
}

proc check_cpu_registers {filename} {
    set source [open $filename r]
    set words [split [string trim [read $source]] "\n"]
    close $source
    if {[llength $words] != 31} {error "TINYCPU_BAD_REGISTER_FILE"}
    set address 1
    foreach word $words {
        if {[scan $word %x expected] != 1} {error "TINYCPU_BAD_REGISTER_WORD"}
        # Tcl 8.5 in the 32-bit simulator may scan FFFFFFFF as signed -1.
        set expected [expr {$expected & 0xFFFFFFFF}]
        set path [format {sim:/tb_tiny_cpu/dut/registers/bank(%d)} $address]
        set actual [examine -radix unsigned $path]
        if {$actual != $expected} {
            error "TINYCPU_REGISTER_MISMATCH x$address expected=$word actual=$actual"
        }
        incr address
    }
}

proc check_cpu_reset {} {
    force -freeze sim:/tb_tiny_cpu/rst 1
    force -freeze sim:/tb_tiny_cpu/clk 0
    run 5 ns
    force -freeze sim:/tb_tiny_cpu/clk 1
    run 1 ns
    if {[examine sim:/tb_tiny_cpu/fault] ne "0" ||
        [examine -radix unsigned sim:/tb_tiny_cpu/debug_pc] != 0 ||
        [examine -radix unsigned sim:/tb_tiny_cpu/debug_state] != 0 ||
        [examine -radix unsigned sim:/tb_tiny_cpu/debug_instruction] != 19 ||
        [examine sim:/tb_tiny_cpu/commit_valid] ne "0" ||
        [examine sim:/tb_tiny_cpu/dmem_req] ne "0" ||
        [examine -radix unsigned sim:/tb_tiny_cpu/dmem_be] != 0} {
        error "TINYCPU_FAULT_RESET_MISMATCH"
    }
    for {set address 1} {$address <= 31} {incr address} {
        set path [format {sim:/tb_tiny_cpu/dut/registers/bank(%d)} $address]
        if {[examine -radix unsigned $path] != 0} {error "TINYCPU_RESET_REGISTER_MISMATCH"}
    }
    echo "TINYCPU_RESET_PASS"
}

proc check_cpu_memory {filename} {
    set source [open $filename r]
    set words [split [string trim [read $source]] "\n"]
    close $source
    if {[llength $words] != 256} {error "TINYCPU_BAD_MEMORY_FILE"}
    set address 0
    foreach word $words {
        if {[scan $word %x expected] != 1} {error "TINYCPU_BAD_MEMORY_WORD"}
        set expected [expr {$expected & 0xFFFFFFFF}]
        set path [format {sim:/tb_tiny_cpu/data_memory/bank(%d)} $address]
        set actual [examine -radix unsigned $path]
        if {$actual != $expected} {
            error "TINYCPU_MEMORY_MISMATCH word=$address expected=$word actual=$actual"
        }
        incr address
    }
    echo "TINYCPU_MEMORY_STATE_PASS words=256"
}
