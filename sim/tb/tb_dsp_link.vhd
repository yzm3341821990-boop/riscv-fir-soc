library ieee;use ieee.std_logic_1164.all;use ieee.numeric_std.all;use ieee.std_logic_textio.all;use std.textio.all;
entity tb_dsp_link is generic(END_PC : natural := 2016);end;
architecture test of tb_dsp_link is
    subtype word is std_logic_vector(31 downto 0);
    signal clk : std_logic := '0';signal reset_n : std_logic := '0';
    signal source_bus,probe_bus : std_logic_vector(319 downto 0) := (others=>'0');
    signal core_clk,core_reset,cq,cw,dq,dw,dr,tv : std_logic;
    signal cbe : std_logic_vector(3 downto 0);signal ca,cd,cr,da,dd,ddata,tp,ti,tval,tn : word;
    signal tr : std_logic_vector(4 downto 0);
    signal freeze : std_logic := '0';signal job_index : natural := 0;
begin
    clk<=not clk after 10 ns when freeze='0' else '0';reset_n<='1' after 100 ns;
    dut : entity work.de2_115_dsp_core port map(clk,reset_n,"0000",open,open,open,open,open,open,open,open,open,
        source_bus,probe_bus,tv,tp,ti,tval,tn,tr,core_clk,core_reset,cq,cw,cbe,ca,cd,cr,dq,dw,dr,da,dd,ddata);
    monitor : process
        file tf : text;variable row : line;variable opened,ended : boolean := false;
        variable aq,aw,bq,bw,br : std_logic;variable aa,ad,ba,bd : word;variable be : std_logic_vector(3 downto 0);
        variable edge,index : natural := 0;
    begin
        wait until rising_edge(core_clk);
        if core_reset='1' then edge:=0;ended:=false;
        else
            if not opened and not ended then
                index:=index+1;job_index<=index;file_open(tf,"trace-"&integer'image(index)&".txt",write_mode);opened:=true;
            end if;
            edge:=edge+1;aq:=cq;aw:=cw;aa:=ca;ad:=cd;be:=cbe;bq:=dq;bw:=dw;br:=dr;ba:=da;bd:=dd;
            wait for 1 ns;
            if opened then
                if aq='1' then
                    if aw='1' then write(row,string'("C W "));else write(row,string'("C R "));ad:=cr;end if;
                    hwrite(row,aa);write(row,string'(" "));hwrite(row,ad);write(row,string'(" "));hwrite(row,be);write(row,string'(" "));write(row,edge);writeline(tf,row);
                end if;
                if bq='1' and br='1' then
                    if bw='1' then write(row,string'("D W "));else write(row,string'("D R "));bd:=ddata;end if;
                    hwrite(row,ba);write(row,string'(" "));hwrite(row,bd);write(row,string'(" "));write(row,edge);writeline(tf,row);
                end if;
                if tv='1' then
                    write(row,string'("I "));hwrite(row,tp);write(row,string'(" "));hwrite(row,ti);write(row,string'(" "));write(row,to_integer(unsigned(tr)));
                    write(row,string'(" "));hwrite(row,tval);write(row,string'(" "));hwrite(row,tn);write(row,string'(" "));write(row,edge);writeline(tf,row);
                    if unsigned(tn)=END_PC then file_close(tf);opened:=false;ended:=true;freeze<='1';end if;
                end if;
            end if;
        end if;
    end process;
end;
