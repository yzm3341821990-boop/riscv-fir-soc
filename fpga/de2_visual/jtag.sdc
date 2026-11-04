# Original USB-Blaster / DE2-115 on-board link, at most 6 MHz.
# This is an explicit conservative interface budget, not a measured cable delay.
# TDI/TMS launch on TCK falling edges. TDO is required at the host rising edge.
# Intel Timing Analyzer Cookbook: JTAG Signals (USB-Blaster I = 166.666 ns).
set jtag_tck [get_ports {altera_reserved_tck}]
set jtag_inputs [get_ports {altera_reserved_tdi altera_reserved_tms}]
set jtag_output [get_ports {altera_reserved_tdo}]
if {[get_collection_size $jtag_tck] != 1 || [get_collection_size $jtag_inputs] != 2 || [get_collection_size $jtag_output] != 1} {
    error "VISUAL_JTAG_PORT_COUNT"
}
create_clock -name altera_reserved_tck -period 166.666 $jtag_tck
set_clock_groups -asynchronous -group {altera_reserved_tck}
# Budget includes board/cable skew: a 40 ns input arrival interval.
set_input_delay -clock altera_reserved_tck -clock_fall -max 20.000 $jtag_inputs
set_input_delay -clock altera_reserved_tck -clock_fall -min -20.000 $jtag_inputs
# Reserve 50 ns for the host setup/return path and 50 ns for external hold.
# These limits deliberately exceed the cookbook's illustrated cable/PCB budgets.
set_output_delay -clock altera_reserved_tck -max 50.000 $jtag_output
set_output_delay -clock altera_reserved_tck -min -50.000 $jtag_output
derive_clock_uncertainty
