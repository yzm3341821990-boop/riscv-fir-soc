# 第二十步：32 KiB M9K 与长块 FIR

本步已经完成 RTL、C 固件、功能仿真与独立板级候选。共享数据 RAM 从 1 KiB 扩到 32 KiB，使用 `altera_mf.altsyncram` M9K 原语；程序 ROM 仍为独立 1 KiB。实现 64/256/1024 点的完整 C 调用比较，保留同一五级 CPU、32 抽头定点语义及 1/2/4 路 MAC。

**当前交付状态：r1 已由用户编译，25 MHz 时序通过，用户已反馈上板行为符合预期。** 本版实际占 7464 LE、3718 寄存器、48 块 M9K，setup/hold 最差余量 +9.726/+0.152 ns。SOF 与源码身份已核对；step19 的实现结论只用于其自身版本。step18 和 step19 的原工程、SOF、哈希与用户反馈均保留。后续源码没有上传 GitHub。

## r1 修订：Quartus 17 的 10481 库绑定错误

用户首次编译在分析与综合阶段报告 `Error (10481)`：`altera_mf` 中没有可直接引用的 `altsyncram` 主单元。旧版使用直接 entity 实例化，仿真库有实体实现，因此 ModelSim 通过；Quartus 17 的综合库通过 `altera_mf_components` 提供组件接口，需要采用组件实例化。

r1 仅在 `shared_ram_m9k.vhd` 引入 `use altera_mf.altera_mf_components.all;`，并将 `memory : entity altera_mf.altsyncram` 改为 `memory : altsyncram`。存储参数、端口、时序、握手与算术逻辑均保持一致。写法依据[官方 IP 实例化示例，第 4.11 节](https://www.intel.com/programmable/technical-pdfs/qps-ugs.pdf)和本机 Quartus 17 的综合组件声明。

首次失败的原始报告、失败源码与 QSF 已[归档](../reports/step20-large-block/quartus-first-failure-10481/failure.json)。新增[组件接口检查](../reports/step20-large-block/binding-validation.json)：在只含实际综合组件声明、没有仿真实体的隔离库中，旧写法确定失败，r1 写法分析通过。该检查使用 ModelSim 编译器，并不替代实际 Quartus 综合/布局布线。

当前原工程中的 RAM 文件已更新，原有六项 GUI 默认设置已核对并保留。用户直接重编译原 QPF 即可。初版冻结 ZIP 继续保留作历史记录，后续使用带 `step20-r1` 的修订包。随后用户已完成 r1 重编译，原始报告及 SOF 身份通过只读审阅，见下一节。

## r1 实际实现结果（2026-10-29）

用户在 Quartus Prime Lite 17.0.0 Build 595 完成全编译，18:00:44 生成 SOF。分析、布局布线、汇编均成功；25 MHz 的三个工况共 18 项时序摘要全部非负、TNS 为零，未约束摘要六项均为零。参考器件 EP4CE115F29C7，66 个实际引脚及 I/O 标准与清单匹配；四个 FIR 乘法通道均在 Fitter 中保留。0 条关键警告、27 条普通警告已保留和归类。

| 项目 | 实际结果 |
| --- | ---: |
| LE | 7464 / 114480 |
| 寄存器 | 3718 |
| 总 M9K | 48 |
| 32 KiB 数据 RAM | 32 块 M9K，真双端口、同一时钟、8192×32 |
| 初值 ROM | 16 块 M9K，综合成 8192×16 位 |
| 总存储位 | 393216 |
| 9 位乘法器元素 | 14 |
| 最差 setup / hold | +9.726 / +0.152 ns |

32 KiB RAM 确认落入 M9K。旧 step19 p4 为 28130 LE；新版为 7464 LE，工程占用减少约 73.5%。两版的存储结构、初值镜像、程序与任务长度均不同，这不是只更改 RAM 一个变量的面积实验，也不能用于推断软件/硬件的板上性能比。

[原始实现报告和哈希](../reports/step20-large-block/quartus-validation.json)、[交付身份](../reports/step20-large-block/implementation-delivery.json)。已核对 SOF SHA256：`1dcf5141800c418da3a6b9a4881fe586b0ef18d8c9483e9cdee6cdabe053d5b4`。独立保留的已审阅 SOF 在本机：

```text
F:/CodexWorkspace/outputs/riscv-fir-soc/step20-r1-verified/riscv_fir_de2_large.sof
```

下一步由用户通过 Programmer 下载这一份 SOF，核对 SW3=1 为 `00006155`、下面八个输出、正常 LED 和 KEY0 重跑行为。当前未收到 step20 实物观察，以下显示值仍按仿真期望记录。

## 1. 本次打开哪个文件

本机已经生成的独立工程为：

```text
F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_large/riscv_fir_de2_large.qpf
```

1. Quartus 中选择 **File → Open Project**，打开以上 QPF。
2. 核对顶层 `de2_115_large_top`，参考器件 `EP4CE115F29C7`。
3. 由用户执行 **Processing → Start Compilation**。本次配置固定 1024 点、四路 FIR，50 MHz 输入实际二分频为 25 MHz。
4. 编译结束后保留整个 `output_files/`。本聊天会只读核对原始报告、源码与镜像身份、M9K 实例、引脚及所有 setup/hold 结果。
5. 核对通过后，由用户通过 USB-Blaster / JTAG 下载 `output_files/riscv_fir_de2_large.sof`，观察下面的数值和按键行为。

引脚及电压沿用已核对的 DE2-115 显示接口：JP7=2.5 V、JP6=3.3 V，完整清单见 [pins.json](../fpga/de2_display/pins.json)。本步不改变板卡跳线。引脚共 66 个。

## 2. 下载后的预期

启动装载器先将 8192 个初始字装入 RAM，再释放 CPU。C 配置 32 个系数、处理 1024 个输入，并在完整调用计时结束后核对全部 1024 个输出。板级监测器同时检查所有 DMA 写地址与数量，额外核对前八个值，并捕获实际写回结果用于显示。

正常状态为 **LEDR0/1 亮，LEDR2 灭，LEDR3 闪**。自检完成前数码管为空白；发生故障则 LEDR0/2 亮、LEDR1 灭，显示 `EEEEEEEE`。

| SW3 | SW2..SW0 | HEX7..HEX0 预期值 | 有符号十进制含义 |
| --- | --- | --- | ---: |
| 0 | 000 | `00000C58` | 3160 |
| 0 | 001 | `FFFFF218` | -3560 |
| 0 | 010 | `000009F7` | 2551 |
| 0 | 011 | `00000F25` | 3877 |
| 0 | 100 | `FFFFEEBC` | -4420 |
| 0 | 101 | `FFFFFB0E` | -1266 |
| 0 | 110 | `00002165` | 8549 |
| 0 | 111 | `FFFFFDD1` | -559 |
| 1 | 任意 | `00006155` | 整段自检 24917 拍 |

按住 **KEY0** 时清除状态并熄灭显示；松开后重新装载全部 RAM，重跑同一程序。结果及周期应与上次一致。这里列的是经过整板功能仿真验证的期望值，收到用户观察后再另行记录实际结果。

`24917` 包括冷调用、诊断读取、全部 1024 点 C 检查及终止监测，排除启动装载。基准的四路冷调用是 `13608` 拍；FIR 内核是另一计时边界。三者分别报告，数码管值不能代入软件/硬件调用比。

## 3. 完整调用比较

下表来自实际 ModelSim C 执行，DMA 没有额外等待。软件与硬件模式对每个长度使用同一初始 RAM、相同 CPU、编译器和基础编译选项。CPU 本身也支持 MUL。软件使用 `-O1` 的 C 定点 FIR，跳过块首之前的零历史，按 64 位累加语义计算并在最后舍入/饱和；不是最优手工汇编实现的性能上限。

| 长度 | C 软件 | 冷调用 P1 | 冷调用 P2 | 冷调用 P4 | 驻留 P1 | 驻留 P2 | 驻留 P4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 24045 | 2662 | 1638 | 1126 | 2403 | 1379 | 867 |
| 256 | 116856 | 9766 | 5670 | 3622 | 9507 | 5411 | 3363 |
| 1024 | 489233 | 38184 | 21800 | 13608 | 37925 | 21541 | 13349 |

块首之前按零历史处理，C 会跳过这些乘加。因此长块的平均软件工作量也更接近完整 32 抽头；不同长度间的比值变化同时受软件边界工作量和配置摊销影响。

1024 点时，软件与四路冷调用的周期比为 **35.95×**；与四路系数驻留调用的周期比为 **36.65×**。这是本组功能仿真的完整调用周期关系，尚无物理板上的成对计时。冷调用包含系数装载；驻留模式在主计时区间前装载系数，该行为也由轨迹检查器核对。

全部 45 组执行还包括周期性 DMA 阻塞：硬件模式在每七个周期的前三个周期不接受 DMA。数据、所有输出和最终状态均保持正确。1024 点 P2 在这个固定等待相位下，内核与完整调用周期均未增加；不能据此推断任意等待条件没有代价。逐次数据见 [measurements.csv](../reports/step20-large-block/measurements.csv)，配对条件和比值见 [comparison.json](../reports/step20-large-block/comparison.json)。

![长块完整调用周期](../artifacts/step20/large-block-complete-call.png)

## 4. 存储和数据布局

数据 RAM 字节地址为 `0..32767`。CPU A 端口支持字节写使能；DMA B 端口传送完整字。不同地址可并行，同一字且任一端口写时由 A 优先、B 等待。复位取消 DMA 握手/响应，但不清整个存储阵列；启动装载器负责重装初值。

| 1024 点固件对象 | RAM 字节地址 |
| --- | ---: |
| samples[1024] | 2048 |
| coefficients[32] | 6144 |
| outputs[1024] | 6272 |
| expected[1024] | 10368 |
| marker | 14464 |
| done / errors | 14468 / 14472 |
| 初始 sp | 32768 |

FIR 页仍为 `0x40003000`，寄存器偏移见[既有 MMIO 语义](fir-mmio-contract.md)。新实体将任务上限扩为 4096 点，并检查两个缓冲完整位于 32 KiB RAM、对齐且互不重叠。本次 C 基准按原方案选择 64/256/1024 点，并在 RAM 中保留完整参考结果和栈；4096 点边界另用组件测试。单独 MMIO 测试覆盖两个各占 16 KiB 的输入/输出缓冲及 4096 点边界。

新文件为 `pipeline_large_cpu`、`fir_mmio_large`、`shared_ram_m9k`、`pipeline_large_soc` 和 `de2_115_large_top`。原版实体继续保留。M9K 原语通过已安装的厂家库使用，没有复制厂家实现代码。Cyclone IV M9K 的真双端口和冲突规则见[官方手册第 3 章，3–11、3–17 页](https://cdrdv2-public.intel.com/654744/cyiv-51003.pdf)；本项目在外部排序冲突访问，避免双写同址。

## 5. 实际验证记录

| 检查 | 实际结果 |
| --- | --- |
| Python | 242 项测试通过；原始 13 组向量可重现；数值错误控制全部拒绝 |
| M9K 模型 | 厂家 `altera_mf.altsyncram` 仿真；8192 字全地址、字节掩码、并行、冲突和复位保持检查 |
| CPU 保护 | 17 个合法/越界/对齐/MMIO 地址场景 |
| 访问错误控制 | 6 个 RAM/CPU 故障全部被断言拒绝 |
| 大块 MMIO | P1/P2/P4 各重复执行两次 4096 点任务；每次比较整个 8192 字银行，另有三组协议/复位检查；3 个边界故障被拒绝 |
| C 系统 | 45 次执行，2080791 条提交逐条 ISA 回放；每例核对 8192 个 RAM 字和 32 个寄存器及全部输出 |
| 板级功能仿真 | 四次完整启动/复位，32 项结果选择，外部 50 MHz 输入时钟独立秒表核对 24917 拍 |
| 板级故障 | ROM 使能、双倍计数、错误快照、提前完成四项均拒绝；只破坏第 1024 个输出时，观察到 C 写入错误并进入 `EEEEEEEE` |

报告入口：[总交付检查](../reports/step20-large-block/delivery-audit.json)、[存储](../reports/step20-large-block/memory-validation.json)、[MMIO](../reports/step20-large-block/mmio-validation.json)、[C 系统](../reports/step20-large-block/system-validation.json)、[整板](../reports/step20-large-block/board-validation.json)、[Python](../reports/step20-large-block/python/validation.json)。历史阶段数量不与本表相加成独立覆盖总数。

## 6. 从源码复现

仓库根目录执行，Python 3.10+。现有固件与镜像已经包含在源码包中，基本检查与工程生成不要求安装 C 编译器。

```powershell
python -m tools.run_step1 --report-dir build/step20-python
python -m tools.prepare_de2_large --output C:/fpga/riscv_fir_large
```

重新生成 C 固件需要固定版本 Zig 0.13.0：

```powershell
python -m tools.build_large_firmware --zig C:/tools/zig-0.13.0/zig.exe --build-dir C:/fpga/large_firmware
```

真实仿真需要已安装的 ModelSim 10.5b 及其预编译 `altera_mf` 库。本机路径为 `E:/quartus/modelsim_ase/win32aloem`：

```powershell
python -m tools.check_m9k_binding
python -m tools.run_large_memory
python -m tools.run_large_mmio
python -m tools.run_large_soc --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/large_soc/full
python -m tools.run_large_board
python -m tools.compare_large_blocks
```

所有仿真使用英文构建目录。完整原始 CPU/DMA 轨迹保存在本机 `F:/CodexWorkspace/outputs/riscv-fir-soc/large_soc/component-fix-system`；源码包保留逐次轨迹 SHA256 和一份真实 N=64/P4 固定样例，用来验证审计器对坏轨迹的拒绝。`--audit-only` 可复用已完成的本机轨迹，不重复仿真。以上脚本均不调用 Quartus。

可选绘图需要 Matplotlib；在相应环境执行 `python -m tools.plot_large_blocks`，得到 PNG/SVG/PDF。实际 Quartus 资源、M9K 映射与 25 MHz 时序已归档；用户板上观察及成对物理性能测量仍待取得。


本轮用户反馈已保存在[上板观察记录](../reports/step20-large-block/board-observation.json)，属于概括接受，独立逐项读数和视频尚未收到。后续使用[step21 九组完整调用计时](step21-board-benchmark-guide.md)取得同一镜像上的软硬件比较。
