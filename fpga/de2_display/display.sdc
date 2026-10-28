create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]
set core_divider [get_registers {*core_clock*}]
if {[get_collection_size $core_divider] != 1} {error "CORE_DIVIDER_REGISTER_COUNT"}
create_generated_clock -name CORE_25 -source [get_ports {CLOCK_50}] -divide_by 2 $core_divider
derive_clock_uncertainty
set reset_registers [get_registers {*reset_pipe*}]
if {[get_collection_size $reset_registers] != 2} {error "RESET_SYNCHRONIZER_REGISTER_COUNT"}
set_false_path -from [get_ports {RESET_N}] -to $reset_registers
set switch_registers [get_registers {*sw_meta*}]
if {[get_collection_size $switch_registers] != 4} {error "SWITCH_SYNCHRONIZER_REGISTER_COUNT"}
set_false_path -from [get_ports {SW[*]}] -to $switch_registers
# Human observation outputs, without an external synchronous receiver.
set_false_path -to [get_ports {LEDR[*] HEX0[*] HEX1[*] HEX2[*] HEX3[*] HEX4[*] HEX5[*] HEX6[*] HEX7[*]}]
