# 第五步：让程序使用位运算、移位与比较

最新 [第十步](step10-c-program-guide.md) 已运行编译的裸机 C 示例；本页保留对应历史阶段的学习内容及限制。

本页为历史阶段示例。当前已加入 [第九步的字节与半字读写](step9-subword-guide.md)；原程序和加载命令继续可用，当前能力以 CPU 契约和最新报告为准。

第四步证明了 CPU 能自行取指、计算和写回。这一步扩展译码器，让程序可以调用 ALU 已有的十种运算，加上立即数形式共 19 条指令。时钟、同步复位、三拍执行和提交接口保持原契约。

本页记录第五步的运算阶段，示范命令继续可用。后续在[第六步](step6-memory-guide.md)加入 LW/SW 与同步 RAM，[第七步](step7-control-flow-guide.md)加入循环，[第八步](step8-upper-immediate-guide.md)加入常量和地址计算；ALU 指令仍为三拍，LW 增加一拍。

| 用途 | 寄存器形式 | 立即数形式 |
| --- | --- | --- |
| 加减 | ADD、SUB | ADDI |
| 位运算 | AND、OR、XOR | ANDI、ORI、XORI |
| 移位 | SLL、SRL、SRA | SLLI、SRLI、SRAI |
| 比较 | SLT、SLTU | SLTI、SLTIU |

这组能力可以用于提取数据字段、调整定点数位宽、比较大小和组合数值。FIR 的循环、访存和乘加仍需后续步骤完成；目前还不能运行完整的 FIR 软件。

## 运行七条指令

在 ModelSim 底部 Transcript 提示符后复制这一条命令，按 Enter：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu/baseline/run_ops_gui.do}
```

脚本自动卸载之前的仿真、重新编译并运行 `alu_demo`。原来的 `run_cpu_gui.do` 仍显示 x1=5、x2=7、x3=12 的三指令示范。

源程序见 [alu_demo.S](../programs/alu_demo.S)，逐字对应的 ROM 文件见 [alu_demo.hex](../programs/alu_demo.hex)。

| 写回时刻 | 指令 | 写回值（十六进制） | 含义 |
| --- | --- | --- | --- |
| 45 ns | ADDI x1,x0,-8 | FFFFFFF8 | 32 位补码中的 -8 |
| 75 ns | ADDI x2,x0,1 | 00000001 | 后面右移一位、与 1 比较 |
| 105 ns | SRL x3,x1,x2 | 7FFFFFFC | 右移一位，高位补 0 |
| 135 ns | SRA x4,x1,x2 | FFFFFFFC | 右移一位，高位补符号位，得到 -4 |
| 165 ns | SLT x5,x1,x2 | 00000001 | 有符号解释：-8 < 1 成立 |
| 195 ns | SLTU x6,x1,x2 | 00000000 | 无符号解释：FFFFFFF8 < 1 不成立 |
| 225 ns | ANDI x7,x1,15 | 00000008 | 保留 x1 的最低四位 |

## 怎样看这次波形

脚本把游标放在 225.5 ns，七次写回均已完成。先在实际寄存器组中看 x3/x4 和 x5/x6：

- x3 与 x4 的原始输入相同，只是右移方式不同。SRL 补 0 后得到大的正整数；SRA 保留符号，得到 -4。
- x5 与 x6 比较的是同两串 32 位数据，只是数值解释不同。寄存器保存位串，指令决定按有符号数还是无符号数计算。
- x7=8，展示 ANDI 怎样从一个数中取出最低四位。

`commit_valid=1` 时，`commit_pc/rd/value` 共同描述刚完成的指令。例如 135 ns 的 `commit_pc=0000000C`、`commit_rd=4`、`commit_value=FFFFFFFC`，表示地址 12 的 SRA 刚把 -4 写入 x4。

Transcript 应自动出现 `TINYCPU_PASS retired=7 warmup=0` 与 `TINYCPU_OPS_GUI_READY ...`。这些是输出标记，不需要输入。检查器在上升沿后等待 1 ns，所以提交日志为 46、76、106、136、166、196、226 ns；实际写回沿比日志早 1 ns。

## 代码与验证

主要 RTL 修改在 [decode_tiny.vhd](../rtl/cpu/decode_tiny.vhd)。它从 opcode/funct3/funct7 选择已有 ALU 操作，禁止把保留移位编码或未实现的 M 扩展误译成普通运算。ALU、寄存器组和三拍状态机继续复用。

完整规则见 [CPU 契约](tiny-cpu-contract.md)。尤其注意 SLTIU 的立即数先符号扩展，再按无符号数比较；SRAI 的编码高位选择算术右移，移位量仍只取低五位。

在项目根目录重新运行：

```powershell
& 'C:\Users\33418\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tools.run_cpu --build-dir 'F:\CodexWorkspace\outputs\riscv-fir-soc\tiny_cpu'
```

本页保留的 [step5-alu-isa/validation.json](../reports/step5-alu-isa/validation.json) 是当时 19 指令版本的证据，检查每次提交、三拍节奏、最终实际寄存器、复位和 FAULT，并拒绝三项故意损坏的 RTL。上述运行命令验证当前最新版本，报告写入 [第十步目录](../reports/step10-c-program/validation.json)。

`python -m tools.check_modelsim_switch --include-cpu` 还会在同一个 ModelSim 进程中检查旧示范与新示范的加载切换。它以控制台模式执行 GUI 宏，检查加载和计算结果；窗口布局仍由实际打开 GUI 时观察。

本阶段证据为 Python 测试与 RTL 功能仿真。后续第六步已实现 LW/SW 数据访存，[第七步](step7-control-flow-guide.md) 已加入条件分支及 JAL/JALR；完整 RV32I、乘除、流水线或 C 运行环境仍待实现，Quartus 综合、时序和上板验证尚未进行。
