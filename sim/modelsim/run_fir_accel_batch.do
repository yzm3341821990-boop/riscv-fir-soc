onerror {quit -code 1 -f}
onbreak {quit -code 1 -f}
do compile_fir_accel.do
source fir_accel_helpers.do
source fir_serial_cases.tcl
foreach case $fir_serial_cases {
    load_fir_serial_case $case
    run -all
    check_fir_serial_finished [lindex $case 1]
    echo "FIR_CASE_PASS name=[lindex $case 0] samples=[lindex $case 1]"
    quit -sim
}
echo "FIR_SERIAL_SUITE_PASS cases=[llength $fir_serial_cases]"
quit -code 0 -f
