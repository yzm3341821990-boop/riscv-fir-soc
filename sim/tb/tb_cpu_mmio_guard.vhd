library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb_cpu_mmio_guard is
    generic(MEM_WORD : natural := 16#0000A103#; LUI_WORD : natural := 16#400030B7#;
            ENABLE_MMIO : boolean := true; EXPECT_FAULT : boolean := false);
end entity;
architecture test of tb_cpu_mmio_guard is
    signal clk : std_logic := '0'; signal rst : std_logic := '1';
    signal ia,ir,da,dw,pc,cv,cp : std_logic_vector(31 downto 0);
    signal req,we,commit_valid,fault : std_logic;
    signal be : std_logic_vector(3 downto 0); signal state : std_logic_vector(2 downto 0);
    signal requests : natural := 0; signal finished : boolean := false;
begin
    clk<=not clk after 5 ns when not finished else '0';
    dut : entity work.tiny_cpu generic map(ENABLE_FIR_MMIO=>ENABLE_MMIO)
        port map(clk=>clk,rst=>rst,imem_addr=>ia,imem_rdata=>ir,dmem_req=>req,dmem_we=>we,
            dmem_be=>be,dmem_addr=>da,dmem_wdata=>dw,dmem_rdata=>x"12345678",
            debug_pc=>pc,debug_instruction=>open,debug_next_pc=>open,debug_state=>state,
            debug_rs1=>open,debug_rs2=>open,debug_rd=>open,debug_rs1_data=>open,debug_rs2_data=>open,
            debug_imm=>open,debug_alu_result=>open,commit_valid=>commit_valid,commit_pc=>cp,
            commit_instruction=>open,commit_value=>cv,commit_rd=>open,fault=>fault);
    rom : process(clk) begin if rising_edge(clk) then
        if rst='0' then
        case to_integer(unsigned(ia(9 downto 2))) is
            when 0 => ir<=std_logic_vector(to_unsigned(LUI_WORD,32));
            when 1 => ir<=std_logic_vector(to_unsigned(MEM_WORD,32));
            when others => ir<=x"00000013";
        end case;
        end if;
        if req='1' then
            requests<=requests+1;
            assert da=x"40003000" and be="1111" report "MMIO_GUARD_BAD_REQUEST" severity failure;
        end if;
    end if; end process;
    stimulus : process begin
        wait for 16 ns; rst<='0';
        for timeout in 1 to 30 loop
            wait until rising_edge(clk); wait for 1 ns;
            if EXPECT_FAULT and fault='1' then
                assert pc=x"00000004" and requests=0 and req='0' report "MMIO_GUARD_FAULT_SIDE_EFFECT" severity failure;
                finished<=true; exit;
            elsif not EXPECT_FAULT and pc=x"00000008" and state="000" then
                assert requests=1 and fault='0' report "MMIO_GUARD_MISSING_WORD" severity failure;
                if MEM_WORD mod 128=3 then assert cv=x"12345678" report "MMIO_GUARD_LOAD_VALUE" severity failure; end if;
                finished<=true; exit;
            end if;
            assert timeout<30 report "MMIO_GUARD_TIMEOUT" severity failure;
        end loop;
        report "CPU_MMIO_GUARD_PASS" severity note; wait;
    end process;
end architecture;
