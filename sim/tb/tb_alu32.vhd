-- Verification-only VHDL-93: one vector per ns, with automatic assertions.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;

entity tb_alu32 is
    generic (
        VECTOR_FILE : string := "alu_vectors.txt";
        EXPECTED_COUNT : natural := 0
    );
end entity;

architecture test of tb_alu32 is
    signal a, b, result, expected : std_logic_vector(31 downto 0) := (others => '0');
    signal alu_op : std_logic_vector(3 downto 0) := (others => '0');
    signal test_index : natural := 0;
    signal finished : boolean := false;

    function hex32(value : std_logic_vector(31 downto 0)) return string is
        constant digits : string := "0123456789ABCDEF";
        variable text : string(1 to 8);
        variable nibble : std_logic_vector(3 downto 0);
    begin
        for i in 0 to 7 loop
            nibble := value(31 - 4*i downto 28 - 4*i);
            case nibble is
                when "0000" | "0001" | "0010" | "0011" |
                     "0100" | "0101" | "0110" | "0111" |
                     "1000" | "1001" | "1010" | "1011" |
                     "1100" | "1101" | "1110" | "1111" =>
                    text(i + 1) := digits(to_integer(unsigned(nibble)) + 1);
                when others => text(i + 1) := 'X';
            end case;
        end loop;
        return text;
    end function;
begin
    dut : entity work.alu32(rtl)
        port map (a => a, b => b, alu_op => alu_op, result => result);

    stimulus : process
        file vectors : text;
        variable status : file_open_status;
        variable row : line;
        variable v_op : std_logic_vector(3 downto 0);
        variable v_a, v_b, v_expected : std_logic_vector(31 downto 0);
        variable good : boolean;
        variable count : natural := 0;
    begin
        file_open(status, vectors, VECTOR_FILE, read_mode);
        assert status = open_ok report "ALU32_BAD_VECTOR_FILE" severity failure;
        while not endfile(vectors) loop
            readline(vectors, row);
            hread(row, v_op, good);
            assert good report "ALU32_BAD_OPCODE line=" & integer'image(count + 1) severity failure;
            hread(row, v_a, good);
            assert good report "ALU32_BAD_A line=" & integer'image(count + 1) severity failure;
            hread(row, v_b, good);
            assert good report "ALU32_BAD_B line=" & integer'image(count + 1) severity failure;
            hread(row, v_expected, good);
            assert good report "ALU32_BAD_EXPECTED line=" & integer'image(count + 1) severity failure;
            count := count + 1;
            test_index <= count;
            alu_op <= v_op;
            a <= v_a;
            b <= v_b;
            expected <= v_expected;
            wait for 1 ns;
            assert result = v_expected
                report "ALU32_MISMATCH vector=" & integer'image(count) &
                       " op=" & integer'image(to_integer(unsigned(v_op))) &
                       " a=" & hex32(v_a) & " b=" & hex32(v_b) &
                       " expected=" & hex32(v_expected) & " actual=" & hex32(result)
                severity failure;
        end loop;
        file_close(vectors);
        assert count > 0 report "ALU32_EMPTY_VECTORS" severity failure;
        assert EXPECTED_COUNT = 0 or count = EXPECTED_COUNT
            report "ALU32_COUNT_MISMATCH count=" & integer'image(count) severity failure;
        finished <= true;
        report "ALU32_PASS vectors=" & integer'image(count) severity note;
        wait;
    end process;
end architecture;
