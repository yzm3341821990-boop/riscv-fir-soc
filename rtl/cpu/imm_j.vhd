library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity imm_j is
    port (
        instruction : in std_logic_vector(31 downto 0);
        immediate : out std_logic_vector(31 downto 0)
    );
end entity;

architecture rtl of imm_j is
    signal offset_bits : std_logic_vector(20 downto 0);
begin
    offset_bits <= instruction(31) & instruction(19 downto 12) & instruction(20) &
                   instruction(30 downto 21) & '0';
    immediate <= std_logic_vector(resize(signed(offset_bits), 32));
end architecture;
