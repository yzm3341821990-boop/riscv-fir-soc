library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity imm_s is
    port (
        instruction : in std_logic_vector(31 downto 0);
        immediate : out std_logic_vector(31 downto 0)
    );
end entity;

architecture rtl of imm_s is
    signal offset_bits : std_logic_vector(11 downto 0);
begin
    offset_bits <= instruction(31 downto 25) & instruction(11 downto 7);
    immediate <= std_logic_vector(resize(signed(offset_bits), 32));
end architecture;
