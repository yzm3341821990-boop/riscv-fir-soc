library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.alu_pkg.all;

entity alu32 is
    port (
        a, b   : in std_logic_vector(31 downto 0);
        alu_op : in std_logic_vector(3 downto 0);
        result : out std_logic_vector(31 downto 0)
    );
end entity;

architecture rtl of alu32 is
begin
    calculate : process(a, b, alu_op)
        variable value : std_logic_vector(31 downto 0);
        variable shift_amount : natural range 0 to 31;
    begin
        value := (others => '0');
        shift_amount := 0;
        case alu_op is
            when ALU_ADD =>
                value := std_logic_vector(unsigned(a) + unsigned(b));
            when ALU_SUB =>
                value := std_logic_vector(unsigned(a) - unsigned(b));
            when ALU_AND =>
                value := a and b;
            when ALU_OR =>
                value := a or b;
            when ALU_XOR =>
                value := a xor b;
            when ALU_SLL =>
                shift_amount := to_integer(unsigned(b(4 downto 0)));
                value := std_logic_vector(shift_left(unsigned(a), shift_amount));
            when ALU_SRL =>
                shift_amount := to_integer(unsigned(b(4 downto 0)));
                value := std_logic_vector(shift_right(unsigned(a), shift_amount));
            when ALU_SRA =>
                shift_amount := to_integer(unsigned(b(4 downto 0)));
                value := std_logic_vector(shift_right(signed(a), shift_amount));
            when ALU_SLT =>
                if signed(a) < signed(b) then
                    value(0) := '1';
                end if;
            when ALU_SLTU =>
                if unsigned(a) < unsigned(b) then
                    value(0) := '1';
                end if;
            when others =>
                null;
        end case;
        result <= value;
    end process;
end architecture;
