library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity shared_ram is
    port(clk,rst : in std_logic;
         a_req,a_we : in std_logic; a_be : in std_logic_vector(3 downto 0);
         a_addr,a_wdata : in std_logic_vector(31 downto 0); a_rdata : out std_logic_vector(31 downto 0);
         b_req,b_we : in std_logic; b_addr,b_wdata : in std_logic_vector(31 downto 0);
         b_allow : in std_logic; b_ready,b_rvalid : out std_logic; b_rdata : out std_logic_vector(31 downto 0));
end entity;
architecture rtl of shared_ram is
    type bank_type is array(0 to 255) of std_logic_vector(31 downto 0);
    signal bank : bank_type := (others=>(others=>'0'));
begin
    b_ready<=b_allow and not rst;
    access_ports : process(clk)
    begin
        if rising_edge(clk) then
            b_rvalid<='0';
            if a_req='1' then
                if a_we='1' then
                    for lane in 0 to 3 loop
                        if a_be(lane)='1' then
                            bank(to_integer(unsigned(a_addr(9 downto 2))))(8*lane+7 downto 8*lane)<=a_wdata(8*lane+7 downto 8*lane);
                        end if;
                    end loop;
                else a_rdata<=bank(to_integer(unsigned(a_addr(9 downto 2)))); end if;
            end if;
            if rst='0' and b_req='1' and b_allow='1' then
                if b_we='1' then bank(to_integer(unsigned(b_addr(9 downto 2))))<=b_wdata;
                else b_rdata<=bank(to_integer(unsigned(b_addr(9 downto 2)))); b_rvalid<='1'; end if;
            end if;
        end if;
    end process;
end architecture;
