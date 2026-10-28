-- Verification-only: two read ports checked before and after each rising edge.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;

entity tb_regfile32 is
    generic (VECTOR_FILE : string := "regfile_vectors.txt"; EXPECTED_COUNT : natural := 0);
end entity;

architecture test of tb_regfile32 is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal we : std_logic := '0';
    signal waddr, raddr1, raddr2 : std_logic_vector(4 downto 0) := (others => '0');
    signal wdata, rdata1, rdata2, expected1, expected2 : std_logic_vector(31 downto 0) := (others => '0');
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
    dut : entity work.regfile32(rtl)
        port map (clk => clk, rst => rst, we => we, waddr => waddr, wdata => wdata,
                  raddr1 => raddr1, raddr2 => raddr2, rdata1 => rdata1, rdata2 => rdata2);

    watchdog : process
    begin
        wait until finished for 1 ms;
        assert finished report "REGFILE32_TIMEOUT" severity failure;
        wait;
    end process;

    stimulus : process
        file vectors : text;
        variable status : file_open_status;
        variable row : line;
        variable count : natural := 0;
        variable v_rst, v_we, v_waddr, v_raddr1, v_raddr2 : integer;
        variable v_wdata, before1, before2, after1, after2 : std_logic_vector(31 downto 0);

        procedure read_int(variable source : inout line; variable value : out integer) is
            variable good : boolean;
        begin
            read(source, value, good);
            assert good report "REGFILE32_BAD_INTEGER line=" & integer'image(count + 1) severity failure;
        end procedure;

        procedure read_word(variable source : inout line;
                            variable value : out std_logic_vector(31 downto 0)) is
            variable good : boolean;
        begin
            hread(source, value, good);
            assert good report "REGFILE32_BAD_WORD line=" & integer'image(count + 1) severity failure;
        end procedure;

        procedure check_ports(constant phase : in string;
                              constant first, second : in std_logic_vector(31 downto 0)) is
        begin
            assert rdata1 = first
                report "REGFILE32_MISMATCH cycle=" & integer'image(count) & " phase=" & phase &
                       " port=1 expected=" & hex32(first) & " actual=" & hex32(rdata1)
                severity failure;
            assert rdata2 = second
                report "REGFILE32_MISMATCH cycle=" & integer'image(count) & " phase=" & phase &
                       " port=2 expected=" & hex32(second) & " actual=" & hex32(rdata2)
                severity failure;
        end procedure;
    begin
        -- Startup connections may be unknown before upstream combinational
        -- logic settles. Expose X data, without converting an X address.
        raddr1 <= (others => 'X');
        raddr2 <= (others => 'U');
        for delta in 1 to 3 loop
            wait for 0 ns;
        end loop;
        assert rdata1 = (rdata1'range => 'X') and rdata2 = (rdata2'range => 'X')
            report "REGFILE32_UNKNOWN_ADDRESS_MISMATCH" severity failure;
        file_open(status, vectors, VECTOR_FILE, read_mode);
        assert status = open_ok report "REGFILE32_BAD_VECTOR_FILE" severity failure;
        while not endfile(vectors) loop
            readline(vectors, row);
            read_int(row, v_rst);
            read_int(row, v_we);
            read_int(row, v_waddr);
            read_word(row, v_wdata);
            read_int(row, v_raddr1);
            read_int(row, v_raddr2);
            read_word(row, before1);
            read_word(row, before2);
            read_word(row, after1);
            read_word(row, after2);
            assert (v_rst = 0 or v_rst = 1) and (v_we = 0 or v_we = 1) and
                   v_waddr >= 0 and v_waddr <= 31 and v_raddr1 >= 0 and v_raddr1 <= 31 and
                   v_raddr2 >= 0 and v_raddr2 <= 31
                report "REGFILE32_BAD_PORT_VALUE" severity failure;
            count := count + 1;
            test_index <= count;
            clk <= '0';
            if v_rst = 1 then rst <= '1'; else rst <= '0'; end if;
            if v_we = 1 then we <= '1'; else we <= '0'; end if;
            waddr <= std_logic_vector(to_unsigned(v_waddr, 5));
            wdata <= v_wdata;
            raddr1 <= std_logic_vector(to_unsigned(v_raddr1, 5));
            raddr2 <= std_logic_vector(to_unsigned(v_raddr2, 5));
            expected1 <= before1;
            expected2 <= before2;
            wait for 4 ns;
            check_ports("before", before1, before2);
            wait for 1 ns;
            clk <= '1';
            expected1 <= after1;
            expected2 <= after2;
            wait for 1 ns;
            check_ports("after", after1, after2);
            wait for 4 ns;
        end loop;
        file_close(vectors);
        assert count > 0 report "REGFILE32_EMPTY_VECTORS" severity failure;
        assert EXPECTED_COUNT = 0 or count = EXPECTED_COUNT
            report "REGFILE32_COUNT_MISMATCH" severity failure;
        clk <= '0';
        finished <= true;
        report "REGFILE32_PASS cycles=" & integer'image(count) &
               " value_checks=" & integer'image(count * 4) severity note;
        wait;
    end process;
end architecture;
