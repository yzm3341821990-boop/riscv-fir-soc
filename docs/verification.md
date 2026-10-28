# 验证记录与结论范围

本页整理已有运行记录，不表示本次文档整理重新执行了仿真或 Quartus 编译。原始日志、源码哈希及生成时间保留在 reports/。

## 证据分层

| 层次 | 现有记录 | 可以支持的结论 |
| --- | --- | --- |
| Python 模型/工具 | [213 项测试及向量审计](../reports/step1/validation.json) | 对应模型、工具、数据和受控错误检查通过 |
| CPU RTL | [188 个程序及故障注入](../reports/step11-software-fir/validation.json) | 已声明指令子集的功能检查；不等于完整 ISA 认证 |
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
- GitHub Actions 已有 Python 3.10/3.12 工作流配置，远端成功运行记录待仓库发布后取得。
