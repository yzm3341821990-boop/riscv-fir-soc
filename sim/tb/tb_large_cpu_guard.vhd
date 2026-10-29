library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb_large_cpu_guard is
    generic(MEM_HEX : string := "0000A103"; LUI_HEX : string := "000010B7";
            EXPECTED_ADDR : natural := 4096; EXPECTED_BE : natural := 15; EXPECTED_VALUE : natural := 16#12345678#;
            ENABLE_MMIO : boolean := true; EXPECT_FAULT : boolean := false);
end entity;
architecture test of tb_large_cpu_guard is
    function parse_hex(text : string) return std_logic_vector is
        variable value : unsigned(31 downto 0) := (others=>'0');
        variable digit : natural;
    begin
        for i in text'range loop
            if text(i)>='0' and text(i)<='9' then digit:=character'pos(text(i))-character'pos('0');
            else digit:=character'pos(text(i))-character'pos('A')+10;end if;
            value:=shift_left(value,4)+digit;
        end loop;return std_logic_vector(value);
    end;
    constant MEM_INSN : std_logic_vector(31 downto 0) := parse_hex(MEM_HEX);
    signal clk : std_logic := '0'; signal rst : std_logic := '1';
    signal ia,ir,da,dw,cp,ci,cv,cn,fp : std_logic_vector(31 downto 0) := (others=>'0');
    signal req,we,commit_valid,fault,ie : std_logic;
    signal be : std_logic_vector(3 downto 0);
    signal rd : std_logic_vector(4 downto 0);
    signal requests,commits : natural := 0;
    signal finished : boolean := false;
begin
    clk<=not clk after 5 ns when not finished else '0';
    dut : entity work.pipeline_large_cpu
        generic map(ENABLE_FIR_MMIO=>ENABLE_MMIO)
        port map(clk=>clk,rst=>rst,imem_en=>ie,imem_addr=>ia,imem_rdata=>ir,
            dmem_req=>req,dmem_we=>we,dmem_be=>be,dmem_addr=>da,dmem_wdata=>dw,dmem_rdata=>x"12345678",
            commit_valid=>commit_valid,commit_pc=>cp,commit_instruction=>ci,
            commit_value=>cv,commit_rd=>rd,commit_next_pc=>cn,fault=>fault,fault_pc=>fp,
            debug_stall=>open,debug_flush=>open,debug_valid=>open);
    rom : process(clk)
    begin
        if rising_edge(clk) then
            if ie='1' then
                case to_integer(unsigned(ia(9 downto 2))) is
                    when 0 => ir<=parse_hex(LUI_HEX);
                    when 1 => ir<=MEM_INSN;
                    when others => ir<=x"00000013";
                end case;
            end if;
            if req='1' then
                requests<=requests+1;
                assert not EXPECT_FAULT and unsigned(da)=EXPECTED_ADDR and unsigned(be)=EXPECTED_BE
                    report "LARGE_GUARD_BAD_REQUEST" severity failure;
            end if;
        end if;
    end process;
    stimulus : process
    begin
        wait for 16 ns; rst<='0';
        for timeout in 1 to 40 loop
            wait until rising_edge(clk); wait for 1 ns;
            if commit_valid='1' then
                commits<=commits+1;
                if cp=x"00000004" then
                    assert not EXPECT_FAULT and requests=1 and cn=x"00000008" and fault='0'
                        report "LARGE_GUARD_WORD_NOT_ACCEPTED" severity failure;
                    if MEM_INSN(6 downto 0)="0000011" then
                        assert unsigned(cv)=EXPECTED_VALUE report "LARGE_GUARD_LOAD_DATA" severity failure;
                    end if;
                    finished<=true; exit;
                end if;
            end if;
            if fault='1' then
                assert EXPECT_FAULT report "LARGE_GUARD_UNEXPECTED_FAULT" severity failure;
                assert fp=x"00000004" and requests=0 and commits=1 and req='0'
                    report "LARGE_GUARD_FAULT_SIDE_EFFECT" severity failure;
                finished<=true; exit;
            end if;
            assert timeout<40 report "LARGE_GUARD_TIMEOUT" severity failure;
        end loop;
        report "LARGE_GUARD_GUARD_PASS" severity note; wait;
    end process;
end architecture;
