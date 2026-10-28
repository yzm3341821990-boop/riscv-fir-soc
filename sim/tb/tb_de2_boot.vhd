library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb_de2_boot is end entity;
architecture test of tb_de2_boot is
    signal clk : std_logic := '0';
    signal reset_n : std_logic := '1';
    signal leds : std_logic_vector(3 downto 0);
    signal finished : boolean := false;
    signal completed_runs : natural := 0;
begin
    clk<=not clk after 10 ns when not finished else '0';
    dut : entity work.de2_115_top generic map(HEARTBEAT_BIT=>3)
        port map(CLOCK_50=>clk,RESET_N=>reset_n,LEDR=>leds);
    watchdog : process begin wait until finished for 1 ms;
        assert finished report "DE2_BOOT_TIMEOUT" severity failure; wait; end process;
    stimulus : process
        variable heartbeat : std_logic;
        procedure tick is begin wait until rising_edge(clk); wait for 1 ns; end;
        procedure press_reset is
        begin
            reset_n<='0'; tick; tick;
            assert leds(2 downto 0)="000" report "DE2_RESET_FLAGS" severity failure;
            reset_n<='1'; tick;
        end;
        procedure wait_pass is
        begin
            for timeout in 1 to 4000 loop
                tick;
                assert leds(2)='0' report "DE2_SELFTEST_REPORTED_ERROR" severity failure;
                exit when leds(0)='1';
                assert timeout<4000 report "DE2_PROGRAM_DID_NOT_COMPLETE" severity failure;
            end loop;
            assert leds(1)='1' report "DE2_RESULT_NOT_PASS" severity failure;
            for n in 1 to 20 loop tick;
                assert leds(2 downto 0)="011" report "DE2_RESULT_NOT_LATCHED" severity failure;
            end loop;
            completed_runs<=completed_runs+1; wait for 1 ns;
        end;
    begin
        -- No external reset pulse: power-up state itself must boot correctly.
        wait_pass;
        heartbeat:=leds(3); for n in 1 to 16 loop tick; end loop;
        assert leds(3)/=heartbeat report "DE2_HEARTBEAT_STOPPED" severity failure;
        press_reset; wait_pass;
        -- Reset while the initial RAM image is still being loaded.
        press_reset; for n in 1 to 30 loop tick; end loop;
        assert leds(0)='0' report "DE2_BOOT_RELEASED_EARLY" severity failure;
        press_reset; wait_pass;
        -- Interrupt a running task after RAM loading; then restart from its image.
        press_reset; for n in 1 to 2600 loop tick; end loop;
        assert leds(0)='0' report "DE2_ACTIVE_RESET_SETUP" severity failure;
        press_reset; wait_pass;
        assert completed_runs=4 report "DE2_RESTART_COUNT" severity failure;
        report "DE2_BOOT_PASS completed_runs=4 reset_phases=3" severity note;
        finished<=true; wait;
    end process;
end architecture;
