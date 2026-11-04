library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity de2_115_dsp_core is
    generic(MAX_RUN_CYCLES : positive := 2000000000;HEARTBEAT_BIT : positive := 24);
    port(CLOCK_50,RESET_N : in std_logic;SW : in std_logic_vector(3 downto 0);
        LEDR : out std_logic_vector(3 downto 0);
        HEX0,HEX1,HEX2,HEX3,HEX4,HEX5,HEX6,HEX7 : out std_logic_vector(6 downto 0);
        JTAG_SOURCE : in std_logic_vector(319 downto 0);JTAG_PROBE : out std_logic_vector(319 downto 0);
        trace_valid : out std_logic;trace_pc,trace_instruction,trace_value,trace_next_pc : out std_logic_vector(31 downto 0);
        trace_rd : out std_logic_vector(4 downto 0);
        tap_clock,tap_reset,tap_req,tap_we : out std_logic;tap_be : out std_logic_vector(3 downto 0);
        tap_addr,tap_wdata,tap_rdata : out std_logic_vector(31 downto 0);
        tap_dma_req,tap_dma_we,tap_dma_ready : out std_logic;
        tap_dma_addr,tap_dma_wdata,tap_dma_rdata : out std_logic_vector(31 downto 0));
end;
architecture rtl of de2_115_dsp_core is
    subtype word is std_logic_vector(31 downto 0);
    type phases is (CLEAR_MEMORY,EMPTY_PROGRAM,LOADING,EXECUTING,FINISHED,FAILED);
    type transfers is (IDLE,WRITE_WORD,READ_ISSUE,READ_WAIT,READ_CAPTURE);
    signal code_req,code_we : std_logic;
    signal code_addr : std_logic_vector(11 downto 0);
    signal code_wdata,code_q : word;
    signal phase : phases := CLEAR_MEMORY;signal transfer : transfers := IDLE;
    signal core_clock : std_logic := '0';signal reset_pipe : std_logic_vector(1 downto 0) := "11";
    signal sw_meta,sw_sync : std_logic_vector(3 downto 0) := (others=>'0');
    attribute preserve : boolean;
    attribute preserve of core_clock,reset_pipe,sw_meta,sw_sync : signal is true;
    signal clear_index : natural range 0 to 8191 := 0;
    signal begin_pending,seq_valid : std_logic := '0';
    signal sequence : unsigned(15 downto 0) := (others=>'0');
    signal program_words : natural range 0 to 4095 := 0;
    signal uploaded_words : natural range 0 to 4095 := 0;
    signal transfer_code : std_logic := '0';
    signal transfer_base : natural range 0 to 8191 := 0;
    signal transfer_count : natural range 1 to 8 := 1;signal transfer_index : natural range 0 to 7 := 0;
    signal transfer_input,transfer_output : std_logic_vector(255 downto 0) := (others=>'0');
    signal cmd_valid,rsp_done : std_logic;
    signal cmd_op : std_logic_vector(2 downto 0);signal cmd_seq : std_logic_vector(15 downto 0);
    signal cmd_addr : std_logic_vector(12 downto 0);signal cmd_count : std_logic_vector(4 downto 0);
    signal cmd_data,rsp_data : std_logic_vector(255 downto 0) := (others=>'0');
    signal rsp_error,rsp_state,state_code : std_logic_vector(3 downto 0) := (others=>'0');
    signal cpu_reset,imem_en,cpu_req,cpu_we,cpu_fault,commit_valid : std_logic;
    signal imem_addr,imem_data,cpu_addr,cpu_wdata,cpu_rdata,commit_pc,commit_instruction,commit_value,commit_next_pc,fault_pc : word;
    signal cpu_be : std_logic_vector(3 downto 0);signal commit_rd : std_logic_vector(4 downto 0);
    signal a_req,a_we : std_logic;signal a_be : std_logic_vector(3 downto 0);
    signal a_addr,a_wdata,ram_q : word;
    signal run_cycles,retired,completed : unsigned(31 downto 0) := (others=>'0');
    signal retired_total : unsigned(63 downto 0) := (others=>'0');
    signal last_pc,last_instruction,return_value,failure_code,failure_pc : word := (others=>'0');
    signal cpu_trap : std_logic;
    signal cpu_trap_pc,cpu_trap_cause,cpu_trap_value : word;
    signal trap_count : unsigned(31 downto 0) := (others=>'0');
    signal last_trap_pc,last_trap_cause,last_trap_value : word := (others=>'0');
    signal timer_req,timer_level,read_timer : std_logic := '0';
    signal timer_q,fir_q,dma_addr,dma_wdata,dma_rdata : word;
    signal fir_req,read_fir,dma_req,dma_we,dma_ready,dma_rvalid,profile_req,profile_reset,dma_allow : std_logic := '0';
    signal profile_page : natural range 0 to 2 := 0;
    signal profile_data : std_logic_vector(255 downto 0);
    signal timer_now,timer_compare,saved_now : std_logic_vector(63 downto 0) := (others=>'0');
    signal saved_compare : std_logic_vector(63 downto 0) := (others=>'1');
    signal saved_pending : std_logic := '0';
    signal interrupt_count : unsigned(31 downto 0) := (others=>'0');
    type event_words is array(0 to 63) of word;
    signal events : event_words := (others=>(others=>'0'));
    signal event_count : natural range 0 to 16 := 0;
    signal event_overflow : std_logic := '0';
    function timer_address(a : word) return boolean is
    begin return a=x"02004000" or a=x"02004004" or a=x"0200BFF8" or a=x"0200BFFC";end function;
    signal heartbeat : unsigned(HEARTBEAT_BIT downto 0) := (others=>'0');
    signal display_word : word;signal display_enable : std_logic;
    type segments is array(0 to 7) of std_logic_vector(6 downto 0);signal digits : segments;
begin
    tap_clock<=core_clock;tap_reset<=cpu_reset;tap_req<=cpu_req;tap_we<=cpu_we;tap_be<=cpu_be;
    tap_addr<=cpu_addr;tap_wdata<=cpu_wdata;tap_rdata<=cpu_rdata;
    tap_dma_req<=dma_req;tap_dma_we<=dma_we;tap_dma_ready<=dma_ready;
    tap_dma_addr<=dma_addr;tap_dma_wdata<=dma_wdata;tap_dma_rdata<=dma_rdata;
    divider : process(CLOCK_50) begin if rising_edge(CLOCK_50) then core_clock<=not core_clock;end if;end process;
    reset_sync : process(core_clock,RESET_N) begin
        if RESET_N='0' then reset_pipe<="11";
        elsif rising_edge(core_clock) then reset_pipe<=reset_pipe(0)&'0';end if;
    end process;
    switches : process(core_clock) begin if rising_edge(core_clock) then
        if reset_pipe(1)='1' then sw_meta<=(others=>'0');sw_sync<=(others=>'0');
        else sw_meta<=SW;sw_sync<=sw_meta;end if;
    end if;end process;
    cpu_reset<='0' when phase=EXECUTING and reset_pipe(1)='0' else '1';
    state_code<=x"1" when phase=CLEAR_MEMORY else x"0" when phase=EMPTY_PROGRAM else
                x"2" when phase=LOADING else x"3" when phase=EXECUTING else x"4" when phase=FINISHED else x"5";
    mailbox : entity work.jtag_live_mailbox port map(core_clock,reset_pipe(1),JTAG_SOURCE,JTAG_PROBE,
        cmd_valid,cmd_op,cmd_seq,cmd_addr,cmd_count,cmd_data,rsp_done,rsp_error,rsp_state,rsp_data);
    processor : entity work.pipeline_dsp_cpu port map(clk=>core_clock,rst=>cpu_reset,imem_en=>imem_en,imem_addr=>imem_addr,imem_rdata=>imem_data,
        dmem_req=>cpu_req,dmem_we=>cpu_we,dmem_be=>cpu_be,dmem_addr=>cpu_addr,dmem_wdata=>cpu_wdata,dmem_rdata=>cpu_rdata,
        commit_valid=>commit_valid,commit_pc=>commit_pc,commit_instruction=>commit_instruction,commit_value=>commit_value,
        commit_next_pc=>commit_next_pc,commit_rd=>commit_rd,fault=>cpu_fault,fault_pc=>fault_pc,
        debug_stall=>open,debug_flush=>open,debug_valid=>open,trap_valid=>cpu_trap,trap_pc=>cpu_trap_pc,trap_cause=>cpu_trap_cause,trap_value=>cpu_trap_value,
        timer_irq=>timer_level,csr_event_valid=>open,csr_event_pc=>open,csr_event_address=>open,debug_m=>open);
    trace_valid<=commit_valid when phase=EXECUTING and reset_pipe(1)='0' else '0';
    trace_pc<=commit_pc;trace_instruction<=commit_instruction;trace_value<=commit_value;trace_next_pc<=commit_next_pc;trace_rd<=commit_rd;
    timer_req<='1' when phase=EXECUTING and cpu_req='1' and timer_address(cpu_addr) else '0';
    timer : entity work.machine_timer port map(core_clock,cpu_reset,timer_req,cpu_we,cpu_be,cpu_addr,cpu_wdata,
        timer_q,timer_level,timer_now,timer_compare);
    timer_read_select : process(core_clock) begin if rising_edge(core_clock) then
        if cpu_reset='1' then read_timer<='0';read_fir<='0';
        elsif cpu_req='1' then
            if cpu_addr(31 downto 12)=x"40003" then read_fir<='1';else read_fir<='0';end if;
            if timer_address(cpu_addr) then read_timer<='1';else read_timer<='0';end if;end if;
    end if;end process;
    cpu_rdata<=timer_q when read_timer='1' else fir_q when read_fir='1' else ram_q;
    fir_req<='1' when phase=EXECUTING and cpu_req='1' and cpu_addr(31 downto 12)=x"40003" else '0';
    accelerator : entity work.fir_mmio_large generic map(MAC_LANES=>4)
        port map(core_clock,cpu_reset,fir_req,cpu_we,cpu_be,cpu_addr,cpu_wdata,fir_q,
            dma_req,dma_we,dma_addr,dma_wdata,dma_ready,dma_rvalid,dma_rdata);
    profile_req<='1' when phase=EXECUTING and cpu_req='1' and cpu_addr=x"40004000" else '0';
    profile_page<=to_integer(unsigned(cmd_addr))-13 when unsigned(cmd_addr)>=13 and unsigned(cmd_addr)<=15 else 0;
    profile_reset<=reset_pipe(1) or begin_pending;
    profiler : entity work.dsp_profiler port map(core_clock,profile_reset,profile_req,cpu_we,cpu_be,cpu_wdata,profile_page,profile_data);
    ram_mux : process(phase,transfer,transfer_code,clear_index,transfer_base,transfer_index,transfer_input,
                      cpu_req,cpu_we,cpu_be,cpu_addr,cpu_wdata,reset_pipe)
    begin
        a_req<='0';a_we<='0';a_be<="1111";a_addr<=(others=>'0');a_wdata<=(others=>'0');
        if reset_pipe(1)='0' then
            if phase=EXECUTING then
                if unsigned(cpu_addr)<32768 or cpu_addr(31 downto 15)=std_logic_vector(to_unsigned(8192,17)) then a_req<=cpu_req;end if;
                a_we<=cpu_we;a_be<=cpu_be;a_addr<=(31 downto 15=>'0')&cpu_addr(14 downto 0);a_wdata<=cpu_wdata;
            elsif phase=CLEAR_MEMORY then a_req<='1';a_we<='1';a_addr<=std_logic_vector(to_unsigned(4*clear_index,32));
            elsif transfer=WRITE_WORD and transfer_code='0' then
                a_req<='1';a_we<='1';a_addr<=std_logic_vector(to_unsigned(4*(transfer_base+transfer_index),32));
                a_wdata<=transfer_input(32*transfer_index+31 downto 32*transfer_index);
            elsif transfer=READ_ISSUE and transfer_code='0' then
                a_req<='1';a_addr<=std_logic_vector(to_unsigned(4*(transfer_base+transfer_index),32));
            end if;
        end if;
    end process;
    dma_allow<=not cpu_reset;
    memory : entity work.shared_ram_m9k port map(core_clock,cpu_reset,a_req,a_we,a_be,a_addr,a_wdata,ram_q,
        dma_req,dma_we,dma_addr,dma_wdata,dma_allow,dma_ready,dma_rvalid,dma_rdata);
    code_mux : process(phase,transfer,transfer_code,clear_index,transfer_base,transfer_index,transfer_input,reset_pipe)
    begin
        code_req<='0';code_we<='0';code_addr<=(others=>'0');code_wdata<=(others=>'0');
        if reset_pipe(1)='0' then
            if phase=CLEAR_MEMORY and clear_index<4096 then
                code_req<='1';code_we<='1';code_addr<=std_logic_vector(to_unsigned(clear_index,12));code_wdata<=x"00000013";
            elsif transfer=WRITE_WORD and transfer_code='1' then
                code_req<='1';code_we<='1';code_addr<=std_logic_vector(to_unsigned(transfer_base+transfer_index,12));
                code_wdata<=transfer_input(32*transfer_index+31 downto 32*transfer_index);
            elsif transfer=READ_ISSUE and transfer_code='1' then
                code_req<='1';code_addr<=std_logic_vector(to_unsigned(transfer_base+transfer_index,12));
            end if;
        end if;
    end process;
    code_memory : entity work.instruction_ram16k_m9k port map(clk=>core_clock,rst=>reset_pipe(1),
        fetch_en=>imem_en,fetch_addr=>imem_addr(13 downto 2),fetch_data=>imem_data,
        host_req=>code_req,host_we=>code_we,host_addr=>code_addr,host_wdata=>code_wdata,host_rdata=>code_q);
    LEDR(0)<='1' when phase=EMPTY_PROGRAM or phase=LOADING or phase=FINISHED else '0';
    LEDR(1)<='1' when phase=FINISHED else '0';LEDR(2)<='1' when phase=FAILED else '0';LEDR(3)<=heartbeat(HEARTBEAT_BIT);
    with sw_sync select display_word<=std_logic_vector(completed) when "0000",std_logic_vector(run_cycles) when "0001",
        std_logic_vector(retired) when "0010",last_pc when "0011",last_instruction when "0100",
        return_value when "0101",failure_code when "0110",x"0000000"&state_code when "0111",
        std_logic_vector(trap_count) when "1000",last_trap_cause when "1001",last_trap_pc when "1010",last_trap_value when "1011",
        saved_now(31 downto 0) when "1100",std_logic_vector(interrupt_count) when "1101",
        std_logic_vector(to_unsigned(event_count,32)) when "1110",saved_compare(31 downto 0) when others;
    display_enable<='1' when reset_pipe(1)='0' else '0';
    decode : for i in 0 to 7 generate d : entity work.hex7seg port map(display_word(4*i+3 downto 4*i),digits(i));end generate;
    HEX0<=digits(0) when display_enable='1' else (others=>'1');HEX1<=digits(1) when display_enable='1' else (others=>'1');
    HEX2<=digits(2) when display_enable='1' else (others=>'1');HEX3<=digits(3) when display_enable='1' else (others=>'1');
    HEX4<=digits(4) when display_enable='1' else (others=>'1');HEX5<=digits(5) when display_enable='1' else (others=>'1');
    HEX6<=digits(6) when display_enable='1' else (others=>'1');HEX7<=digits(7) when display_enable='1' else (others=>'1');
    controller : process(core_clock)
        variable op,address,items : natural;variable page : std_logic_vector(255 downto 0);variable complete_code : boolean;
    begin
        if rising_edge(core_clock) then
            rsp_done<='0';
            if reset_pipe(1)='1' then
                phase<=CLEAR_MEMORY;clear_index<=0;begin_pending<='0';seq_valid<='0';sequence<=(others=>'0');program_words<=0;
                uploaded_words<=0;transfer<=IDLE;transfer_base<=0;transfer_count<=1;transfer_index<=0;transfer_code<='0';
                transfer_input<=(others=>'0');transfer_output<=(others=>'0');rsp_data<=(others=>'0');rsp_state<=x"1";rsp_error<=x"0";
                run_cycles<=(others=>'0');retired<=(others=>'0');retired_total<=(others=>'0');completed<=(others=>'0');
                last_pc<=(others=>'0');last_instruction<=(others=>'0');return_value<=(others=>'0');failure_code<=(others=>'0');failure_pc<=(others=>'0');heartbeat<=(others=>'0');
                trap_count<=(others=>'0');last_trap_pc<=(others=>'0');last_trap_cause<=(others=>'0');last_trap_value<=(others=>'0');
                events<=(others=>(others=>'0'));event_count<=0;event_overflow<='0';interrupt_count<=(others=>'0');
                saved_now<=(others=>'0');saved_compare<=(others=>'1');saved_pending<='0';
            else
                heartbeat<=heartbeat+1;
                if phase=CLEAR_MEMORY then
                    if clear_index=8191 then
                        if begin_pending='1' then phase<=LOADING;begin_pending<='0';rsp_done<='1';rsp_state<=x"2";
                        else phase<=EMPTY_PROGRAM;end if;
                    else clear_index<=clear_index+1;end if;
                elsif phase=EXECUTING then
                    run_cycles<=run_cycles+1;
                    saved_now<=timer_now;saved_compare<=timer_compare;saved_pending<=timer_level;
                    -- The CPU event was produced at the preceding edge: run_cycles
                    -- now equals that event's elapsed nonreset cycle number.
                    if cpu_trap='1' or (commit_valid='1' and commit_instruction=x"30200073") then
                        if event_count<16 then
                            events(4*event_count)<=std_logic_vector(run_cycles);
                            if cpu_trap='1' then
                                events(4*event_count+1)<=cpu_trap_pc;events(4*event_count+2)<=cpu_trap_cause;events(4*event_count+3)<=x"00000001";
                            else
                                events(4*event_count+1)<=commit_pc;events(4*event_count+2)<=commit_next_pc;events(4*event_count+3)<=x"00000002";
                            end if;
                            event_count<=event_count+1;
                        else event_overflow<='1';end if;
                    end if;
                    -- synthesis translate_off
                    assert not(cpu_trap='1' and commit_valid='1') report "CPU2_TRAP_NOT_DRAINED" severity failure;
                    -- synthesis translate_on
                    if cpu_trap='1' then
                        trap_count<=trap_count+1;
                        if cpu_trap_cause(31)='1' then interrupt_count<=interrupt_count+1;end if;last_trap_pc<=cpu_trap_pc;last_trap_cause<=cpu_trap_cause;last_trap_value<=cpu_trap_value;
                    end if;
                    if commit_valid='1' then
                        retired<=retired+1;retired_total<=retired_total+1;last_pc<=commit_pc;last_instruction<=commit_instruction;
                        if commit_rd="01010" then return_value<=commit_value;end if;
                    end if;
                    if cpu_fault='1' then phase<=FAILED;failure_code<=x"00000001";failure_pc<=fault_pc;
                    elsif commit_valid='1' and unsigned(commit_pc)>=4*program_words then
                        phase<=FAILED;failure_code<=x"00000003";failure_pc<=commit_pc;
                    elsif commit_valid='1' and unsigned(commit_next_pc)=4*program_words then phase<=FINISHED;completed<=completed+1;
                    elsif run_cycles=MAX_RUN_CYCLES-1 then phase<=FAILED;failure_code<=x"00000002";failure_pc<=imem_addr;end if;
                end if;
                case transfer is
                    when WRITE_WORD =>
                        if transfer_code='1' then uploaded_words<=uploaded_words+1;end if;
                        if transfer_index+1=transfer_count then transfer<=IDLE;rsp_done<='1';
                        else transfer_index<=transfer_index+1;end if;
                    when READ_ISSUE => transfer<=READ_WAIT;
                    when READ_WAIT => transfer<=READ_CAPTURE;
                    when READ_CAPTURE =>
                        page:=transfer_output;
                        if transfer_code='1' then page(32*transfer_index+31 downto 32*transfer_index):=code_q;
                        else page(32*transfer_index+31 downto 32*transfer_index):=ram_q;end if;
                        transfer_output<=page;
                        if transfer_index+1=transfer_count then rsp_data<=page;transfer<=IDLE;rsp_done<='1';
                        else transfer_index<=transfer_index+1;transfer<=READ_ISSUE;end if;
                    when IDLE =>
                        if cmd_valid='1' then
                            op:=to_integer(unsigned(cmd_op));address:=to_integer(unsigned(cmd_addr));items:=to_integer(unsigned(cmd_count));
                            rsp_data<=(others=>'0');rsp_error<=x"0";rsp_state<=state_code;rsp_done<='1';
                            if op=4 then
                                if items/=0 or cmd_data/=(cmd_data'range=>'0') or address>15 then rsp_error<=x"1";
                                else
                                    page:=(others=>'0');
                                    if address=0 then
                                        page(31 downto 0):=x"44535036";page(63 downto 32):=x"00360001";page(95 downto 64):=std_logic_vector(to_unsigned(25000000,32));
                                        page(127 downto 96):=std_logic_vector(to_unsigned(program_words,32));page(159 downto 128):=x"0000"&std_logic_vector(sequence);
                                        page(191 downto 160):=x"0000000"&state_code;page(223 downto 192):=std_logic_vector(completed);page(255 downto 224):=failure_code;
                                    elsif address=1 then
                                        page:=failure_pc&return_value&last_instruction&last_pc&std_logic_vector(retired_total)&std_logic_vector(retired)&std_logic_vector(run_cycles);
                                    elsif address=2 then
                                        page:=x"10000000"&x"00000100"&x"00000080"&x"00000080"&x"00000146"&x"00000008"&x"00002000"&x"00001000";
                                    elsif address=3 then
                                        page(31 downto 0):=x"0000007F";page(63 downto 32):=std_logic_vector(trap_count);
                                        page(95 downto 64):=last_trap_pc;page(127 downto 96):=last_trap_cause;page(159 downto 128):=last_trap_value;
                                        page(191 downto 160):=std_logic_vector(to_unsigned(event_count,32));page(192):=event_overflow;
                                        page(255 downto 224):=std_logic_vector(to_unsigned(25000000,32));
                                    elsif address>=13 then page:=profile_data;
                                    elsif address<12 then
                                        for k in 0 to 7 loop page(32*k+31 downto 32*k):=events(8*(address-4)+k);end loop;
                                    else
                                        page:=std_logic_vector(to_unsigned(16,32))&std_logic_vector(to_unsigned(25000000,32))&
                                            (31 downto 1=>'0')&saved_pending&std_logic_vector(interrupt_count)&saved_compare&saved_now;
                                    end if;
                                    rsp_data<=page;
                                end if;
                            elsif phase=EXECUTING or phase=CLEAR_MEMORY then rsp_error<=x"2";
                            elsif op=5 then
                                if address/=0 or items/=0 or cmd_data(255 downto 32)/=(255 downto 32=>'0') or unsigned(cmd_data(31 downto 0))<1 or unsigned(cmd_data(31 downto 0))>4095 then rsp_error<=x"1";
                                elsif seq_valid='1' and unsigned(cmd_seq)/=sequence+1 then rsp_error<=x"3";
                                else
                                    sequence<=unsigned(cmd_seq);seq_valid<='1';program_words<=to_integer(unsigned(cmd_data(31 downto 0)));phase<=CLEAR_MEMORY;clear_index<=0;
                                    begin_pending<='1';uploaded_words<=0;run_cycles<=(others=>'0');retired<=(others=>'0');
                                    trap_count<=(others=>'0');last_trap_pc<=(others=>'0');last_trap_cause<=(others=>'0');last_trap_value<=(others=>'0');
                events<=(others=>(others=>'0'));event_count<=0;event_overflow<='0';interrupt_count<=(others=>'0');
                saved_now<=(others=>'0');saved_compare<=(others=>'1');saved_pending<='0';
                                    last_pc<=(others=>'0');last_instruction<=(others=>'0');return_value<=(others=>'0');failure_code<=(others=>'0');failure_pc<=(others=>'0');rsp_done<='0';
                                end if;
                            elsif seq_valid='0' or unsigned(cmd_seq)/=sequence then rsp_error<=x"3";
                            elsif op=3 then
                                if address/=0 or items/=0 or cmd_data/=(cmd_data'range=>'0') then rsp_error<=x"1";
                                elsif phase/=LOADING then rsp_error<=x"2";
                                else
                                    complete_code:=uploaded_words=program_words;
                                    if not complete_code then rsp_error<=x"5";
                                    else phase<=EXECUTING;rsp_state<=x"3";end if;
                                end if;
                            elsif op=1 or op=2 or op=6 or op=7 then
                                if ((op=1 or op=6) and phase/=LOADING) or ((op=2 or op=7) and phase/=LOADING and phase/=FINISHED and phase/=FAILED) then rsp_error<=x"2";
                                elsif items<1 or items>8 or address+items>8192 or ((op=6 or op=7) and address+items>program_words) or (op=6 and address/=uploaded_words) then rsp_error<=x"4";
                                else
                                    transfer_base<=address;transfer_count<=items;transfer_index<=0;transfer_input<=cmd_data;transfer_output<=(others=>'0');
                                    if op=6 or op=7 then transfer_code<='1';else transfer_code<='0';end if;
                                    if op=1 or op=6 then transfer<=WRITE_WORD;else transfer<=READ_ISSUE;end if;rsp_done<='0';
                                end if;
                            else rsp_error<=x"9";end if;
                        end if;
                end case;
            end if;
        end if;
    end process;
end;
