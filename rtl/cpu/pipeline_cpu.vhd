library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity pipeline_cpu is
    generic (ENABLE_FIR_MMIO : boolean := false);
    port (
        clk, rst : in std_logic;
        imem_en : out std_logic;
        imem_addr : out std_logic_vector(31 downto 0);
        imem_rdata : in std_logic_vector(31 downto 0);
        dmem_req, dmem_we : out std_logic;
        dmem_be : out std_logic_vector(3 downto 0);
        dmem_addr, dmem_wdata : out std_logic_vector(31 downto 0);
        dmem_rdata : in std_logic_vector(31 downto 0);
        commit_valid : out std_logic;
        commit_pc, commit_instruction, commit_value, commit_next_pc : out std_logic_vector(31 downto 0);
        commit_rd : out std_logic_vector(4 downto 0);
        fault : out std_logic;
        fault_pc : out std_logic_vector(31 downto 0);
        debug_stall, debug_flush : out std_logic;
        debug_valid : out std_logic_vector(3 downto 0)
    );
end entity;

architecture rtl of pipeline_cpu is
    subtype word is std_logic_vector(31 downto 0);
    subtype regno is std_logic_vector(4 downto 0);
    type execute_stage is record
        valid, bad_fetch : std_logic;
        pc, instruction, first, second : word;
    end record;
    constant EMPTY_EX : execute_stage := ('0','0', x"00000000",x"00000013",x"00000000",x"00000000");
    type later_stage is record
        valid, load, store : std_logic;
        pc, instruction, result, address, store_data, next_pc : word;
        rd : regno;
    end record;
    constant EMPTY_LATER : later_stage := ('0','0','0', x"00000000",x"00000013",
        x"00000000",x"00000000",x"00000000",x"00000000","00000");
    signal ex : execute_stage := EMPTY_EX;
    signal mem, wb : later_stage := EMPTY_LATER;
    signal fetch_pc, id_pc : word := (others => '0');
    signal id_valid, id_bad, stopped, faulted : std_logic := '0';
    signal fault_address : word := (others => '0');
    signal id_rs1, id_rs2, id_rd, ex_rs1, ex_rs2, ex_rd : regno;
    signal id_first, id_second, capture_first, capture_second, first, second : word;
    signal id_legal, id_ui, id_load, id_store, id_branch, id_jump, id_jr,
           id_upper, id_upc, id_mul : std_logic;
    signal id_op, ex_op : std_logic_vector(3 downto 0);
    signal legal, use_imm, load, store, branch, jump, jr, upper, upc, mul : std_logic;
    signal imm_i, imm_s, imm_b, imm_j, imm_u, immediate, alu_a, alu_b, alu_result,
           mul_result, ex_result, target, wb_value : word;
    signal redirect, ex_fault, hazard, rf_we, fetch_ok : std_logic;
begin
    id_decode : entity work.decode_tiny(rtl)
        port map(imem_rdata,id_legal,id_ui,id_load,id_store,id_branch,id_jump,id_jr,
                 id_upper,id_upc,id_mul,id_rs1,id_rs2,id_rd,id_op);
    ex_decode : entity work.decode_tiny(rtl)
        port map(ex.instruction,legal,use_imm,load,store,branch,jump,jr,
                 upper,upc,mul,ex_rs1,ex_rs2,ex_rd,ex_op);
    registers : entity work.regfile32(rtl)
        port map(clk,rst,rf_we,wb.rd,id_rs1,id_rs2,wb_value,id_first,id_second);
    i_offset : entity work.imm_i(rtl) port map(ex.instruction,imm_i);
    s_offset : entity work.imm_s(rtl) port map(ex.instruction,imm_s);
    b_offset : entity work.imm_b(rtl) port map(ex.instruction,imm_b);
    j_offset : entity work.imm_j(rtl) port map(ex.instruction,imm_j);
    u_offset : entity work.imm_u(rtl) port map(ex.instruction,imm_u);
    arithmetic : entity work.alu32(rtl) port map(alu_a,alu_b,ex_op,alu_result);
    multiplier : entity work.mul32(rtl) port map(first,second,mul_result);

    immediate <= imm_u when upper = '1' else imm_s when store = '1' else
                 imm_b when branch = '1' else imm_j when jump = '1' and jr = '0' else imm_i;
    alu_a <= ex.pc when upc = '1' else first;
    alu_b <= immediate when use_imm = '1' else second;
    ex_result <= std_logic_vector(unsigned(ex.pc)+4) when jump = '1' else
                 mul_result when mul = '1' else alu_result;
    rf_we <= '1' when rst = '0' and wb.valid = '1' and wb.rd /= "00000" else '0';
    capture_first <= wb_value when rf_we = '1' and wb.rd = id_rs1 else id_first;
    capture_second <= wb_value when rf_we = '1' and wb.rd = id_rs2 else id_second;

    forwarding : process(ex,ex_rs1,ex_rs2,mem,wb,wb_value)
    begin
        first <= ex.first; second <= ex.second;
        if wb.valid = '1' and wb.rd /= "00000" then
            if wb.rd = ex_rs1 then first <= wb_value; end if;
            if wb.rd = ex_rs2 then second <= wb_value; end if;
        end if;
        -- Newest producer wins; a MEM load has no result until WB.
        if mem.valid = '1' and mem.load = '0' and mem.rd /= "00000" then
            if mem.rd = ex_rs1 then first <= mem.result; end if;
            if mem.rd = ex_rs2 then second <= mem.result; end if;
        end if;
    end process;

    hazard <= '1' when id_valid = '1' and ex.valid = '1' and load = '1' and ex_rd /= "00000" and
        (ex_rd = id_rs1 or ex_rd = id_rs2) else '0';
    fetch_ok <= '1' when fetch_pc(31 downto 10) = "0000000000000000000000" and
                         fetch_pc(1 downto 0) = "00" else '0';
    imem_en <= '1' when rst = '0' and stopped = '0' and hazard = '0' and
                        redirect = '0' and ex_fault = '0' and fetch_ok = '1' else '0';
    imem_addr <= fetch_pc;
    debug_stall <= hazard when rst = '0' and stopped = '0' else '0';
    debug_flush <= redirect when rst = '0' and stopped = '0' else '0';
    debug_valid <= id_valid & ex.valid & mem.valid & wb.valid;
    fault <= faulted;
    fault_pc <= fault_address;

    control_transfer : process(ex,legal,branch,jump,jr,first,second,imm_b,imm_j,imm_i,load,store,alu_result)
        variable taken, bad : boolean;
        variable next_address : word;
    begin
        taken := false;
        next_address := std_logic_vector(unsigned(ex.pc)+4);
        if branch = '1' then
            case ex.instruction(14 downto 12) is
                when "000" => taken := first = second;
                when "001" => taken := first /= second;
                when "100" => taken := signed(first) < signed(second);
                when "101" => taken := signed(first) >= signed(second);
                when "110" => taken := unsigned(first) < unsigned(second);
                when "111" => taken := unsigned(first) >= unsigned(second);
                when others => null;
            end case;
            if taken then next_address := std_logic_vector(unsigned(ex.pc)+unsigned(imm_b)); end if;
        elsif jump = '1' then
            taken := true;
            if jr = '1' then
                next_address := std_logic_vector(unsigned(first)+unsigned(imm_i)); next_address(0) := '0';
            else next_address := std_logic_vector(unsigned(ex.pc)+unsigned(imm_j));
            end if;
        end if;
        bad := legal /= '1' or ex.bad_fetch = '1';
        if taken and (next_address(31 downto 10) /= "0000000000000000000000" or
                      next_address(1 downto 0) /= "00") then bad := true; end if;
        if load = '1' or store = '1' then
            if alu_result(31 downto 10) /= "0000000000000000000000" and not
               (ENABLE_FIR_MMIO and alu_result(31 downto 12)=x"40003" and
                ex.instruction(14 downto 12)="010" and alu_result(1 downto 0)="00") then
                bad := true;
            end if;
            case ex.instruction(13 downto 12) is
                when "01" => if alu_result(0) /= '0' then bad := true; end if;
                when "10" => if alu_result(1 downto 0) /= "00" then bad := true; end if;
                when others => null;
            end case;
        end if;
        target <= next_address;
        redirect <= '0'; ex_fault <= '0';
        if ex.valid = '1' then
            if bad then ex_fault <= '1';
            elsif taken then redirect <= '1'; end if;
        end if;
    end process;

    memory_bus : process(mem,rst)
        variable lane : natural range 0 to 3;
    begin
        dmem_req <= '0'; dmem_we <= '0'; dmem_be <= "0000";
        dmem_addr <= mem.address; dmem_wdata <= (others => '0');
        if rst = '0' and mem.valid = '1' and (mem.load = '1' or mem.store = '1') then
            dmem_req <= '1'; dmem_we <= mem.store;
            lane := to_integer(unsigned(mem.address(1 downto 0)));
            case mem.instruction(13 downto 12) is
                when "00" =>
                    dmem_be <= std_logic_vector(shift_left(to_unsigned(1,4),lane));
                    dmem_wdata <= std_logic_vector(shift_left(resize(unsigned(mem.store_data(7 downto 0)),32),8*lane));
                when "01" =>
                    dmem_be <= std_logic_vector(shift_left(to_unsigned(3,4),lane));
                    dmem_wdata <= std_logic_vector(shift_left(resize(unsigned(mem.store_data(15 downto 0)),32),8*lane));
                when others => dmem_be <= "1111"; dmem_wdata <= mem.store_data;
            end case;
        end if;
    end process;
    load_result : process(wb,dmem_rdata)
        variable shifted : unsigned(31 downto 0);
    begin
        wb_value <= wb.result;
        if wb.valid = '1' and wb.load = '1' then
            shifted := shift_right(unsigned(dmem_rdata),8*to_integer(unsigned(wb.address(1 downto 0))));
            case wb.instruction(14 downto 12) is
                when "000" => wb_value <= std_logic_vector(resize(signed(shifted(7 downto 0)),32));
                when "001" => wb_value <= std_logic_vector(resize(signed(shifted(15 downto 0)),32));
                when "100" => wb_value <= std_logic_vector(resize(shifted(7 downto 0),32));
                when "101" => wb_value <= std_logic_vector(resize(shifted(15 downto 0),32));
                when others => wb_value <= dmem_rdata;
            end case;
        end if;
    end process;

    pipeline : process(clk)
    begin
        if rising_edge(clk) then
            commit_valid <= '0';
            if rst = '1' then
                fetch_pc <= (others => '0'); id_pc <= (others => '0');
                id_valid <= '0'; id_bad <= '0'; ex <= EMPTY_EX; mem <= EMPTY_LATER; wb <= EMPTY_LATER;
                stopped <= '0'; faulted <= '0'; fault_address <= (others => '0');
                commit_pc <= (others => '0'); commit_instruction <= (others => '0');
                commit_rd <= (others => '0'); commit_value <= (others => '0'); commit_next_pc <= (others => '0');
            else
                if wb.valid = '1' then
                    commit_valid <= '1'; commit_pc <= wb.pc; commit_instruction <= wb.instruction;
                    commit_rd <= wb.rd; commit_next_pc <= wb.next_pc;
                    if wb.rd = "00000" then commit_value <= (others => '0'); else commit_value <= wb_value; end if;
                end if;
                wb <= mem;
                mem <= EMPTY_LATER;
                if stopped = '1' then
                    ex <= EMPTY_EX; id_valid <= '0';
                    if mem.valid = '0' and wb.valid = '0' then faulted <= '1'; end if;
                elsif ex_fault = '1' then
                    stopped <= '1'; fault_address <= ex.pc; ex <= EMPTY_EX; id_valid <= '0';
                else
                    mem.valid <= ex.valid; mem.pc <= ex.pc; mem.instruction <= ex.instruction;
                    mem.load <= load; mem.store <= store; mem.rd <= ex_rd;
                    mem.result <= ex_result; mem.address <= alu_result; mem.store_data <= second; mem.next_pc <= target;
                    if redirect = '1' then
                        fetch_pc <= target; id_valid <= '0'; ex <= EMPTY_EX;
                    elsif hazard = '1' then
                        ex <= EMPTY_EX;
                    else
                        ex.valid <= id_valid; ex.bad_fetch <= id_bad; ex.pc <= id_pc;
                        ex.instruction <= imem_rdata; ex.first <= capture_first; ex.second <= capture_second;
                        id_valid <= '1'; id_pc <= fetch_pc; id_bad <= not fetch_ok;
                        fetch_pc <= std_logic_vector(unsigned(fetch_pc)+4);
                    end if;
                end if;
            end if;
        end if;
    end process;
end architecture;
