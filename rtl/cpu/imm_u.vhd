library ieee;
use ieee.std_logic_1164.all;

entity imm_u is
    port (
        instruction : in std_logic_vector(31 downto 0);
        immediate : out std_logic_vector(31 downto 0)
    );
end entity;

architecture rtl of imm_u is
begin
    immediate <= instruction(31 downto 12) & x"000";
end architecture;
