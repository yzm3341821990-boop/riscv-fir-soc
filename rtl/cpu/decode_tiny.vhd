library ieee;
use ieee.std_logic_1164.all;
use work.alu_pkg.all;

entity decode_tiny is
    port (
        instruction : in std_logic_vector(31 downto 0);
        legal, use_immediate : out std_logic;
        memory_read, memory_write : out std_logic;
        branch_instruction, jump_instruction, jump_register : out std_logic;
        upper_instruction, upper_pc_relative : out std_logic;
        multiply_instruction : out std_logic;
        rs1, rs2, rd : out std_logic_vector(4 downto 0);
        alu_op : out std_logic_vector(3 downto 0)
    );
end entity;

architecture rtl of decode_tiny is
begin
    decode : process(instruction)
        variable valid_encoding : boolean;
        variable immediate_form : boolean;
        variable chosen_op : alu_operation;
    begin
        valid_encoding := false;
        immediate_form := false;
        chosen_op := ALU_ADD;
        legal <= '0';
        use_immediate <= '0';
        memory_read <= '0';
        memory_write <= '0';
        branch_instruction <= '0';
        jump_instruction <= '0';
        jump_register <= '0';
        upper_instruction <= '0';
        upper_pc_relative <= '0';
        multiply_instruction <= '0';
        rs1 <= (others => '0');
        rs2 <= (others => '0');
        rd <= (others => '0');
        alu_op <= ALU_ADD;
        case instruction(6 downto 0) is
            when "0110111" | "0010111" =>
                valid_encoding := true;
                immediate_form := true;
                upper_instruction <= '1';
                if instruction(6 downto 0) = "0010111" then
                    upper_pc_relative <= '1';
                end if;
            when "1100011" =>
                case instruction(14 downto 12) is
                    when "000" | "001" | "100" | "101" | "110" | "111" =>
                        valid_encoding := true;
                        branch_instruction <= '1';
                    when others => null;
                end case;
            when "1101111" =>
                valid_encoding := true;
                immediate_form := true;
                jump_instruction <= '1';
            when "1100111" =>
                if instruction(14 downto 12) = "000" then
                    valid_encoding := true;
                    immediate_form := true;
                    jump_instruction <= '1';
                    jump_register <= '1';
                end if;
            when "0000011" =>
                if instruction(14 downto 12) = "000" or instruction(14 downto 12) = "001" or
                   instruction(14 downto 12) = "010" or instruction(14 downto 12) = "100" or
                   instruction(14 downto 12) = "101" then
                    valid_encoding := true;
                    immediate_form := true;
                    memory_read <= '1';
                end if;
            when "0100011" =>
                if instruction(14 downto 12) = "000" or instruction(14 downto 12) = "001" or
                   instruction(14 downto 12) = "010" then
                    valid_encoding := true;
                    immediate_form := true;
                    memory_write <= '1';
                end if;
            when "0010011" =>
                immediate_form := true;
                case instruction(14 downto 12) is
                    when "000" => chosen_op := ALU_ADD; valid_encoding := true;
                    when "010" => chosen_op := ALU_SLT; valid_encoding := true;
                    when "011" => chosen_op := ALU_SLTU; valid_encoding := true;
                    when "100" => chosen_op := ALU_XOR; valid_encoding := true;
                    when "110" => chosen_op := ALU_OR; valid_encoding := true;
                    when "111" => chosen_op := ALU_AND; valid_encoding := true;
                    when "001" =>
                        if instruction(31 downto 25) = "0000000" then
                            chosen_op := ALU_SLL;
                            valid_encoding := true;
                        end if;
                    when "101" =>
                        if instruction(31 downto 25) = "0000000" then
                            chosen_op := ALU_SRL;
                            valid_encoding := true;
                        elsif instruction(31 downto 25) = "0100000" then
                            chosen_op := ALU_SRA; -- SRAI
                            valid_encoding := true;
                        end if;
                    when others => null;
                end case;
            when "0110011" =>
                if instruction(31 downto 25) = "0000000" then
                    valid_encoding := true;
                    case instruction(14 downto 12) is
                        when "000" => chosen_op := ALU_ADD;
                        when "001" => chosen_op := ALU_SLL;
                        when "010" => chosen_op := ALU_SLT;
                        when "011" => chosen_op := ALU_SLTU;
                        when "100" => chosen_op := ALU_XOR;
                        when "101" => chosen_op := ALU_SRL;
                        when "110" => chosen_op := ALU_OR;
                        when "111" => chosen_op := ALU_AND;
                        when others => valid_encoding := false;
                    end case;
                elsif instruction(31 downto 25) = "0000001" and instruction(14 downto 12) = "000" then
                    valid_encoding := true;
                    multiply_instruction <= '1';
                elsif instruction(31 downto 25) = "0100000" then
                    case instruction(14 downto 12) is
                        when "000" => chosen_op := ALU_SUB; valid_encoding := true;
                        when "101" => chosen_op := ALU_SRA; valid_encoding := true;
                        when others => null;
                    end case;
                end if;
            when others => null;
        end case;
        if valid_encoding then
            legal <= '1';
            alu_op <= chosen_op;
            if instruction(6 downto 0) /= "1101111" and instruction(6 downto 0) /= "0110111" and
               instruction(6 downto 0) /= "0010111" then
                rs1 <= instruction(19 downto 15);
            end if;
            if instruction(6 downto 0) = "0100011" or instruction(6 downto 0) = "1100011" then
                rs2 <= instruction(24 downto 20);
            else
                rd <= instruction(11 downto 7);
            end if;
            if immediate_form then
                use_immediate <= '1';
            else
                rs2 <= instruction(24 downto 20);
            end if;
        end if;
    end process;
end architecture;
