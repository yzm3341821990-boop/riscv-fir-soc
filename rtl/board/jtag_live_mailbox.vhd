library ieee;
use ieee.std_logic_1164.all;
entity jtag_live_mailbox is
    port(clk,rst : in std_logic;
        source_async : in std_logic_vector(319 downto 0);
        probe_word : out std_logic_vector(319 downto 0);
        cmd_valid : out std_logic;
        cmd_op : out std_logic_vector(2 downto 0);
        cmd_seq : out std_logic_vector(15 downto 0);
        cmd_addr : out std_logic_vector(12 downto 0);
        cmd_count : out std_logic_vector(4 downto 0);
        cmd_data : out std_logic_vector(255 downto 0);
        rsp_done : in std_logic;
        rsp_error,rsp_state : in std_logic_vector(3 downto 0);
        rsp_data : in std_logic_vector(255 downto 0));
end entity;
architecture rtl of jtag_live_mailbox is
    type state_type is (ARM_LINK,IDLE,SETTLE,LATCH_REQUEST,WAIT_RESPONSE,CONFIRM);
    signal state : state_type := ARM_LINK;
    signal source_meta,source_sync,request_copy : std_logic_vector(319 downto 0) := (others=>'0');
    signal arm_count : natural range 0 to 5 := 0;
    signal active_token,ack,dispatch : std_logic := '0';
    signal response : std_logic_vector(255 downto 0) := (others=>'0');
    signal error_reg : std_logic_vector(3 downto 0) := x"7";
    signal state_reg : std_logic_vector(3 downto 0) := (others=>'0');
    attribute preserve : boolean;
    attribute preserve of source_meta,source_sync : signal is true;
begin
    cmd_valid<=dispatch;
    cmd_op<=request_copy(310 downto 308);cmd_seq<=request_copy(307 downto 292);
    cmd_addr<=request_copy(291 downto 279);cmd_count<=request_copy(278 downto 274);
    cmd_data<=request_copy(255 downto 0);
    probe_word<=x"4C"&ack&request_copy(310 downto 274)&error_reg&state_reg&x"01"&"00"&response;
    synchronizer : process(clk)
    begin
        if rising_edge(clk) then
            if rst='1' then source_meta<=(others=>'0');source_sync<=(others=>'0');
            else source_meta<=source_async;source_sync<=source_meta;end if;
        end if;
    end process;
    transaction : process(clk)
    begin
        if rising_edge(clk) then
            dispatch<='0';
            if rst='1' then
                state<=ARM_LINK;arm_count<=0;request_copy<=(others=>'0');
                active_token<='0';ack<='0';response<=(others=>'0');error_reg<=x"7";state_reg<=(others=>'0');
            else
                case state is
                    when ARM_LINK =>
                        -- Adopt the held token without executing a pre-reset write/run.
                        if arm_count=5 then
                            request_copy<=source_sync;ack<=source_sync(311);active_token<=source_sync(311);
                            state_reg<=rsp_state;state<=IDLE;
                        else arm_count<=arm_count+1;end if;
                    when IDLE =>
                        if source_sync(311)/=ack then state<=SETTLE;end if;
                    when SETTLE => request_copy<=source_sync;state<=LATCH_REQUEST;
                    when LATCH_REQUEST =>
                        if source_sync/=request_copy then request_copy<=source_sync;
                        elsif source_sync(311)=ack then state<=IDLE;
                        else
                            active_token<=request_copy(311);
                            if request_copy(319 downto 312)/=x"51" or request_copy(273 downto 266)/=x"00"
                                or request_copy(265 downto 258)/=x"01" or request_copy(257 downto 256)/="00" then
                                response<=(others=>'0');error_reg<=x"1";state_reg<=rsp_state;state<=CONFIRM;
                            else dispatch<='1';state<=WAIT_RESPONSE;end if;
                        end if;
                    when WAIT_RESPONSE =>
                        if rsp_done='1' then
                            response<=rsp_data;error_reg<=rsp_error;state_reg<=rsp_state;state<=CONFIRM;
                        end if;
                    when CONFIRM =>
                        -- All response bits have been registered for a full core period.
                        ack<=active_token;state<=IDLE;
                end case;
            end if;
        end if;
    end process;
end architecture;
