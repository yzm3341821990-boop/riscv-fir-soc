# 验证记录与结论范围

本页整理各版本运行记录。2026-10-29 用户已完成 step18 编译，25 MHz 时序通过，并确认板上结果正确。原始报告及 SOF 哈希归档在 [step18 实现记录](../reports/step18-pipeline-soc/quartus-validation.json)，用户原话见[板上观察记录](../reports/step18-pipeline-soc/board-observation.json)。本地主线另新增 step19 的 1/2/4 路 FIR 功能仿真、匹配比较和板级候选工程，见[指南](step19-parallel-fir-guide.md)。原始日志、源码哈希及生成时间保留在 reports/；下面 step16 的数字仍是历史多周期版本。

## 证据分层

| 层次 | 现有记录 | 可以支持的结论 |
| --- | --- | --- |
| Python 模型/工具 | [213 项测试及向量审计](../reports/step1/validation.json) | 对应模型、工具、数据和受控错误检查通过 |
| CPU RTL | [188 个程序及故障注入](../reports/step11-software-fir/validation.json) | 已声明指令子集的功能检查；不等于完整 ISA 认证 |
| 独立五级流水线 RTL | [216 个场景、10 项故障注入](../reports/step17-pipeline/validation.json) | 同一 38 条指令的提交/访存/RF/RAM 一致性、旁路、load-use、跳转清空及故障排空；未接板级 SoC |
| 流水线 FIR 系统 | [第十八步](../reports/step18-pipeline-soc/validation.json)、[默认 CPU 回归](../reports/step18-pipeline-soc/core-regression/validation.json)、[板级功能仿真](../reports/step18-pipeline-soc/board/validation.json) | 当前带可选 MMIO 的 CPU、42 组匹配基准、C/DMA 轨迹、4 次启动/复位与 694 拍整段自检；无新 Quartus 或实物结论 |
| FIR RTL | [24 组核用例](../reports/step12-fir-accelerator/validation.json) | 定点、握手、等待与复位检查通过 |
| 协同系统 | [9 个系统用例、20 个 MMIO 用例](../reports/step13-fir-soc/validation.json) | C→CPU→MMIO→FIR→RAM 的事务和结果检查，其中包括主动超时用例 |
| 公平周期比较 | [42 次仿真测量](../reports/step14-fir-benchmark/validation.json) | 同平台、同数据布局、同计时边界下的模拟周期关系 |
| 显示 RTL | [四次运行、32 项输出选择、六项故障注入](../reports/step16-display/simulation-validation.json) | 显示译码、数据快照、周期边界、冻结、复位及错误显示检查通过 |
| FPGA 实现 | [显示工程实现与时序](../reports/step16-display/quartus-validation.json) | 在所声明参考器件及约束下，综合、布局布线与静态时序通过 |
| 实物反馈 | [初版 LED/KEY0 反馈](../reports/step16-display/previous-board-feedback.json)、[后续反馈](../reports/documentation/board-observation.json) | 用户报告自检/复位符合预期，且新版可用；完整视频和逐项实物读数待补 |

历史阶段测试数量是当时的快照，不能把不同阶段的数量相加成一个独立覆盖总数。报告源码哈希应与其声称的版本核对。

## 参考实现结果

| 指标 | 数码管工程 |
| --- | ---: |
| Quartus | Lite 17.0.0 Build 595 |
| 参考器件 | EP4CE115F29C7 |
| 输入 / 系统时钟 | 50 MHz / 25 MHz |
| LE | 27,451 / 114,480（约 24%） |
| 寄存器 | 11,567 |
| 逻辑存储位 | 9,216 |
| 9 位乘法器元素 | 8 |
| 拟合引脚 | 66，逐项核对位置和 I/O 标准 |
| 最差 setup / hold slack | +7.710 / +0.180 ns |
| 未约束时钟及输入/输出端口计数 | 均为 0 |
| Critical warnings / 普通 warnings | 0 / 15 |

原始[实现报告目录](../reports/step16-display/quartus/)保留全部警告。LED/HEX 没有外部同步采样接收器，相关输出路径被明确排除；异步按键/开关仅到同步链首级的路径排除，内部时钟路径正常分析。没有数值 MTBF 或实测最高频率结论。

早期 50 MHz 参考实现出现 -5.474 ns setup 违例，见[历史失败记录](../reports/step15-quartus/first-50mhz/status.json)。当前用真实二分频得到 25 MHz，使用相应生成时钟约束。

## 三种计时数字必须区分

1. **板级自检程序计数：1131 拍。** 当前数码管版本从 CPU 获释边沿计到末尾监测边沿，包含配置、计算、轮询和 C 检查；排除 RAM 初值装载。仿真采用外部时钟独立秒表核对，数码管预期为 0000046B。
2. **FIR 外设计数 CYCLES。** 定义为 START 接受到最后一次输出写入接受之间的间隔，见 [MMIO 契约](fir-mmio-contract.md)。
3. **第十四步基准完整调用区间。** 专门固件使用 RAM 标记围住调用，采用相同 CPU/MUL、编译器、初始 RAM 和 signed32 数据布局，见[基准契约](fir-benchmark-contract.md)。

基准 N=8、无额外 DMA 等待时：

| 模式 | 模拟完整调用周期 | 软件周期 / 该模式 |
| --- | ---: | ---: |
| 软件 FIR | 2044 | 1.000× |
| 硬件冷调用，包含系数配置 | 919 | 2.224× |
| 硬件调用，系数预先驻留 | 392 | 5.214× |

驻留模式的首次装载在标记区间之外单独保留，硬件两种固件整段程序均执行 997 拍。上述周期关系不能与当前 1131 拍自检程序直接相除，也不能当作板上实测加速比。逐次结果在 [CSV](../reports/step14-fir-benchmark/comparison.csv)和[测量记录](../reports/step14-fir-benchmark/measurements.json)。

## 已确认与待补

- 用户已报告下载到开发板，初版 LED 状态和 KEY0 重跑符合预期。
- 数码管新版交付后，用户反馈“可以了”。这支持基本显示可用，尚未逐项确认八个数值、周期数与重复次数。
- 用户负责录制视频，当前没有视频文件、视频核验或最终展示链接。
- 完整芯片丝印/板卡修订、实际配置文件与 Programmer 日志的对应关系尚未形成完整独立记录；不从共用 JTAG ID 推断封装/速度等级。
- 尚无板上软件/硬件成对性能测量、持续稳定性或配置 Flash 固化验证。
- v0.1 公开仓库的 Python 3.10/3.12 运行 40790245986 已成功；本地 step18/19 尚未上传，不能沿用该 CI 状态。

## Step19 当前验证与待补

| 层次 | 实际执行结果 |
| --- | --- |
| Python | 225 项测试；13 组原始向量、1711 样本、65 哈希；三个数值错误控制被拒绝 |
| 三种 MAC 路数 | 72 场景、5565 个主流输出；signed16 与完整 signed40 均逐样本相等 |
| 核级错误控制 | 14 个 2/4 路故障全部被断言拒绝；非法 3/8 路配置被拒绝 |
| MMIO | 60 场景，三种配置均覆盖非法配置、重复任务、DMA 等待、最后写回及复位；4 个错误控制被拒绝 |
| CPU + FIR 系统 | 27 个 C 系统场景（含软件超时），126 次匹配调用；完整 RAM、寄存器和提交/访存轨迹审计 |
| 板级功能仿真 | 三配置共 12 次完整启动/复位、96 项结果选择、外部输入时钟独立秒表核对 |
| 单路兼容 | 原串行 24 场景与 12 项错误控制通过；五级板级自检仍为 694 拍 |
| 交付核对 | 130 个当前源码哈希、87 个生成文件哈希、每配置 66 引脚；全部本地文档/图片链接检查 |

见[完整报告](../reports/step19-parallel-fir/validation.json)、[交付审计](../reports/step19-parallel-fir/delivery-audit.json)和[运行指南](step19-parallel-fir-guide.md)。完整调用/内核/板级自检各有边界。四路 139 拍是系数驻留完整调用，502 拍是另一固件的整段板级自检；二者不能互相替代。

step18 旧 SOF 与工程哈希保持，用户已报告上板结果正确。step19 的四路 p4 随后通过用户实际编译，25 MHz setup/hold 为 +11.166/+0.119 ns，占 28,130 LE、14 个 9 位乘法器元素；用户概括确认板上符合预期，见[实现记录](../reports/step19-parallel-fir/quartus-p4-validation.json)与[反馈](../reports/step19-parallel-fir/board-p4-observation.json)。同版 p1/p2/p4 编译数据均已归档；基准完整调用的板上成对计时尚待取得。

## Step20 长块候选

[第二十步](step20-large-block-guide.md)新增独立 32 KiB M9K RAM、扩大范围的 CPU/MMIO 和 1024 点板级版本。242 项 Python 回归通过；8192 字全地址、17 个 CPU 地址场景、6 个 RAM/CPU 错误控制通过。三种并行度均重复完成 4096 点 MMIO 任务，另有协议/复位和 3 个边界故障检查。45 次 C 执行、2080791 条提交逐条回放，各例核对全 RAM、32 个寄存器和全部输出。四次板级复位及独立秒表核对 24917 拍；四个板级故障被拒绝，第 1024 点破坏也触发实际 C 错误指示。

报告、源码哈希和交付检查见 [step20 交付审计](../reports/step20-large-block/delivery-audit.json)。该冻结报告记录最初交付时的功能状态；随后 r1 的实际实现与上板反馈如下，新内容尚未上传 GitHub。

Step20 r1 记录：首次用户 Quartus 编译遇到 10481，原始日志保留；将 RAM 从直接 vendor entity 实例化改为厂家组件包实例化。新增仅含综合组件声明的隔离分析检查，旧式绑定失败、r1 通过；功能回归按新源码重新执行。随后用户已完成 r1 的 Quartus 编译，原始实现证据另列如下。见[修订指南](step20-large-block-guide.md)。

后续 r1 实际 Quartus 编译已通过：7464 LE，数据 RAM 确认为 32 个真双端口 M9K，总 M9K 48，25 MHz setup/hold +9.726/+0.152 ns，66 引脚匹配、未约束摘要全零；SOF 哈希与固定源码一致。原始报告与审阅见[实现记录](../reports/step20-large-block/quartus-validation.json)，用户板上观察仍待补。


## Step21 同一镜像计时

[250 项 Python 测试](../reports/step21-board-benchmark/python/validation.json)与[板级仿真](../reports/step21-board-benchmark/validation.json)通过。4 次完整扫描共核对 36 项显示；外部 50 MHz 时钟独立秒表、6 组硬件等待敏感性、固定答案表拒绝、最后输出损坏和 9 项受控错误均留有记录。[交付审计](../reports/step21-board-benchmark/delivery-audit.json)核对了工程输入和 66 个引脚。随后已完成[用户实际 Quartus 编译审阅](../reports/step21-board-benchmark/quartus-validation.json)：14,171 LE、32 M9K、四个 FIR 通道，25 MHz setup/hold +10.184/+0.181 ns，所有 18 项时序与 66 引脚检查通过。仅有六项允许的 GUI QSF 默认设置变化，RTL、固件、ROM bank 与交付输入一致。用户随后回复“ok，符合预期，继续吧”，作为概括上板接受记录；逐项数字与视频没有代填。

## Step22 结果整理

新增统计生成器从 step19/20/21 原始 JSON 重建周期/资源表，并记录输入哈希；图表使用独立的 Matplotlib 环境生成、已视觉检查。[本轮 Python 检查](../reports/step22-project-summary/python/validation.json)保留当前源码和完整 250 项测试结果，未重新运行 Quartus 或未改动的 RTL。上板确认见[原话记录](../reports/step21-board-benchmark/board-observation.json)。
