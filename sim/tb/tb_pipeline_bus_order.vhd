library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb_pipeline_bus_order is end entity;
architecture test of tb_pipeline_bus_order is
    subtype word is std_logic_vector(31 downto 0);
    type words is array(natural range <>) of word;
    type numbers is array(natural range <>) of natural;
    -- Alternate distinct RAM=13 and MMIO SRC_ADDR=77 on consecutive read cycles.
    constant program : words := (x"400030B7",x"04D00113",x"0020A423",x"00D00293",
        x"00502023",x"0080A183",x"00002203",x"0080A303",x"00002383",x"00338433",
        x"00802223",x"00402483",x"0080A503",x"00150593");
    constant expected_rd : numbers := (1,2,0,5,0,3,4,6,7,8,0,9,10,11);
    constant expected_value : words := (x"40003000",x"0000004D",x"00000000",x"0000000D",
        x"00000000",x"0000004D",x"0000000D",x"0000004D",x"0000000D",x"0000005A",
        x"00000000",x"0000005A",x"0000004D",x"0000004E");
    signal clk : std_logic := '0'; signal rst : std_logic := '1';
    signal ie,valid,fault,req,we : std_logic;
    signal ia,ir,pc,insn,value,next_pc : word := (others=>'0');
    signal rd : std_logic_vector(4 downto 0);
    signal requests : natural := 0;
    signal finished : boolean := false;
begin
    clk<=not clk after 5 ns when not finished else '0';
    dut : entity work.pipeline_fir_soc
        port map(clk=>clk,rst=>rst,host_active=>'0',host_req=>'0',host_addr=>(others=>'0'),host_wdata=>(others=>'0'),
            dma_allow=>'1',imem_addr=>ia,imem_rdata=>ir,imem_en=>ie,
            commit_valid=>valid,commit_pc=>pc,commit_instruction=>insn,commit_value=>value,commit_next_pc=>next_pc,
            commit_rd=>rd,fault=>fault,fault_pc=>open,debug_stall=>open,debug_flush=>open,debug_valid=>open,
            trace_cpu_req=>req,trace_cpu_we=>we,trace_cpu_be=>open,trace_cpu_addr=>open,trace_cpu_wdata=>open,
            trace_cpu_rdata=>open,trace_dma_req=>open,trace_dma_we=>open,trace_dma_ready=>open,
            trace_dma_addr=>open,trace_dma_wdata=>open,trace_dma_rdata=>open);
    rom : process(clk)
        variable index : natural;
    begin
        if rising_edge(clk) then
            if ie='1' then
                index:=to_integer(unsigned(ia(9 downto 2)));
                if index<program'length then ir<=program(index); else ir<=x"00000013"; end if;
            end if;
            if req='1' then requests<=requests+1; end if;
        end if;
    end process;
    check : process
        variable count : natural := 0;
    begin
        wait for 16 ns; rst<='0';
        for cycle in 1 to 50 loop
            wait until rising_edge(clk); wait for 1 ns;
            assert fault='0' report "PIPE_ORDER_CPU_FAULT" severity failure;
            if valid='1' then
                assert unsigned(pc)=4*count and insn=program(count) and
                    to_integer(unsigned(rd))=expected_rd(count) and value=expected_value(count) and
                    unsigned(next_pc)=4*(count+1)
                    report "PIPE_ORDER_RESPONSE_OR_FORWARDING index="&integer'image(count) severity failure;
                count:=count+1;
                if count=program'length then
                    assert requests=9 and cycle=20 report "PIPE_ORDER_COUNTS" severity failure;
                    finished<=true; exit;
                end if;
            end if;
            assert cycle<50 report "PIPE_ORDER_TIMEOUT" severity failure;
        end loop;
        report "PIPE_BUS_ORDER_PASS commits=14 requests=9 cycles=20" severity note; wait;
    end process;
end architecture;
