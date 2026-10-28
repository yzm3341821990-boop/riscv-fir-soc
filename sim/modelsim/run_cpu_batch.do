onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
do compile_cpu.do
source cpu_helpers.do
source cpu_cases.tcl
set cpu_passed 0
foreach case $tiny_cpu_cases {
    catch {quit -sim}
    lassign $case name program trace registers count expect_fault fault_pc inject_reset memory memory_trace reset_load
    load_cpu_case $case
    run -all
    check_cpu_finished
    check_cpu_registers $registers
    check_cpu_memory $memory
    check_cpu_reset
    if {$expect_fault} {echo "TINYCPU_FAULT_RESET_PASS"}
    check_cpu_memory $memory
    echo "TINYCPU_RESET_PRESERVES_MEMORY_PASS"
    echo "TINYCPU_CASE_PASS name=$name retired=$count"
    incr cpu_passed
}
echo "TINYCPU_SUITE_PASS cases=$cpu_passed"
quit -code 0 -force
