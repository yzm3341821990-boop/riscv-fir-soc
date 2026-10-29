library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.benchmark_images_pkg.all;
entity de2_115_benchmark_top is
    generic(HEARTBEAT_BIT : positive := 24);
    port(CLOCK_50,RESET_N : in std_logic; SW : in std_logic_vector(3 downto 0);
         LEDR : out std_logic_vector(3 downto 0);
         HEX0,HEX1,HEX2,HEX3,HEX4,HEX5,HEX6,HEX7 : out std_logic_vector(6 downto 0));
end entity;
architecture rtl of de2_115_benchmark_top is
    subtype word is std_logic_vector(31 downto 0);
    type boot_state_type is (BOOT_WAIT,BOOT_WRITE,RUNNING);
    signal boot_state : boot_state_type := BOOT_WAIT;
    signal boot_index : unsigned(12 downto 0) := (others=>'0');
    signal profile_index : natural range 0 to 8 := 0;
    signal boot_done,job_finished : std_logic := '0';
    signal reset_pipe : std_logic_vector(1 downto 0) := "11";
    signal core_clock : std_logic := '0';
    signal sw_meta,sw_sync : std_logic_vector(3 downto 0) := (others=>'0');
    attribute preserve : boolean;
    attribute preserve of reset_pipe : signal is true;
    attribute preserve of core_clock : signal is true;
    attribute preserve of sw_meta : signal is true;
    attribute preserve of sw_sync : signal is true;
    signal system_reset : std_logic := '1';
    signal host_active,host_req : std_logic;
    signal seed_q,host_addr,imem_addr,imem_data : word;
    signal imem_en,commit_valid : std_logic;
    signal commit_next_pc : word;
    signal cpu_fault,cpu_req,cpu_we : std_logic;
    signal cpu_be : std_logic_vector(3 downto 0);
    signal cpu_addr,cpu_wdata : word;
    signal dma_req,dma_we,dma_ready : std_logic;
    signal dma_addr,dma_wdata : word;
    signal halted,complete_latch,pass_latch,error_latch,c_done_seen : std_logic := '0';
    signal result_count : natural range 0 to 1024 := 0;
    signal watchdog : unsigned(19 downto 0) := (others=>'0');
    signal heartbeat : unsigned(HEARTBEAT_BIT downto 0) := (others=>'0');
    signal marker_write,start_event,stop_event,timer_done,timer_error : std_logic;
    signal timer_ticks : word;
    type measurement_array is array(0 to 8) of word;
    signal measurements : measurement_array := (others=>(others=>'0'));
    type segment_array is array(0 to 7) of std_logic_vector(6 downto 0);
    signal digits : segment_array;
    signal display_word : word;
    signal display_enable : std_logic;
begin
    clock_divider : process(CLOCK_50)
    begin if rising_edge(CLOCK_50) then core_clock<=not core_clock;end if;end process;
    reset_synchronizer : process(core_clock,RESET_N)
    begin
        if RESET_N='0' then reset_pipe<="11";
        elsif rising_edge(core_clock) then reset_pipe<=reset_pipe(0)&'0';end if;
    end process;
    switch_synchronizer : process(core_clock)
    begin
        if rising_edge(core_clock) then
            if reset_pipe(1)='1' then sw_meta<=(others=>'0');sw_sync<=(others=>'0');
            else sw_meta<=SW;sw_sync<=sw_meta;end if;
        end if;
    end process;
    system_reset<=reset_pipe(1) or not boot_done or job_finished or error_latch;
    host_active<=not boot_done or job_finished or halted;
    host_req<='1' when boot_state=BOOT_WRITE and reset_pipe(1)='0' else '0';
    host_addr<=std_logic_vector(shift_left(resize(boot_index,32),2));
    LEDR<=std_logic_vector'(heartbeat(HEARTBEAT_BIT)&error_latch&pass_latch&complete_latch);
    marker_write<='1' when boot_done='1' and halted='0' and job_finished='0'
        and cpu_req='1' and cpu_we='1' and cpu_be="1111"
        and unsigned(cpu_addr)=MARKER_ADDRS(profile_index) else '0';
    start_event<='1' when marker_write='1' and cpu_wdata=x"00000001" else '0';
    stop_event<='1' when marker_write='1' and cpu_wdata=x"00000002" else '0';
    timer : entity work.call_cycle_timer port map(core_clock,system_reset,start_event,stop_event,timer_ticks,timer_done,timer_error);
    synchronous_roms : process(core_clock)
    begin
        if rising_edge(core_clock) then
            seed_q<=RAM_SEED_IMAGE(8192*(profile_index/3)+to_integer(boot_index));
            if system_reset='1' then imem_data<=x"00000013";
            elsif imem_en='1' then imem_data<=PROGRAM_IMAGE(256*profile_index+to_integer(unsigned(imem_addr(9 downto 2))));end if;
        end if;
    end process;
    boot_loader : process(core_clock)
    begin
        if rising_edge(core_clock) then
            if reset_pipe(1)='1' then
                boot_state<=BOOT_WAIT;boot_index<=(others=>'0');boot_done<='0';profile_index<=0;
            else
                case boot_state is
                    when BOOT_WAIT => boot_state<=BOOT_WRITE;
                    when BOOT_WRITE =>
                        if boot_index=8191 then boot_done<='1';boot_state<=RUNNING;
                        else boot_index<=boot_index+1;boot_state<=BOOT_WAIT;end if;
                    when RUNNING =>
                        if job_finished='1' and profile_index<8 then
                            profile_index<=profile_index+1;boot_index<=(others=>'0');boot_done<='0';boot_state<=BOOT_WAIT;
                        end if;
                end case;
            end if;
        end if;
    end process;
    soc : entity work.pipeline_large_soc generic map(FIR_LANES=>4)
        port map(clk=>core_clock,rst=>system_reset,host_active=>host_active,host_req=>host_req,
            host_addr=>host_addr,host_wdata=>seed_q,host_we=>'1',host_rdata=>open,dma_allow=>'1',
            imem_addr=>imem_addr,imem_rdata=>imem_data,imem_en=>imem_en,commit_next_pc=>commit_next_pc,fault_pc=>open,
            debug_stall=>open,debug_flush=>open,debug_valid=>open,
            commit_valid=>commit_valid,commit_pc=>open,commit_instruction=>open,commit_value=>open,commit_rd=>open,fault=>cpu_fault,
            trace_cpu_req=>cpu_req,trace_cpu_we=>cpu_we,trace_cpu_be=>cpu_be,trace_cpu_addr=>cpu_addr,
            trace_cpu_wdata=>cpu_wdata,trace_cpu_rdata=>open,trace_dma_req=>dma_req,trace_dma_we=>dma_we,
            trace_dma_ready=>dma_ready,trace_dma_addr=>dma_addr,trace_dma_wdata=>dma_wdata,trace_dma_rdata=>open);
    display_enable<=complete_latch and not reset_pipe(1) when error_latch='1' or unsigned(sw_sync)<9 else '0';
    display_word<=x"EEEEEEEE" when error_latch='1' else measurements(to_integer(unsigned(sw_sync))) when unsigned(sw_sync)<9 else (others=>'0');
    digit_decode : for n in 0 to 7 generate
        digit : entity work.hex7seg port map(nibble=>display_word(4*n+3 downto 4*n),segments=>digits(n));
    end generate;
    HEX0<=digits(0) when display_enable='1' else (others=>'1');
    HEX1<=digits(1) when display_enable='1' else (others=>'1');
    HEX2<=digits(2) when display_enable='1' else (others=>'1');
    HEX3<=digits(3) when display_enable='1' else (others=>'1');
    HEX4<=digits(4) when display_enable='1' else (others=>'1');
    HEX5<=digits(5) when display_enable='1' else (others=>'1');
    HEX6<=digits(6) when display_enable='1' else (others=>'1');
    HEX7<=digits(7) when display_enable='1' else (others=>'1');
    self_check : process(core_clock)
        procedure fail_run is
        begin error_latch<='1';complete_latch<='1';pass_latch<='0';halted<='1';end;
        procedure accept_output(address,data : word) is
        begin
            if result_count<SAMPLE_COUNTS(profile_index) then
                if unsigned(address)/=OUTPUT_BASES(profile_index)+4*result_count then fail_run;
                else
                    if result_count<8 then
                        if data/=EXPECTED_Y(result_count) then fail_run;end if;
                    end if;
                    result_count<=result_count+1;
                end if;
            else fail_run;end if;
        end;
    begin
        if rising_edge(core_clock) then
            if reset_pipe(1)='1' then
                heartbeat<=(others=>'0');watchdog<=(others=>'0');measurements<=(others=>(others=>'0'));
                halted<='0';complete_latch<='0';pass_latch<='0';error_latch<='0';
                c_done_seen<='0';result_count<=0;job_finished<='0';
            else
                heartbeat<=heartbeat+1;
                if job_finished='1' then
                    job_finished<='0';watchdog<=(others=>'0');result_count<=0;c_done_seen<='0';
                elsif boot_done='1' and halted='0' then
                    watchdog<=watchdog+1;
                    if cpu_fault='1' or timer_error='1' or watchdog=(watchdog'range=>'1') then fail_run;end if;
                    if marker_write='1' and cpu_wdata/=x"00000001" and cpu_wdata/=x"00000002" then fail_run;end if;
                    if cpu_req='1' and cpu_we='1' and cpu_be="1111" then
                        if unsigned(cpu_addr)=DONE_ADDRS(profile_index) and cpu_wdata=x"00000001" then c_done_seen<='1';end if;
                        if unsigned(cpu_addr)=ERROR_ADDRS(profile_index) and cpu_wdata/=x"00000000" then fail_run;end if;
                        if unsigned(cpu_addr)>=OUTPUT_BASES(profile_index) and unsigned(cpu_addr)<OUTPUT_BASES(profile_index)+4*SAMPLE_COUNTS(profile_index) then
                            if profile_index mod 3=0 then accept_output(cpu_addr,cpu_wdata);else fail_run;end if;
                        end if;
                    end if;
                    if dma_req='1' then
                        if profile_index mod 3=0 then fail_run;
                        elsif dma_ready='1' and dma_we='1' then accept_output(dma_addr,dma_wdata);end if;
                    end if;
                    if commit_valid='1' and unsigned(commit_next_pc)=PROGRAM_ENDS(profile_index) then
                        if c_done_seen='1' and result_count=SAMPLE_COUNTS(profile_index) and timer_done='1'
                            and timer_error='0' and error_latch='0' and cpu_fault='0' then
                            measurements(profile_index)<=timer_ticks;
                            if profile_index=8 then halted<='1';complete_latch<='1';pass_latch<='1';
                            else job_finished<='1';end if;
                        else fail_run;end if;
                    end if;
                end if;
            end if;
        end if;
    end process;
end architecture;
