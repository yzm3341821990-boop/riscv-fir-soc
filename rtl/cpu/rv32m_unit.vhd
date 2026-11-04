library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity rv32m_unit is
    port (
        clk, rst, req_valid : in std_logic;
        req_ready : out std_logic;
        req_op : in std_logic_vector(2 downto 0);
        req_a, req_b : in std_logic_vector(31 downto 0);
        rsp_valid : out std_logic;
        rsp_ready : in std_logic;
        rsp_result : out std_logic_vector(31 downto 0);
        busy : out std_logic;
        iteration : out std_logic_vector(5 downto 0)
    );
end entity;

architecture rtl of rv32m_unit is
    type state_type is (IDLE, EXECUTE, RESPONSE);
    signal state : state_type := IDLE;
    signal opcode : std_logic_vector(2 downto 0) := "000";
    signal ticks : natural range 0 to 31 := 0;
    signal product_acc, product_shift : unsigned(63 downto 0) := (others=>'0');
    signal product_factor : unsigned(31 downto 0) := (others=>'0');
    signal quotient, divisor : unsigned(31 downto 0) := (others=>'0');
    signal remainder_value : unsigned(32 downto 0) := (others=>'0');
    signal original_a, result_register : std_logic_vector(31 downto 0) := (others=>'0');
    signal product_negative, quotient_negative, remainder_negative, zero_divisor : boolean := false;
    function magnitude(value : std_logic_vector(31 downto 0); negative : boolean) return unsigned is
    begin
        if negative then return unsigned(not value)+1; end if;
        return unsigned(value);
    end;
begin
    req_ready <= '1' when state=IDLE and rst='0' else '0';
    rsp_valid <= '1' when state=RESPONSE and rst='0' else '0';
    busy <= '1' when state/=IDLE and rst='0' else '0';
    rsp_result <= result_register;
    iteration <= std_logic_vector(to_unsigned(ticks,6));

    datapath : process(clk)
        variable negative_a, negative_b : boolean;
        variable a_mag, b_mag, next_q, final_q, final_r : unsigned(31 downto 0);
        variable product : unsigned(63 downto 0);
        variable trial : unsigned(32 downto 0);
    begin
        if rising_edge(clk) then
            if rst='1' then
                state<=IDLE;
                opcode<="000"; ticks<=0;
                product_acc<=(others=>'0'); product_shift<=(others=>'0');
                product_factor<=(others=>'0'); quotient<=(others=>'0');
                divisor<=(others=>'0'); remainder_value<=(others=>'0');
                original_a<=(others=>'0'); result_register<=(others=>'0');
                product_negative<=false; quotient_negative<=false;
                remainder_negative<=false; zero_divisor<=false;
            else
                case state is
                    when IDLE =>
                        if req_valid='1' then
                            negative_a := req_a(31)='1' and
                                (req_op="001" or req_op="010" or req_op="100" or req_op="110");
                            negative_b := req_b(31)='1' and
                                (req_op="001" or req_op="100" or req_op="110");
                            a_mag:=magnitude(req_a,negative_a);
                            b_mag:=magnitude(req_b,negative_b);
                            opcode<=req_op; original_a<=req_a; ticks<=0;
                            product_acc<=(others=>'0'); product_shift<=resize(a_mag,64);
                            product_factor<=b_mag; quotient<=a_mag; divisor<=b_mag;
                            remainder_value<=(others=>'0');
                            product_negative<=negative_a xor negative_b;
                            quotient_negative<=negative_a xor negative_b;
                            remainder_negative<=negative_a;
                            zero_divisor<=req_b=x"00000000";
                            state<=EXECUTE;
                        end if;
                    when EXECUTE =>
                        if opcode(2)='0' then
                            product:=product_acc;
                            if product_factor(0)='1' then product:=product+product_shift; end if;
                            product_acc<=product;
                            product_shift<=shift_left(product_shift,1);
                            product_factor<=shift_right(product_factor,1);
                            if ticks=31 then
                                if product_negative then product:=(not product)+1; end if;
                                if opcode="000" then result_register<=std_logic_vector(product(31 downto 0));
                                else result_register<=std_logic_vector(product(63 downto 32)); end if;
                                state<=RESPONSE;
                            end if;
                        else
                            trial:=remainder_value(31 downto 0) & quotient(31);
                            next_q:=quotient(30 downto 0) & '0';
                            if trial>=resize(divisor,33) then
                                trial:=trial-resize(divisor,33); next_q(0):='1';
                            end if;
                            quotient<=next_q; remainder_value<=trial;
                            if ticks=31 then
                                final_q:=next_q; final_r:=trial(31 downto 0);
                                if quotient_negative then final_q:=(not final_q)+1; end if;
                                if remainder_negative then final_r:=(not final_r)+1; end if;
                                if zero_divisor then
                                    if opcode(1)='0' then result_register<=x"FFFFFFFF";
                                    else result_register<=original_a; end if;
                                elsif opcode(1)='0' then result_register<=std_logic_vector(final_q);
                                else result_register<=std_logic_vector(final_r); end if;
                                state<=RESPONSE;
                            end if;
                        end if;
                        if ticks<31 then ticks<=ticks+1; end if;
                    when RESPONSE =>
                        if rsp_ready='1' then state<=IDLE; end if;
                end case;
            end if;
        end if;
    end process;
end architecture;
