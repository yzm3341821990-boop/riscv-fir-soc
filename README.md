# RISC-V CPU + Q15 FIR SoC on DE2-115

自设计五级流水线 CPU 运行裸机 C，通过 MMIO 驱动 32 抽头 FIR 加速器。CPU 和加速器共享 32 KiB 真双口 M9K RAM；同一镜像自动运行三种长度、三种软硬件模式，并在数码管上显示由实际标记写入驱动的周期计数。

当前 CPU 支持 **37 种 RV32I 指令与 MUL**，包含旁路、load-use 暂停、控制转移清空和访存等待。精确范围见[CPU 契约](docs/pipeline-cpu-contract.md)。完整 M 扩展、标准异常/CSR、中断与实时音频属于后续扩展。

## 当前验证状态

| 项目 | 已有证据 |
| --- | --- |
| 数值语义 | signed16 Q15 输入/系数、40 位累加、最近舍入（半格远离零）、signed16 饱和 |
| CPU 与系统 | 独立 ISA 提交/访存/RF/RAM 检查，C 软件与 FIR 硬件逐样本比较 |
| 板级功能仿真 | step21 四次完整扫描、36 项显示检查，独立外部时钟秒表和故障控制 |
| 实际 Quartus 实现 | EP4CE115F29C7，25 MHz，14,171 LE、3,778 寄存器、32 M9K、14 个 9 位乘法器元素 |
| 静态时序 | 最差 setup/hold +10.184/+0.181 ns，18 项检查通过，未约束摘要全零 |
| 实物反馈 | 用户对 step21 下载后行为回复“ok，符合预期，继续吧”；[原话及范围](reports/step21-board-benchmark/board-observation.json) |

逐项数字抄录、Programmer 日志与视频尚未提供。下面的精确周期和比值来自可回放的 RTL 仿真；上板反馈按用户概括确认记录。

## 软件与四路 FIR 的完整调用比较

固定同一 CPU/MUL 能力、时钟、输入、初始 RAM 与定点规则。冷调用包含系数配置；驻留模式在计时前装好系数。启动与结果检查在该计时区间外。

| 点数 | 软件周期 | 四路冷调用周期 | 四路驻留周期 | 软件/冷调用 | 软件/驻留 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 24,045 | 1,126 | 867 | 21.35× | 27.73× |
| 256 | 116,856 | 3,622 | 3,363 | 32.26× | 34.75× |
| 1024 | 489,233 | 13,608 | 13,349 | 35.95× | 36.65× |

![Complete-call simulation comparison](artifacts/step22/complete-call-comparison.png)

[完整分析与计时范围](docs/project-results.md) · [原始数据与输入哈希](reports/step22-project-summary/summary.json) · [CSV](reports/step22-project-summary/complete-call-comparison.csv)

## 快速复现

Python 3.10+；数值模型、工具和检查使用标准库。在仓库根目录执行：

```sh
python -m tools.run_step1 --report-dir build/check
python -m tools.build_project_summary
```

生成独立 Quartus 工程，以 Windows 英文路径为例：

```powershell
python -m tools.prepare_de2_benchmark --output C:/fpga/riscv_fir_benchmark
```

在 Quartus Prime Lite 17.0 打开生成的 `riscv_fir_de2_benchmark.qpf`，用户执行编译、检查报告并下载。ModelSim 功能验证、详细环境和引脚条件见[运行指南](docs/quickstart.md)。

## 文档与展示

| 内容 | 入口 |
| --- | --- |
| 当前系统结构与内存布局 | [Architecture](docs/architecture.md) |
| 九组计时、SW3..SW0、KEY0 与 LED | [板上操作指南](docs/step21-board-benchmark-guide.md) |
| 长块与 1/2/4 路实验 | [性能与资源分析](docs/project-results.md) |
| 发布范围、证据与保留事项 | [审阅清单](docs/release-review.md) |
| 最新视频拍摄顺序 | [Demo](docs/demo-recording-step21.md) |
| 原始编译和时序报告 | [Quartus review](reports/step21-board-benchmark/quartus-validation.json) |
| 历史多周期版本与逐步开发 | [历史入口](docs/quickstart-v0.1.md)、[开发顺序](docs/development-history.md) |
| 发布状态与来源 | [GitHub 状态](docs/github-publishing.md)、[THIRD_PARTY](THIRD_PARTY.md) |

`rtl/` 为可综合 VHDL-93；`firmware/` 和 `programs/` 保存 C、ELF、初始镜像及编译清单；`sim/`、`model/`、`tests/`、`tools/` 保存检查器；`reports/` 保存证据；`artifacts/` 保存由数据生成的图表。保留原多周期和旧五级版本。

当前未指定代码许可证。公开源码与第三方依赖的来源边界见 THIRD_PARTY.md。
