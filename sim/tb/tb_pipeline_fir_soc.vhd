library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;
entity tb_pipeline_fir_soc is
    generic(PROGRAM_FILE : string := "program.hex"; INITIAL_FILE : string := "initial_memory.txt";
            END_PC : natural := 292; OUTPUT_ADDR : natural := 704; STALL_DMA : boolean := true;
            NEVER_READY : boolean := false; FIR_LANES : positive := 1);
end entity;
architecture test of tb_pipeline_fir_soc is
    subtype word is std_logic_vector(31 downto 0);
    type bank_type is array(0 to 255) of word;
    impure function load_rom return bank_type is
        file f : text open read_mode is PROGRAM_FILE; variable row : line;
        variable result : bank_type := (others=>x"00000013"); variable n : natural := 0;
    begin
        while not endfile(f) loop
            assert n<256 report "SOC_ROM_TOO_LONG" severity failure;
            readline(f,row); hread(row,result(n)); n:=n+1;
        end loop; return result;
    end;
    function hex(value : word) return string is
        constant digits : string := "0123456789ABCDEF"; variable result : string(1 to 8);
    begin
        for k in 0 to 7 loop result(k+1):=digits(to_integer(unsigned(value(31-4*k downto 28-4*k)))+1); end loop;
        return result;
    end;
    constant rom : bank_type := load_rom;
    signal clk : std_logic := '0'; signal rst,host_active : std_logic := '1';
    signal host_req : std_logic := '0'; signal host_addr,host_wdata : word := (others=>'0');
    signal imem_addr,imem_rdata,pc,next_pc,commit_pc,commit_instruction,commit_value : word;
    signal state : std_logic_vector(2 downto 0); signal commit_rd : std_logic_vector(4 downto 0);
    signal commit_valid,fault,dma_allow,imem_en : std_logic;
    signal cycles,retired_count : natural := 0;
    signal cpu_req,cpu_we,dma_req,dma_we,dma_ready : std_logic;
    signal cpu_be : std_logic_vector(3 downto 0);
    signal cpu_addr,cpu_wdata,cpu_rdata,dma_addr,dma_wdata,dma_rdata : word;
    signal cpu_requests,dma_reads,dma_writes : natural := 0;
    signal finished : boolean := false;
begin
    clk<=not clk after 5 ns when not finished else '0';
    dma_allow<='0' when NEVER_READY or (STALL_DMA and cycles mod 7<3) else '1';
    dut : entity work.pipeline_fir_soc
        generic map(FIR_LANES=>FIR_LANES)
        port map(clk=>clk,rst=>rst,host_active=>host_active,host_req=>host_req,host_addr=>host_addr,host_wdata=>host_wdata,
            dma_allow=>dma_allow,imem_addr=>imem_addr,imem_rdata=>imem_rdata,imem_en=>imem_en,
            commit_valid=>commit_valid,commit_pc=>commit_pc,commit_instruction=>commit_instruction,
            commit_value=>commit_value,commit_next_pc=>next_pc,commit_rd=>commit_rd,fault=>fault,fault_pc=>open,
            debug_stall=>open,debug_flush=>open,debug_valid=>open,
            trace_cpu_req=>cpu_req,trace_cpu_we=>cpu_we,trace_cpu_be=>cpu_be,
            trace_cpu_addr=>cpu_addr,trace_cpu_wdata=>cpu_wdata,trace_cpu_rdata=>cpu_rdata,
            trace_dma_req=>dma_req,trace_dma_we=>dma_we,trace_dma_ready=>dma_ready,
            trace_dma_addr=>dma_addr,trace_dma_wdata=>dma_wdata,trace_dma_rdata=>dma_rdata);
    instruction_memory : process(clk)
    begin
        if rising_edge(clk) and imem_en='1' then
            assert unsigned(imem_addr)<1024 and imem_addr(1 downto 0)="00" report "SOC_FETCH_RANGE" severity failure;
            imem_rdata<=rom(to_integer(unsigned(imem_addr(9 downto 2))));
        end if;
    end process;
    counter : process(clk) begin if rising_edge(clk) then cycles<=cycles+1; end if; end process;
    watchdog : process begin wait until finished for 1 ms;
        assert finished report "SOC_TIMEOUT" severity failure; wait; end process;
    stimulus : process
        file f : text open read_mode is INITIAL_FILE; variable row : line; variable v : word;
        procedure tick is begin wait until rising_edge(clk); wait for 1 ns; end;
    begin
        for n in 0 to 255 loop
            assert not endfile(f) report "SOC_SHORT_INITIAL_IMAGE" severity failure;
            readline(f,row); hread(row,v); host_addr<=std_logic_vector(to_unsigned(4*n,32)); host_wdata<=v; host_req<='1'; tick;
        end loop;
        assert endfile(f) report "SOC_EXTRA_INITIAL_IMAGE" severity failure;
        host_req<='0'; host_active<='0'; tick; rst<='0';
        wait;
    end process;
    -- Logging/checking at +1 ns avoids synchronous read and commit delta races.
    monitor : process
        variable active : boolean;
        variable sampled_next : word;
        variable aq,aw,bq,bw,br : std_logic;
        variable aa,ad,ba,bd : word; variable ab : std_logic_vector(3 downto 0);
        variable task_busy : boolean := false;
        variable source,dest,length : natural := 0;
        variable accepted_outputs : natural := 0;
        variable active_edges : natural := 0;
    begin
        wait until rising_edge(clk); active:=rst='0' and host_active='0'; sampled_next:=next_pc;
        aq:=cpu_req; aw:=cpu_we; aa:=cpu_addr; ad:=cpu_wdata; ab:=cpu_be;
        bq:=dma_req; bw:=dma_we; ba:=dma_addr; bd:=dma_wdata; br:=dma_ready;
        wait for 1 ns;
        if active then
            active_edges:=active_edges+1;
            assert fault='0' report "SOC_CPU_FAULT" severity failure;
            if aq='1' then
                cpu_requests<=cpu_requests+1;
                if aa(31 downto 12)=x"40003" and aw='1' then
                    case to_integer(unsigned(aa(11 downto 0))) is
                        when 8 => source:=to_integer(unsigned(ad));
                        when 12 => dest:=to_integer(unsigned(ad));
                        when 16 => length:=to_integer(unsigned(ad));
                        when 0 => if ad=x"00000001" then task_busy:=true; accepted_outputs:=0; end if;
                        when others => null;
                    end case;
                elsif task_busy and unsigned(aa)<1024 then
                    assert not ((unsigned(aa)>=source and unsigned(aa)<source+4*length) or
                                (unsigned(aa)>=dest and unsigned(aa)<dest+4*length))
                        report "SOC_CPU_ACCESSES_OWNED_BUFFER" severity failure;
                end if;
                if aw='1' then
                    report "SOC_BUS mode=W addr="&hex(aa)&" data="&hex(ad)&" be="&hex(x"0000000"&ab)&" cycle="&integer'image(cycles) severity note;
                else report "SOC_BUS mode=R addr="&hex(aa)&" data="&hex(cpu_rdata)&" be="&hex(x"0000000"&ab)&" cycle="&integer'image(cycles) severity note;
                end if;
            end if;
            if bq='1' and br='1' then
                assert not (aq='1' and aa(31 downto 10)="0000000000000000000000" and aa(9 downto 2)=ba(9 downto 2)
                    and (aw='1' or bw='1')) report "SOC_RAM_COLLISION" severity failure;
                if bw='1' then
                    report "SOC_DMA mode=W addr="&hex(ba)&" data="&hex(bd)&" cycle="&integer'image(cycles) severity note;
                    dma_writes<=dma_writes+1; accepted_outputs:=accepted_outputs+1;
                    if accepted_outputs=length then task_busy:=false; end if;
                else
                    report "SOC_DMA mode=R addr="&hex(ba)&" data="&hex(dma_rdata)&" cycle="&integer'image(cycles) severity note;
                    dma_reads<=dma_reads+1;
                end if;
            end if;
            if commit_valid='1' then
                report "SOC_COMMIT pc="&hex(commit_pc)&" insn="&hex(commit_instruction)&
                    " rd="&integer'image(to_integer(unsigned(commit_rd)))&" value="&hex(commit_value)&" next="&hex(next_pc) severity note;
                retired_count<=retired_count+1;
            end if;
            if commit_valid='1' and unsigned(next_pc)=END_PC then
                if NEVER_READY then
                    assert dma_reads=0 and dma_writes=0 report "SOC_TIMEOUT_DMA_COUNTS" severity failure;
                else assert dma_reads=8 and dma_writes=8 report "SOC_DMA_COUNTS" severity failure; end if;
                report "FIR_SOC_CPU_PASS" severity note;
                report "PIPE_EXECUTION_EDGES count="&integer'image(active_edges) severity note;
                finished<=true;
            end if;
        end if;
    end process;
end architecture;
