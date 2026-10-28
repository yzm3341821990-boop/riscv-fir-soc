# 第六步：把数据存进 RAM，再读回来

最新 [第十步](step10-c-program-guide.md) 已运行编译的裸机 C 示例；本页保留对应历史阶段的学习内容及限制。

本页为历史阶段示例。当前已加入 [第九步的字节与半字读写](step9-subword-guide.md)；原程序和加载命令继续可用，当前能力以 CPU 契约和最新报告为准。

本页保留第六步的学习示范与历史验证范围。后续已加入 [第七步的循环求和](step7-control-flow-guide.md) 与 [第八步的常量及地址计算](step8-upper-immediate-guide.md)；下面的读写示范可继续在当前 CPU 上运行。

CPU 已能执行 19 种运算指令；现在增加 LW 和 SW，共支持 21 种指令。LW 把内存中的 32 位数读进寄存器，SW 把寄存器中的 32 位数保存到内存。FIR 后续需要在 RAM 中保存输入、系数与结果，这一步先证明读写通路正确。

## 运行演示

在 ModelSim 底部 Transcript 输入这一条命令：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu/baseline/run_memory_gui.do}
```

脚本自动卸载之前的仿真、编译并运行八条指令，游标放在 275.5 ns。原先的 `run_cpu_gui.do` 和 `run_ops_gui.do` 继续可用。

源程序在 [memory_demo.S](../programs/memory_demo.S)，实际 ROM 字码在 [memory_demo.hex](../programs/memory_demo.hex)。

| 写回/完成时刻 | 指令 | 发生的事 |
| --- | --- | --- |
| 45 ns | ADDI x1,x0,64 | x1=64，作为数据地址 |
| 75 ns | ADDI x2,x0,12 | x2=12，作为待保存的数据 |
| 105 ns | SW x2,0(x1) | 把 12 存入字节地址 64 |
| 145 ns | LW x3,0(x1) | 从字节地址 64 读回，x3=12 |
| 175 ns | ADDI x4,x3,5 | 使用读回的数继续计算，x4=17 |
| 205 ns | SW x4,4(x1) | 把 17 存入字节地址 68 |
| 245 ns | LW x5,4(x1) | 从字节地址 68 读回，x5=17 |
| 275 ns | SUB x6,x5,x3 | 17−12，得到 x6=5 |

`SW x2,0(x1)` 中的地址是 x1+0，数据来自 x2；`LW x5,4(x1)` 中的地址是 x1+4，结果写入 x5。数字 4 是字节偏移，一个 32 位字占四个字节。

## 先看哪些波形

先看最下方的 `RAM_byte64`、`RAM_byte68`，以及 x3、x5、x6：

| 波形 | 最终十六进制值 | 十进制含义 |
| --- | --- | --- |
| RAM_byte64 | 0000000C | 地址 64 保存 12 |
| RAM_byte68 | 00000011 | 地址 68 保存 17 |
| x3 | 0000000C | 第一次读回 12 |
| x5 | 00000011 | 第二次读回 17 |
| x6 | 00000005 | 使用两次读回的数据计算得到 5 |

内部 RAM 是 256 个 word 的数组，所以字节地址 64 对应 `bank(16)`，字节地址 68 对应 `bank(17)`。脚本用字节地址作标签，避免把数组下标与 CPU 地址混淆。程序 ROM 和数据 RAM 是两个独立空间。

再看 `Data RAM interface` 这一组：

- `dmem_req=1` 时，上升沿接受一笔访问。
- `dmem_we=1` 表示写，`dmem_we=0` 表示读；只在 req=1 时有意义。
- `dmem_addr` 是字节地址，示范中为十六进制 40 或 44。
- `dmem_wdata` 是写数据，`dmem_rdata` 是同步读返回的数据。

第一次 SW 在 105 ns 写入 12。第一次 LW 在 135 ns 发出读请求，RAM 随后输出 12，CPU 到 145 ns 才把它写入 x3。因此 LW 比普通运算多一拍。第二次读请求为 235 ns，x5 写回为 245 ns。

Transcript 最后应自动显示 `TINYCPU_PASS retired=8 warmup=0`、`TINYCPU_MEMORY_PASS requests=4 warmup_requests=0` 和 `TINYCPU_MEMORY_GUI_READY ...`。它们是输出标记，不要输入。

## 本版硬件约定

数据 RAM 为 1 KiB，仅支持四字节对齐的整字读写，合法起始地址为 0、4、…、1020。越界、未对齐地址以及尚未实现的访存指令会令 CPU 在该条指令处进入 FAULT，不发出 RAM 请求。

CPU 复位清除寄存器、PC 和控制状态，保留 RAM 已保存的内容。数组初始为 0，RAM 读输出在首次有效读之前可以为 X；CPU 不会提前使用它。详细接口、周期和故障规则见 [CPU 契约](tiny-cpu-contract.md)。

新增源码包括 [imm_s.vhd](../rtl/cpu/imm_s.vhd) 的 store 立即数拼接和 [data_ram.vhd](../rtl/cpu/data_ram.vhd) 的同步数据 RAM；[tiny_cpu.vhd](../rtl/cpu/tiny_cpu.vhd) 增加读写接口与 LOAD_WRITEBACK 状态。

## 验证与复现

在项目根目录执行：

```powershell
& 'C:\Users\33418\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tools.run_cpu --build-dir 'F:\CodexWorkspace\outputs\riscv-fir-soc\tiny_cpu'
```

本步历史报告在 [step6-memory/validation.json](../reports/step6-memory/validation.json)，绑定该报告记录的源码哈希。上述命令现在运行当前完整 CPU 回归，结果写入 [step8-upper-immediate/validation.json](../reports/step10-c-program/validation.json)。除提交包与最终寄存器外，还逐笔核对内存访问，并比较每个用例结束及 CPU 复位后的全部实际 RAM 字。包括地址边界、负偏移、地址回绕、写后读、寄存器别名、LW x0、错误访问无副作用，以及读请求已接受但未写回时的复位。

故障注入保留前阶段的三项，另测试 store 错用立即数、load 把地址写进寄存器、S 立即数错误零扩展与 pending load 忽略复位。加载切换回归命令仍为 `python -m tools.check_modelsim_switch --include-cpu`。

本步完成范围为 Python 与 RTL 功能仿真。尚未进行 Quartus 综合、M9K 推断/资源检查、时序分析或上板；分支跳转已在第七步加入，其他访存宽度、乘除和流水线仍待实现。
