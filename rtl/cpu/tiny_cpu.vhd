library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tiny_cpu is
    generic (ENABLE_FIR_MMIO : boolean := false);
    port (
        clk, rst : in std_logic;
        imem_addr : out std_logic_vector(31 downto 0);
        imem_rdata : in std_logic_vector(31 downto 0);
        dmem_req, dmem_we : out std_logic;
        dmem_be : out std_logic_vector(3 downto 0);
        dmem_addr, dmem_wdata : out std_logic_vector(31 downto 0);
        dmem_rdata : in std_logic_vector(31 downto 0);
        debug_pc, debug_instruction, debug_next_pc : out std_logic_vector(31 downto 0);
        debug_state : out std_logic_vector(2 downto 0);
        debug_rs1, debug_rs2, debug_rd : out std_logic_vector(4 downto 0);
        debug_rs1_data, debug_rs2_data, debug_imm, debug_alu_result : out std_logic_vector(31 downto 0);
        commit_valid : out std_logic;
        commit_pc, commit_instruction, commit_value : out std_logic_vector(31 downto 0);
        commit_rd : out std_logic_vector(4 downto 0);
        fault : out std_logic
    );
end entity;

architecture rtl of tiny_cpu is
    type state_type is (FETCH_REQUEST, FETCH_CAPTURE, EXECUTE, LOAD_WRITEBACK, FAULTED);
    signal state : state_type;
    signal pc_reg, instruction_reg : std_logic_vector(31 downto 0);
    signal rs1_address, rs2_address, rd_address : std_logic_vector(4 downto 0);
    signal rs1_data, rs2_data, immediate, immediate_i, immediate_s, immediate_b, immediate_j, immediate_u,
           alu_a, alu_b, alu_value,
           writeback_value, load_value, store_data, multiply_value : std_logic_vector(31 downto 0);
    signal multiply_instruction : std_logic;
    signal byte_mask : std_logic_vector(3 downto 0);
    signal operation : std_logic_vector(3 downto 0);
    signal decoded_legal, use_immediate, register_write_enable : std_logic;
    signal fault_reg : std_logic;
    signal memory_read, memory_write, memory_request, address_valid : std_logic;
    signal branch_instruction, jump_instruction, jump_register, control_target_valid : std_logic;
    signal upper_instruction, upper_pc_relative : std_logic;
    signal sequential_pc, next_pc : std_logic_vector(31 downto 0);
begin
    decoder : entity work.decode_tiny(rtl)
        port map (instruction => instruction_reg, legal => decoded_legal,
                  use_immediate => use_immediate, rs1 => rs1_address, rs2 => rs2_address,
                  memory_read => memory_read, memory_write => memory_write,
                  branch_instruction => branch_instruction, jump_instruction => jump_instruction,
                  jump_register => jump_register,
                  upper_instruction => upper_instruction, upper_pc_relative => upper_pc_relative,
                  multiply_instruction => multiply_instruction,
                  rd => rd_address, alu_op => operation);
    immediates : entity work.imm_i(rtl)
        port map (instruction => instruction_reg, immediate => immediate_i);
    store_immediates : entity work.imm_s(rtl)
        port map (instruction => instruction_reg, immediate => immediate_s);
    branch_immediates : entity work.imm_b(rtl)
        port map (instruction => instruction_reg, immediate => immediate_b);
    jump_immediates : entity work.imm_j(rtl)
        port map (instruction => instruction_reg, immediate => immediate_j);
    upper_immediates : entity work.imm_u(rtl)
        port map (instruction => instruction_reg, immediate => immediate_u);
    registers : entity work.regfile32(rtl)
        port map (clk => clk, rst => rst, we => register_write_enable,
                  waddr => rd_address, wdata => writeback_value,
                  raddr1 => rs1_address, raddr2 => rs2_address,
                  rdata1 => rs1_data, rdata2 => rs2_data);
    arithmetic : entity work.alu32(rtl)
        port map (a => alu_a, b => alu_b, alu_op => operation, result => alu_value);
    multiplier : entity work.mul32(rtl)
        port map (a => rs1_data, b => rs2_data, result => multiply_value);

    immediate <= immediate_u when upper_instruction = '1' else
                 immediate_s when memory_write = '1' else
                 immediate_b when branch_instruction = '1' else
                 immediate_j when jump_instruction = '1' and jump_register = '0' else immediate_i;
    alu_b <= immediate when use_immediate = '1' else rs2_data;
    alu_a <= pc_reg when upper_pc_relative = '1' else rs1_data;
    sequential_pc <= std_logic_vector(unsigned(pc_reg) + 4);
    writeback_value <= load_value when state = LOAD_WRITEBACK else
                       multiply_value when multiply_instruction = '1' else
                       sequential_pc when jump_instruction = '1' else alu_value;
    register_write_enable <= '1' when rst = '0' and rd_address /= "00000" and
        ((state = EXECUTE and decoded_legal = '1' and control_target_valid = '1' and
          memory_read = '0' and memory_write = '0') or
         state = LOAD_WRITEBACK) else '0';
    address_valid <= '1' when (alu_value(31 downto 10) = "0000000000000000000000" and
        ((instruction_reg(13 downto 12) = "00") or
         (instruction_reg(13 downto 12) = "01" and alu_value(0) = '0') or
         (instruction_reg(13 downto 12) = "10" and alu_value(1 downto 0) = "00"))) or
        (ENABLE_FIR_MMIO and alu_value(31 downto 12) = x"40003" and
         instruction_reg(14 downto 12) = "010" and alu_value(1 downto 0) = "00") else '0';
    memory_request <= '1' when state = EXECUTE and decoded_legal = '1' and rst = '0' and
        (memory_read = '1' or memory_write = '1') and address_valid = '1' else '0';
    dmem_req <= memory_request;
    dmem_we <= memory_write when memory_request = '1' else '0';
    dmem_be <= byte_mask;
    dmem_addr <= alu_value;
    dmem_wdata <= store_data;
    imem_addr <= pc_reg;
    debug_pc <= pc_reg;
    debug_instruction <= instruction_reg;
    debug_next_pc <= next_pc;
    debug_rs1 <= rs1_address;
    debug_rs2 <= rs2_address;
    debug_rd <= rd_address;
    debug_rs1_data <= rs1_data;
    debug_rs2_data <= rs2_data;
    debug_imm <= immediate;
    debug_alu_result <= alu_value;
    fault <= fault_reg;
    with state select debug_state <=
        "000" when FETCH_REQUEST,
        "001" when FETCH_CAPTURE,
        "010" when EXECUTE,
        "011" when LOAD_WRITEBACK,
        "100" when FAULTED;

    -- Lane zero contains the byte at the lowest address (little-endian).
    format_store : process(memory_request, instruction_reg, alu_value, rs2_data)
        variable lane : natural range 0 to 3;
    begin
        byte_mask <= "0000";
        store_data <= (others => '0');
        if memory_request = '1' then
            lane := to_integer(unsigned(alu_value(1 downto 0)));
            case instruction_reg(13 downto 12) is
                when "00" =>
                    byte_mask <= std_logic_vector(shift_left(to_unsigned(1, 4), lane));
                    store_data <= std_logic_vector(shift_left(resize(unsigned(rs2_data(7 downto 0)), 32), 8*lane));
                when "01" =>
                    byte_mask <= std_logic_vector(shift_left(to_unsigned(3, 4), lane));
                    store_data <= std_logic_vector(shift_left(resize(unsigned(rs2_data(15 downto 0)), 32), 8*lane));
                when others =>
                    byte_mask <= "1111";
                    store_data <= rs2_data;
            end case;
        end if;
    end process;

    format_load : process(dmem_rdata, alu_value, instruction_reg, state)
        variable shifted : unsigned(31 downto 0);
    begin
        load_value <= dmem_rdata;
        if state = LOAD_WRITEBACK then
            shifted := shift_right(unsigned(dmem_rdata), 8*to_integer(unsigned(alu_value(1 downto 0))));
            case instruction_reg(14 downto 12) is
                when "000" => load_value <= std_logic_vector(resize(signed(shifted(7 downto 0)), 32));
                when "001" => load_value <= std_logic_vector(resize(signed(shifted(15 downto 0)), 32));
                when "100" => load_value <= std_logic_vector(resize(shifted(7 downto 0), 32));
                when "101" => load_value <= std_logic_vector(resize(shifted(15 downto 0), 32));
                when others => null;
            end case;
        end if;
    end process;

    choose_next_pc : process(pc_reg, sequential_pc, instruction_reg, rs1_data, rs2_data,
                             immediate_i, immediate_b, immediate_j,
                             branch_instruction, jump_instruction, jump_register)
        variable take_branch : boolean;
        variable changes_control : boolean;
        variable target : std_logic_vector(31 downto 0);
    begin
        take_branch := false;
        changes_control := false;
        target := sequential_pc;
        if branch_instruction = '1' then
            case instruction_reg(14 downto 12) is
                when "000" => take_branch := rs1_data = rs2_data;
                when "001" => take_branch := rs1_data /= rs2_data;
                when "100" => take_branch := signed(rs1_data) < signed(rs2_data);
                when "101" => take_branch := signed(rs1_data) >= signed(rs2_data);
                when "110" => take_branch := unsigned(rs1_data) < unsigned(rs2_data);
                when "111" => take_branch := unsigned(rs1_data) >= unsigned(rs2_data);
                when others => null;
            end case;
            if take_branch then
                target := std_logic_vector(unsigned(pc_reg) + unsigned(immediate_b));
                changes_control := true;
            end if;
        elsif jump_instruction = '1' then
            changes_control := true;
            if jump_register = '1' then
                target := std_logic_vector(unsigned(rs1_data) + unsigned(immediate_i));
                target(0) := '0'; -- JALR clears only bit zero before alignment checking.
            else
                target := std_logic_vector(unsigned(pc_reg) + unsigned(immediate_j));
            end if;
        end if;
        next_pc <= target;
        control_target_valid <= '1';
        -- This teaching core rejects transfers outside its fixed 1 KiB ROM.
        -- It has a fatal FAULT interface, not an architectural trap handler.
        if changes_control then
            if target(31 downto 10) /= "0000000000000000000000" or target(1 downto 0) /= "00" then
                control_target_valid <= '0';
            end if;
        end if;
    end process;

    control : process(clk)
        procedure retire(value : std_logic_vector(31 downto 0)) is
        begin
            commit_valid <= '1';
            commit_pc <= pc_reg;
            commit_instruction <= instruction_reg;
            commit_rd <= rd_address;
            if rd_address = "00000" then
                commit_value <= (others => '0');
            else
                commit_value <= value;
            end if;
            pc_reg <= next_pc;
            state <= FETCH_REQUEST;
        end procedure;
    begin
        if rising_edge(clk) then
            if rst = '1' then
                pc_reg <= (others => '0');
                instruction_reg <= x"00000013";
                state <= FETCH_REQUEST;
                fault_reg <= '0';
                commit_valid <= '0';
                commit_pc <= (others => '0');
                commit_instruction <= (others => '0');
                commit_rd <= (others => '0');
                commit_value <= (others => '0');
            else
                commit_valid <= '0';
                case state is
                    when FETCH_REQUEST =>
                        state <= FETCH_CAPTURE;
                    when FETCH_CAPTURE =>
                        instruction_reg <= imem_rdata;
                        state <= EXECUTE;
                    when EXECUTE =>
                        if decoded_legal /= '1' or control_target_valid /= '1' or
                           ((memory_read = '1' or memory_write = '1') and address_valid /= '1') then
                            fault_reg <= '1';
                            state <= FAULTED;
                        elsif memory_read = '1' then
                            state <= LOAD_WRITEBACK;
                        else
                            retire(writeback_value);
                        end if;
                    when LOAD_WRITEBACK =>
                        retire(load_value);
                    when FAULTED => null;
                end case;
            end if;
        end if;
    end process;
end architecture;
