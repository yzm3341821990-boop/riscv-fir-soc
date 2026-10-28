library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity data_ram is
    port (
        clk, req, we : in std_logic;
        byte_enable : in std_logic_vector(3 downto 0);
        addr, wdata : in std_logic_vector(31 downto 0);
        rdata : out std_logic_vector(31 downto 0)
    );
end entity;

architecture rtl of data_ram is
    type ram_type is array(0 to 255) of std_logic_vector(31 downto 0);
    signal bank : ram_type := (others => (others => '0'));
begin
    access_word : process(clk)
    begin
        if rising_edge(clk) then
            if req = '1' then
                if we = '1' then
                    for lane in 0 to 3 loop
                        if byte_enable(lane) = '1' then
                            bank(to_integer(unsigned(addr(9 downto 2))))(8*lane+7 downto 8*lane) <=
                                wdata(8*lane+7 downto 8*lane);
                        end if;
                    end loop;
                else
                    rdata <= bank(to_integer(unsigned(addr(9 downto 2))));
                end if;
            end if;
        end if;
    end process;
end architecture;
