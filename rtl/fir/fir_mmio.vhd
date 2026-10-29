library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity fir_mmio is
    generic(MAC_LANES : positive := 1);
    port(clk,rst,bus_req,bus_we : in std_logic;
         bus_be : in std_logic_vector(3 downto 0);
         bus_addr,bus_wdata : in std_logic_vector(31 downto 0);
         bus_rdata : out std_logic_vector(31 downto 0);
         dma_req,dma_we : out std_logic;
         dma_addr,dma_wdata : out std_logic_vector(31 downto 0);
         dma_ready,dma_rvalid : in std_logic;
         dma_rdata : in std_logic_vector(31 downto 0));
end entity;
architecture rtl of fir_mmio is
    subtype word is std_logic_vector(31 downto 0);
    type state_type is (IDLE, CLEAR_CORE, READ_REQUEST, READ_WAIT, FEED_CORE, WAIT_RESULT, WRITE_REQUEST);
    type coeff_bank is array(0 to 31) of signed(15 downto 0);
    signal state : state_type;
    signal source_addr,dest_addr,count,cycles,written,error_code : unsigned(31 downto 0);
    signal sample_index : unsigned(31 downto 0);
    signal coefficient_mask : std_logic_vector(31 downto 0);
    signal coefficients : coeff_bank;
    signal done_flag : std_logic;
    signal status_word : word;
    signal input_sample,core_output,cfg_data : signed(15 downto 0);
    signal core_acc : signed(39 downto 0);
    signal clear_valid,clear_ready,cfg_valid,cfg_ready,s_valid,s_ready,m_valid,m_ready,core_busy : std_logic;
    signal cfg_addr : unsigned(4 downto 0);

    procedure record_error(variable current : inout unsigned(31 downto 0); code : natural) is
    begin if current=0 then current:=to_unsigned(code,32); end if; end;
begin
    core : entity work.fir_serial generic map(MAC_LANES=>MAC_LANES)
        port map(clk,rst,clear_valid,clear_ready,cfg_valid,cfg_ready,
        cfg_addr,cfg_data,s_valid,s_ready,input_sample,m_valid,m_ready,core_output,core_acc,core_busy);
    status_word(31 downto 3)<=(others=>'0');
    status_word(0)<='0' when state=IDLE else '1';
    status_word(1)<=done_flag;
    status_word(2)<='0' when rst='1' else '0' when error_code=0 else '1';
    clear_valid<='1' when state=CLEAR_CORE and rst='0' else '0';
    s_valid<='1' when state=FEED_CORE and rst='0' else '0';
    m_ready<='1' when state=WRITE_REQUEST and dma_ready='1' and rst='0' else '0';
    cfg_addr<=unsigned(bus_addr(6 downto 2));
    cfg_data<=signed(bus_wdata(15 downto 0));
    cfg_valid<='1' when state=IDLE and rst='0' and bus_req='1' and bus_we='1'
        and bus_addr(31 downto 12)=x"40003" and bus_addr(11 downto 7)="00010"
        and bus_addr(1 downto 0)="00" and bus_be="1111"
        and signed(bus_wdata)=resize(signed(bus_wdata(15 downto 0)),32) else '0';
    dma_req<='1' when rst='0' and (state=READ_REQUEST or state=WRITE_REQUEST) else '0';
    dma_we<='1' when state=WRITE_REQUEST else '0';
    dma_addr<=std_logic_vector(dest_addr+shift_left(sample_index,2)) when state=WRITE_REQUEST
              else std_logic_vector(source_addr+shift_left(sample_index,2));
    dma_wdata<=std_logic_vector(resize(core_output,32));

    controller : process(clk)
        variable offset : natural range 0 to 4095;
        variable err : unsigned(31 downto 0);
        variable invalid : natural;
    begin
        if rising_edge(clk) then
            if rst='1' then
                state<=IDLE; source_addr<=(others=>'0'); dest_addr<=(others=>'0'); count<=(others=>'0');
                cycles<=(others=>'0'); written<=(others=>'0'); error_code<=(others=>'0');
                sample_index<=(others=>'0'); done_flag<='0'; coefficient_mask<=(others=>'0');
                coefficients<=(others=>(others=>'0')); input_sample<=(others=>'0'); bus_rdata<=(others=>'0');
            else
                err:=error_code;
                if state/=IDLE then cycles<=cycles+1; end if;
                case state is
                    when IDLE => null;
                    when CLEAR_CORE => if clear_ready='1' then state<=READ_REQUEST; end if;
                    when READ_REQUEST => if dma_ready='1' then state<=READ_WAIT; end if;
                    when READ_WAIT =>
                        if dma_rvalid='1' then
                            if signed(dma_rdata)/=resize(signed(dma_rdata(15 downto 0)),32) then
                                record_error(err,7); state<=IDLE; done_flag<='0';
                            else input_sample<=signed(dma_rdata(15 downto 0)); state<=FEED_CORE; end if;
                        end if;
                    when FEED_CORE => if s_ready='1' then state<=WAIT_RESULT; end if;
                    when WAIT_RESULT => if m_valid='1' then state<=WRITE_REQUEST; end if;
                    when WRITE_REQUEST =>
                        if dma_ready='1' then
                            written<=written+1;
                            if sample_index+1=count then
                                done_flag<='1'; state<=IDLE; -- DONE_AFTER_ACCEPTED_WRITE
                            else sample_index<=sample_index+1; state<=READ_REQUEST; end if;
                        end if;
                end case;
                if bus_req='1' then
                    offset:=to_integer(unsigned(bus_addr(11 downto 0)));
                    if bus_addr(31 downto 12)/=x"40003" or bus_addr(1 downto 0)/="00" or bus_be/="1111" then
                        record_error(err,8); if bus_we='0' then bus_rdata<=(others=>'0'); end if;
                    elsif bus_we='1' then
                        if state/=IDLE then record_error(err,1);
                        elsif offset>=256 and offset<=380 then
                            if signed(bus_wdata)/=resize(signed(bus_wdata(15 downto 0)),32) then record_error(err,7);
                            else
                                coefficients((offset-256)/4)<=signed(bus_wdata(15 downto 0));
                                coefficient_mask((offset-256)/4)<='1';
                            end if;
                        else
                            case offset is
                                when 0 =>
                                    if bus_wdata=x"00000001" then
                                        invalid:=0;
                                        if count=0 or count>128 then invalid:=2;
                                        elsif source_addr(1 downto 0)/="00" or dest_addr(1 downto 0)/="00" then invalid:=3;
                                        elsif source_addr>1020 or dest_addr>1020 then invalid:=4;
                                        elsif source_addr+shift_left(count,2)>1024 or dest_addr+shift_left(count,2)>1024 then invalid:=4;
                                        elsif source_addr<dest_addr+shift_left(count,2) and dest_addr<source_addr+shift_left(count,2) then invalid:=5;
                                        elsif coefficient_mask/=x"FFFFFFFF" then invalid:=6;
                                        end if;
                                        if invalid/=0 then record_error(err,invalid);
                                        else
                                            state<=CLEAR_CORE; done_flag<='0'; err:=(others=>'0');
                                            cycles<=(others=>'0'); written<=(others=>'0'); sample_index<=(others=>'0');
                                        end if;
                                    elsif bus_wdata=x"00000002" then done_flag<='0'; err:=(others=>'0');
                                    elsif bus_wdata/=x"00000000" then record_error(err,9); end if;
                                when 8 => source_addr<=unsigned(bus_wdata);
                                when 12 => dest_addr<=unsigned(bus_wdata);
                                when 16 => count<=unsigned(bus_wdata);
                                when others => record_error(err,8);
                            end case;
                        end if;
                    else
                        if offset>=256 and offset<=380 then
                            bus_rdata<=std_logic_vector(resize(coefficients((offset-256)/4),32));
                        else
                            case offset is
                                when 0 => bus_rdata<=(others=>'0');
                                when 4 => bus_rdata<=status_word;
                                when 8 => bus_rdata<=std_logic_vector(source_addr);
                                when 12 => bus_rdata<=std_logic_vector(dest_addr);
                                when 16 => bus_rdata<=std_logic_vector(count);
                                when 20 => bus_rdata<=std_logic_vector(cycles);
                                when 24 => bus_rdata<=std_logic_vector(written);
                                when 28 => bus_rdata<=std_logic_vector(error_code);
                                when others => bus_rdata<=(others=>'0'); record_error(err,8);
                            end case;
                        end if;
                    end if;
                end if;
                error_code<=err;
            end if;
        end if;
    end process;
end architecture;
