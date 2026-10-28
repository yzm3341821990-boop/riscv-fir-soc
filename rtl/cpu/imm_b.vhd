library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity imm_b is
    port (
        instruction : in std_logic_vector(31 downto 0);
        immediate : out std_logic_vector(31 downto 0)
    );
end entity;

architecture rtl of imm_b is
    signal offset_bits : std_logic_vector(12 downto 0);
begin
    offset_bits <= instruction(31) & instruction(7) & instruction(30 downto 25) &
                   instruction(11 downto 8) & '0';
    immediate <= std_logic_vector(resize(signed(offset_bits), 32));
end architecture;
