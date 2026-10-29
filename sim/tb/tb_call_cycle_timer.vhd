library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb_call_cycle_timer is end;
architecture test of tb_call_cycle_timer is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal start_event,stop_event,done,error : std_logic := '0';
    signal ticks : std_logic_vector(7 downto 0);
    signal finished : boolean := false;
begin
    clk<=not clk after 5 ns when not finished else '0';
    dut : entity work.call_cycle_timer generic map(COUNTER_WIDTH=>8)
        port map(clk,rst,start_event,stop_event,ticks,done,error);
    watchdog : process begin wait until finished for 20 us;
        assert finished report "CALL_TIMER_TIMEOUT" severity failure; wait; end process;
    stimulus : process
        procedure tick is begin wait until rising_edge(clk); wait for 1 ns; end;
        procedure reset_unit is
        begin rst<='1';start_event<='0';stop_event<='0';tick;rst<='0';tick;
            assert ticks=x"00" and done='0' and error='0' report "CALL_TIMER_RESET" severity failure;end;
        procedure begin_call is begin start_event<='1';tick;start_event<='0';end;
    begin
        tick;reset_unit;
        for i in 1 to 11 loop tick;end loop;
        assert ticks=x"00" report "CALL_TIMER_COUNTS_BEFORE_START" severity failure;
        begin_call;
        for i in 1 to 6 loop tick;end loop;
        stop_event<='1';tick;stop_event<='0';
        assert ticks=x"07" and done='1' and error='0' report "CALL_TIMER_EDGE_INTERVAL" severity failure;
        for i in 1 to 19 loop tick;end loop;
        assert ticks=x"07" and done='1' report "CALL_TIMER_NOT_FROZEN" severity failure;
        stop_event<='1';tick;stop_event<='0';
        assert error='1' report "CALL_TIMER_DUPLICATE_STOP" severity failure;
        reset_unit;stop_event<='1';tick;stop_event<='0';
        assert error='1' report "CALL_TIMER_STOP_WITHOUT_START" severity failure;
        reset_unit;start_event<='1';stop_event<='1';tick;
        assert error='1' report "CALL_TIMER_SIMULTANEOUS_MARKERS" severity failure;
        reset_unit;begin_call;start_event<='1';tick;start_event<='0';
        assert error='1' report "CALL_TIMER_DUPLICATE_START" severity failure;
        reset_unit;begin_call;for i in 1 to 13 loop tick;end loop;
        reset_unit;for i in 1 to 9 loop tick;end loop;
        assert ticks=x"00" and done='0' report "CALL_TIMER_CANCEL_GHOST_DONE" severity failure;
        begin_call;stop_event<='1';tick;stop_event<='0';
        assert ticks=x"01" and done='1' report "CALL_TIMER_MINIMUM_INTERVAL" severity failure;
        reset_unit;begin_call;for i in 1 to 256 loop tick;end loop;
        assert error='1' and done='0' report "CALL_TIMER_OVERFLOW_WRAPPED" severity failure;
        report "CALL_TIMER_PASS edge_interval=7 minimum=1 frozen=true overflow_rejected=true" severity note;
        finished<=true;wait;
    end process;
end architecture;
