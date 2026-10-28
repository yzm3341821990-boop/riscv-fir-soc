# Source for the three-word demo ROM. Only ADDI and ADD are needed here.
# Simulation stops after the third commit; there is no halt instruction.
    addi x1, x0, 5
    addi x2, x0, 7
    add  x3, x1, x2
