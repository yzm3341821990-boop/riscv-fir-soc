# 运行当前五级 CPU + FIR 项目

本页对应 step21 九组计时镜像，用户已经反馈下载后符合预期。旧多周期和逐模块操作保留在[历史运行入口](quickstart-v0.1.md)。

## Python 检查与结果表

Python 3.10+，在仓库根目录运行，无第三方依赖：

```sh
python -m tools.run_step1 --report-dir build/check
python -m tools.build_project_summary
```

第一条执行数值、CPU 参考、工具/导出及故障检查；它不启动 Quartus，也不等同于重新执行所有 RTL。第二条从保存的报告重新生成统计 JSON 和 CSV。可选图形使用 requirements-visualization.txt 中的环境，并执行 `python -m tools.build_project_summary --plots`。

## ModelSim 功能验证

已执行环境为 ModelSim Intel FPGA Starter Edition 10.5b，使用其 `altera_mf` 模型。Windows 英文输出路径示例：

```powershell
python -m tools.run_board_benchmark --build-dir C:/fpga/benchmark_sim
```

默认工具位置为本机已安装路径；移到其他电脑时按脚本 `--help` 设置 ModelSim 工具目录。完整回归会运行四次整套扫描、独立秒表、协议/复位和受控错误场景，保留日志。运行需要数分钟；没有厂商仿真器时只运行 Python 检查，并保留既有 RTL 报告的来源范围。

## 生成 Quartus 工程

已有九份 ELF、HEX 和初始 RAM，生成工程无需先重编译 C：

```powershell
python -m tools.prepare_de2_benchmark --output C:/fpga/riscv_fir_benchmark
```

生成目录包含自足的 HDL、ROM/MIF、QPF/QSF、SDC、ModelSim 宏和输入清单。在 Quartus Prime Lite 17.0 打开 `riscv_fir_de2_benchmark.qpf`，顶层 `de2_115_benchmark_top`，参考目标 `EP4CE115F29C7`。

用户负责 Start Compilation、下载和板卡操作。新的编译应核对输入清单、实际 M9K/DSP、66 引脚及 I/O 标准、18 项 setup/hold/脉宽和未约束项后再使用 SOF。[现有实现报告](../reports/step21-board-benchmark/quartus-validation.json)只对应其记录的源码与 SOF 哈希。

本机原工程路径：

```text
F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_benchmark/riscv_fir_de2_benchmark.qpf
F:/CodexWorkspace/outputs/riscv-fir-soc/step21-verified/riscv_fir_de2_benchmark.sof
```

板卡及 JP7/JP6、引脚条件沿用[参考板契约](de2-reference-contract.md)，不能把同系列芯片视为任意板都可直接下载。

## 板上操作

上电/KEY0 松开后自动运行九组，全部通过时 LEDR0/1 亮、LEDR2 灭、LEDR3 闪。SW3..SW0 四位选择编号 0..8，9..15 空白；失败显示 EEEEEEEE。九项对应值及复位行为见[step21 指南](step21-board-benchmark-guide.md)。

用户已对该版本概括确认符合预期。记录视频或抄录时按[当前拍摄指南](demo-recording-step21.md)保留实际显示；期望值与实际观察分栏保存。
