create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]
set core_divider [get_registers {*core_clock*}]
if {[get_collection_size $core_divider] != 1} {error "CORE_DIVIDER_REGISTER_COUNT"}
create_generated_clock -name CORE_25 -source [get_ports {CLOCK_50}] -divide_by 2 $core_divider
derive_clock_uncertainty
# KEY0 is asynchronous; only its arrival at the reset synchronizer is exempt.
set reset_registers [get_registers {*reset_pipe*}]
if {[get_collection_size $reset_registers] != 2} {error "RESET_SYNCHRONIZER_REGISTER_COUNT"}
set_false_path -from [get_ports {RESET_N}] -to $reset_registers
# Human-observed LEDs have no external capture clock or synchronous data contract.
set_false_path -to [get_ports {LEDR[*]}]
