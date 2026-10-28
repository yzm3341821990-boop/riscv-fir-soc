library ieee;
use ieee.std_logic_1164.all;

package alu_pkg is
    subtype alu_operation is std_logic_vector(3 downto 0);
    constant ALU_ADD  : alu_operation := "0000";
    constant ALU_SUB  : alu_operation := "0001";
    constant ALU_AND  : alu_operation := "0010";
    constant ALU_OR   : alu_operation := "0011";
    constant ALU_XOR  : alu_operation := "0100";
    constant ALU_SLL  : alu_operation := "0101";
    constant ALU_SRL  : alu_operation := "0110";
    constant ALU_SRA  : alu_operation := "0111";
    constant ALU_SLT  : alu_operation := "1000";
    constant ALU_SLTU : alu_operation := "1001";
end package;
