# 第十八步：五级 CPU + FIR 系统与独立板级工程

本步已把五级流水线 CPU 接入既有共享 RAM 和 FIR MMIO，运行与第一版相同的裸机 C 自检固件，并提供单独的 DE2-115 工程。功能仿真、完整轨迹回放与板级输出检查见 [系统报告](../reports/step18-pipeline-soc/validation.json)、[CPU 回归](../reports/step18-pipeline-soc/core-regression/validation.json)和[板级仿真](../reports/step18-pipeline-soc/board/validation.json)。2026-10-29 用户已编译并确认板上结果正确；[实现记录](../reports/step18-pipeline-soc/quartus-validation.json)与[用户反馈原话](../reports/step18-pipeline-soc/board-observation.json)已归档。逐项视频仍待提供。

归档实现为 28,122 LE、11,967 寄存器、1,792 存储位、8 个 9 位乘法器元素；25 MHz 最差 setup/hold 为 +11.572/+0.145 ns。0 错误、0 关键警告、27 条普通警告，66 引脚核对一致，未约束摘要各项为零。SOF SHA256 为 `26014351c56578bf3e36895764db8cf9860d0fd6034e67876f1f5c6318cb6496`。该记录绑定冻结的 step18 源码 ZIP；step19 的参数化 RTL 与并行候选配置须重新编译验证。

## 复现步骤

已准备的工程位于：

`F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_pipeline/riscv_fir_de2_pipeline.qpf`

1. 在 Quartus 中打开这个 QPF，顶层应为 `de2_115_pipeline_top`。
2. 选择 **Processing → Start Compilation**，等待完整编译结束。
3. 在报告中检查编译成功、器件、setup/hold 时序和关键警告。参考目标仍为 EP4CE115F29C7，输入 50 MHz、实际二分频系统时钟 25 MHz，沿用已核对的 66 个引脚与 JP7=2.5 V、JP6=3.3 V 配置。
4. 编译产生的文件应为 `output_files/riscv_fir_de2_pipeline.sof`。时序与配置确认后，通过 USB-Blaster / JTAG 下载。
5. 用下表检查开关、显示和复位。将编译结果与板上现象发回来，便于归档真实实现证据。

生成脚本只准备文件，不运行 Quartus。已归档编译由用户执行，后续编译和下载也由用户负责。reference-images 子目录是镜像生成过程的旧版参考文件；本步要打开的是根目录的 riscv_fir_de2_pipeline.qpf。

## 预期显示

正常完成后 LEDR0/1 亮、LEDR2 灭、LEDR3 闪。SW3=0，SW2..SW0 选择实际 DMA 写回快照，SW0 是最低位：

| SW2 SW1 SW0 | HEX7..HEX0 | signed32 整数 |
| --- | --- | ---: |
| 000 | 00002000 | 8192 |
| 001 | 00003000 | 12288 |
| 010 | FFFFA800 | -22528 |
| 011 | 00004400 | 17408 |
| 100 | FFFFD000 | -12288 |
| 101 | 00003C00 | 15360 |
| 110 | FFFFE200 | -7680 |
| 111 | FFFFF800 | -2048 |

**SW3=1：预期显示 `000002B6`，即 694 拍。** 这是从 CPU 首个有效 core-clock 边沿到板级终端观察边沿、两端均包含的整段自检时钟数；包含 C 配置、FIR 运行、轮询、核对、流水线填充及控制转移代价，排除复位和 RAM 装载。该数值已通过独立的外部输入时钟 stopwatch 检查，完成后保持。

第一版多周期程序显示 0000046B（1131 拍），属于另一 CPU 实现。两者不能直接当作已测得的实际耗时比；新核是否在 25 MHz 下通过时序，要看本次编译。

KEY0 按住后显示空白，松开会重载全部 256 个 RAM 字并重跑。运行期间空白；错误或看门狗超时显示 EEEEEEEE、LEDR2 亮。

## 代码和接口

- [流水线 SoC 顶层](../rtl/soc/pipeline_fir_soc.vhd)：CPU、MMIO、共享 RAM 与 DMA 的连接。
- [新的板级顶层](../rtl/board/de2_115_pipeline_top.vhd)：ROM enable、提交结束判断、初值装载、显示与周期。
- [系统契约](pipeline-soc-contract.md)：MMIO 访问保护、读响应来源、计时和结束边界。
- [工程生成器](../tools/prepare_de2_pipeline.py)：可在其他英文目录重新生成相同固件和引脚工程。

指令 ROM 在流水线暂停时必须保持原输出；结束判断使用寄存的 commit_next_pc。CPU 新增默认 false 的 ENABLE_FIR_MMIO 泛型，独立 CPU 默认行为保持 step17 的 RAM 限制；SoC 显式开启对齐 LW/SW 的 FIR 页访问。共享 RAM 与 MMIO 的读响应选择随接受的读请求登记，支持相邻周期访问不同目标。

## 复现命令

在项目根目录执行。第一条只生成工程，不编译或下载：

```powershell
python -m tools.prepare_de2_pipeline --output F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_pipeline
```

功能验证命令分别为：

```powershell
python -m tools.run_pipeline_soc
python -m tools.run_pipeline_board
python -m tools.run_pipeline_cpu --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/pipeline_step18_core --report-dir reports/step18-pipeline-soc/core-regression
python -m tools.run_step1 --report-dir reports/step18-pipeline-soc/python
```

Python 完整检查为 216 项。CPU 回归为 216 个场景及 10 项故障注入。SoC 验证包含 11 项 MMIO 保护、相邻 RAM/MMIO 读响应与依赖检查、9 个 C 系统场景（含永久 DMA 等待导致的软件超时）和 42 组匹配基准。板级环境检查 4 次启动/复位、32 次结果选择、计数冻结、错误显示；提前完成、忽略 ROM enable、错误计数和错误输出的受控修改必须失败。

板级 testbench 使用本机 ModelSim 10.5b 自带 modelsim_lib.util.init_signal_spy，只读观察真实 CPU 的最后提交，避免用同一个停止条件推导自身的期望。该依赖只在 testbench 中，不进入 Quartus RTL。

## 性能数据的边界

本步沿用 step14 同一编译器、固件、32 抽头、N=8、RAM 布局、七组输入及三种运行模式，分别检查无额外 DMA 等待和周期性等待。完整调用周期仍由两笔真实 marker 写入的接受沿之差计算，见 [CSV 对照](../reports/step18-pipeline-soc/comparison.csv)。系数驻留配置在计时区间外，成本单独记录；FIR 内部 CYCLES、完整调用和板级 694 拍整段自检属于不同边界，不能混用。

基准 base 数据、无额外 DMA 等待的功能仿真结果如下：

| CPU | 软件完整调用 | 硬件冷调用，含系数配置 | 系数预先驻留调用 |
| --- | ---: | ---: | ---: |
| 第一版多周期 | 2044 | 919 | 392 |
| 新五级流水线 | 769 | 590 | 331 |

在同一个新流水线 CPU 上，软件/冷调用周期比为 1.303×，软件/驻留调用周期比为 2.323×。软件基线自身也因流水线加快，因此相对硬件加速比随比较平台变化。FIR 内部仍是同一个串行 MAC，当前无等待内核均为 297 拍。这些均为模拟时钟周期，不是新版本板上实测耗时。

本步是本地下一版候选工程；已公开的 v0.1 保存第一版多周期实现与对应证据。待本版编译和实物观察完成后再整理下一次 GitHub 更新。
