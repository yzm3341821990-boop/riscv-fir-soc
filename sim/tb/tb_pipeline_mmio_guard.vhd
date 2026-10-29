library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb_pipeline_mmio_guard is
    generic(MEM_WORD : natural := 16#0000A103#; LUI_WORD : natural := 16#400030B7#;
            ENABLE_MMIO : boolean := true; EXPECT_FAULT : boolean := false);
end entity;
architecture test of tb_pipeline_mmio_guard is
    signal clk : std_logic := '0'; signal rst : std_logic := '1';
    signal ia,ir,da,dw,cp,ci,cv,cn,fp : std_logic_vector(31 downto 0) := (others=>'0');
    signal req,we,commit_valid,fault,ie : std_logic;
    signal be : std_logic_vector(3 downto 0);
    signal rd : std_logic_vector(4 downto 0);
    signal requests,commits : natural := 0;
    signal finished : boolean := false;
begin
    clk<=not clk after 5 ns when not finished else '0';
    dut : entity work.pipeline_cpu
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
                    when 0 => ir<=std_logic_vector(to_unsigned(LUI_WORD,32));
                    when 1 => ir<=std_logic_vector(to_unsigned(MEM_WORD,32));
                    when others => ir<=x"00000013";
                end case;
            end if;
            if req='1' then
                requests<=requests+1;
                assert not EXPECT_FAULT and da=x"40003000" and be="1111"
                    report "PIPE_MMIO_BAD_REQUEST" severity failure;
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
                        report "PIPE_MMIO_WORD_NOT_ACCEPTED" severity failure;
                    if MEM_WORD mod 128=3 then
                        assert cv=x"12345678" report "PIPE_MMIO_LOAD_DATA" severity failure;
                    end if;
                    finished<=true; exit;
                end if;
            end if;
            if fault='1' then
                assert EXPECT_FAULT report "PIPE_MMIO_UNEXPECTED_FAULT" severity failure;
                assert fp=x"00000004" and requests=0 and commits=1 and req='0'
                    report "PIPE_MMIO_FAULT_SIDE_EFFECT" severity failure;
                finished<=true; exit;
            end if;
            assert timeout<40 report "PIPE_MMIO_TIMEOUT" severity failure;
        end loop;
        report "PIPE_MMIO_GUARD_PASS" severity note; wait;
    end process;
end architecture;
