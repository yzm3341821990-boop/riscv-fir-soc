library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity mul32 is
    port (a, b : in std_logic_vector(31 downto 0);
          result : out std_logic_vector(31 downto 0));
end entity;

architecture rtl of mul32 is
    signal product : unsigned(63 downto 0);
begin
    -- Signed and unsigned multiplication have identical low 32 bits.
    product <= unsigned(a) * unsigned(b);
    result <= std_logic_vector(product(31 downto 0));
end architecture;
