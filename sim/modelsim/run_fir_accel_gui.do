# Generated copies prepend an absolute fir_accel_directory.
onerror {abort}
onbreak {echo "FIR_SERIAL_STOPPED: inspect Transcript"; abort}
if {![info exists fir_accel_directory]} {set fir_accel_directory [pwd]}
catch {quit -sim}
cd $fir_accel_directory
do compile_fir_accel.do
source fir_accel_helpers.do
load_fir_serial_case {software_fir 8 false true} false
view wave
delete wave *
add wave -divider "Load coefficients and clear history"
foreach name {clk rst cfg_valid cfg_ready clear_valid clear_ready} {add wave sim:/tb_fir_serial/$name}
add wave -radix unsigned sim:/tb_fir_serial/cfg_addr
add wave -radix decimal sim:/tb_fir_serial/cfg_data
add wave -divider "Input -> 32 serial MAC edges -> output handshake"
foreach name {s_valid s_ready} {add wave sim:/tb_fir_serial/$name}
add wave -radix decimal sim:/tb_fir_serial/s_data
add wave sim:/tb_fir_serial/busy
add wave sim:/tb_fir_serial/dut/state
add wave -label tap_index -radix unsigned sim:/tb_fir_serial/dut/tap_index
add wave -label running_acc -radix decimal sim:/tb_fir_serial/dut/accumulator
foreach name {m_valid m_ready} {add wave sim:/tb_fir_serial/$name}
add wave -radix decimal sim:/tb_fir_serial/m_data
add wave -radix decimal sim:/tb_fir_serial/m_acc
add wave -radix unsigned sim:/tb_fir_serial/checked_samples
add wave -divider "Actual accepted DUT outputs captured by testbench"
for {set n 0} {$n < 8} {incr n} {
    add wave -label y$n -radix decimal [format {sim:/tb_fir_serial/observed_y(%d)} $n]
}
add wave sim:/tb_fir_serial/finished
run -all
check_fir_serial_finished 8
configure wave -timelineunits ns
WaveRestoreCursors [list {Cursor 1} $now 0]
wave zoom full
echo "FIR_ACCEL_GUI_READY samples=8 expected_outputs=8192,12288,-22528,17408,-12288,15360,-7680,-2048."
