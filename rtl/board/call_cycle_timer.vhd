library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity call_cycle_timer is
    generic(COUNTER_WIDTH : positive := 32);
    port(clk,rst,start_event,stop_event : in std_logic;
         ticks : out std_logic_vector(COUNTER_WIDTH-1 downto 0);
         done,error : out std_logic);
end entity;
architecture rtl of call_cycle_timer is
    type state_type is (IDLE,COUNTING,COMPLETE,INVALID);
    signal state : state_type;
    signal counter : unsigned(COUNTER_WIDTH-1 downto 0);
begin
    ticks<=std_logic_vector(counter);
    done<='1' when state=COMPLETE else '0';
    error<='1' when state=INVALID else '0';
    count_edges : process(clk)
    begin
        if rising_edge(clk) then
            if rst='1' then state<=IDLE;counter<=(others=>'0');
            else
                case state is
                    when IDLE =>
                        if stop_event='1' then state<=INVALID;
                        elsif start_event='1' then state<=COUNTING;counter<=(others=>'0');end if;
                    when COUNTING =>
                        if start_event='1' or counter=(counter'range=>'1') then state<=INVALID;
                        else
                            counter<=counter+1;
                            if stop_event='1' then state<=COMPLETE;end if;
                        end if;
                    when COMPLETE =>
                        if start_event='1' or stop_event='1' then state<=INVALID;end if;
                    when INVALID => null;
                end case;
            end if;
        end if;
    end process;
end architecture;
