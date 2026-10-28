library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;

entity tb_tiny_cpu is
    generic (
        PROGRAM_FILE : string := "cases/demo/program.hex";
        TRACE_FILE : string := "cases/demo/expected_trace.txt";
        MEMORY_TRACE_FILE : string := "cases/demo/expected_memory_trace.txt";
        INITIAL_MEMORY_FILE : string := "";
        EXPECTED_COUNT : natural := 3;
        EXPECT_FAULT : boolean := false;
        FAULT_PC : natural := 0;
        INJECT_RESET : boolean := false;
        RESET_DURING_LOAD : boolean := false
    );
end entity;

architecture test of tb_tiny_cpu is
    subtype word is std_logic_vector(31 downto 0);
    type rom_type is array(0 to 255) of word;
    impure function load_program(filename : string) return rom_type is
        file source : text;
        variable status : file_open_status;
        variable row : line;
        variable good : boolean;
        variable memory : rom_type := (others => x"00000013");
        variable value : word;
        variable count : natural := 0;
    begin
        file_open(status, source, filename, read_mode);
        assert status = open_ok report "TINYCPU_BAD_PROGRAM_FILE" severity failure;
        while not endfile(source) loop
            assert count < 256 report "TINYCPU_PROGRAM_TOO_LONG" severity failure;
            readline(source, row);
            hread(row, value, good);
            assert good report "TINYCPU_BAD_PROGRAM_WORD" severity failure;
            memory(count) := value;
            count := count + 1;
        end loop;
        file_close(source);
        assert count > 0 report "TINYCPU_EMPTY_PROGRAM" severity failure;
        return memory;
    end function;
    constant rom : rom_type := load_program(PROGRAM_FILE);
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal imem_addr, imem_rdata, debug_pc, debug_instruction : word := (others => '0');
    signal debug_next_pc : word;
    signal debug_state : std_logic_vector(2 downto 0);
    signal dmem_req, dmem_we : std_logic;
    signal dmem_be : std_logic_vector(3 downto 0);
    signal dmem_addr, dmem_wdata, dmem_rdata : word;
    signal boot_active, loader_req : std_logic := '0';
    signal loader_addr, loader_data : word := (others => '0');
    signal ram_req, ram_we : std_logic;
    signal ram_be : std_logic_vector(3 downto 0);
    signal ram_addr, ram_wdata : word;
    signal initial_memory_ready : boolean := INITIAL_MEMORY_FILE = "";
    signal debug_rs1, debug_rs2, debug_rd : std_logic_vector(4 downto 0);
    signal debug_rs1_data, debug_rs2_data, debug_imm, debug_alu_result : word;
    signal commit_valid, fault : std_logic;
    signal commit_pc, commit_instruction, commit_value : word;
    signal commit_rd : std_logic_vector(4 downto 0);
    signal retired_count : natural := 0;
    signal multiply_count : natural := 0;
    signal memory_request_count : natural := 0;
    signal finished : boolean := false;

    function hex32(value : word) return string is
        constant digits : string := "0123456789ABCDEF";
        variable result : string(1 to 8);
        variable nibble : std_logic_vector(3 downto 0);
    begin
        for i in 0 to 7 loop
            nibble := value(31 - i*4 downto 28 - i*4);
            case nibble is
                when "0000" | "0001" | "0010" | "0011" |
                     "0100" | "0101" | "0110" | "0111" |
                     "1000" | "1001" | "1010" | "1011" |
                     "1100" | "1101" | "1110" | "1111" =>
                    result(i + 1) := digits(to_integer(unsigned(nibble)) + 1);
                when others => result(i + 1) := 'X';
            end case;
        end loop;
        return result;
    end function;

    function is_load(instruction : word) return boolean is
    begin
        return instruction(6 downto 0) = "0000011" and
            (instruction(14 downto 12) = "000" or instruction(14 downto 12) = "001" or
             instruction(14 downto 12) = "010" or instruction(14 downto 12) = "100" or
             instruction(14 downto 12) = "101");
    end function;

    function is_store(instruction : word) return boolean is
    begin
        return instruction(6 downto 0) = "0100011" and
            (instruction(14 downto 12) = "000" or instruction(14 downto 12) = "001" or
             instruction(14 downto 12) = "010");
    end function;

    function instruction_at(pc : word) return word is
    begin
        -- This address comes from the expected trace, never from DUT outputs.
        assert pc(31 downto 10) = "0000000000000000000000" and pc(1 downto 0) = "00"
            report "TINYCPU_BAD_EXPECTED_PC" severity failure;
        return rom(to_integer(unsigned(pc(9 downto 2))));
    end function;
begin
    dut : entity work.tiny_cpu(rtl)
        port map (clk => clk, rst => rst, imem_addr => imem_addr, imem_rdata => imem_rdata,
            dmem_req => dmem_req, dmem_we => dmem_we, dmem_be => dmem_be, dmem_addr => dmem_addr,
            dmem_wdata => dmem_wdata, dmem_rdata => dmem_rdata,
            debug_pc => debug_pc, debug_next_pc => debug_next_pc,
            debug_instruction => debug_instruction, debug_state => debug_state,
            debug_rs1 => debug_rs1, debug_rs2 => debug_rs2, debug_rd => debug_rd,
            debug_rs1_data => debug_rs1_data, debug_rs2_data => debug_rs2_data,
            debug_imm => debug_imm, debug_alu_result => debug_alu_result,
            commit_valid => commit_valid, commit_pc => commit_pc, commit_instruction => commit_instruction,
            commit_value => commit_value, commit_rd => commit_rd, fault => fault);

    -- Testbench-only loader uses the actual RAM port while CPU reset is held.
    ram_req <= loader_req when boot_active = '1' else dmem_req;
    ram_we <= '1' when boot_active = '1' else dmem_we;
    ram_be <= "1111" when boot_active = '1' else dmem_be;
    ram_addr <= loader_addr when boot_active = '1' else dmem_addr;
    ram_wdata <= loader_data when boot_active = '1' else dmem_wdata;
    data_memory : entity work.data_ram(rtl)
        port map (clk => clk, req => ram_req, we => ram_we, byte_enable => ram_be,
                  addr => ram_addr, wdata => ram_wdata, rdata => dmem_rdata);

    synchronous_rom : process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                imem_rdata <= x"00000013";
            else
                assert imem_addr(31 downto 10) = "0000000000000000000000" and
                       imem_addr(1 downto 0) = "00"
                    report "TINYCPU_BAD_IMEM_ADDRESS" severity failure;
                imem_rdata <= rom(to_integer(unsigned(imem_addr(9 downto 2))));
            end if;
        end if;
    end process;

    stimulus : process
        file trace : text;
        file memory_trace : text;
        variable status : file_open_status;
        variable row : line;
        variable good : boolean;
        variable expected_pc, expected_instruction, expected_value, expected_next_pc : word;
        variable expected_current_pc : word := (others => '0');
        variable expected_rd : integer;
        variable count : natural := 0;
        variable warmup_count : natural := 0;
        variable multiplications : natural := 0;
        variable complete : boolean := false;
        variable stopped_pc : word;
        variable requests : natural := 0;
        variable warmup_requests : natural := 0;
        variable expect_memory_request : boolean := false;
        variable instruction_phase : natural := 0;
        variable duration : natural := 3;
        variable current_instruction : word;

        procedure open_memory_trace is
        begin
            file_open(status, memory_trace, MEMORY_TRACE_FILE, read_mode);
            assert status = open_ok report "TINYCPU_BAD_MEMORY_TRACE_FILE" severity failure;
        end procedure;

        procedure tick is
            variable memory_row : line;
            variable memory_good : boolean;
            variable mode : character;
            variable expected_address, expected_data : word;
            variable expected_be : std_logic_vector(3 downto 0);
            variable check_read_data : boolean := false;
        begin
            clk <= '0';
            wait for 5 ns;
            -- Sample accepted requests before the rising edge changes CPU state.
            -- This scoreboard uses its own trace file, independently of commits.
            check_read_data := false;
            if rst = '1' then
                assert dmem_req = '0' and dmem_be = "0000"
                    report "TINYCPU_MISMATCH memory_request_during_reset" severity failure;
            elsif expect_memory_request then
                assert dmem_req = '1' and not endfile(memory_trace)
                    report "TINYCPU_MISMATCH missing_memory_request" severity failure;
                readline(memory_trace, memory_row);
                read(memory_row, mode, memory_good);
                assert memory_good and (mode = 'R' or mode = 'W')
                    report "TINYCPU_BAD_MEMORY_TRACE_MODE" severity failure;
                hread(memory_row, expected_address, memory_good);
                assert memory_good report "TINYCPU_BAD_MEMORY_TRACE_ADDRESS" severity failure;
                hread(memory_row, expected_data, memory_good);
                assert memory_good report "TINYCPU_BAD_MEMORY_TRACE_DATA" severity failure;
                hread(memory_row, expected_be, memory_good);
                assert memory_good report "TINYCPU_BAD_MEMORY_TRACE_BE" severity failure;
                assert dmem_addr = expected_address and dmem_be = expected_be and
                       ((mode = 'R' and dmem_we = '0') or (mode = 'W' and dmem_we = '1'))
                    report "TINYCPU_MISMATCH memory_transaction expected_addr=" & hex32(expected_address) &
                           " actual_addr=" & hex32(dmem_addr) severity failure;
                if mode = 'W' then
                    assert dmem_wdata = expected_data
                        report "TINYCPU_MISMATCH memory_store_data expected=" & hex32(expected_data) &
                               " actual=" & hex32(dmem_wdata) severity failure;
                else
                    check_read_data := true;
                end if;
                requests := requests + 1;
                memory_request_count <= requests;
                report "TINYCPU_MEMORY_REQUEST mode=" & mode & " addr=" & hex32(expected_address) &
                       " data=" & hex32(expected_data) &
                       " be=" & integer'image(to_integer(unsigned(expected_be))) severity note;
            else
                assert dmem_req = '0' and dmem_be = "0000"
                    report "TINYCPU_MISMATCH unexpected_memory_request" severity failure;
            end if;
            clk <= '1';
            wait for 1 ns;
            if check_read_data then
                assert dmem_rdata = expected_data
                    report "TINYCPU_MISMATCH synchronous_read_data expected=" & hex32(expected_data) &
                           " actual=" & hex32(dmem_rdata) severity failure;
            end if;
        end procedure;

        procedure load_initial_memory is
            file source : text;
            variable source_status : file_open_status;
            variable source_row : line;
            variable source_good : boolean;
            variable value : word;
            variable index : natural := 0;
        begin
            if INITIAL_MEMORY_FILE /= "" then
                file_open(source_status, source, INITIAL_MEMORY_FILE, read_mode);
                assert source_status = open_ok report "TINYCPU_BAD_INITIAL_MEMORY_FILE" severity failure;
                boot_active <= '1';
                rst <= '1';
                while not endfile(source) loop
                    assert index < 256 report "TINYCPU_INITIAL_MEMORY_TOO_LONG" severity failure;
                    readline(source, source_row);
                    hread(source_row, value, source_good);
                    assert source_good report "TINYCPU_BAD_INITIAL_MEMORY_WORD" severity failure;
                    loader_req <= '1';
                    loader_addr <= std_logic_vector(to_unsigned(4*index, 32));
                    loader_data <= value;
                    tick;
                    assert commit_valid = '0' and fault = '0'
                        report "TINYCPU_MISMATCH cpu_active_during_loader" severity failure;
                    wait for 4 ns;
                    index := index + 1;
                end loop;
                file_close(source);
                assert index = 256 report "TINYCPU_INITIAL_MEMORY_TOO_SHORT" severity failure;
                loader_req <= '0';
                boot_active <= '0';
                initial_memory_ready <= true;
                report "TINYCPU_INITIAL_MEMORY_PASS words=256" severity note;
            end if;
        end procedure;

        procedure reset_core is
        begin
            rst <= '1';
            expected_current_pc := (others => '0');
            multiplications := 0;
            multiply_count <= 0;
            expect_memory_request := false;
            file_close(memory_trace);
            open_memory_trace;
            requests := 0;
            memory_request_count <= 0;
            for i in 1 to 2 loop
                tick;
                assert commit_valid = '0' and fault = '0' and debug_pc = x"00000000" and debug_state = "000"
                    report "TINYCPU_MISMATCH reset" severity failure;
                wait for 4 ns;
            end loop;
            rst <= '0';
        end procedure;

        procedure open_trace is
        begin
            file_open(status, trace, TRACE_FILE, read_mode);
            assert status = open_ok report "TINYCPU_BAD_TRACE_FILE" severity failure;
        end procedure;

        procedure check_commit is
        begin
            assert count < EXPECTED_COUNT and not endfile(trace)
                report "TINYCPU_MISMATCH unexpected_commit" severity failure;
            readline(trace, row);
            hread(row, expected_pc, good);
            assert good report "TINYCPU_BAD_TRACE_PC" severity failure;
            hread(row, expected_instruction, good);
            assert good report "TINYCPU_BAD_TRACE_INSTRUCTION" severity failure;
            read(row, expected_rd, good);
            assert good and expected_rd >= 0 and expected_rd <= 31
                report "TINYCPU_BAD_TRACE_RD" severity failure;
            hread(row, expected_value, good);
            assert good report "TINYCPU_BAD_TRACE_VALUE" severity failure;
            hread(row, expected_next_pc, good);
            assert good report "TINYCPU_BAD_TRACE_NEXT_PC" severity failure;
            assert expected_pc = expected_current_pc and expected_instruction = instruction_at(expected_current_pc)
                report "TINYCPU_BAD_TRACE_EXECUTION_PATH" severity failure;
            assert commit_valid = '1' and commit_pc = expected_pc and
                   commit_instruction = expected_instruction and
                   commit_rd = std_logic_vector(to_unsigned(expected_rd, 5)) and commit_value = expected_value
                report "TINYCPU_MISMATCH commit=" & integer'image(count + 1) &
                       " pc_expected=" & hex32(expected_pc) & " pc_actual=" & hex32(commit_pc) &
                       " value_expected=" & hex32(expected_value) & " value_actual=" & hex32(commit_value)
                severity failure;
            assert debug_pc = expected_next_pc
                report "TINYCPU_MISMATCH next_pc expected=" & hex32(expected_next_pc) &
                       " actual=" & hex32(debug_pc) severity failure;
            report "TINYCPU_COMMIT pc=" & hex32(commit_pc) &
                   " rd=" & integer'image(to_integer(unsigned(commit_rd))) &
                   " value=" & hex32(commit_value) & " next_pc=" & hex32(expected_next_pc) severity note;
            expected_current_pc := expected_next_pc;
            if commit_instruction(31 downto 25) = "0000001" and
               commit_instruction(14 downto 12) = "000" and commit_instruction(6 downto 0) = "0110011" then
                multiplications := multiplications + 1;
                multiply_count <= multiplications;
            end if;
            count := count + 1;
            retired_count <= count;
        end procedure;
    begin
        assert not RESET_DURING_LOAD or INJECT_RESET
            report "TINYCPU_BAD_LOAD_RESET_SCENARIO" severity failure;
        open_trace;
        open_memory_trace;
        load_initial_memory;
        reset_core;
        if INJECT_RESET then
            assert EXPECTED_COUNT >= 2 and not EXPECT_FAULT
                report "TINYCPU_BAD_RESET_SCENARIO" severity failure;
            -- Abort a fetch: assert reset before the 35 ns capture edge.
            tick;
            assert commit_valid = '0' report "TINYCPU_MISMATCH early_commit" severity failure;
            wait for 4 ns;
            reset_core;
            -- Make registers dirty, then abort the next fetch and start again.
            instruction_phase := 0;
            while count < 2 loop
                instruction_phase := instruction_phase + 1;
                current_instruction := instruction_at(expected_current_pc);
                if is_load(current_instruction) then duration := 4; else duration := 3; end if;
                expect_memory_request := instruction_phase = 3 and
                                         (is_load(current_instruction) or is_store(current_instruction));
                tick;
                assert fault = '0' report "TINYCPU_MISMATCH warmup_fault" severity failure;
                if instruction_phase = duration then
                    check_commit;
                    instruction_phase := 0;
                else
                    assert commit_valid = '0' report "TINYCPU_MISMATCH warmup_timing" severity failure;
                end if;
                wait for 4 ns;
            end loop;
            warmup_count := count;
            if RESET_DURING_LOAD then
                assert is_load(instruction_at(expected_current_pc))
                    report "TINYCPU_BAD_LOAD_RESET_SCENARIO" severity failure;
                -- Accept the next read, then reset before its writeback edge.
                for phase in 1 to 3 loop
                    expect_memory_request := phase = 3;
                    tick;
                    assert commit_valid = '0' and fault = '0'
                        report "TINYCPU_MISMATCH pending_load_committed_early" severity failure;
                    wait for 4 ns;
                end loop;
                assert debug_state = "011"
                    report "TINYCPU_MISMATCH pending_load_state" severity failure;
            else
                expect_memory_request := false;
                tick;
                assert commit_valid = '0' report "TINYCPU_MISMATCH early_commit" severity failure;
                wait for 4 ns;
            end if;
            warmup_requests := requests;
            reset_core;
            file_close(trace);
            open_trace;
            count := 0;
            retired_count <= 0;
        end if;
        instruction_phase := 0;
        for cycle in 1 to 8192 loop
            instruction_phase := instruction_phase + 1;
            current_instruction := instruction_at(expected_current_pc);
            -- A faulting instruction is rejected on EXECUTE, including LW faults.
            if count < EXPECTED_COUNT and is_load(current_instruction) then
                duration := 4;
            else
                duration := 3;
            end if;
            expect_memory_request := count < EXPECTED_COUNT and instruction_phase = 3 and
                                     (is_load(current_instruction) or is_store(current_instruction));
            tick;
            assert fault = '0' or fault = '1'
                report "TINYCPU_MISMATCH unknown_fault" severity failure;
            if instruction_phase /= duration then
                assert commit_valid = '0' report "TINYCPU_MISMATCH commit_timing" severity failure;
            end if;
            if commit_valid = '1' then
                check_commit;
            elsif instruction_phase = duration and count < EXPECTED_COUNT then
                assert false report "TINYCPU_MISMATCH missing_commit" severity failure;
            end if;
            assert debug_pc = expected_current_pc
                report "TINYCPU_MISMATCH pc expected=" & hex32(expected_current_pc) &
                       " actual=" & hex32(debug_pc) severity failure;
            if fault = '1' then
                assert EXPECT_FAULT and instruction_phase = 3 and count = EXPECTED_COUNT and commit_valid = '0' and
                       debug_pc = std_logic_vector(to_unsigned(FAULT_PC, 32)) and debug_state = "100" and
                       debug_instruction = rom(FAULT_PC / 4)
                    report "TINYCPU_MISMATCH fault_boundary" severity failure;
                stopped_pc := debug_pc;
                expect_memory_request := false;
                for hold_cycle in 1 to 2 loop
                    wait for 4 ns;
                    tick;
                    assert fault = '1' and debug_pc = stopped_pc and commit_valid = '0'
                        report "TINYCPU_MISMATCH fault_hold" severity failure;
                end loop;
                complete := true;
                exit;
            elsif count = EXPECTED_COUNT and not EXPECT_FAULT then
                complete := true;
                exit;
            end if;
            if instruction_phase = duration then instruction_phase := 0; end if;
            wait for 4 ns;
        end loop;
        assert complete report "TINYCPU_TIMEOUT" severity failure;
        assert endfile(trace) report "TINYCPU_UNUSED_EXPECTATIONS" severity failure;
        assert endfile(memory_trace) report "TINYCPU_UNUSED_MEMORY_EXPECTATIONS" severity failure;
        file_close(trace);
        file_close(memory_trace);
        clk <= '0';
        finished <= true;
        report "TINYCPU_PASS retired=" & integer'image(count) & " warmup=" & integer'image(warmup_count)
            severity note;
        report "TINYCPU_MEMORY_PASS requests=" & integer'image(requests) &
               " warmup_requests=" & integer'image(warmup_requests) severity note;
        report "TINYCPU_MULTIPLY_PASS operations=" & integer'image(multiplications) severity note;
        wait;
    end process;
end architecture;
