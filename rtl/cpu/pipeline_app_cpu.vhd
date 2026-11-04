library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity pipeline_app_cpu is
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
        debug_valid : out std_logic_vector(3 downto 0);
        trap_valid : out std_logic;
        trap_pc, trap_cause, trap_value : out std_logic_vector(31 downto 0);
        timer_irq : in std_logic;
        csr_event_valid : out std_logic;
        csr_event_pc : out std_logic_vector(31 downto 0);
        csr_event_address : out std_logic_vector(11 downto 0);
        debug_m : out std_logic_vector(2 downto 0)
    );
end entity;

architecture rtl of pipeline_app_cpu is
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
    signal id_valid, id_bad : std_logic := '0';
    signal fault_address : word := (others => '0');
    signal id_rs1, id_rs2, id_rd, ex_rs1, ex_rs2, ex_rd : regno;
    signal id_first, id_second, capture_first, capture_second, first, second : word;
    signal id_legal, id_ui, id_load, id_store, id_branch, id_jump, id_jr,
           id_upper, id_upc, id_mul : std_logic;
    signal id_op, ex_op : std_logic_vector(3 downto 0);
    signal legal, use_imm, load, store, branch, jump, jr, upper, upc, mul : std_logic;
    signal imm_i, imm_s, imm_b, imm_j, imm_u, immediate, alu_a, alu_b, alu_result,
           mul_result, ex_result, target, wb_value : word;
    signal redirect, ex_fault, hazard, rf_we, fetch_ok, serial_wait : std_logic;
    signal base_id_rs1, base_id_rs2, base_ex_rs1, base_ex_rs2, base_ex_rd : regno;
    signal base_legal, csr_form, csr_known, csr_write, machine_legal, is_mret : std_logic;
    signal csr_old, csr_new, exception_code, exception_value : word;
    signal mstatus : word := x"00001800";
    signal mie : word := (others=>'0');
    signal irq_requested, irq_wait : std_logic;
    signal interrupt_pc : word;
    signal id_m, long_m, m_active, m_start, m_ready, m_valid, m_take, m_stall : std_logic := '0';
    signal m_result : word;
    signal mtvec, mscratch, mepc, mcause, mtval : word := (others => '0');
begin
    id_decode : entity work.decode_tiny(rtl)
        port map(imem_rdata,id_legal,id_ui,id_load,id_store,id_branch,id_jump,id_jr,
                 id_upper,id_upc,id_mul,base_id_rs1,base_id_rs2,id_rd,id_op);
    ex_decode : entity work.decode_tiny(rtl)
        port map(ex.instruction,base_legal,use_imm,load,store,branch,jump,jr,
                 upper,upc,mul,base_ex_rs1,base_ex_rs2,base_ex_rd,ex_op);
    registers : entity work.regfile32(rtl)
        port map(clk,rst,rf_we,wb.rd,id_rs1,id_rs2,wb_value,id_first,id_second);
    i_offset : entity work.imm_i(rtl) port map(ex.instruction,imm_i);
    s_offset : entity work.imm_s(rtl) port map(ex.instruction,imm_s);
    b_offset : entity work.imm_b(rtl) port map(ex.instruction,imm_b);
    j_offset : entity work.imm_j(rtl) port map(ex.instruction,imm_j);
    u_offset : entity work.imm_u(rtl) port map(ex.instruction,imm_u);
    arithmetic : entity work.alu32(rtl) port map(alu_a,alu_b,ex_op,alu_result);
    multiplier : entity work.mul32(rtl) port map(first,second,mul_result);

    multi_cycle : entity work.rv32m_unit(rtl)
        port map(clk=>clk,rst=>rst,req_valid=>m_start,req_ready=>m_ready,
            req_op=>ex.instruction(14 downto 12),req_a=>first,req_b=>second,
            rsp_valid=>m_valid,rsp_ready=>m_take,rsp_result=>m_result,busy=>open,iteration=>open);
    id_m <= '1' when imem_rdata(6 downto 0)="0110011" and imem_rdata(31 downto 25)="0000001" else '0';
    long_m <= '1' when ex.instruction(6 downto 0)="0110011" and
                  ex.instruction(31 downto 25)="0000001" and ex.instruction(14 downto 12)/="000" else '0';
    m_start <= '1' when rst='0' and ex.valid='1' and long_m='1' and m_active='0' and
                         ex_fault='0' and serial_wait='0' and irq_requested='0' else '0';
    m_take <= m_active when rst='0' else '0';
    m_stall <= '1' when ex.valid='1' and long_m='1' and ex_fault='0' and (m_active='0' or m_valid='0') else '0';
    debug_m <= m_active & (m_start and m_ready) & (m_valid and m_take) when rst='0' else "000";
    m_lifecycle : process(clk)
    begin
        if rising_edge(clk) then
            if rst='1' then m_active<='0';
            elsif m_start='1' and m_ready='1' then m_active<='1';
            elsif m_valid='1' and m_take='1' then m_active<='0'; end if;
        end if;
    end process;

    -- CSR source register participates in the normal bypass and load-use logic.
    id_rs2 <= imem_rdata(24 downto 20) when id_m='1' else base_id_rs2;
    ex_rs2 <= ex.instruction(24 downto 20) when long_m='1' else base_ex_rs2;
    id_rs1 <= imem_rdata(19 downto 15) when id_m='1' else imem_rdata(19 downto 15) when imem_rdata(6 downto 0)="1110011" and
               imem_rdata(14)='0' and imem_rdata(13 downto 12)/="00" else base_id_rs1;
    ex_rs1 <= ex.instruction(19 downto 15) when long_m='1' or (csr_form='1' and ex.instruction(14)='0') else base_ex_rs1;
    ex_rd <= ex.instruction(11 downto 7) when csr_form='1' or long_m='1' else base_ex_rd;
    csr_form <= '1' when ex.instruction(6 downto 0)="1110011" and
                        ex.instruction(13 downto 12)/="00" else '0';
    is_mret <= '1' when ex.instruction=x"30200073" else '0';
    machine_legal <= '1' when (csr_form='1' and csr_known='1') or is_mret='1' or
                     ex.instruction=x"00000073" or ex.instruction=x"00100073" else '0';
    legal <= base_legal or machine_legal or long_m;
    csr_access : process(ex,first,mstatus,mtvec,mscratch,mepc,mcause,mtval,mie,timer_irq)
        variable old_value, source_value, new_value : word;
        variable known, writing : std_logic;
    begin
        old_value := (others=>'0'); known := '1'; writing := '0';
        case ex.instruction(31 downto 20) is
            when x"300" => old_value:=mstatus;
            when x"304" => old_value:=mie;
            when x"344" => old_value(7):=timer_irq;
            when x"305" => old_value:=mtvec;
            when x"340" => old_value:=mscratch;
            when x"341" => old_value:=mepc;
            when x"342" => old_value:=mcause;
            when x"343" => old_value:=mtval;
            when others => known:='0';
        end case;
        source_value:=first;
        if ex.instruction(14)='1' then
            source_value:=(others=>'0'); source_value(4 downto 0):=ex.instruction(19 downto 15);
        end if;
        new_value:=old_value;
        case ex.instruction(13 downto 12) is
            when "01" => new_value:=source_value; writing:='1';
            when "10" =>
                new_value:=old_value or source_value;
                if ex.instruction(19 downto 15)/="00000" then writing:='1'; end if;
            when "11" =>
                new_value:=old_value and not source_value;
                if ex.instruction(19 downto 15)/="00000" then writing:='1'; end if;
            when others => null;
        end case;
        csr_old<=old_value; csr_new<=new_value; csr_known<=known; csr_write<=writing;
    end process;

    immediate <= imm_u when upper = '1' else imm_s when store = '1' else
                 imm_b when branch = '1' else imm_j when jump = '1' and jr = '0' else imm_i;
    alu_a <= ex.pc when upc = '1' else first;
    alu_b <= immediate when use_imm = '1' else second;
    ex_result <= m_result when long_m='1' else csr_old when csr_form='1' else
                 std_logic_vector(unsigned(ex.pc)+4) when jump = '1' else
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
    fetch_ok <= '1' when fetch_pc(31 downto 14) = "000000000000000000" and
                         fetch_pc(1 downto 0) = "00" else '0';
    -- Serialize system operations and trap entry behind all older side effects.
    serial_wait <= '1' when ex.valid='1' and (ex.instruction(6 downto 0)="1110011" or ex_fault='1') and
                            (mem.valid='1' or wb.valid='1') else '0';
    irq_requested <= timer_irq and mie(7) and mstatus(3) and not m_active;
    irq_wait <= '1' when irq_requested='1' and (mem.valid='1' or wb.valid='1') else '0';
    -- The first unexecuted instruction may be in EX, ID or the fetch frontier.
    interrupt_pc <= ex.pc when ex.valid='1' else id_pc when id_valid='1' else fetch_pc;
    imem_en <= '1' when rst='0' and hazard='0' and m_stall='0' and serial_wait='0' and irq_requested='0' and
                        redirect='0' and ex_fault='0' and fetch_ok='1' else '0';
    imem_addr <= fetch_pc;
    debug_stall <= hazard or m_stall or serial_wait or irq_wait when rst='0' else '0';
    debug_flush <= redirect or ex_fault or irq_requested when rst='0' and serial_wait='0' and irq_wait='0' else '0';
    debug_valid <= id_valid & ex.valid & mem.valid & wb.valid;
    -- Timer input is synchronous to clk; no asynchronous IRQ is supported.
    -- Architectural exceptions are reported on trap_*, not as a terminal fault.
    fault <= '0';
    fault_pc <= fault_address;

    control_transfer : process(ex,legal,branch,jump,jr,first,second,imm_b,imm_j,imm_i,
                               load,store,alu_result,is_mret,mepc)
        variable taken, bad, misaligned, accessible : boolean;
        variable next_address, cause_value, detail : word;
    begin
        taken:=false; bad:=false;
        next_address:=std_logic_vector(unsigned(ex.pc)+4);
        cause_value:=x"00000002"; detail:=ex.instruction;
        if branch='1' then
            case ex.instruction(14 downto 12) is
                when "000" => taken:=first=second;
                when "001" => taken:=first/=second;
                when "100" => taken:=signed(first)<signed(second);
                when "101" => taken:=signed(first)>=signed(second);
                when "110" => taken:=unsigned(first)<unsigned(second);
                when "111" => taken:=unsigned(first)>=unsigned(second);
                when others => null;
            end case;
            if taken then next_address:=std_logic_vector(unsigned(ex.pc)+unsigned(imm_b)); end if;
        elsif jump='1' then
            taken:=true;
            if jr='1' then
                next_address:=std_logic_vector(unsigned(first)+unsigned(imm_i)); next_address(0):='0';
            else next_address:=std_logic_vector(unsigned(ex.pc)+unsigned(imm_j)); end if;
        elsif is_mret='1' then taken:=true; next_address:=mepc;
        end if;
        if ex.bad_fetch='1' then bad:=true; cause_value:=x"00000001"; detail:=ex.pc;
        elsif legal/='1' then bad:=true;
        elsif ex.instruction=x"00000073" then bad:=true; cause_value:=x"0000000B"; detail:=(others=>'0');
        elsif ex.instruction=x"00100073" then bad:=true; cause_value:=x"00000003"; detail:=ex.pc;
        elsif taken and next_address(1 downto 0)/="00" then
            bad:=true; cause_value:=x"00000000"; detail:=next_address;
        elsif load='1' or store='1' then
            misaligned:=false;
            case ex.instruction(13 downto 12) is
                when "01" => misaligned:=alu_result(0)/='0';
                when "10" => misaligned:=alu_result(1 downto 0)/="00";
                when others => null;
            end case;
            accessible:=unsigned(alu_result)<32768 or alu_result(31 downto 15)=std_logic_vector(to_unsigned(8192,17)) or
                (ex.instruction(13 downto 12)="10" and (alu_result=x"02004000" or
                 alu_result=x"02004004" or alu_result=x"0200BFF8" or alu_result=x"0200BFFC"));
            if misaligned then
                bad:=true; detail:=alu_result;
                if store='1' then cause_value:=x"00000006"; else cause_value:=x"00000004"; end if;
            elsif not accessible then
                bad:=true; detail:=alu_result;
                if store='1' then cause_value:=x"00000007"; else cause_value:=x"00000005"; end if;
            end if;
        end if;
        target<=next_address; exception_code<=cause_value; exception_value<=detail;
        redirect<='0'; ex_fault<='0';
        if ex.valid='1' then
            if bad then ex_fault<='1'; elsif taken then redirect<='1'; end if;
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
            commit_valid <= '0'; trap_valid<='0'; csr_event_valid<='0';
            if rst = '1' then
                fetch_pc <= (others => '0'); id_pc <= (others => '0');
                id_valid <= '0'; id_bad <= '0'; ex <= EMPTY_EX; mem <= EMPTY_LATER; wb <= EMPTY_LATER;
                fault_address <= (others => '0');
                mie<=(others=>'0'); csr_event_pc<=(others=>'0'); csr_event_address<=(others=>'0');
                mstatus<=x"00001800"; mtvec<=(others=>'0'); mscratch<=(others=>'0');
                mepc<=(others=>'0'); mcause<=(others=>'0'); mtval<=(others=>'0');
                trap_pc<=(others=>'0'); trap_cause<=(others=>'0'); trap_value<=(others=>'0');
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
                if serial_wait='1' or irq_wait='1' or m_stall='1' then
                    -- Keep bypassed operands when a producer retires during the drain.
                    ex.first<=first; ex.second<=second;
                elsif ex_fault='1' then
                    mepc<=ex.pc; mcause<=exception_code; mtval<=exception_value;
                    mstatus(7)<=mstatus(3); mstatus(3)<='0';
                    trap_valid<='1'; trap_pc<=ex.pc; trap_cause<=exception_code; trap_value<=exception_value;
                    fault_address<=ex.pc;
                    fetch_pc<=mtvec; ex<=EMPTY_EX; id_valid<='0';
                elsif irq_requested='1' then
                    -- Older effects have retired. EX/ID have never executed.
                    mepc<=interrupt_pc; mcause<=x"80000007"; mtval<=(others=>'0');
                    mstatus(7)<=mstatus(3); mstatus(3)<='0';
                    trap_valid<='1'; trap_pc<=interrupt_pc; trap_cause<=x"80000007"; trap_value<=(others=>'0');
                    fault_address<=interrupt_pc;
                    fetch_pc<=mtvec; ex<=EMPTY_EX; id_valid<='0';
                else
                    if ex.valid='1' and csr_form='1' then
                        csr_event_valid<='1'; csr_event_pc<=ex.pc; csr_event_address<=ex.instruction(31 downto 20);
                    end if;
                    if ex.valid='1' and csr_form='1' and csr_write='1' then
                        case ex.instruction(31 downto 20) is
                            when x"300" => mstatus<=(csr_new and x"00000088") or x"00001800";
                            when x"304" => mie<=csr_new and x"00000080";
                            -- mip.MTIP is a read-only peripheral level; writes have no effect.
                            when x"344" => null;
                            when x"305" => mtvec<=csr_new(31 downto 2) & "00";
                            when x"340" => mscratch<=csr_new;
                            when x"341" => mepc<=csr_new(31 downto 2) & "00";
                            when x"342" => mcause<=csr_new;
                            when x"343" => mtval<=csr_new;
                            when others => null;
                        end case;
                    end if;
                    if ex.valid='1' and is_mret='1' then mstatus(3)<=mstatus(7); mstatus(7)<='1'; end if;
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
