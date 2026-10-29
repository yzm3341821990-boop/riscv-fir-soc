library ieee;
use ieee.std_logic_1164.all;
entity pipeline_large_soc is
    generic(FIR_LANES : positive := 1);
    port(clk,rst,host_active,host_req : in std_logic;
         host_addr,host_wdata : in std_logic_vector(31 downto 0);
         host_we : in std_logic; host_rdata : out std_logic_vector(31 downto 0);
         dma_allow : in std_logic;
         imem_addr : out std_logic_vector(31 downto 0);
         imem_rdata : in std_logic_vector(31 downto 0); imem_en : out std_logic;
         commit_valid : out std_logic;
         commit_pc,commit_instruction,commit_value,commit_next_pc : out std_logic_vector(31 downto 0);
         commit_rd : out std_logic_vector(4 downto 0); fault : out std_logic;
         fault_pc : out std_logic_vector(31 downto 0);
         debug_stall,debug_flush : out std_logic; debug_valid : out std_logic_vector(3 downto 0);
         trace_cpu_req,trace_cpu_we : out std_logic; trace_cpu_be : out std_logic_vector(3 downto 0);
         trace_cpu_addr,trace_cpu_wdata,trace_cpu_rdata : out std_logic_vector(31 downto 0);
         trace_dma_req,trace_dma_we,trace_dma_ready : out std_logic;
         trace_dma_addr,trace_dma_wdata,trace_dma_rdata : out std_logic_vector(31 downto 0));
end entity;
architecture rtl of pipeline_large_soc is
    signal cpu_rst,cpu_req,cpu_we,mmio_select,response_mmio,a_req,a_we : std_logic;
    signal cpu_be,a_be : std_logic_vector(3 downto 0);
    signal cpu_addr,cpu_wdata,cpu_rdata,mmio_rdata,a_addr,a_wdata,a_rdata : std_logic_vector(31 downto 0);
    signal dma_req,dma_we,dma_ready,dma_rvalid,mmio_req : std_logic;
    signal dma_addr,dma_wdata,dma_rdata : std_logic_vector(31 downto 0);
begin
    trace_cpu_req<=cpu_req; trace_cpu_we<=cpu_we; trace_cpu_be<=cpu_be;
    trace_cpu_addr<=cpu_addr; trace_cpu_wdata<=cpu_wdata; trace_cpu_rdata<=cpu_rdata;
    trace_dma_req<=dma_req; trace_dma_we<=dma_we; trace_dma_ready<=dma_ready;
    trace_dma_addr<=dma_addr; trace_dma_wdata<=dma_wdata; trace_dma_rdata<=dma_rdata;
    cpu_rst<=rst or host_active;
    processor : entity work.pipeline_large_cpu generic map(ENABLE_FIR_MMIO=>true)
        port map(clk=>clk,rst=>cpu_rst,imem_en=>imem_en,imem_addr=>imem_addr,imem_rdata=>imem_rdata,
            dmem_req=>cpu_req,dmem_we=>cpu_we,dmem_be=>cpu_be,dmem_addr=>cpu_addr,dmem_wdata=>cpu_wdata,dmem_rdata=>cpu_rdata,
            commit_valid=>commit_valid,commit_pc=>commit_pc,commit_instruction=>commit_instruction,
            commit_value=>commit_value,commit_next_pc=>commit_next_pc,commit_rd=>commit_rd,
            fault=>fault,fault_pc=>fault_pc,debug_stall=>debug_stall,debug_flush=>debug_flush,debug_valid=>debug_valid);
    mmio_select<='1' when cpu_addr(31 downto 12)=x"40003" else '0';
    mmio_req<=cpu_req and mmio_select;
    a_req<=host_req when host_active='1' else cpu_req and not mmio_select;
    a_we<=host_we when host_active='1' else cpu_we;
    a_be<="1111" when host_active='1' else cpu_be;
    a_addr<=host_addr when host_active='1' else cpu_addr;
    a_wdata<=host_wdata when host_active='1' else cpu_wdata;
    host_rdata<=a_rdata;
    cpu_rdata<=mmio_rdata when response_mmio='1' else a_rdata;
    response_select : process(clk)
    begin
        if rising_edge(clk) then
            if cpu_rst='1' then response_mmio<='0';
            elsif cpu_req='1' and cpu_we='0' then response_mmio<=mmio_select; end if;
        end if;
    end process;
    shared_memory : entity work.shared_ram_m9k port map(clk,rst,a_req,a_we,a_be,a_addr,a_wdata,a_rdata,
        dma_req,dma_we,dma_addr,dma_wdata,dma_allow,dma_ready,dma_rvalid,dma_rdata);
    accelerator : entity work.fir_mmio_large generic map(MAC_LANES=>FIR_LANES)
        port map(clk,rst,mmio_req,cpu_we,cpu_be,cpu_addr,cpu_wdata,mmio_rdata,
        dma_req,dma_we,dma_addr,dma_wdata,dma_ready,dma_rvalid,dma_rdata);
end architecture;
