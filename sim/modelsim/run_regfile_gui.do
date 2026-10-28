# The generated copy receives an absolute directory assignment from Python.
onerror {abort}
onbreak {echo "REGFILE32_STOPPED: inspect Transcript"; abort}
if {![info exists regfile_directory]} {set regfile_directory [pwd]}
# ModelSim refuses cd while a design is loaded, even after run -all returns.
catch {quit -sim}
cd $regfile_directory
do compile_regfile.do
source vector_count.tcl
vsim -voptargs=+acc -gEXPECTED_COUNT=$regfile_expected_count work.tb_regfile32
set BreakOnAssertion 3
view wave
delete wave *
add wave -divider "Clock and control"
add wave -radix unsigned sim:/tb_regfile32/test_index
add wave sim:/tb_regfile32/clk
add wave sim:/tb_regfile32/rst
add wave sim:/tb_regfile32/we
add wave -divider "Write port"
add wave -radix unsigned sim:/tb_regfile32/waddr
add wave -radix hexadecimal sim:/tb_regfile32/wdata
add wave -divider "Read port 1"
add wave -radix unsigned sim:/tb_regfile32/raddr1
add wave -radix hexadecimal sim:/tb_regfile32/expected1
add wave -radix hexadecimal sim:/tb_regfile32/rdata1
add wave -divider "Read port 2"
add wave -radix unsigned sim:/tb_regfile32/raddr2
add wave -radix hexadecimal sim:/tb_regfile32/expected2
add wave -radix hexadecimal sim:/tb_regfile32/rdata2
add wave sim:/tb_regfile32/finished
run -all
if {[string tolower [examine sim:/tb_regfile32/finished]] ne "true"} {
    error "REGFILE32_NOT_FINISHED"
}
configure wave -timelineunits ns
WaveRestoreCursors {{Cursor 1} {17 ns} 0}
quietly wave cursor active 1
WaveRestoreZoom {0 ns} {90 ns}
echo "REGFILE32_GUI_READY: inspect x1 write at the 15 ns rising edge."
