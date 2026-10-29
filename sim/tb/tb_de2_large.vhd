library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library modelsim_lib;
use modelsim_lib.util.all;
use work.large_board_images_pkg.all;
entity tb_de2_large is
    generic(EXPECT_C_ERROR : boolean := false; EXPECT_ERROR : boolean := false; FIR_LANES : positive := 4);
end entity;
architecture test of tb_de2_large is
    subtype word is std_logic_vector(31 downto 0);
    type segment_array is array(0 to 7) of std_logic_vector(6 downto 0);
    type pattern_array is array(0 to 15) of std_logic_vector(6 downto 0);
    -- Physical segment expectations: bit 0=a at top, bit 6=g in middle; active low.
    constant PATTERNS : pattern_array := ("1000000","1111001","0100100","0110000",
        "0011001","0010010","0000010","1111000","0000000","0010000",
        "0001000","0000011","1000110","0100001","0000110","0001110");
    type result_array is array(0 to 7) of word;
    constant RESULTS : result_array := (x"00000C58",x"FFFFF218",x"000009F7",x"00000F25",x"FFFFEEBC",x"FFFFFB0E",x"00002165",x"FFFFFDD1");
    signal clk : std_logic := '0';
    signal reset_n : std_logic := '1';
    signal switches : std_logic_vector(3 downto 0) := (others=>'0');
    signal leds : std_logic_vector(3 downto 0);
    signal segments : segment_array;
    signal nibble : std_logic_vector(3 downto 0) := (others=>'0');
    signal decoder_segments : std_logic_vector(6 downto 0);
    signal decoder_finished,finished : boolean := false;
    signal completed_runs : natural := 0;
    signal measured_cycles : natural := 0;
    signal observed_cpu_req,observed_cpu_we : std_logic := '0';
    signal observed_cpu_addr,observed_cpu_wdata : word := (others=>'0');
    signal c_error_seen : boolean := false;
    signal observed_commit : std_logic := '0';
    signal observed_next_pc : word := (others=>'0');
    function observed_word(s : segment_array) return word is
        variable result : word := (others=>'0');
        variable found : boolean;
    begin
        for digit in 0 to 7 loop
            found:=false;
            for value in 0 to 15 loop
                if s(digit)=PATTERNS(value) then
                    result(4*digit+3 downto 4*digit):=std_logic_vector(to_unsigned(value,4)); found:=true;
                end if;
            end loop;
            assert found report "LARGE_DISPLAY_INVALID_DIGIT" severity failure;
        end loop;
        return result;
    end;
begin
    -- Read-only ModelSim observation of the real CPU retirement boundary.
    -- Signature verified in this installation's vhdl_src/modelsim_lib/mti_util.vhd.
    terminal_spies : process
    begin
        init_signal_spy("/tb_de2_large/dut/commit_valid", "/tb_de2_large/observed_commit");
        init_signal_spy("/tb_de2_large/dut/commit_next_pc", "/tb_de2_large/observed_next_pc");
        init_signal_spy("/tb_de2_large/dut/cpu_req", "/tb_de2_large/observed_cpu_req");
        init_signal_spy("/tb_de2_large/dut/cpu_we", "/tb_de2_large/observed_cpu_we");
        init_signal_spy("/tb_de2_large/dut/cpu_addr", "/tb_de2_large/observed_cpu_addr");
        init_signal_spy("/tb_de2_large/dut/cpu_wdata", "/tb_de2_large/observed_cpu_wdata");
        wait;
    end process;
    terminal_monitor : process
        variable terminal_seen : boolean := false;
    begin
        wait until rising_edge(clk); wait for 2 ns;
        if reset_n='0' then terminal_seen:=false; c_error_seen<=false;
        else
            if observed_cpu_req='1' and observed_cpu_we='1' and unsigned(observed_cpu_addr)=C_ERRORS_ADDRESS and observed_cpu_wdata/=x"00000000" then c_error_seen<=true; end if;
            if observed_commit='1' and unsigned(observed_next_pc)=PROGRAM_END then terminal_seen:=true; end if;
            if leds(0)='1' and leds(2)='0' then
                assert terminal_seen report "LARGE_DISPLAY_FINISHED_BEFORE_TERMINAL_COMMIT" severity failure;
            end if;
        end if;
    end process;
    clk<=not clk after 10 ns when not finished else '0';
    dut : entity work.de2_115_large_top generic map(HEARTBEAT_BIT=>3,FIR_LANES=>FIR_LANES)
        port map(CLOCK_50=>clk,RESET_N=>reset_n,SW=>switches,LEDR=>leds,
            HEX0=>segments(0),HEX1=>segments(1),HEX2=>segments(2),HEX3=>segments(3),
            HEX4=>segments(4),HEX5=>segments(5),HEX6=>segments(6),HEX7=>segments(7));
    decoder : entity work.hex7seg port map(nibble=>nibble,segments=>decoder_segments);
    decoder_test : process
    begin
        for value in 0 to 15 loop
            nibble<=std_logic_vector(to_unsigned(value,4)); wait for 2 ns;
            assert decoder_segments=PATTERNS(value) report "LARGE_DISPLAY_SEGMENT_POLARITY_OR_ORDER" severity failure;
        end loop;
        nibble<="XXXX"; wait for 2 ns;
        assert decoder_segments="1111111" report "LARGE_DISPLAY_UNKNOWN_NOT_BLANK" severity failure;
        decoder_finished<=true; wait;
    end process;
    watchdog : process begin wait until finished for 20 ms;
        assert finished report "LARGE_DISPLAY_TIMEOUT" severity failure; wait; end process;
    stimulus : process
        variable first_count : word;
        variable heartbeat : std_logic;
        variable elapsed_ticks,expected_cycles : natural;
        procedure tick is begin wait until rising_edge(clk); wait for 1 ns; end;
        procedure settle is begin for n in 1 to 10 loop tick; end loop; end;
        procedure check_blank is
        begin
            for d in 0 to 7 loop
                assert segments(d)="1111111" report "LARGE_DISPLAY_RESET_OR_BUSY_NOT_BLANK" severity failure;
            end loop;
        end;
        procedure press_reset is
        begin
            reset_n<='0'; settle;
            assert leds(2 downto 0)="000" report "LARGE_DISPLAY_RESET_FLAGS" severity failure;
            check_blank; reset_n<='1'; tick;
        end;
        procedure finish_and_check is
        begin
            elapsed_ticks:=0;
            for timeout in 1 to 250000 loop
                tick;
                elapsed_ticks:=elapsed_ticks+1;
                assert leds(2)='0' report "LARGE_DISPLAY_SELFTEST_ERROR" severity failure;
                exit when leds(0)='1';
                if timeout mod 300=0 then check_blank; end if;
                assert timeout<250000 report "LARGE_DISPLAY_CPU_NOT_FINISHED" severity failure;
            end loop;
            assert leds(1)='1' report "LARGE_DISPLAY_SELFTEST_NOT_PASS" severity failure;
            for index in 0 to 7 loop
                switches<=std_logic_vector(to_unsigned(index,4)); settle;
                assert observed_word(segments)=RESULTS(index)
                    report "LARGE_DISPLAY_ACTUAL_RESULT_OR_DIGIT_ORDER index="&integer'image(index) severity failure;
            end loop;
            switches<="1000"; settle; first_count:=observed_word(segments);
            assert unsigned(first_count)>1000 and unsigned(first_count)<500000 report "LARGE_DISPLAY_CYCLE_RANGE" severity failure;
            if completed_runs=0 then
                -- Independent stopwatch from the external 50 MHz input: 2 reset
                -- core edges and 16384 loader edges precede the measured interval.
                expected_cycles:=(elapsed_ticks+1)/2-(2+2*8192);
                assert to_integer(unsigned(first_count))=expected_cycles
                    report "LARGE_DISPLAY_CYCLE_EDGE_BOUNDARY" severity failure;
                measured_cycles<=to_integer(unsigned(first_count));
            else assert to_integer(unsigned(first_count))=measured_cycles report "LARGE_DISPLAY_RESTART_COUNT_DIFFERS" severity failure;
            end if;
            for n in 1 to 100 loop tick; end loop;
            assert observed_word(segments)=first_count report "LARGE_DISPLAY_COUNTER_NOT_FROZEN" severity failure;
            switches<="1111"; settle;
            assert observed_word(segments)=first_count report "LARGE_DISPLAY_INDEX_ALTERS_CYCLE_MODE" severity failure;
            completed_runs<=completed_runs+1; wait for 1 ns;
        end;
    begin
        wait for 2 ns; check_blank;
        if EXPECT_ERROR then
            for timeout in 1 to 250000 loop
                tick; exit when leds(2)='1';
                assert timeout<250000 report "LARGE_DISPLAY_EXPECTED_ERROR_MISSING" severity failure;
            end loop;
            assert leds(2 downto 0)="101" report "LARGE_DISPLAY_ERROR_FLAGS" severity failure;
            settle;
            assert observed_word(segments)=x"EEEEEEEE" report "LARGE_DISPLAY_ERROR_WORD" severity failure;
            if EXPECT_C_ERROR then
                assert c_error_seen report "LARGE_DISPLAY_FULL_C_CHECK_MISSING" severity failure;
                report "LARGE_DISPLAY_C_DETECTED_LAST_OUTPUT_PASS" severity note;
            end if;
            press_reset; check_blank;
            completed_runs<=1;
            report "LARGE_DISPLAY_EXPECTED_ERROR_PASS" severity note;
            finished<=true; wait;
        end if;
        finish_and_check;
        heartbeat:=leds(3); for n in 1 to 16 loop tick; end loop;
        assert leds(3)/=heartbeat report "LARGE_DISPLAY_HEARTBEAT_STOPPED" severity failure;
        press_reset; finish_and_check;
        press_reset; for n in 1 to 30 loop tick; end loop;
        press_reset; finish_and_check;
        press_reset; for n in 1 to 33772 loop tick; end loop;
        assert leds(0)='0' report "LARGE_DISPLAY_ACTIVE_RESET_SETUP" severity failure;
        press_reset; finish_and_check;
        assert decoder_finished and completed_runs=4 report "LARGE_DISPLAY_CHECKS_INCOMPLETE" severity failure;
        report "LARGE_DISPLAY_PASS completed_runs=4 results_checked=32 program_cycles="&integer'image(measured_cycles) severity note;
        finished<=true; wait;
    end process;
end architecture;
