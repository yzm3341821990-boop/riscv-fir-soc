onerror {quit -code 1 -f}
onbreak {quit -code 1 -f}
do compile_benchmark.do
source benchmark_cases.tcl
source benchmark_helpers.do
foreach case $benchmark_cases {
    load_benchmark_case $case
    run -all
    check_benchmark_finished
    dump_benchmark_state [lindex $case 0]
    echo "BENCH_CASE_PASS name=[lindex $case 0]"
    quit -sim
}
echo "FIR_BENCHMARK_SUITE_PASS cases=[llength $benchmark_cases]"
quit -code 0 -f
