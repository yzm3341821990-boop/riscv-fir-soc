# 第二十一步：同一镜像的板上成对计时

step20 r1 已完成用户编译、25 MHz 时序审阅和用户“对的，进行下一步吧”的上板反馈，见[观察记录](../reports/step20-large-block/board-observation.json)。那一版保留用于结果展示。本步提供新的测量工程，将原方案中的软件/硬件完整调用比较带到板上。

**当前状态：用户 Quartus 全编译已完成，源码、引脚、资源、25 MHz 时序及 SOF 身份已审阅通过，用户已反馈下载后行为符合预期。** 下表仍是仿真验证的期望值，独立逐项数字尚未抄录。step21 实际资源和时序见本文下方实现记录。

## 1. 现在编译这个工程

```text
F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_benchmark/riscv_fir_de2_benchmark.qpf
```

顶层为 `de2_115_benchmark_top`，参考器件 `EP4CE115F29C7`，50 MHz 输入实际二分频为 25 MHz，仍使用原来的 66 个引脚和 I/O 标准。CPU、FIR、32 KiB M9K 和数值规则沿用已编译的 step20 r1；新增的是程序/初值 ROM bank、执行编排及调用计数器。

1. 用户打开上述 QPF，执行 **Processing → Start Compilation**。
2. 保留 `output_files/`；本聊天只读核对原始报告、引脚、实际资源、所有 setup/hold 与 SOF 身份。
3. 核对通过后，由用户通过 USB-Blaster 下载 `output_files/riscv_fir_de2_benchmark.sof`。
4. 等待自检结束。九组在同一镜像里自动执行，软件的 1024 点计算也由实际 CPU 完成。

编译与板卡操作仍由用户执行。生成脚本不运行 Quartus。旧工程、旧 SOF 和对应报告保持原样。

## 2. 开关读取九组计数

**本工程的四个开关共同表示编号：SW3..SW0。** 自检完成后选择编号 0～8，显示相应完整调用周期。编号 9～15 显示空白。这里 SW3 参与完整编号，与 step20 的显示选择含义不同。

| 编号 | SW3..SW0 | 点数 | 调用模式 | HEX7..HEX0 期望值 | 十进制周期 |
| ---: | --- | ---: | --- | --- | ---: |
| 0 | 0000 | 64 | C 软件 | `00005DED` | 24045 |
| 1 | 0001 | 64 | 四路硬件冷调用 | `00000466` | 1126 |
| 2 | 0010 | 64 | 四路系数驻留 | `00000363` | 867 |
| 3 | 0011 | 256 | C 软件 | `0001C878` | 116856 |
| 4 | 0100 | 256 | 四路硬件冷调用 | `00000E26` | 3622 |
| 5 | 0101 | 256 | 四路系数驻留 | `00000D23` | 3363 |
| 6 | 0110 | 1024 | C 软件 | `00077711` | 489233 |
| 7 | 0111 | 1024 | 四路硬件冷调用 | `00003528` | 13608 |
| 8 | 1000 | 1024 | 四路系数驻留 | `00003425` | 13349 |

正常为 LEDR0/1 亮、LEDR2 灭、LEDR3 闪。自检期间数码管空白；任一组 C 结果、地址/数量、标记或结束检查失败时，显示 `EEEEEEEE`，LEDR0/2 亮、LEDR1 灭。整体通过前不会把局部完成显示为通过。

按住 KEY0 清除状态与显示，松开重新执行全部九组。结束后计数冻结，切换开关只读取已保存值。

下载后请优先照抄 **0110、0111、1000** 三个位置的实际显示，即 1024 点的软件、冷调用和驻留值。其余六组也可按表记录或录入视频。[读数模板](../reports/step21-board-benchmark/board-measurement-template.csv)的实际读数栏保持为空，收到观察后再填写。

## 3. 计数怎样产生

每组使用原有已编译 C 固件。板上 `call_cycle_timer` 在 CPU 接受 `marker=1` 全字写入时开始，在同地址接受 `marker=2` 写入时冻结，记录两个接受沿的间隔。显示值来自硬件计数寄存器，可综合 RTL 中没有期望周期表。

```mermaid
flowchart LR
    A[选择 ROM bank 并重装初值] --> B[CPU 执行对应 C 程序]
    B --> C[marker 1 开始计数]
    C --> D[软件计算或 FIR 调用]
    D --> E[marker 2 冻结计数]
    E --> F[C 核对全部 N 个输出并正常返回]
    F --> G{九组都完成}
    G -->|否| A
    G -->|是| H[允许开关读取九个实际计数]
```

每种长度的三个模式初始 RAM 完全相同，CPU、MUL 能力、存储配置和时钟来自同一个 bitstream。每组之前重新装载 8192 个字，并复位 CPU/FIR，避免上一组的状态污染下一组。三个长度各使用一份初值 ROM，九个配置分别使用相应程序 ROM bank。

冷调用将系数配置包含在区间内；驻留程序在计时之前装载系数，因此首次预装成本在区间外。驻留模式并不继承前一组硬件状态。初值装载、区间后的 C 结果检查，以及 hw_cycles/hw_written 诊断读取均不计入完整调用。这是 FIR 调用的周期比较，不是上电到全部九组结束的总时间。

每组 C 核对全部 N 个输出。板级另外核对实际结果写入的地址、数量和前八个值，软件路径观察 CPU 写入，硬件路径观察 DMA 接受的写入；两者都须到达对应程序的终止提交。

## 4. 验证证据

[完整板级报告](../reports/step21-board-benchmark/validation.json)保存了：

- 四次完整启动/复位，共 36 项计数显示；包括正常 KEY0 重跑、装载中复位和第 7 组 DMA 进行中复位。
- 独立监测器从外部 50 MHz 时钟计数，并在核心接受边沿前采样 CPU 请求；逐组核对实际标记间隔与显示寄存器。
- 冷/驻留系数配置时机、软件及 DMA 输出地址与数量、九次终止提交、非法显示编号和结束冻结。
- 4 个计数器错误控制、5 个板级错误控制全部被拒绝；故意破坏第 1024 个输出时，实际观察到 C 错误并显示 `EEEEEEEE`。
- 延迟敏感性：每个硬件调用第一次 DMA 请求额外等待 31 个核心边沿，六个硬件计数均增加 32 拍，三个软件计数不变。增加量包含软件轮询粒度。使用原始期望值伪装显示的错误版本被外部秒表拒绝。

这些延迟与错误注入只存在于测试副本，不进入交付工程。计数器还独立检查了起止边沿、冻结、重复/乱序标记、复位取消和溢出。

## 5. 从源码复现

Python 3.10+，仓库根目录执行。已有九份 ELF/镜像，无需重新安装 C 编译器即可生成工程：

```powershell
python -m tools.prepare_de2_benchmark --output C:/fpga/riscv_fir_benchmark
python -m tools.run_step1 --report-dir build/step21-python
```

本机 ModelSim 10.5b 及其 `altera_mf` 库已安装，完整功能验证：

```powershell
python -m tools.run_board_benchmark --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/board_benchmark/final
```

脚本保留每个场景、延迟变化和受控故障日志，不调用 Quartus。精确边界见[板级计时契约](board-benchmark-contract.md)。新工程的资源、静态时序、SOF 和板上读数收到后单独归档；当前不把仿真期望值写成实测。后续版本尚未上传 GitHub，许可证仍未代选。

## 7. 用户编译与 SOF 下载

本次用户编译的 Flow Status 为 Successful（2026-10-29 21:27:33），参考器件 EP4CE115F29C7。只读审阅见[完整实现记录](../reports/step21-board-benchmark/quartus-validation.json)：

| 项目 | step21 实际结果 |
| --- | ---: |
| LE | 14,171 / 114,480（12%） |
| 寄存器 | 3,778 |
| 存储位 | 262,144 |
| M9K | 32，全部为 8192×32 的同钟真双口共享 RAM |
| 9 位乘法器元素 | 14 |
| FIR 乘法通道 | 4 |
| 实际引脚 | 66，位置和 I/O 标准均匹配 |
| 25 MHz 最差 setup / hold 余量 | +10.184 / +0.181 ns |

三个工况共 18 项 setup/hold/脉宽检查非负，六项未约束摘要为零。27 项普通诊断已归档，无关键警告；人机 LED/HEX 输出保留默认驱动/转换速率诊断。Fitter RAM Summary 仅列出共享数据 RAM，本版没有单独列为 M9K 的 ROM，不能沿用 step20 的 48 块 M9K 数字。

使用已核对并另存的下载文件：

```text
F:/CodexWorkspace/outputs/riscv-fir-soc/step21-verified/riscv_fir_de2_benchmark.sof
SHA256 fbff1eba713bb10db223ce81766b1e236fc4dcede977f0b84009c25a4ec6bbf3
```

由用户使用既有 USB-Blaster/JTAG 流程下载。完成后检查 LEDR0/1 亮、LEDR2 灭、LEDR3 闪；SW3..SW0 四位选 0110、0111、1000，优先照抄这三项实际显示。KEY0 按住清状态、松开重跑全部九组。下载或观测尚未由 agent 执行，视频和实测字段保持待补。

## 8. 用户上板反馈

用户在上述下载与三项显示/LED 检查说明后回复“ok，符合预期，继续吧”。原话、对应 SOF 与证据范围见[上板观察记录](../reports/step21-board-benchmark/board-observation.json)。该反馈作为整体行为接受，未生成九项数字抄录、Programmer 日志或视频。性能/资源汇总见[结果分析](project-results.md)，本轮无需重复编译。
