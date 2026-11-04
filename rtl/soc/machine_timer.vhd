library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- One clock domain. Synchronous reads return the value before the active edge.
entity machine_timer is
    port (
        clk, rst, req, we : in std_logic;
        be : in std_logic_vector(3 downto 0);
        addr, wdata : in std_logic_vector(31 downto 0);
        rdata : out std_logic_vector(31 downto 0);
        irq : out std_logic;
        now_value, cmp_value : out std_logic_vector(63 downto 0)
    );
end entity;

architecture rtl of machine_timer is
    signal ticks : unsigned(63 downto 0) := (others=>'0');
    signal deadline : unsigned(63 downto 0) := (others=>'1');
begin
    now_value <= std_logic_vector(ticks);
    cmp_value <= std_logic_vector(deadline);
    irq <= '1' when ticks >= deadline else '0';
    process(clk)
    begin
        if rising_edge(clk) then
            rdata <= (others=>'0');
            if rst='1' then
                ticks <= (others=>'0'); deadline <= (others=>'1');
            else
                ticks <= ticks+1;
                if req='1' and be="1111" then
                    case addr is
                        when x"02004000" =>
                            rdata <= std_logic_vector(deadline(31 downto 0));
                            if we='1' then deadline(31 downto 0)<=unsigned(wdata); end if;
                        when x"02004004" =>
                            rdata <= std_logic_vector(deadline(63 downto 32));
                            if we='1' then deadline(63 downto 32)<=unsigned(wdata); end if;
                        when x"0200BFF8" =>
                            rdata <= std_logic_vector(ticks(31 downto 0));
                            if we='1' then ticks<=ticks(63 downto 32) & unsigned(wdata); end if;
                        when x"0200BFFC" =>
                            rdata <= std_logic_vector(ticks(63 downto 32));
                            if we='1' then ticks<=unsigned(wdata) & ticks(31 downto 0); end if;
                        when others => null;
                    end case;
                end if;
            end if;
        end if;
    end process;
end architecture;
