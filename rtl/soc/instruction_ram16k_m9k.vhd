library ieee;use ieee.std_logic_1164.all;use ieee.numeric_std.all;
library altera_mf;use altera_mf.altera_mf_components.all;

entity instruction_ram16k_m9k is
    port(clk,rst,fetch_en : in std_logic;
        fetch_addr : in std_logic_vector(11 downto 0);
        fetch_data : out std_logic_vector(31 downto 0);
        host_req,host_we : in std_logic;
        host_addr : in std_logic_vector(11 downto 0);
        host_wdata : in std_logic_vector(31 downto 0);
        host_rdata : out std_logic_vector(31 downto 0));
end;
architecture rtl of instruction_ram16k_m9k is
    signal held_addr,address_a,address_b : std_logic_vector(11 downto 0) := (others=>'0');
    signal q_a,q_b : std_logic_vector(31 downto 0);
    signal read_a,read_b,write_b : std_logic;
begin
    -- Hold the address as well as the read enable during pipeline stalls.
    process(clk) begin if rising_edge(clk) then
        if rst='1' then held_addr<=(others=>'0');
        elsif fetch_en='1' then held_addr<=fetch_addr;end if;
    end if;end process;
    address_a<=fetch_addr when fetch_en='1' else held_addr;
    address_b<=host_addr when host_req='1' else (others=>'0');
    read_a<=fetch_en and not rst;
    read_b<=host_req and not host_we and not rst;
    write_b<=host_req and host_we and not rst;
    fetch_data<=x"00000013" when rst='1' else q_a;
    host_rdata<=x"00000000" when rst='1' else q_b;
    memory : altsyncram
        generic map(intended_device_family=>"Cyclone IV E",ram_block_type=>"M9K",
            operation_mode=>"BIDIR_DUAL_PORT",width_a=>32,width_b=>32,
            widthad_a=>12,widthad_b=>12,numwords_a=>4096,numwords_b=>4096,
            width_byteena_a=>4,width_byteena_b=>4,byte_size=>8,
            address_reg_b=>"CLOCK0",indata_reg_b=>"CLOCK0",byteena_reg_b=>"CLOCK0",
            rdcontrol_reg_b=>"CLOCK0",wrcontrol_wraddress_reg_b=>"CLOCK0",
            outdata_reg_a=>"UNREGISTERED",outdata_reg_b=>"UNREGISTERED",
            read_during_write_mode_mixed_ports=>"OLD_DATA",power_up_uninitialized=>"FALSE")
        port map(clock0=>clk,address_a=>address_a,address_b=>address_b,
            data_a=>(others=>'0'),data_b=>host_wdata,wren_a=>'0',wren_b=>write_b,
            rden_a=>read_a,rden_b=>read_b,byteena_a=>"1111",byteena_b=>"1111",q_a=>q_a,q_b=>q_b);
end;
