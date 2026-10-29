library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;

entity tb_pipeline_cpu is
    generic (PROGRAM_FILE : string; TRACE_FILE : string; MEMORY_TRACE_FILE : string;
             INITIAL_MEMORY_FILE : string := ""; EXPECTED_COUNT : natural;
             EXPECT_FAULT : boolean := false; FAULT_PC : natural := 0;
             EXPECT_CYCLES : natural := 0; EXPECT_STALLS : integer := -1;
             RESET_AT_CYCLE : natural := 0);
end entity;

architecture test of tb_pipeline_cpu is
    subtype word is std_logic_vector(31 downto 0);
    type words is array(0 to 255) of word;
    impure function load_words(path : string; fill : word) return words is
        file f : text;
        variable s : file_open_status;
        variable row : line;
        variable result : words := (others => fill);
        variable good : boolean;
        variable i : natural := 0;
    begin
        if path /= "" then
            file_open(s, f, path, read_mode);
            assert s = open_ok report "PIPE_BAD_FILE " & path severity failure;
            while not endfile(f) loop
                assert i < 256 report "PIPE_FILE_TOO_LONG" severity failure;
                readline(f, row); hread(row, result(i), good);
                assert good report "PIPE_BAD_HEX" severity failure;
                i := i + 1;
            end loop;
            file_close(f);
        end if;
        return result;
    end function;
    constant rom : words := load_words(PROGRAM_FILE, x"00000013");
    constant initial : words := load_words(INITIAL_MEMORY_FILE, x"00000000");
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal imem_en, req, we, commit_valid, fault, stall, flush : std_logic;
    signal imem_addr, imem_data, addr, wdata, rdata : word := (others => '0');
    signal commit_pc, commit_instruction, commit_value, commit_next_pc, fault_address : word;
    signal rd : std_logic_vector(4 downto 0);
    signal be : std_logic_vector(3 downto 0);
    signal stages : std_logic_vector(3 downto 0);
    signal boot : std_logic := '1';
    signal loader_addr, loader_data : word := (others => '0');
    signal ram_req, ram_we : std_logic;
    signal ram_be : std_logic_vector(3 downto 0);
    signal ram_addr, ram_data : word;
    signal finished : boolean := false;
begin
    dut : entity work.pipeline_cpu(rtl)
        port map(clk => clk, rst => rst, imem_en => imem_en,
            imem_addr => imem_addr, imem_rdata => imem_data,
            dmem_req => req, dmem_we => we, dmem_be => be, dmem_addr => addr,
            dmem_wdata => wdata, dmem_rdata => rdata, commit_valid => commit_valid,
            commit_pc => commit_pc, commit_instruction => commit_instruction,
            commit_rd => rd, commit_value => commit_value, commit_next_pc => commit_next_pc,
            fault => fault, fault_pc => fault_address,
            debug_stall => stall, debug_flush => flush, debug_valid => stages);
    ram_req <= '1' when boot = '1' else req;
    ram_we <= '1' when boot = '1' else we;
    ram_be <= "1111" when boot = '1' else be;
    ram_addr <= loader_addr when boot = '1' else addr;
    ram_data <= loader_data when boot = '1' else wdata;
    data_memory : entity work.data_ram(rtl)
        port map(clk => clk, req => ram_req, we => ram_we, byte_enable => ram_be,
                 addr => ram_addr, wdata => ram_data, rdata => rdata);
    instruction_memory : process(clk)
    begin
        if rising_edge(clk) and imem_en = '1' then
            assert not is_x(imem_addr) and unsigned(imem_addr) < 1024 and imem_addr(1 downto 0) = "00"
                report "PIPE_BAD_IMEM_REQUEST" severity failure;
            imem_data <= rom(to_integer(unsigned(imem_addr(9 downto 2))));
        end if;
    end process;
    stimulus : process
        file tf, mf : text;
        variable status : file_open_status;
        variable row : line;
        variable good : boolean;
        variable epc, einst, eval, enext, ea, ed : word;
        variable erd : integer;
        variable eb : std_logic_vector(3 downto 0);
        variable mode : character;
        variable count, requests, cycles, stalls, flushes : natural := 0;
        variable check_read : boolean;
        procedure tick(checking : boolean) is
        begin
            clk <= '0'; wait for 5 ns;
            check_read := false;
            if rst = '1' then
                assert req = '0' and be = "0000" and imem_en = '0'
                    report "PIPE_RESET_REQUEST" severity failure;
            elsif checking then
                if stall = '1' then stalls := stalls + 1; end if;
                if flush = '1' then flushes := flushes + 1; end if;
                if req = '1' then
                    assert not endfile(mf) report "PIPE_EXTRA_MEMORY_REQUEST" severity failure;
                    readline(mf, row); read(row, mode, good);
                    assert good report "PIPE_BAD_MEMORY_MODE" severity failure;
                    hread(row, ea, good); assert good severity failure;
                    hread(row, ed, good); assert good severity failure;
                    hread(row, eb, good); assert good severity failure;
                    assert addr = ea and be = eb and
                           ((mode = 'W' and we = '1') or (mode = 'R' and we = '0'))
                        report "PIPE_MEMORY_MISMATCH" severity failure;
                    if we = '1' then
                        assert wdata = ed report "PIPE_STORE_DATA_MISMATCH" severity failure;
                    else check_read := true;
                    end if;
                    requests := requests + 1;
                else
                    assert be = "0000" and we = '0' report "PIPE_IDLE_MASK" severity failure;
                end if;
            end if;
            clk <= '1'; wait for 1 ns;
            if check_read then assert rdata = ed report "PIPE_LOAD_BUS_MISMATCH" severity failure; end if;
            if rst = '1' then
                assert commit_valid = '0' and fault = '0' and stages = "0000"
                    report "PIPE_RESET_STATE" severity failure;
            elsif checking and commit_valid = '1' then
                if count = 0 and EXPECT_CYCLES > 0 then
                    assert cycles = 5 report "PIPE_FIRST_COMMIT_TIMING" severity failure;
                end if;
                assert count < EXPECTED_COUNT and not endfile(tf)
                    report "PIPE_EXTRA_COMMIT" severity failure;
                readline(tf, row);
                hread(row, epc, good); assert good severity failure;
                hread(row, einst, good); assert good severity failure;
                read(row, erd, good); assert good severity failure;
                hread(row, eval, good); assert good severity failure;
                hread(row, enext, good); assert good severity failure;
                assert commit_pc = epc and commit_instruction = einst and
                       to_integer(unsigned(rd)) = erd and commit_value = eval and commit_next_pc = enext
                    report "PIPE_COMMIT_MISMATCH index=" & integer'image(count) &
                           " pc=" & integer'image(to_integer(unsigned(commit_pc))) severity failure;
                count := count + 1;
            end if;
            wait for 4 ns;
        end procedure;
        procedure reset is
        begin
            rst <= '1'; tick(false); tick(false); rst <= '0';
        end procedure;
    begin
        -- Initialize through the actual RAM port, independent of the CPU.
        for i in 0 to 255 loop
            loader_addr <= std_logic_vector(to_unsigned(4*i,32)); loader_data <= initial(i); tick(false);
        end loop;
        boot <= '0'; reset;
        if RESET_AT_CYCLE > 0 then
            for i in 1 to RESET_AT_CYCLE loop tick(false); end loop;
            reset;
            report "PIPE_RESET_IN_FLIGHT_PASS cycle=" & integer'image(RESET_AT_CYCLE) severity note;
        end if;
        file_open(status, tf, TRACE_FILE, read_mode); assert status = open_ok severity failure;
        file_open(status, mf, MEMORY_TRACE_FILE, read_mode); assert status = open_ok severity failure;
        for i in 1 to 100000 loop
            cycles := cycles + 1; tick(true);
            if fault = '1' then
                assert EXPECT_FAULT and count = EXPECTED_COUNT and
                       fault_address = std_logic_vector(to_unsigned(FAULT_PC,32))
                    report "PIPE_FAULT_MISMATCH" severity failure;
                for j in 1 to 4 loop
                    tick(false);
                    assert fault = '1' and commit_valid = '0' and req = '0' and imem_en = '0'
                        report "PIPE_FAULT_NOT_QUIET" severity failure;
                end loop;
                exit;
            end if;
            exit when not EXPECT_FAULT and count = EXPECTED_COUNT;
        end loop;
        assert count = EXPECTED_COUNT and (not EXPECT_FAULT or fault = '1') report "PIPE_TIMEOUT" severity failure;
        assert endfile(tf) and endfile(mf) report "PIPE_UNUSED_EXPECTATIONS" severity failure;
        if EXPECT_CYCLES > 0 then
            assert cycles = EXPECT_CYCLES report "PIPE_THROUGHPUT_MISMATCH" severity failure;
        end if;
        if EXPECT_STALLS >= 0 then
            assert stalls = EXPECT_STALLS report "PIPE_STALL_COUNT_MISMATCH" severity failure;
        end if;
        report "PIPE_PASS retired=" & integer'image(count) & " cycles=" & integer'image(cycles) &
               " requests=" & integer'image(requests) & " stalls=" & integer'image(stalls) &
               " flushes=" & integer'image(flushes) severity note;
        finished <= true; clk <= '0'; wait;
    end process;
end architecture;
