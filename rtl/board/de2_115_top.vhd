library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.board_images_pkg.all;
entity de2_115_top is
    generic(HEARTBEAT_BIT : positive := 24);
    port(CLOCK_50,RESET_N : in std_logic; LEDR : out std_logic_vector(3 downto 0));
end entity;
architecture rtl of de2_115_top is
    subtype word is std_logic_vector(31 downto 0);
    type boot_state_type is (BOOT_WAIT, BOOT_WRITE, RUNNING);
    signal boot_state : boot_state_type := BOOT_WAIT;
    signal boot_index : unsigned(7 downto 0) := (others=>'0');
    signal boot_done : std_logic := '0';
    signal reset_pipe : std_logic_vector(1 downto 0) := "11";
    signal core_clock : std_logic := '0';
    attribute preserve : boolean;
    attribute preserve of reset_pipe : signal is true;
    attribute preserve of core_clock : signal is true;
    signal system_reset : std_logic := '1';
    signal host_active,host_req : std_logic;
    signal seed_q,host_addr,imem_addr,imem_data,pc : word;
    signal cpu_state : std_logic_vector(2 downto 0);
    signal cpu_fault,cpu_req,cpu_we : std_logic;
    signal cpu_be : std_logic_vector(3 downto 0);
    signal cpu_addr,cpu_wdata : word;
    signal dma_req,dma_we,dma_ready : std_logic;
    signal dma_addr,dma_wdata : word;
    signal halted,complete_latch,pass_latch,error_latch,c_done_seen : std_logic := '0';
    signal result_count : natural range 0 to 8 := 0;
    signal watchdog : unsigned(19 downto 0) := (others=>'0');
    signal heartbeat : unsigned(HEARTBEAT_BIT downto 0) := (others=>'0');
begin
    clock_divider : process(CLOCK_50)
    begin
        if rising_edge(CLOCK_50) then core_clock<=not core_clock; end if;
    end process;
    reset_synchronizer : process(core_clock,RESET_N)
    begin
        if RESET_N='0' then reset_pipe<="11";
        elsif rising_edge(core_clock) then reset_pipe<=reset_pipe(0)&'0'; end if;
    end process;
    system_reset<=reset_pipe(1) or not boot_done or error_latch;
    host_active<=not boot_done or halted;
    host_req<='1' when boot_state=BOOT_WRITE and reset_pipe(1)='0' else '0';
    host_addr<=std_logic_vector(shift_left(resize(boot_index,32),2));
    LEDR<=std_logic_vector'(heartbeat(HEARTBEAT_BIT)&error_latch&pass_latch&complete_latch);

    synchronous_roms : process(core_clock)
    begin
        if rising_edge(core_clock) then
            seed_q<=RAM_SEED_IMAGE(to_integer(boot_index));
            if system_reset='1' then imem_data<=x"00000013";
            else imem_data<=PROGRAM_IMAGE(to_integer(unsigned(imem_addr(9 downto 2)))); end if;
        end if;
    end process;
    boot_loader : process(core_clock)
    begin
        if rising_edge(core_clock) then
            if reset_pipe(1)='1' then
                boot_state<=BOOT_WAIT; boot_index<=(others=>'0'); boot_done<='0';
            else
                case boot_state is
                    when BOOT_WAIT => boot_state<=BOOT_WRITE;
                    when BOOT_WRITE =>
                        -- seed_q is the registered ROM word for this index.
                        if boot_index=255 then boot_done<='1'; boot_state<=RUNNING;
                        else boot_index<=boot_index+1; boot_state<=BOOT_WAIT; end if;
                    when RUNNING => null;
                end case;
            end if;
        end if;
    end process;
    soc : entity work.fir_soc
        port map(clk=>core_clock,rst=>system_reset,host_active=>host_active,host_req=>host_req,
            host_addr=>host_addr,host_wdata=>seed_q,dma_allow=>'1',imem_addr=>imem_addr,imem_rdata=>imem_data,
            debug_pc=>pc,debug_next_pc=>open,debug_state=>cpu_state,
            commit_valid=>open,commit_pc=>open,commit_instruction=>open,commit_value=>open,commit_rd=>open,fault=>cpu_fault,
            trace_cpu_req=>cpu_req,trace_cpu_we=>cpu_we,trace_cpu_be=>cpu_be,
            trace_cpu_addr=>cpu_addr,trace_cpu_wdata=>cpu_wdata,trace_cpu_rdata=>open,
            trace_dma_req=>dma_req,trace_dma_we=>dma_we,trace_dma_ready=>dma_ready,
            trace_dma_addr=>dma_addr,trace_dma_wdata=>dma_wdata,trace_dma_rdata=>open);

    self_check : process(core_clock)
        procedure fail_run is
        begin error_latch<='1'; complete_latch<='1'; pass_latch<='0'; halted<='1'; end;
    begin
        if rising_edge(core_clock) then
            if reset_pipe(1)='1' then
                heartbeat<=(others=>'0'); watchdog<=(others=>'0');
                halted<='0'; complete_latch<='0'; pass_latch<='0'; error_latch<='0';
                c_done_seen<='0'; result_count<=0;
            else
                heartbeat<=heartbeat+1;
                if boot_done='1' and halted='0' then
                    watchdog<=watchdog+1;
                    if cpu_fault='1' or watchdog=(watchdog'range=>'1') then fail_run; end if;
                    if cpu_req='1' and cpu_we='1' and cpu_be="1111" then
                        if unsigned(cpu_addr)=C_DONE_ADDRESS and cpu_wdata=x"00000001" then c_done_seen<='1'; end if;
                        if unsigned(cpu_addr)=C_ERRORS_ADDRESS and cpu_wdata/=x"00000000" then fail_run; end if;
                    end if;
                    if dma_req='1' and dma_ready='1' and dma_we='1' then
                        if result_count<8 then
                            if unsigned(dma_addr)/=OUTPUT_BASE+4*result_count or dma_wdata/=EXPECTED_Y(result_count) then fail_run;
                            else result_count<=result_count+1; end if;
                        else fail_run; end if;
                    end if;
                    if unsigned(pc)=PROGRAM_END and cpu_state="000" then
                        halted<='1'; complete_latch<='1';
                        if c_done_seen='1' and result_count=8 and error_latch='0' and cpu_fault='0' then pass_latch<='1';
                        else fail_run; end if;
                    end if;
                end if;
            end if;
        end if;
    end process;
end architecture;
