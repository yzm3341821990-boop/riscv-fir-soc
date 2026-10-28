# 第三步：寄存器组——看见数据在时钟沿被保存

ALU 已经能计算。接下来，寄存器组提供保存操作数与运算结果的位置。RISC-V 的 x0～x31 各为 32 位，当前实现提供两个组合读口和一个上升沿写口，x0 固定返回零。精确规则见 [寄存器组契约](regfile-contract.md)。

## 运行

在 ModelSim 底部 Transcript 的 `ModelSim>` 后输入：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/regfile32/baseline/run_regfile_gui.do}
```

脚本会先卸载当前仿真，再加载寄存器组测试，清理 Wave 中的旧信号，并按控制、写口、读口分组显示。成功时 Transcript 应出现下面的运行结果。**这两行是输出示例，观察即可，不要输入命令栏。**

```text
REGFILE32_PASS cycles=1610 value_checks=6440
REGFILE32_GUI_READY: inspect x1 write at the 15 ns rising edge.
```

黄色游标初始放在 17 ns。仿真完整结束时间为 16100 ns；游标用来查看较早时刻。Objects 中的当前值与游标历史值可能不同，应以 Wave 游标处的数据读这一段过程。

## 先看 x1 写入 5

10～20 ns 是第二条测试。此时 `rst=0`、`we=1`、`waddr=1`、`wdata=00000005`、`raddr1=1`。

- 12 ns：还没到写上升沿，`rdata1=00000000`。
- 15 ns：clk 从 0 变 1，寄存器 x1 接收写入。
- 17 ns：读口得到已保存的数据，`rdata1=00000005`。

`expected1` 和 `rdata1` 分别是期望和实际值；第二读口对应 `expected2`、`rdata2`。

需要放大时，在 Transcript 输入：

```tcl
WaveRestoreCursors {{Cursor 1} {17 ns} 0}
quietly wave cursor active 1
WaveRestoreZoom {10 ns} {20 ns}
```

## 各组信号

| 信号 | 作用 |
| --- | --- |
| clk | 时钟，低到高的边沿触发写入/同步复位 |
| rst | 高有效同步复位，在上升沿清零普通寄存器 |
| we | 写使能，0 时跨过上升沿也保持原值 |
| waddr | 写哪个寄存器，按十进制显示 |
| wdata | 写入的 32 位数据，按十六进制显示 |
| raddr1/raddr2 | 两个独立读地址，按十进制显示 |
| rdata1/rdata2 | 两个读口实际数据，按十六进制显示 |
| expected1/expected2 | testbench 在该阶段使用的参考值 |
| test_index | 当前测试周期序号 |

## 接着观察这些事件

| 时间 | 事件 | 要看到的行为 |
| --- | --- | --- |
| 0～10 ns | 初始同步复位，上升沿在 5 ns | x0 读为零；普通寄存器在有效复位沿后清零 |
| 10～20 ns | 写 x1=5，上升沿在 15 ns | 读 x1 从 0 变为 5 |
| 20～30 ns | 写 x2=7，上升沿在 25 ns | 读口 1 的 x1=5，读口 2 的 x2 从 0 变为 7 |
| 30～40 ns | we=0，却把写数据改成 DEADBEEF | x1 仍为 5，x2 仍为 7 |
| 40～50 ns | 尝试向 x0 写 FFFFFFFF | 读 x0 仍为 0，x1 仍为 5 |
| 50～60 ns | 覆盖写 x1=9，上升沿在 55 ns | x1 从 5 变为 9 |
| 60～70 ns | rst=1、we=1，上升沿在 65 ns | 沿前 x1=9、x2=7，沿后都清零，复位优先 |

这里的 10 ns 周期是 testbench 的激励安排，不是已验证的 FPGA 工作频率。读口在写上升沿前返回旧值，沿后返回新值；当前没有写入前旁路。

## 复现和源码

正式源码：[regfile32.vhd](../rtl/cpu/regfile32.vhd)。验证记录：[validation.json](../reports/step3-regfile/validation.json)。

在项目根目录重新生成并验证英文工作副本：

```powershell
& 'C:\Users\33418\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tools.run_regfile --build-dir 'F:\CodexWorkspace\outputs\riscv-fir-soc\regfile32'
```

Python 参考与向量工具仅使用标准库。完整的数值回归运行 `python -m tools.run_step1`；寄存器 RTL 回归还需要 ModelSim。

两个模块的工作副本都生成后，`python -m tools.check_modelsim_switch` 可在同一 ModelSim 进程中检查“已加载 ALU → 寄存器组 → ALU → 寄存器组”的加载顺序与数值完成。它以控制台模式执行正式 GUI 宏，检查卸载、目录切换和仿真结果；窗口显示效果由实际 GUI 使用确认。

若旧脚本曾提示 `Cannot change directory while a simulation is in progress`，原因是目录切换发生在旧仿真卸载之前。当前入口已将 `quit -sim` 放在 `cd` 前。更新源码后，应重新运行模块工具，刷新英文路径中的宏。

本轮覆盖 32×32 个读地址组合、全部可写地址、512 个固定种子随机周期和复位保持等情形，并执行两个受控 RTL 故障。计数反映这些测试已执行，不代表穷尽所有时序组合。

完成观察后，下一模块是译码器与立即数生成器：它们负责从 32 位机器指令中选出源/目标寄存器和运算控制。当前 ALU 与寄存器组还没有连接成能执行指令的 CPU。
