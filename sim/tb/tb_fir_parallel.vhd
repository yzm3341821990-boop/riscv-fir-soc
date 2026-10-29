library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;

entity tb_fir_parallel is
    generic (
        MAC_LANES : positive := 1;
        INPUT_FILE : string := "cases/software_fir/input.hex";
        COEFF_FILE : string := "cases/software_fir/coefficients.hex";
        OUTPUT_FILE : string := "cases/software_fir/expected.hex";
        ACC_FILE : string := "cases/software_fir/accumulators.hex";
        SAMPLE_COUNT : natural := 8;
        CHECK_PROTOCOL : boolean := false;
        USE_STALLS : boolean := true;
        STRESS_BUSY : boolean := true
    );
end entity;

architecture test of tb_fir_parallel is
    constant MAC_CYCLES : positive := 32 / MAC_LANES;
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal clear_valid, clear_ready, cfg_valid, cfg_ready : std_logic := '0';
    signal s_valid, s_ready, m_valid, m_ready, busy : std_logic := '0';
    signal cfg_addr : unsigned(4 downto 0) := (others => '0');
    signal cfg_data, s_data, m_data : signed(15 downto 0) := (others => '0');
    signal m_acc : signed(39 downto 0);
    signal finished : boolean := false;
    signal checked_samples : natural := 0;
    signal stalled_cycles : natural := 0;
    signal protocol_output_checks : natural := 0;
    signal output_index : natural := 0;
    type sample_array is array(natural range <>) of signed(15 downto 0);
    signal observed_y : sample_array(0 to 7) := (others => (others => '0'));
begin
    clk <= not clk after 5 ns when not finished else '0';
    dut : entity work.fir_serial
        generic map(MAC_LANES=>MAC_LANES)
        port map(clk, rst, clear_valid, clear_ready, cfg_valid, cfg_ready,
                 cfg_addr, cfg_data, s_valid, s_ready, s_data,
                 m_valid, m_ready, m_data, m_acc, busy);

    watchdog : process
    begin
        wait until finished for 1 ms;
        assert finished report "FIR_TIMEOUT" severity failure;
        wait;
    end process;

    stimulus : process
        file inputs : text open read_mode is INPUT_FILE;
        file coeffs : text open read_mode is COEFF_FILE;
        file outputs : text open read_mode is OUTPUT_FILE;
        file accs : text open read_mode is ACC_FILE;
        variable row : line;
        variable word : std_logic_vector(31 downto 0);
        variable acc_word : std_logic_vector(39 downto 0);
        variable coefficients : sample_array(0 to 31);
        variable x, y : signed(15 downto 0);
        variable a : signed(39 downto 0);
        variable pauses : natural;

        procedure tick is
        begin
            wait until rising_edge(clk);
            wait for 1 ns;
        end procedure;

        procedure idle_check is
        begin
            assert busy = '0' and m_valid = '0' and clear_ready = '1'
                and cfg_ready = '1' and s_ready = '1'
                report "FIR_IDLE_OR_GHOST_OUTPUT" severity failure;
        end procedure;

        procedure write_coefficient(address : natural; value : integer) is
        begin
            cfg_valid <= '1'; cfg_addr <= to_unsigned(address, 5);
            cfg_data <= to_signed(value, 16);
            wait for 1 ns;
            assert cfg_ready = '1' and s_ready = '0'
                report "FIR_CFG_PRIORITY" severity failure;
            tick;
            cfg_valid <= '0';
            wait for 1 ns;
        end procedure;

        procedure clear_history is
        begin
            clear_valid <= '1';
            wait for 1 ns;
            assert clear_ready = '1' and cfg_ready = '0' and s_ready = '0'
                report "FIR_CLEAR_PRIORITY" severity failure;
            tick;
            clear_valid <= '0';
            wait for 1 ns;
            assert busy = '0' and m_valid = '0'
                report "FIR_CLEAR_STATE" severity failure;
        end procedure;

        procedure check_sample(value : signed(15 downto 0);
                               expected_y : signed(15 downto 0);
                               expected_a : signed(39 downto 0);
                               stalls : natural; record_output : boolean) is
        begin
            idle_check;
            s_data <= value; s_valid <= '1'; m_ready <= '0';
            tick;
            s_valid <= '0';
            assert busy = '1' and s_ready = '0' and m_valid = '0'
                report "FIR_INPUT_ACCEPTANCE" severity failure;
            -- These single-cycle/held requests are deliberately NOT accepted.
            if STRESS_BUSY then
                clear_valid <= '1'; cfg_valid <= '1'; cfg_addr <= to_unsigned(0, 5);
                cfg_data <= to_signed(-32768, 16);
                s_valid <= '1'; s_data <= to_signed(-12345, 16);
            end if;
            for step in 1 to MAC_CYCLES loop
                assert clear_ready = '0' and cfg_ready = '0' and s_ready = '0'
                    report "FIR_BUSY_ACCEPTED_CONTROL" severity failure;
                tick;
                if step < MAC_CYCLES then
                    assert m_valid = '0' report "FIR_EARLY_RESULT" severity failure;
                else
                    assert m_valid = '1' report "FIR_PARALLEL_LATENCY" severity failure;
                end if;
            end loop;
            assert m_data = expected_y report "FIR_OUTPUT_MISMATCH index=" &
                integer'image(checked_samples) & " expected=" & integer'image(to_integer(expected_y)) &
                " actual=" & integer'image(to_integer(m_data)) severity failure;
            assert m_acc = expected_a report "FIR_RAW_ACC_MISMATCH index=" &
                integer'image(checked_samples) severity failure;
            for delay in 1 to stalls loop
                tick;
                assert m_valid = '1' and busy = '1' and m_data = expected_y
                    and m_acc = expected_a and s_ready = '0' and cfg_ready = '0'
                    and clear_ready = '0' report "FIR_STALLED_OUTPUT_CHANGED" severity failure;
                stalled_cycles <= stalled_cycles + 1;
            end loop;
            clear_valid <= '0'; cfg_valid <= '0'; s_valid <= '0';
            m_ready <= '1';
            tick;
            m_ready <= '0';
            idle_check;
            if record_output then
                if checked_samples < 8 then observed_y(checked_samples) <= m_data; end if;
                checked_samples <= checked_samples + 1;
            else
                protocol_output_checks <= protocol_output_checks + 1;
            end if;
            wait for 1 ns;
        end procedure;

        procedure reset_dut is
        begin
            rst <= '1'; clear_valid <= '1'; cfg_valid <= '1'; s_valid <= '1'; m_ready <= '1';
            wait for 1 ns;
            assert clear_ready = '0' and cfg_ready = '0' and s_ready = '0' and m_valid = '0'
                report "FIR_RESET_HANDSHAKE" severity failure;
            tick;
            assert busy = '0' and m_data = 0 and m_acc = 0
                report "FIR_RESET_STATE" severity failure;
            rst <= '0'; clear_valid <= '0'; cfg_valid <= '0'; s_valid <= '0'; m_ready <= '0';
            wait for 1 ns;
            idle_check;
        end procedure;
    begin
        tick; tick;
        rst <= '0'; wait for 1 ns;
        idle_check;
        if CHECK_PROTOCOL then
            -- All coefficient locations must reset, not only H[0].
            for k in 0 to 31 loop write_coefficient(k, 12345); end loop;
            reset_dut;
            for n in 0 to 31 loop
                check_sample(to_signed(32767,16), to_signed(0,16), to_signed(0,40), 0, false);
            end loop;
            for phase in 1 to 3 loop
                clear_history;
                write_coefficient(0, 16384);
                s_data <= to_signed(6,16); s_valid <= '1'; tick; s_valid <= '0';
                -- Reset before first, middle and final MAC edge.
                for n in 1 to (phase-1)*(MAC_CYCLES/2-1) + (phase/3) loop tick; end loop;
                reset_dut;
                for n in 1 to 35 loop tick; idle_check; end loop;
                check_sample(to_signed(7,16), to_signed(0,16), to_signed(0,40), 0, false);
            end loop;
            write_coefficient(0, 16384);
            s_data <= to_signed(6,16); s_valid <= '1'; tick; s_valid <= '0';
            for n in 1 to MAC_CYCLES loop tick; end loop;
            assert m_valid = '1' report "FIR_RESET_HOLD_SETUP" severity failure;
            reset_dut;
            for n in 1 to 35 loop tick; idle_check; end loop;
            check_sample(to_signed(7,16), to_signed(0,16), to_signed(0,40), 0, false);

            -- Clear wins over config and sample; rejected controls have no effect.
            write_coefficient(0, 16384); write_coefficient(1, 16384);
            clear_history;
            check_sample(to_signed(100,16), to_signed(50,16), to_signed(1638400,40), 3, false);
            cfg_valid <= '1'; cfg_addr <= to_unsigned(0,5); cfg_data <= to_signed(0,16);
            s_valid <= '1'; s_data <= to_signed(200,16);
            clear_history;
            cfg_valid <= '0'; s_valid <= '0'; wait for 1 ns;
            check_sample(to_signed(0,16), to_signed(0,16), to_signed(0,40), 0, false);
            check_sample(to_signed(100,16), to_signed(50,16), to_signed(1638400,40), 0, false);
            -- Configuration wins over sample and preserves history.
            cfg_valid <= '1'; cfg_addr <= to_unsigned(0,5); cfg_data <= to_signed(0,16);
            s_valid <= '1'; s_data <= to_signed(200,16); wait for 1 ns;
            assert s_ready = '0' and cfg_ready = '1' report "FIR_CFG_WITH_SAMPLE" severity failure;
            tick; cfg_valid <= '0'; s_valid <= '0'; wait for 1 ns;
            check_sample(to_signed(0,16), to_signed(50,16), to_signed(1638400,40), 0, false);
            for n in 1 to 35 loop tick; idle_check; end loop;

            -- Legal pending requests stay asserted until the ready edge.
            write_coefficient(0,16384); write_coefficient(1,0); clear_history;
            s_data <= to_signed(4,16); s_valid <= '1'; tick; s_valid <= '0';
            for n in 1 to MAC_CYCLES loop tick; end loop;
            assert m_valid = '1' and m_data = 2 report "FIR_PENDING_SETUP" severity failure;
            cfg_valid <= '1'; cfg_addr <= to_unsigned(0,5); cfg_data <= to_signed(8192,16);
            for n in 1 to 2 loop
                tick;
                assert cfg_ready = '0' and m_valid = '1' and m_data = 2
                    report "FIR_PENDING_CFG_STALL" severity failure;
            end loop;
            m_ready <= '1'; tick;
            assert cfg_ready = '1' and s_ready = '0' report "FIR_PENDING_CFG_READY" severity failure;
            m_ready <= '0'; tick; cfg_valid <= '0'; wait for 1 ns;
            protocol_output_checks <= protocol_output_checks + 1; wait for 1 ns;
            check_sample(to_signed(8,16),to_signed(2,16),to_signed(65536,40),0,false);

            clear_history; write_coefficient(0,16384);
            s_data <= to_signed(4,16); s_valid <= '1'; tick;
            -- Next input is held throughout MAC and output backpressure.
            s_data <= to_signed(8,16);
            for n in 1 to MAC_CYCLES loop tick; end loop;
            assert m_valid = '1' and m_data = 2 and s_ready = '0'
                report "FIR_PENDING_INPUT_STALL" severity failure;
            m_ready <= '1'; tick;
            assert s_ready = '1' report "FIR_PENDING_INPUT_READY" severity failure;
            tick; s_valid <= '0'; m_ready <= '0';
            for n in 1 to MAC_CYCLES loop tick; end loop;
            assert m_valid = '1' and m_data = 4 and m_acc = 131072
                report "FIR_PENDING_INPUT_LOST" severity failure;
            m_ready <= '1'; tick; m_ready <= '0'; idle_check;
            protocol_output_checks <= protocol_output_checks + 2; wait for 1 ns;
            reset_dut;
            report "FIR_PROTOCOL_PASS reset_points=5 priority=2 clear_preserves_coefficients=1 pending_requests=2" severity note;
        end if;

        for k in 0 to 31 loop
            assert not endfile(coeffs) report "FIR_MISSING_COEFFICIENT" severity failure;
            readline(coeffs,row); hread(row,word);
            assert signed(word) = resize(signed(word(15 downto 0)),32)
                report "FIR_BAD_COEFFICIENT_ENCODING" severity failure;
            coefficients(k) := signed(word(15 downto 0));
            write_coefficient(k,to_integer(coefficients(k)));
        end loop;
        assert endfile(coeffs) report "FIR_EXTRA_COEFFICIENT" severity failure;
        clear_history;
        for n in 0 to SAMPLE_COUNT-1 loop
            output_index <= n;
            assert not endfile(inputs) and not endfile(outputs) and not endfile(accs)
                report "FIR_MISSING_VECTOR" severity failure;
            readline(inputs,row); hread(row,word); x := signed(word(15 downto 0));
            assert signed(word) = resize(x,32) report "FIR_BAD_SAMPLE_ENCODING" severity failure;
            readline(outputs,row); hread(row,word); y := signed(word(15 downto 0));
            assert signed(word) = resize(y,32) report "FIR_BAD_OUTPUT_ENCODING" severity failure;
            readline(accs,row); hread(row,acc_word); a := signed(acc_word);
            pauses := 0;
            if USE_STALLS then pauses := n mod 4; end if;
            check_sample(x,y,a,pauses,true);
            if USE_STALLS then
                for gap in 1 to n mod 3 loop tick; idle_check; end loop;
            end if;
        end loop;
        assert endfile(inputs) and endfile(outputs) and endfile(accs)
            report "FIR_EXTRA_VECTOR" severity failure;
        for n in 1 to 35 loop tick; idle_check; end loop;
        assert checked_samples = SAMPLE_COUNT report "FIR_LOST_RESULT" severity failure;
        report "FIR_SERIAL_PASS samples=" & integer'image(checked_samples) &
            " stalls=" & integer'image(stalled_cycles) & " protocol_outputs=" &
            integer'image(protocol_output_checks) severity note;
        finished <= true;
        wait;
    end process;
end architecture;
