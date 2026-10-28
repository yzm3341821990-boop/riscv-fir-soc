library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity regfile32 is
    port (
        clk, rst, we : in std_logic;
        waddr, raddr1, raddr2 : in std_logic_vector(4 downto 0);
        wdata : in std_logic_vector(31 downto 0);
        rdata1, rdata2 : out std_logic_vector(31 downto 0)
    );
end entity;

architecture rtl of regfile32 is
    type register_bank is array(1 to 31) of std_logic_vector(31 downto 0);
    signal bank : register_bank;
begin
    write_port : process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                bank <= (others => (others => '0'));
            elsif we = '1' and waddr /= "00000" then
                bank(to_integer(unsigned(waddr))) <= wdata;
            end if;
        end if;
    end process;

    read_ports : process(bank, raddr1, raddr2)
        variable first, second : natural range 0 to 31;
    begin
        rdata1 <= (others => 'X');
        rdata2 <= (others => 'X');
        first := 0;
        second := 0;
        -- X is a simulation diagnostic, not a hardware unknown detector.
        -- Only binary addresses belong to the architectural contract.
        if not is_x(raddr1) then
            first := to_integer(unsigned(raddr1));
            if first = 0 then
                rdata1 <= (others => '0');
            else
                rdata1 <= bank(first);
            end if;
        end if;
        if not is_x(raddr2) then
            second := to_integer(unsigned(raddr2));
            if second = 0 then
                rdata2 <= (others => '0');
            else
                rdata2 <= bank(second);
            end if;
        end if;
    end process;
end architecture;
