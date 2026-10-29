library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity fir_serial is
    generic (MAC_LANES : positive := 1);
    port (
        clk, rst : in std_logic;
        clear_valid : in std_logic;
        clear_ready : out std_logic;
        cfg_valid : in std_logic;
        cfg_ready : out std_logic;
        cfg_addr : in unsigned(4 downto 0);
        cfg_data : in signed(15 downto 0);
        s_valid : in std_logic;
        s_ready : out std_logic;
        s_data : in signed(15 downto 0);
        m_valid : out std_logic;
        m_ready : in std_logic;
        m_data : out signed(15 downto 0);
        m_acc : out signed(39 downto 0);
        busy : out std_logic
    );
end entity;

architecture rtl of fir_serial is
    type state_type is (IDLE, MAC, HOLD_OUTPUT);
    type sample_bank is array(0 to 31) of signed(15 downto 0);
    type partial_bank is array(0 to 3) of signed(39 downto 0);
    signal state : state_type;
    signal coefficients, history : sample_bank;
    signal tap_index : natural range 0 to 31;
    signal accumulator, output_acc : signed(39 downto 0);
    signal output_data : signed(15 downto 0);

    function quantize(value : signed(39 downto 0)) return signed is
        variable wide, rounded : signed(40 downto 0);
        variable magnitude : unsigned(40 downto 0);
    begin
        -- Widen before negating; even the signed40 minimum is well-defined.
        wide := resize(value, 41);
        if wide < 0 then magnitude := unsigned(-wide);
        else magnitude := unsigned(wide); end if;
        rounded := signed(shift_right(magnitude + to_unsigned(16384,41), 15));
        if value < 0 then rounded := -rounded; end if;
        if rounded > 32767 then return to_signed(32767,16);
        elsif rounded < -32768 then return to_signed(-32768,16);
        else return resize(rounded,16); end if;
    end function;
begin
    assert MAC_LANES = 1 or MAC_LANES = 2 or MAC_LANES = 4
        report "FIR_MAC_LANES_MUST_BE_1_2_OR_4" severity failure;
    clear_ready <= '1' when state = IDLE and rst = '0' else '0';
    cfg_ready <= '1' when state = IDLE and rst = '0' and clear_valid = '0' else '0';
    s_ready <= '1' when state = IDLE and rst = '0' and clear_valid = '0'
                      and cfg_valid = '0' else '0';
    m_valid <= '1' when state = HOLD_OUTPUT and rst = '0' else '0';
    busy <= '0' when state = IDLE else '1';
    m_data <= output_data;
    m_acc <= output_acc;

    engine : process(clk)
        variable product : signed(31 downto 0);
        variable partials : partial_bank;
        variable total : signed(39 downto 0);
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state <= IDLE;
                coefficients <= (others => (others => '0'));
                history <= (others => (others => '0'));
                tap_index <= 0; accumulator <= (others => '0');
                output_data <= (others => '0'); output_acc <= (others => '0');
            else
                case state is
                    when IDLE =>
                        if clear_valid = '1' then
                            history <= (others => (others => '0')); -- CLEAR_HISTORY
                            tap_index <= 0; accumulator <= (others => '0');
                            output_data <= (others => '0'); output_acc <= (others => '0');
                        elsif cfg_valid = '1' then
                            coefficients(to_integer(cfg_addr)) <= cfg_data;
                        elsif s_valid = '1' then
                            for k in 31 downto 1 loop history(k) <= history(k-1); end loop;
                            history(0) <= s_data;
                            accumulator <= (others => '0'); tap_index <= 0;
                            state <= MAC;
                        end if;
                    when MAC =>
                        partials := (others => (others => '0'));
                        for lane in 0 to MAC_LANES-1 loop
                            product := history(tap_index+lane) * coefficients(tap_index+lane);
                            partials(lane) := resize(product,40);
                        end loop;
                        -- Extend every signed product before the balanced reduction.
                        total := accumulator + ((partials(0)+partials(1)) + (partials(2)+partials(3)));
                        accumulator <= total;
                        if tap_index = 32-MAC_LANES then
                            output_acc <= total;
                            output_data <= quantize(total);
                            state <= HOLD_OUTPUT;
                        else tap_index <= tap_index + MAC_LANES; end if;
                    when HOLD_OUTPUT =>
                        if m_ready = '1' then state <= IDLE; end if;
                end case;
            end if;
        end if;
    end process;
end architecture;
