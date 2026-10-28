# 第十五步：打开并编译 Quartus 参考工程

后续进度：用户已反馈第一版 LED/KEY0 自检符合预期。新增数码管显示另见[第十六步](step16-display-guide.md)。以下保留第一版参考编译流程。

本步已经把工程整理到一个英文路径，不需要手工新建项目或逐个添加源码。当前先做电脑上的编译；不用连接开发板，也不运行 Programmer。

## 你现在的操作

1. 打开 **Quartus Prime Lite 17.0**。
2. 点击 **File → Open Project…**。
3. 在文件名框粘贴 `F:\CodexWorkspace\outputs\riscv-fir-soc\de2_115\riscv_fir_de2_115.qpf` 并打开。
4. 工程名应为 `riscv_fir_de2_115`，顶层应为 `de2_115_top`。参考器件为 `EP4CE115F29C7`。
5. 点击 **Processing → Start Compilation**，等待各阶段结束。
6. 在 Compilation Report 中查看 **Flow Summary** 的资源，以及 **TimeQuest Timing Analyzer** 的时序结果。综合/布局成功和时序通过是不同结论，不能只看是否生成了 SOF。

工程入口：[riscv_fir_de2_115.qpf](F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115/riscv_fir_de2_115.qpf)。上述英文目录由脚本生成，仓库中的 `fpga/de2_115` 是可复现模板，不是完整扁平化工程目录。

## 这个工程增加了什么

- 同步程序 ROM：保存已验证 C 驱动的实际机器码。
- 同步初值 ROM 与 RAM 装载器：每次上电或复位后覆盖全部 256 个 RAM 字，再释放 CPU。
- 按键复位同步逻辑：异步进入复位、经两级寄存器释放；板载 50 MHz 经真实二分频生成 25 MHz，内部逻辑使用同一系统时钟。
- 独立结果检查：检查真实 DMA 写入的八个输出、C done/errors 和程序末尾，错误或超时可锁存显示。
- LED 显示与时钟心跳。内部接口和 CPU/FIR 算法沿用已经通过仿真的版本。

参考 LED 定义：LEDR0=程序结束，LEDR1=自检通过，LEDR2=错误/超时，LEDR3=心跳。正常完成后 LEDR0、LEDR1 为高，LEDR2 为低，心跳持续变化。**这是设计与仿真规定的行为，尚未声称在实物上看到这些灯。**

## 参考目标与约束

参考工程使用 Cyclone IV E `EP4CE115F29C7`。板名已确认，完整芯片丝印和跳线还没有现场核实；此时的报告仅适用于参考目标，不能作为实际器件确认。

时钟与 I/O 引脚根据 [Terasic 官方 DE2-115 用户手册](https://www.terasic.com.tw/wiki/images/f/ff/DE2_115_User_manual_2013.pdf)的表 4-2、4-3、4-5、4-8 配置：CLOCK_50 在 Y2、50 MHz、3.3 V；KEY0 在 M23，其电压随 JP7，工程采用默认 2.5 V；四个红灯在 G19/F19/E19/F21，2.5 V。实际下载前须核对完整 FPGA 料号和 JP7 档位。

首次 50 MHz 尝试完成综合和布局布线，但最差 setup slack 为 -5.474 ns，未通过时序，历史报告保存在 `reports/step15-quartus/first-50mhz/`。当前电路用真实二分频生成 25 MHz，并在 SDC 中分别定义 20 ns 输入时钟和 divide_by=2 的生成时钟。异步按键只到复位同步链的路径被排除，链内时钟路径仍分析；人眼观察的 LED 输出没有外部采样时钟，显式作为异步输出排除。没有仅修改约束来掩盖内部违例。

## 本机实际编译结果

2026-10-28 使用 Quartus Prime Lite 17.0.0 Build 595 对参考器件完成全编译，约用时 4 分 30 秒；重新编译时用时可能不同。综合、布局布线、汇编和静态时序均成功，0 errors、0 critical warnings、16 条普通 warnings。生成的 SOF 位于工程目录的 `output_files/riscv_fir_de2_115.sof`，目前仅生成、未下载。

| 项目 | 结果 |
| --- | ---: |
| 逻辑单元 | 26,980 / 114,480（24%） |
| 寄存器 | 11,271 |
| 逻辑存储位 | 9,216 |
| 9 位乘法器元素 | 8 / 532 |
| 外部输入 / 内部系统时钟 | 50 MHz / 25 MHz |
| 已分析角落中最差 setup slack | +7.131 ns |
| 已分析角落中最差 hold slack | +0.180 ns |
| 未约束时钟及输入/输出端口计数 | 均为 0 |

普通警告完整保留在报告中：LED 尚未显式指定驱动强度/转换速率；时钟输入还有 Cyclone IV 电气接口要求提示；布线器曾提示拥塞，但最终时序通过。其余包括工具许可提示、库中仿真元值选择和未使用的调试信号/乘法器位裁剪。当前不据此声称已完成实物 I/O 电气核验。两级复位同步链被识别，未获得数值 MTBF 结论。

目前双端口共享 RAM 被实现为寄存器及选择逻辑，未推导为 M9K；报告中的两块 M9K 来自程序和初值 ROM。后续优化共享 RAM 推导时，需要重新验证读写冲突行为、启动装载、功能及资源/时序，不能直接沿用这次报告。

## 重新生成与验证

开发者命令：

```sh
python -m tools.prepare_de2_project
python -m tools.run_de2_boot
quartus_sh --flow compile riscv_fir_de2_115
python -m tools.collect_de2_build
```

Python 命令在仓库根目录运行；`quartus_sh` 在生成的英文工程目录运行，必要时使用本机 Quartus 可执行文件的完整路径。收集脚本核对源码、生成 ROM、拟合后的六个引脚、各编译阶段、时序余量及未约束路径计数，并保存原始报告和 SOF 哈希。Quartus 17 自动追加的版本元数据、同义未用引脚设置和 SOURCE 根分区默认设置单独记录，实际 QPF/QSF/SDC 也随报告保存；器件、引脚、RTL 或其他设置修改仍使收集失败。

已有 ModelSim 检查覆盖自动上电启动、完成后重启、装载中复位和运行中复位；四次完整运行通过。种子 ROM 地址错误、过早释放 CPU、把种子数据全部写为零的三项受控错误均由运行中的断言发现。

原 C 固件本身也检查八个结果。板级监控另检查与参考输入对应的实际 DMA 输出，因此即使错误初始化把输入、系数和 C 自检参考一起清成零，也不能借此获得 PASS。

主要文件：

- [可综合顶层](../rtl/board/de2_115_top.vhd)
- [工程与引脚模板](../fpga/de2_115/riscv_fir_de2_115.qsf)、[时钟约束](../fpga/de2_115/board.sdc)
- [启动/复位契约](de2-reference-contract.md)
- [启动仿真报告](../reports/step15-quartus/boot-validation.json)
- [Quartus 验证、资源及 SOF 哈希](../reports/step15-quartus/quartus-validation.json)
- [原始综合、布局布线、时序及引脚报告](../reports/step15-quartus/quartus/)

Quartus 的综合、布局布线、时序及汇编报告已分别归档；下载与实物结果另行记录。本页编译脚本不执行硬件编程；用户随后报告已下载并通过 LED/KEY0 检查。没有配置 Flash 擦写记录。
