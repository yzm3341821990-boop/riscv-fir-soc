library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity dsp_profiler is
    port(clk,rst,req,we : in std_logic;be : in std_logic_vector(3 downto 0);data : in std_logic_vector(31 downto 0);
        page : in natural range 0 to 2;result : out std_logic_vector(255 downto 0));
end;
architecture rtl of dsp_profiler is
    type totals_type is array(0 to 2) of unsigned(63 downto 0);
    type counts_type is array(0 to 2) of unsigned(31 downto 0);
    signal totals : totals_type := (others=>(others=>'0'));
    signal counts : counts_type := (others=>(others=>'0'));
    signal ticks,started : unsigned(63 downto 0) := (others=>'0');
    signal active : natural range 0 to 3 := 0;
    signal bad : std_logic := '0';
begin
    result(63 downto 0)<=std_logic_vector(totals(page));
    result(95 downto 64)<=std_logic_vector(counts(page));
    result(127 downto 96)<=std_logic_vector(to_unsigned(active,32));
    result(159 downto 128)<=(31 downto 1=>'0')&bad;
    result(255 downto 160)<=(others=>'0');
    counter : process(clk) begin if rising_edge(clk) then
        if rst='1' then
            ticks<=(others=>'0');started<=(others=>'0');active<=0;bad<='0';
            totals<=(others=>(others=>'0'));counts<=(others=>(others=>'0'));
        else
            ticks<=ticks+1;
            if req='1' then
                if we/='1' or be/="1111" then bad<='1';
                elsif data=x"00000000" then
                    if active=0 then bad<='1';
                    else totals(active-1)<=totals(active-1)+(ticks-started);counts(active-1)<=counts(active-1)+1;active<=0;end if;
                elsif unsigned(data)<=3 then
                    if active/=0 then bad<='1';else active<=to_integer(unsigned(data));started<=ticks;end if;
                else bad<='1';end if;
            end if;
        end if;
    end if;end process;
end;
