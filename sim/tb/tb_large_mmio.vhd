library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;

entity tb_large_mmio is
    generic (INPUT_FILE : string := "cases/demo/input.hex";
             COEFF_FILE : string := "cases/demo/coefficients.hex";
             OUTPUT_FILE : string := "cases/demo/expected.hex";
             SAMPLE_COUNT : positive := 8;
             CHECK_PROTOCOL : boolean := false; MAC_LANES : positive := 1);
end entity;
architecture test of tb_large_mmio is
    subtype word is std_logic_vector(31 downto 0);
    type bank_type is array(0 to 8191) of word;
    impure function load_bank return bank_type is
        file f : text open read_mode is INPUT_FILE;
        variable row : line; variable v : word;
        variable result : bank_type := (others => x"55555555");
    begin
        for n in 0 to SAMPLE_COUNT-1 loop readline(f,row); hread(row,v); result(n):=v; end loop;
        return result;
    end;
    signal bank : bank_type := load_bank;
    signal clk : std_logic := '0'; signal rst : std_logic := '1';
    signal req,we : std_logic := '0';
    signal addr,wdata,rdata : word := (others=>'0');
    signal be : std_logic_vector(3 downto 0) := "1111";
    signal dma_req,dma_we,dma_ready,dma_rvalid : std_logic := '0';
    signal dma_addr,dma_wdata,dma_rdata : word := (others=>'0');
    signal reads,writes,phase : natural := 0;
    signal force_wait, hold_writes : boolean := false;
    signal corrupt_input,restore_input : boolean := false;
    signal finished : boolean := false;
begin
    clk <= not clk after 5 ns when not finished else '0';
    dma_ready <= '0' when force_wait or (hold_writes and dma_we='1') or phase mod 5=0 else '1';
    dut : entity work.fir_mmio_large generic map(MAC_LANES=>MAC_LANES)
        port map(clk,rst,req,we,be,addr,wdata,rdata,
        dma_req,dma_we,dma_addr,dma_wdata,dma_ready,dma_rvalid,dma_rdata);
    ram : process(clk)
        variable previous_wait : boolean := false;
        variable held_addr,held_data : word; variable held_we : std_logic;
    begin
        if rising_edge(clk) then
            phase<=phase+1; dma_rvalid<='0';
            if corrupt_input then bank(0)<=x"00008000";
            elsif restore_input then bank(0)<=load_bank(0); end if;
            if rst='1' then previous_wait:=false;
            else
                if previous_wait then
                    assert dma_req='1' and dma_addr=held_addr and dma_wdata=held_data and dma_we=held_we
                        report "LARGE_MMIO_DMA_STALL_CHANGED" severity failure;
                end if;
                previous_wait:=dma_req='1' and dma_ready='0';
                held_addr:=dma_addr; held_data:=dma_wdata; held_we:=dma_we;
                if dma_req='1' and dma_ready='1' then
                    assert unsigned(dma_addr)<=32764 and dma_addr(1 downto 0)="00"
                        report "LARGE_MMIO_DMA_ADDRESS" severity failure;
                    if dma_we='1' then
                        bank(to_integer(unsigned(dma_addr(14 downto 2))))<=dma_wdata;
                        writes<=writes+1;
                    else
                        dma_rdata<=bank(to_integer(unsigned(dma_addr(14 downto 2))));
                        dma_rvalid<='1'; reads<=reads+1;
                    end if;
                end if;
            end if;
        end if;
    end process;
    watchdog : process begin wait until finished for 10 ms;
        assert finished report "LARGE_MMIO_TIMEOUT" severity failure; wait; end process;
    stimulus : process
        file cf : text open read_mode is COEFF_FILE;
        file yf : text open read_mode is OUTPUT_FILE;
        variable row : line; variable v,status : word;
        variable coefficients : bank_type;
        variable expected : bank_type := (others=>x"55555555");
        variable before_reads,before_writes : natural;
        procedure tick is begin wait until rising_edge(clk); wait for 1 ns; end;
        procedure write_reg(offset : natural; value : word) is
        begin req<='1'; we<='1'; addr<=std_logic_vector(to_unsigned(16#40003000#+offset,32)); wdata<=value;
            tick; req<='0'; we<='0'; tick; end;
        procedure read_reg(offset : natural; variable value : out word) is
        begin req<='1'; we<='0'; addr<=std_logic_vector(to_unsigned(16#40003000#+offset,32));
            tick; value:=rdata; req<='0'; tick; end;
        procedure expect_reg(offset : natural; value : word) is
            variable actual : word;
        begin read_reg(offset,actual); assert actual=value
            report "LARGE_MMIO_REGISTER_MISMATCH offset="&integer'image(offset) severity failure; end;
        procedure configure is
        begin
            for k in 0 to 31 loop write_reg(16#100#+4*k,coefficients(k)); end loop;
            write_reg(8,x"00000000"); write_reg(12,x"00004000");
            write_reg(16,std_logic_vector(to_unsigned(SAMPLE_COUNT,32)));
        end;
        procedure wait_done(expected_status : word; expected_count : natural := SAMPLE_COUNT) is
        begin
            for timeout in 0 to 200000 loop
                read_reg(4,status); exit when status(0)='0';
                assert timeout<200000 report "LARGE_MMIO_POLL_TIMEOUT" severity failure;
            end loop;
            assert status=expected_status report "LARGE_MMIO_BAD_FINAL_STATUS" severity failure;
            expect_reg(24,std_logic_vector(to_unsigned(expected_count,32)));
            read_reg(20,v); assert unsigned(v)>0 report "LARGE_MMIO_NO_CYCLES" severity failure;
        end;
        procedure check_outputs is
        begin
            for n in 0 to 8191 loop
                assert bank(n)=expected(n) report "LARGE_MMIO_RAM_MISMATCH word="&integer'image(n) severity failure;
            end loop;
        end;
        procedure expect_rejection(code : natural) is
        begin
            before_reads:=reads; before_writes:=writes;
            write_reg(0,x"00000001"); expect_reg(4,x"00000004");
            expect_reg(28,std_logic_vector(to_unsigned(code,32)));
            assert reads=before_reads and writes=before_writes report "LARGE_MMIO_REJECTED_TASK_DMA" severity failure;
            write_reg(0,x"00000002"); expect_reg(4,x"00000000");
        end;
        procedure reset_dut is
        begin rst<='1'; tick; assert dma_req='0' report "LARGE_MMIO_RESET_DMA" severity failure;
            rst<='0'; tick; expect_reg(4,x"00000000"); expect_reg(24,x"00000000"); end;
    begin
        tick; tick; rst<='0'; tick;
        for n in 0 to 8191 loop expected(n):=bank(n); end loop;
        for k in 0 to 31 loop readline(cf,row); hread(row,coefficients(k)); end loop;
        for n in 0 to SAMPLE_COUNT-1 loop readline(yf,row); hread(row,expected(4096+n)); end loop;
        if CHECK_PROTOCOL then
            write_reg(16,x"00000000"); expect_rejection(2);
            write_reg(16,x"00001001"); expect_rejection(2);
            write_reg(16,x"00000001"); write_reg(8,x"00000001"); expect_rejection(3);
            write_reg(8,x"FFFFFFFC"); expect_rejection(4);
            write_reg(8,x"00007FFC"); write_reg(16,x"00000002"); expect_rejection(4);
            write_reg(8,x"00000000"); write_reg(12,x"00000000"); expect_rejection(5);
            write_reg(12,x"00004000"); expect_rejection(6);
            for k in 0 to 30 loop write_reg(16#100#+4*k,coefficients(k)); end loop;
            expect_rejection(6);
            write_reg(16#100#,x"00008000"); expect_reg(28,x"00000007"); write_reg(0,x"00000002");
            be<="0011"; write_reg(8,x"00000010"); be<="1111";
            expect_reg(28,x"00000008"); write_reg(0,x"00000002");
            read_reg(32,v); assert v=x"00000000" report "LARGE_MMIO_UNKNOWN_READ" severity failure;
            expect_reg(28,x"00000008"); write_reg(0,x"00000002");
            write_reg(20,x"FFFFFFFF"); expect_reg(28,x"00000008"); write_reg(0,x"00000002");
            write_reg(0,x"00000003"); expect_reg(28,x"00000009"); write_reg(0,x"00000002");
        end if;
        configure;
        for repeat_job in 1 to 2 loop
            before_reads:=reads; before_writes:=writes;
            write_reg(0,x"00000001");
            if CHECK_PROTOCOL and repeat_job=1 then
                expect_reg(4,x"00000001");
                write_reg(8,x"00000004"); write_reg(16#100#,x"00000000");
                write_reg(0,x"00000002"); write_reg(0,x"00000001");
                expect_reg(8,x"00000000"); expect_reg(16#100#,coefficients(0));
                wait_done(x"00000006"); expect_reg(28,x"00000001");
            else wait_done(x"00000002"); end if;
            assert reads-before_reads=SAMPLE_COUNT and writes-before_writes=SAMPLE_COUNT
                report "LARGE_MMIO_DMA_COUNT" severity failure;
            check_outputs;
            write_reg(0,x"00000002"); expect_reg(4,x"00000000");
        end loop;
        if CHECK_PROTOCOL then
            -- A final blocked RAM write must keep BUSY=1 and DONE=0.
            write_reg(16,x"00000001"); hold_writes<=true;
            write_reg(0,x"00000001");
            for timeout in 0 to 100 loop
                tick; exit when dma_req='1' and dma_we='1';
                assert timeout<100 report "LARGE_MMIO_WRITE_WAIT_SETUP" severity failure;
            end loop;
            for n in 1 to 5 loop tick; end loop;
            expect_reg(4,x"00000001"); expect_reg(24,x"00000000");
            hold_writes<=false; wait_done(x"00000002",1);
            write_reg(0,x"00000002");
            write_reg(12,x"00007FFC"); write_reg(0,x"00000001"); wait_done(x"00000002",1);
            assert bank(8191)=expected(4096) report "LARGE_MMIO_LAST_RAM_WORD_WRITE" severity failure;
            write_reg(0,x"00000002"); write_reg(8,x"00007FFC"); write_reg(12,x"00003FFC");
            write_reg(0,x"00000001"); wait_done(x"00000002",1);
            assert bank(4095)=x"00001000" report "LARGE_MMIO_LAST_RAM_WORD_READ" severity failure;
            -- Restore the full-block expected count for following jobs.
            reset_dut; configure; force_wait<=true; before_writes:=writes;
            write_reg(0,x"00000001"); for n in 1 to 5 loop tick; end loop;
            reset_dut; force_wait<=false;
            for n in 1 to 45 loop tick; end loop;
            assert writes=before_writes report "LARGE_MMIO_RESET_GHOST_WRITE" severity failure;
            configure; write_reg(0,x"00000001");
            for n in 1 to 10 loop tick; end loop;
            before_writes:=writes; reset_dut;
            for n in 1 to 45 loop tick; end loop;
            assert writes=before_writes report "LARGE_MMIO_RESET_MAC_GHOST_WRITE" severity failure;
            configure; hold_writes<=true; write_reg(0,x"00000001");
            for timeout in 0 to 100 loop
                tick; exit when dma_req='1' and dma_we='1';
                assert timeout<100 report "LARGE_MMIO_RESET_WRITE_SETUP" severity failure;
            end loop;
            before_writes:=writes; reset_dut; hold_writes<=false;
            for n in 1 to 45 loop tick; end loop;
            assert writes=before_writes report "LARGE_MMIO_RESET_PENDING_WRITE" severity failure;
            configure; corrupt_input<=true; tick; corrupt_input<=false; tick;
            before_reads:=reads; before_writes:=writes; write_reg(0,x"00000001");
            for timeout in 0 to 40 loop
                read_reg(4,status); exit when status(0)='0';
                assert timeout<40 report "LARGE_MMIO_BAD_ENCODING_TIMEOUT" severity failure;
            end loop;
            assert status=x"00000004" and writes=before_writes and reads=before_reads+1
                report "LARGE_MMIO_BAD_ENCODING_SIDE_EFFECT" severity failure;
            expect_reg(28,x"00000007"); expect_reg(24,x"00000000");
            restore_input<=true; tick; restore_input<=false; tick;
            report "FIR_LARGE_MMIO_PROTOCOL_PASS" severity note;
        end if;
        report "FIR_LARGE_MMIO_PASS samples="&integer'image(SAMPLE_COUNT)&" jobs=2" severity note;
        finished<=true; wait;
    end process;
end architecture;
