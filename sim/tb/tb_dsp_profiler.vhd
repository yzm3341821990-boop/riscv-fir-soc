library ieee;use ieee.std_logic_1164.all;use ieee.numeric_std.all;
entity tb_dsp_profiler is end;
architecture test of tb_dsp_profiler is
    signal clk : std_logic := '0';signal rst,req,we : std_logic := '0';
    signal be : std_logic_vector(3 downto 0) := "1111";signal data : std_logic_vector(31 downto 0) := (others=>'0');
    signal page : natural range 0 to 2 := 0;signal result : std_logic_vector(255 downto 0);signal done : boolean := false;
begin
    clk<=not clk after 5 ns when not done else '0';
    dut : entity work.dsp_profiler port map(clk,rst,req,we,be,data,page,result);
    driver : process
        procedure tick is begin wait until rising_edge(clk);wait for 1 ns;end;
        procedure marker(v : natural) is begin req<='1';we<='1';data<=std_logic_vector(to_unsigned(v,32));tick;req<='0';end;
    begin
        rst<='1';tick;rst<='0';tick;
        for i in 0 to 2 loop
            page<=i;marker(i+1);for n in 1 to 20 loop tick;end loop;marker(0);
            assert unsigned(result(63 downto 0))=21 and unsigned(result(95 downto 64))=1 and result(159 downto 96)=x"0000000000000000" report "DSP_PROFILE_BOUNDARY" severity failure;
        end loop;
        page<=0;marker(1);tick;marker(0);
        assert unsigned(result(63 downto 0))=23 and unsigned(result(95 downto 64))=2 report "DSP_PROFILE_ACCUMULATION" severity failure;
        marker(0);assert result(128)='1' report "DSP_PROFILE_UNMATCHED_END" severity failure;
        rst<='1';tick;rst<='0';tick;assert unsigned(result)=0 report "DSP_PROFILE_RESET" severity failure;
        marker(2);marker(3);assert result(128)='1' report "DSP_PROFILE_NESTED_START" severity failure;
        rst<='1';tick;rst<='0';tick;be<="0011";marker(1);assert result(128)='1' report "DSP_PROFILE_WIDTH" severity failure;
        report "DSP_PROFILE_PASS" severity note;done<=true;wait;
    end process;
end;
