library ieee;
use ieee.std_logic_1164.all;
entity de2_115_app_top is
    port(CLOCK_50,RESET_N : in std_logic;SW : in std_logic_vector(3 downto 0);LEDR : out std_logic_vector(3 downto 0);
        HEX0,HEX1,HEX2,HEX3,HEX4,HEX5,HEX6,HEX7 : out std_logic_vector(6 downto 0));
end;
architecture rtl of de2_115_app_top is
    component altsource_probe
        generic(enable_metastability : string := "NO";instance_id : string := "CPU5";lpm_type : string := "altsource_probe";
            probe_width : natural := 320;source_width : natural := 320;sld_auto_instance_index : string := "YES";
            sld_instance_index : natural := 0;source_initial_value : string := "0");
        port(probe : in std_logic_vector(probe_width-1 downto 0);source : out std_logic_vector(source_width-1 downto 0));
    end component;
    signal source_bus,probe_bus : std_logic_vector(319 downto 0);
begin
    debug_link : altsource_probe generic map(instance_id=>"CPU5",probe_width=>320,source_width=>320) port map(probe=>probe_bus,source=>source_bus);
    core : entity work.de2_115_app_core port map(CLOCK_50,RESET_N,SW,LEDR,HEX0,HEX1,HEX2,HEX3,HEX4,HEX5,HEX6,HEX7,
        source_bus,probe_bus,open,open,open,open,open,open);
end;
