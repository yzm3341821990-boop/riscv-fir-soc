library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library modelsim_lib;
use modelsim_lib.util.all;
use work.benchmark_images_pkg.all;
entity tb_de2_benchmark is
    generic(EXPECT_ERROR : boolean := false; CHECK_REFERENCES : boolean := true;
            SINGLE_RUN : boolean := false);
end entity;
architecture test of tb_de2_benchmark is
    subtype word is std_logic_vector(31 downto 0);
    type segment_array is array(0 to 7) of std_logic_vector(6 downto 0);
    type pattern_array is array(0 to 15) of std_logic_vector(6 downto 0);
    constant PATTERNS : pattern_array := ("1000000","1111001","0100100","0110000",
        "0011001","0010010","0000010","1111000","0000000","0010000",
        "0001000","0000011","1000110","0100001","0000110","0001110");
    -- Independently recorded complete-call intervals from step20 actual CPU traces.
    constant REFERENCES : natural_array(0 to 8) := (24045,1126,867,116856,3622,3363,489233,13608,13349);
    signal clk : std_logic := '0';
    signal reset_n : std_logic := '1';
    signal switches : std_logic_vector(3 downto 0) := (others=>'0');
    signal leds : std_logic_vector(3 downto 0);
    signal segments : segment_array;
    signal finished : boolean := false;
    signal completed_runs : natural := 0;
    signal intervals : natural_array(0 to 8) := (others=>0);
    signal measured_pairs,terminal_pairs : std_logic_vector(8 downto 0) := (others=>'0');
    signal observed_profile : natural range 0 to 8 := 0;
    signal observed_cpu_req,observed_cpu_we,observed_commit : std_logic := '0';
    signal observed_dma_req,observed_dma_we,observed_dma_ready : std_logic := '0';
    signal observed_cpu_addr,observed_cpu_wdata,observed_next_pc,observed_dma_addr : word := (others=>'0');
    signal observed_cpu_be : std_logic_vector(3 downto 0) := (others=>'0');
    signal c_error_seen : boolean := false;
    signal c_error_profile : natural := 0;
    function observed_word(s : segment_array) return word is
        variable result : word := (others=>'0');variable found : boolean;
    begin
        for digit in 0 to 7 loop
            found:=false;
            for value in 0 to 15 loop
                if s(digit)=PATTERNS(value) then result(4*digit+3 downto 4*digit):=std_logic_vector(to_unsigned(value,4));found:=true;end if;
            end loop;
            assert found report "BOARD_BENCH_INVALID_DIGIT" severity failure;
        end loop;
        return result;
    end;
begin
    clk<=not clk after 10 ns when not finished else '0';
    dut : entity work.de2_115_benchmark_top generic map(HEARTBEAT_BIT=>3)
        port map(CLOCK_50=>clk,RESET_N=>reset_n,SW=>switches,LEDR=>leds,
            HEX0=>segments(0),HEX1=>segments(1),HEX2=>segments(2),HEX3=>segments(3),
            HEX4=>segments(4),HEX5=>segments(5),HEX6=>segments(6),HEX7=>segments(7));
    spies : process
    begin
        init_signal_spy("/tb_de2_benchmark/dut/profile_index","/tb_de2_benchmark/observed_profile");
        init_signal_spy("/tb_de2_benchmark/dut/cpu_req","/tb_de2_benchmark/observed_cpu_req");
        init_signal_spy("/tb_de2_benchmark/dut/cpu_we","/tb_de2_benchmark/observed_cpu_we");
        init_signal_spy("/tb_de2_benchmark/dut/cpu_be","/tb_de2_benchmark/observed_cpu_be");
        init_signal_spy("/tb_de2_benchmark/dut/cpu_addr","/tb_de2_benchmark/observed_cpu_addr");
        init_signal_spy("/tb_de2_benchmark/dut/cpu_wdata","/tb_de2_benchmark/observed_cpu_wdata");
        init_signal_spy("/tb_de2_benchmark/dut/commit_valid","/tb_de2_benchmark/observed_commit");
        init_signal_spy("/tb_de2_benchmark/dut/commit_next_pc","/tb_de2_benchmark/observed_next_pc");
        init_signal_spy("/tb_de2_benchmark/dut/dma_req","/tb_de2_benchmark/observed_dma_req");
        init_signal_spy("/tb_de2_benchmark/dut/dma_we","/tb_de2_benchmark/observed_dma_we");
        init_signal_spy("/tb_de2_benchmark/dut/dma_ready","/tb_de2_benchmark/observed_dma_ready");
        init_signal_spy("/tb_de2_benchmark/dut/dma_addr","/tb_de2_benchmark/observed_dma_addr");
        wait;
    end process;
    -- Sample before the divider updates core_clock: requests here are precisely
    -- those accepted on the upcoming odd external input-clock edge.
    monitor : process(clk)
        type bool_array is array(0 to 8) of boolean;
        variable started,ended,retired : bool_array := (others=>false);
        variable beginnings,coefficients,writes : natural_array(0 to 8) := (others=>0);
        variable input_ticks : natural := 0;variable p,last_profile : natural := 0;
        procedure check_write(address : word) is
        begin
            assert started(p) and not ended(p) report "BOARD_BENCH_OUTPUT_OUTSIDE_MARKERS" severity failure;
            assert unsigned(address)=OUTPUT_BASES(p)+4*writes(p) report "BOARD_BENCH_OUTPUT_ORDER" severity failure;
            writes(p):=writes(p)+1;
        end;
    begin
        if rising_edge(clk) then
            input_ticks:=input_ticks+1;
            if reset_n='0' then
                started:=(others=>false);ended:=(others=>false);retired:=(others=>false);
                beginnings:=(others=>0);coefficients:=(others=>0);writes:=(others=>0);last_profile:=0;
                intervals<=(others=>0);measured_pairs<=(others=>'0');terminal_pairs<=(others=>'0');c_error_seen<=false;
            elsif input_ticks mod 2=1 then
                p:=observed_profile;
                if p/=last_profile then
                    assert p=last_profile+1 and retired(last_profile) report "BOARD_BENCH_ADVANCED_BEFORE_TERMINAL" severity failure;
                    last_profile:=p;
                end if;
                if observed_cpu_req='1' and observed_cpu_we='1' and observed_cpu_be="1111" then
                    if unsigned(observed_cpu_addr)=ERROR_ADDRS(p) and observed_cpu_wdata/=x"00000000" then c_error_seen<=true;c_error_profile<=p;end if;
                    if unsigned(observed_cpu_addr)=MARKER_ADDRS(p) then
                        if observed_cpu_wdata=x"00000001" then
                            assert not started(p) and not ended(p) report "BOARD_BENCH_START_ORDER" severity failure;
                            started(p):=true;beginnings(p):=input_ticks;
                        elsif observed_cpu_wdata=x"00000002" then
                            assert started(p) and not ended(p) report "BOARD_BENCH_END_ORDER" severity failure;
                            assert (input_ticks-beginnings(p)) mod 2=0 report "BOARD_BENCH_CORE_EDGE_PHASE" severity failure;
                            assert writes(p)=SAMPLE_COUNTS(p) report "BOARD_BENCH_MARKER_BEFORE_OUTPUTS" severity failure;
                            if p mod 3=0 then assert coefficients(p)=0 report "BOARD_BENCH_SOFTWARE_USED_MMIO" severity failure;
                            else assert coefficients(p)=32 report "BOARD_BENCH_COEFFICIENT_COUNT" severity failure;end if;
                            intervals(p)<=(input_ticks-beginnings(p))/2;measured_pairs(p)<='1';ended(p):=true;
                        else assert false report "BOARD_BENCH_UNKNOWN_MARKER" severity failure;end if;
                    elsif unsigned(observed_cpu_addr)>=16#40003100# and unsigned(observed_cpu_addr)<=16#4000317C# then
                        coefficients(p):=coefficients(p)+1;
                        if p mod 3=1 then assert started(p) and not ended(p) report "BOARD_BENCH_COLD_SETUP_OUTSIDE" severity failure;
                        elsif p mod 3=2 then assert not started(p) report "BOARD_BENCH_RESIDENT_SETUP_INSIDE" severity failure;
                        else assert false report "BOARD_BENCH_SOFTWARE_COEFFICIENT_MMIO" severity failure;end if;
                    elsif unsigned(observed_cpu_addr)>=OUTPUT_BASES(p) and unsigned(observed_cpu_addr)<OUTPUT_BASES(p)+4*SAMPLE_COUNTS(p) then
                        assert p mod 3=0 report "BOARD_BENCH_HARDWARE_CPU_OUTPUT_WRITE" severity failure;check_write(observed_cpu_addr);
                    end if;
                end if;
                if observed_dma_req='1' and observed_dma_ready='1' and observed_dma_we='1' then
                    assert p mod 3/=0 report "BOARD_BENCH_SOFTWARE_DMA" severity failure;check_write(observed_dma_addr);
                end if;
                if observed_commit='1' and unsigned(observed_next_pc)=PROGRAM_ENDS(p) then
                    assert started(p) and ended(p) and not retired(p) report "BOARD_BENCH_TERMINAL_WITHOUT_INTERVAL" severity failure;
                    retired(p):=true;terminal_pairs(p)<='1';
                end if;
            end if;
            if reset_n='1' and leds(0)='1' and leds(2)='0' then
                assert terminal_pairs="111111111" report "BOARD_BENCH_FINISHED_BEFORE_ALL_TERMINALS" severity failure;
            end if;
        end if;
    end process;
    watchdog : process begin wait until finished for 300 ms;
        assert finished report "BOARD_BENCH_TIMEOUT" severity failure;wait;end process;
    stimulus : process
        variable heartbeat : std_logic;variable saved : word;
        procedure tick is begin wait until rising_edge(clk);wait for 1 ns;end;
        procedure settle is begin for n in 1 to 10 loop tick;end loop;end;
        procedure check_blank is
        begin for n in 0 to 7 loop assert segments(n)="1111111" report "BOARD_BENCH_NOT_BLANK" severity failure;end loop;end;
        procedure press_reset is
        begin reset_n<='0';settle;assert leds(2 downto 0)="000" report "BOARD_BENCH_RESET_FLAGS" severity failure;
            check_blank;reset_n<='1';tick;end;
        procedure finish_and_check is
        begin
            for timeout in 1 to 3000000 loop
                tick;assert leds(2)='0' report "BOARD_BENCH_SELFTEST_ERROR" severity failure;
                exit when leds(0)='1';if timeout mod 1000=0 then check_blank;end if;
                assert timeout<3000000 report "BOARD_BENCH_NO_COMPLETION" severity failure;
            end loop;
            assert leds(1)='1' and measured_pairs="111111111" and terminal_pairs="111111111" report "BOARD_BENCH_NOT_ALL_PASSED" severity failure;
            for p in 0 to 8 loop
                switches<=std_logic_vector(to_unsigned(p,4));settle;
                assert to_integer(unsigned(observed_word(segments)))=intervals(p) report "BOARD_BENCH_EXTERNAL_STOPWATCH_DIFFERS" severity failure;
                if CHECK_REFERENCES then
                    assert intervals(p)=REFERENCES(p) report "BOARD_BENCH_MATCHED_REFERENCE_DIFFERS" severity failure;
                end if;
                report "BOARD_BENCH_MEASUREMENT index="&integer'image(p)&" cycles="&integer'image(intervals(p)) severity note;
            end loop;
            saved:=observed_word(segments);for n in 1 to 100 loop tick;end loop;
            assert observed_word(segments)=saved report "BOARD_BENCH_NOT_FROZEN" severity failure;
            for p in 9 to 15 loop switches<=std_logic_vector(to_unsigned(p,4));settle;check_blank;end loop;
            completed_runs<=completed_runs+1;wait for 1 ns;
        end;
    begin
        wait for 2 ns;check_blank;
        if EXPECT_ERROR then
            for timeout in 1 to 3000000 loop tick;exit when leds(2)='1';assert timeout<3000000 report "BOARD_BENCH_ERROR_NOT_DETECTED" severity failure;end loop;
            assert leds(2 downto 0)="101" and c_error_seen and c_error_profile=7 report "BOARD_BENCH_WRONG_ERROR_CAUSE" severity failure;
            switches<="1111";settle;assert observed_word(segments)=x"EEEEEEEE" report "BOARD_BENCH_ERROR_DISPLAY" severity failure;
            report "BOARD_BENCH_LAST_OUTPUT_ERROR_PASS profile=7 sample=1023" severity note;finished<=true;wait;
        end if;
        finish_and_check;
        if SINGLE_RUN then
            report "BOARD_BENCH_PASS completed_runs=1 measurements_checked=9" severity note;
            finished<=true;wait;
        end if;
        heartbeat:=leds(3);for n in 1 to 16 loop tick;end loop;assert leds(3)/=heartbeat report "BOARD_BENCH_HEARTBEAT_STOPPED" severity failure;
        press_reset;finish_and_check;
        press_reset;for n in 1 to 30 loop tick;end loop;press_reset;finish_and_check;
        press_reset;
        for timeout in 1 to 3000000 loop tick;exit when observed_profile=7 and observed_dma_req='1';assert timeout<3000000 report "BOARD_BENCH_DMA_RESET_SETUP" severity failure;end loop;
        assert leds(0)='0' report "BOARD_BENCH_DMA_RESET_ALREADY_DONE" severity failure;
        press_reset;finish_and_check;
        assert completed_runs=4 report "BOARD_BENCH_RUNS_MISSING" severity failure;
        report "BOARD_BENCH_PASS completed_runs=4 measurements_checked=36" severity note;
        finished<=true;wait;
    end process;
end architecture;
