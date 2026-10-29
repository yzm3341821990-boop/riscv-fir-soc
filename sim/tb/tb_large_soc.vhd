library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;
entity tb_large_soc is
    generic(PROGRAM_FILE : string := "program.hex"; INITIAL_FILE : string := "initial_memory.txt";
        TRACE_FILE : string := "trace.txt"; FINAL_FILE : string := "final-memory.txt";
        END_PC : natural := 416; FIR_LANES : positive := 4; STALL_DMA : boolean := false);
end entity;
architecture test of tb_large_soc is
    subtype word is std_logic_vector(31 downto 0);
    type bank_type is array(0 to 255) of word;
    impure function load_rom return bank_type is
        file f : text open read_mode is PROGRAM_FILE;variable row : line;
        variable result : bank_type := (others=>x"00000013");variable n : natural := 0;
    begin
        while not endfile(f) loop assert n<256 report "LARGE_ROM_OVERFLOW" severity failure;
            readline(f,row);hread(row,result(n));n:=n+1;end loop;return result;
    end;
    function hex(value : word) return string is
        constant digits : string := "0123456789ABCDEF";variable result : string(1 to 8);
    begin
        for k in 0 to 7 loop result(k+1):=digits(to_integer(unsigned(value(31-4*k downto 28-4*k)))+1);end loop;
        return result;
    end;
    constant rom : bank_type := load_rom;
    signal clk : std_logic := '0';signal rst,host_active : std_logic := '1';
    signal host_req,host_we : std_logic := '1';
    signal host_addr,host_wdata,host_rdata : word := (others=>'0');
    signal ia,ir,cp,ci,cv,cn,fp : word := (others=>'0');
    signal ie,commit_valid,fault,dma_allow : std_logic;
    signal rd : std_logic_vector(4 downto 0);
    signal cq,cw,dq,dw,dr : std_logic;signal cbe : std_logic_vector(3 downto 0);
    signal ca,cd,cr,da,dd,data_read : word;
    signal cycles : natural := 0;
    signal execution_done,begin_readback,finished : boolean := false;
begin
    -- The clock stops at CPU completion for Tcl to snapshot the actual RF,
    -- then resumes only for public host-port RAM readback.
    clk<=not clk after 5 ns when not finished and (not execution_done or begin_readback) else '0';
    dma_allow<='0' when STALL_DMA and cycles mod 7<3 else '1';
    dut : entity work.pipeline_large_soc generic map(FIR_LANES=>FIR_LANES)
        port map(clk=>clk,rst=>rst,host_active=>host_active,host_req=>host_req,
            host_addr=>host_addr,host_wdata=>host_wdata,host_we=>host_we,host_rdata=>host_rdata,
            dma_allow=>dma_allow,imem_addr=>ia,imem_rdata=>ir,imem_en=>ie,
            commit_valid=>commit_valid,commit_pc=>cp,commit_instruction=>ci,commit_value=>cv,commit_next_pc=>cn,
            commit_rd=>rd,fault=>fault,fault_pc=>fp,debug_stall=>open,debug_flush=>open,debug_valid=>open,
            trace_cpu_req=>cq,trace_cpu_we=>cw,trace_cpu_be=>cbe,trace_cpu_addr=>ca,trace_cpu_wdata=>cd,trace_cpu_rdata=>cr,
            trace_dma_req=>dq,trace_dma_we=>dw,trace_dma_ready=>dr,trace_dma_addr=>da,trace_dma_wdata=>dd,trace_dma_rdata=>data_read);
    fetch : process(clk)
    begin
        if rising_edge(clk) and ie='1' then
            assert unsigned(ia)<1024 and ia(1 downto 0)="00" report "LARGE_FETCH_RANGE" severity failure;
            ir<=rom(to_integer(unsigned(ia(9 downto 2))));
        end if;
    end process;
    counter : process(clk) begin if rising_edge(clk) then cycles<=cycles+1;end if;end process;
    watchdog : process begin wait until execution_done for 100 ms;
        assert execution_done report "LARGE_CPU_TIMEOUT" severity failure;
        wait until finished for 1 ms;assert finished report "LARGE_READBACK_TIMEOUT" severity failure;wait;end process;
    host : process
        file initial : text open read_mode is INITIAL_FILE;
        file final_memory : text open write_mode is FINAL_FILE;
        variable row : line;variable v : word;
        procedure tick is begin wait until rising_edge(clk);wait for 1 ns;end;
    begin
        for n in 0 to 8191 loop
            assert not endfile(initial) report "LARGE_SHORT_RAM_IMAGE" severity failure;
            readline(initial,row);hread(row,v);host_addr<=std_logic_vector(to_unsigned(4*n,32));host_wdata<=v;tick;
        end loop;
        assert endfile(initial) report "LARGE_EXTRA_RAM_IMAGE" severity failure;
        host_req<='0';host_active<='0';tick;rst<='0';
        wait until begin_readback;
        host_active<='1';host_req<='1';host_we<='0';
        for n in 0 to 8191 loop
            host_addr<=std_logic_vector(to_unsigned(4*n,32));tick;
            hwrite(row,host_rdata);writeline(final_memory,row);
        end loop;
        file_close(final_memory);host_req<='0';finished<=true;
        report "LARGE_RAM_READBACK_PASS words=8192" severity note;wait;
    end process;
    monitor : process
        file trace : text open write_mode is TRACE_FILE;
        variable row : line;variable active : boolean;
        variable aq,aw,bq,bw,br : std_logic;
        variable aa,ad,ba,bd : word;variable abe : std_logic_vector(3 downto 0);
        variable active_edges : natural := 0;
    begin
        wait until rising_edge(clk);
        active:=rst='0' and host_active='0' and not execution_done;
        aq:=cq;aw:=cw;aa:=ca;ad:=cd;abe:=cbe;
        bq:=dq;bw:=dw;ba:=da;bd:=dd;br:=dr;
        wait for 1 ns;
        if active then
            active_edges:=active_edges+1;
            assert fault='0' report "LARGE_CPU_FAULT" severity failure;
            if aq='1' then
                if aw='1' then write(row,string'("C W ")&hex(aa)&" "&hex(ad));
                else write(row,string'("C R ")&hex(aa)&" "&hex(cr));end if;
                write(row," "&hex(x"0000000"&abe)&" "&integer'image(cycles));writeline(trace,row);
            end if;
            if bq='1' and br='1' then
                if bw='1' then write(row,string'("D W ")&hex(ba)&" "&hex(bd));
                else write(row,string'("D R ")&hex(ba)&" "&hex(data_read));end if;
                write(row," "&integer'image(cycles));writeline(trace,row);
            end if;
            if commit_valid='1' then
                write(row,string'("I ")&hex(cp)&" "&hex(ci)&" "&integer'image(to_integer(unsigned(rd)))&" "&hex(cv)&" "&hex(cn)&" "&integer'image(cycles));
                writeline(trace,row);
                if unsigned(cn)=END_PC then
                    execution_done<=true;file_close(trace);
                    report "LARGE_EXECUTION_PASS edges="&integer'image(active_edges) severity note;
                end if;
            end if;
        end if;
    end process;
end architecture;
