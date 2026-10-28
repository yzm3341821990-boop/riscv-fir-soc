library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity imm_i is
    port (instruction : in std_logic_vector(31 downto 0);
          immediate : out std_logic_vector(31 downto 0));
end entity;

architecture rtl of imm_i is
begin
    immediate <= std_logic_vector(resize(signed(instruction(31 downto 20)), 32));
end architecture;
