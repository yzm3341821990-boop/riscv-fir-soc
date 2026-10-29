library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library altera_mf;
use altera_mf.altera_mf_components.all;

entity shared_ram_m9k is
    port(clk,rst : in std_logic;
         a_req,a_we : in std_logic; a_be : in std_logic_vector(3 downto 0);
         a_addr,a_wdata : in std_logic_vector(31 downto 0); a_rdata : out std_logic_vector(31 downto 0);
         b_req,b_we : in std_logic; b_addr,b_wdata : in std_logic_vector(31 downto 0);
         b_allow : in std_logic; b_ready,b_rvalid : out std_logic; b_rdata : out std_logic_vector(31 downto 0));
end entity;

architecture rtl of shared_ram_m9k is
    signal conflict,accept_b,ready_i,wa,wb,ra,rb : std_logic;
    signal address_a,address_b : std_logic_vector(12 downto 0);
begin
    conflict<='1' when a_req='1' and a_addr(14 downto 2)=b_addr(14 downto 2)
                      and (a_we='1' or b_we='1') else '0';
    ready_i<=b_allow and not rst and not conflict;
    b_ready<=ready_i;
    accept_b<=b_req and ready_i;
    wa<=a_req and a_we;ra<=a_req and not a_we;
    wb<=accept_b and b_we;rb<=accept_b and not b_we;
    address_a<=a_addr(14 downto 2) when a_req='1' else (others=>'0');
    address_b<=b_addr(14 downto 2) when accept_b='1' else (others=>'0');
    -- Quartus 17 exposes this megafunction through its component package.
    memory : altsyncram
        generic map(intended_device_family=>"Cyclone IV E",ram_block_type=>"M9K",
            operation_mode=>"BIDIR_DUAL_PORT",width_a=>32,width_b=>32,
            widthad_a=>13,widthad_b=>13,numwords_a=>8192,numwords_b=>8192,
            width_byteena_a=>4,width_byteena_b=>4,byte_size=>8,
            address_reg_b=>"CLOCK0",indata_reg_b=>"CLOCK0",byteena_reg_b=>"CLOCK0",
            rdcontrol_reg_b=>"CLOCK0",wrcontrol_wraddress_reg_b=>"CLOCK0",
            outdata_reg_a=>"UNREGISTERED",outdata_reg_b=>"UNREGISTERED",
            read_during_write_mode_mixed_ports=>"OLD_DATA",power_up_uninitialized=>"FALSE")
        port map(clock0=>clk,address_a=>address_a,address_b=>address_b,
            data_a=>a_wdata,data_b=>b_wdata,wren_a=>wa,wren_b=>wb,rden_a=>ra,rden_b=>rb,
            byteena_a=>a_be,byteena_b=>"1111",q_a=>a_rdata,q_b=>b_rdata);
    response : process(clk)
    begin
        if rising_edge(clk) then
            if rst='1' then b_rvalid<='0';else b_rvalid<=rb;end if;
            -- synthesis translate_off
            if a_req='1' then
                assert unsigned(a_addr)<32768 report "M9K_A_ADDRESS_RANGE" severity failure;
            end if;
            if accept_b='1' then
                assert unsigned(b_addr)<32768 and b_addr(1 downto 0)="00"
                    report "M9K_B_ADDRESS_RANGE_OR_ALIGNMENT" severity failure;
            end if;
            -- synthesis translate_on
        end if;
    end process;
end architecture;
