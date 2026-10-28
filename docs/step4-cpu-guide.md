# 第四步：CPU 自己执行三条指令

最新 [第十步](step10-c-program-guide.md) 已运行编译的裸机 C 示例；本页保留对应历史阶段的学习内容及限制。

本页为历史阶段示例。当前已加入 [第九步的字节与半字读写](step9-subword-guide.md)；原程序和加载命令继续可用，当前能力以 CPU 契约和最新报告为准。

这一阶段把 ALU、寄存器组、立即数生成器、译码器与 PC/控制状态机连接起来。testbench 提供时钟、复位和同步 ROM；CPU 根据机器指令自行选取寄存器、运算并写回。

本页记录首次连接 CPU 时的 ADDI、ADD、SUB 三指令阶段；后续在[第五步](step5-alu-isa-guide.md)扩展为 19 种 ALU 指令，在[第六步](step6-memory-guide.md)加入 LW/SW 与 RAM，在[第七步](step7-control-flow-guide.md)加入分支跳转，并在[第八步](step8-upper-immediate-guide.md)加入 LUI/AUIPC。这里的三指令程序和加载命令继续可用。完整 RV32I、流水线和 C 运行环境仍待实现。接口与周期规则见 [最小 CPU 契约](tiny-cpu-contract.md)。

## 运行这一段程序

源程序在 [programs/demo.S](../programs/demo.S)，对应机器码在 [programs/demo.hex](../programs/demo.hex)：

| 地址 | 机器码 | 汇编 | 结果 |
| --- | --- | --- | --- |
| 00000000 | 00500093 | ADDI x1,x0,5 | x1=5 |
| 00000004 | 00700113 | ADDI x2,x0,7 | x2=7 |
| 00000008 | 002081B3 | ADD x3,x1,x2 | x3=12 |

在 ModelSim 的 Transcript 提示符后，只复制下面这一条命令，再按 Enter：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu/baseline/run_cpu_gui.do}
```

脚本会先卸载当前仿真，再切换目录和编译，支持从之前的 ALU/寄存器组界面直接执行。以下是预期的自动输出示例，**不要把它们作为命令输入**：

```text
TINYCPU_COMMIT pc=00000000 rd=1 value=00000005
TINYCPU_COMMIT pc=00000004 rd=2 value=00000007
TINYCPU_COMMIT pc=00000008 rd=3 value=0000000C
TINYCPU_PASS retired=3 warmup=0
TINYCPU_GUI_READY x1=5 x2=7 x3=12: inspect commits at 45, 75 and 105 ns.
```

实际输出会带 ModelSim 的 `#`、时间和级别等前缀。提交检查在上升沿后 1 ns 执行，所以日志时间为 46/76/106 ns；写回本身发生在 45/75/105 ns 的上升沿。

## 这次看什么

波形中有三组：时钟与指令、提交记录、实际寄存器内容。先只看 `x1/x2/x3`。

| 时刻 | 发生的事 | 寄存器变化 |
| --- | --- | --- |
| 5、15 ns | 有效同步复位沿 | 普通寄存器清零，PC=0 |
| 45 ns | 第一条指令写回 | x1 从 0 变成 5 |
| 75 ns | 第二条指令写回 | x2 从 0 变成 7 |
| 105 ns | 第三条指令写回 | x3 从 0 变成十六进制 0000000C，即十进制 12 |

脚本把游标放在 105.5 ns，此时三次写回均已生效。最初 0～5 ns 的普通寄存器可能显示 X，表示还没有经过有效复位；这不表示已经执行了错误指令。

然后看 `commit_valid`：它为 1 时，下列数据共同描述刚完成的指令：

- `commit_pc`：这条指令的地址。
- `commit_rd`：结果写入哪个寄存器。
- `commit_value`：实际写回的数据。

例如第三次提交时，`commit_pc=00000008`、`commit_rd=3`、`commit_value=0000000C`，意思是“地址 8 的指令刚把 12 写入 x3”。

此时当前 `PC` 已经更新为 0000000C，即下一条指令的地址。PC 和计算结果恰好都出现 0C，含义不同；读本次提交应使用 commit_pc。

## 为什么每条指令分三拍

当前程序存储器按同步读建模，不能在刚给出地址的同一时刻就假定拿到了数据：

1. state=0：请求取指，让 ROM 在上升沿采样 PC。
2. state=1：在下一拍锁存 ROM 已返回的指令。
3. state=2：读取寄存器、经过 ALU，在上升沿写回并更新 PC。

三个时钟完成一条指令，状态依次循环为 0→1→2→0。等待和周期是这版执行结构的约定；后续会逐步扩展功能并改造流水线。

## 文件与复现

| 文件 | 作用 |
| --- | --- |
| `rtl/cpu/decode_tiny.vhd` | 从指令中提取寄存器地址，判断 ADDI/ADD/SUB 并选择控制信号 |
| `rtl/cpu/imm_i.vhd` | 把 12 位立即数符号扩展为 32 位 |
| `rtl/cpu/tiny_cpu.vhd` | 连接现有模块，保存 PC/指令并控制三拍执行 |
| `sim/tb/tb_tiny_cpu.vhd` | 同步 ROM 模型、复位/时钟激励与提交断言 |
| `model/tiny_cpu.py` | 小型汇编编码器和独立架构参考 |
| `tools/generate_cpu_vectors.py` | 生成各程序和期望轨迹/最终寄存器 |
| `reports/step4-tiny-cpu/` | 本轮真实仿真记录及故障注入日志 |

在项目根目录重新生成、编译并运行全套用例：

```powershell
& 'C:\Users\33418\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tools.run_cpu --build-dir 'F:\CodexWorkspace\outputs\riscv-fir-soc\tiny_cpu'
```

之后回到 ModelSim，重新输入上面的 `do` 命令查看示范。正式修改写在项目源码中，英文工作目录只是生成的运行副本。该命令验证当前最新指令子集，最新报告位置见 [第十步说明](step10-c-program-guide.md)；本页保留的 step4 报告是当时三指令版本的证据。

测试包括负立即数、回绕、寄存器依赖、x0/x31、严格非法解码、FAULT 后复位状态检查、固定种子随机程序及两种中途复位用例。除提交包外，工具直接检查实际寄存器存储值；两项 RTL 故障会验证检查器确实能拒绝错误的 PC 步长和立即数扩展。

`python -m tools.check_modelsim_switch --include-cpu` 在同一 ModelSim 进程中回归旧模块与新 CPU 的加载切换。此检查以控制台模式执行 GUI 宏，覆盖卸载、目录切换、加载与程序结果；不把它称作窗口渲染验证。

本步形成了能执行三条指令的最小通路。后续第五至第八步已扩展运算、整字访存、控制转移与 U 型常量/地址计算，第九步加入字节与半字读写后，当前共 37 种指令；完整 RV32I、五级流水线和 FIR 加速器接口仍待实现。综合、时序和上板验证分别保留证据。
