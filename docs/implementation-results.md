# 并行 FIR 实现记录

日期：2026-10-29。本表记录用户实际执行的 Quartus Prime Lite 17.0.0 Build 595 编译。Agent 读取报告并检查配置、源码与镜像哈希，不执行 Quartus 或板卡操作。

## 同版参数扫描的当前进度

三个配置使用 step19 参数化 RTL，工程只改变 `FIR_LANES`。

| 配置 | p1（单路） | p2（双路） | p4（四路） |
| --- | --- | --- | --- |
| RTL 与匹配基准 | 已验证 | 已验证 | 已验证 |
| 实际 Quartus 编译 | 成功 | 成功 | 成功 |
| 核心目标/约束时钟 | 25 MHz | 25 MHz | 25 MHz |
| 逻辑单元 | 28,122 / 114,480 | 28,130 / 114,480 | 28,130 / 114,480 |
| 寄存器 | 11,967 | 11,966 | 11,965 |
| 存储位 | 1,792 | 1,792 | 1,792 |
| 9 位乘法器元素 | 8 / 532 | 10 / 532 | 14 / 532 |
| 实际 FIR 乘法通道 | 1 | 2 | 4 |
| 最差 setup / hold | +11.572 / +0.145 ns | +10.152 / +0.152 ns | +11.166 / +0.119 ns |
| 未约束摘要 | 各项均为 0 | 各项均为 0 | 各项均为 0 |
| 错误 / 关键警告 / 普通警告 | 0 / 0 / 27 | 0 / 0 / 27 | 0 / 0 / 27 |
| 板级整段自检仿真 | 694 拍 | 562 拍 | 502 拍 |
| 用户板上反馈 | 未单独收到 | 未单独收到 | 概括确认符合预期 |

p4 的 66 个实际引脚与 I/O 标准逐项匹配清单，QSF 只增加了允许的 Quartus GUI 默认项。Fitter 层次中存在四个 `fir_serial:core|lpm_mult:Mult0..Mult3` 乘法实例。所有工况的 setup、hold 和最小脉宽余量均非负。27 条警告和原始报告完整保留，见[编译记录](../reports/step19-parallel-fir/quartus-p4-validation.json)。

SOF SHA256：`c0efccc055cbd7df08efb14a10806ee11ee663522825047e7b0e32dcffd309c8`。本机已生成镜像与前一轮验证源码相匹配；用户原话“是和你预期的一样”见[观察记录](../reports/step19-parallel-fir/board-p4-observation.json)。未收到独立 Programmer 日志、逐项读数或视频，因此不另外推断图像身份的独立现场证明或板上成对基准测量。

双路 p2 的实际编译记录见[报告](../reports/step19-parallel-fir/quartus-p2-validation.json)，SOF SHA256 为 `5e26f8982e620655ab9bfcd116a625dc5d32df90f21aa892b9cae6f2fcf3ece1`。双路与四路的 25 个源码输入哈希一致，Fitter 分别确认 2/4 个 FIR 乘法通道。p2 的“好了”按编译完成反馈记录，不推断额外的板上读数。

## 历史单路参考

step18 的未参数化单路实现占 28,122 LE、11,967 寄存器、8 个 9 位乘法器元素，25 MHz setup/hold 为 +11.572/+0.145 ns，已获用户上板反馈。其 FIR RTL 与 step19 参数化版本不同。即使表面逻辑单元数量只相差 8，也不能直接将该差值解释为“相同源码中增加三条 MAC 的面积成本”。本轮同版 p1/p2/p4 的 25 项源码输入哈希已核实一致，因此采用本轮三组实际实现作受控对照，历史 step18 不代入新表。

已有实现的结构化数据见[JSON](../reports/step19-parallel-fir/implementation-comparison.json)与[CSV](../reports/step19-parallel-fir/implementation-comparison.csv)。完整调用的周期比较见[第十九步指南](step19-parallel-fir-guide.md)，属于功能仿真，与板级整段自检、静态时序分别报告。

## 成组比较完成与后续

同版 p1/p2/p4 已全部编译并通过 25 MHz 时序。单路记录见[报告](../reports/step19-parallel-fir/quartus-p1-validation.json)。本轮结果中四路相对单路增加 6 个 9 位乘法器元素、逻辑单元增加 8；完整调用的功能周期从冷调用 590 拍降至 398 拍、驻留调用 331 拍降至 139 拍。该结果只适用于本次固定配置，不是所有数据长度或任意布局下的面积/时序保证。

本项完整 1/2/4 路实验已形成实际资源、静态时序及功能周期对照；四路有用户板上接受反馈，p1/p2 没有额外独立板上测量。下一项推进原方案中的 64/256/1024 样本长块实验及片上存储支持，另建候选工程，保留本轮三份已编译镜像。

## Step20 另建候选

32 KiB M9K 与 64/256/1024 点 C 基准已完成实际功能仿真，见[第二十步指南](step20-large-block-guide.md)。本候选更换了共享 RAM，随后已通过用户编译和时序核对，实际结果见下一节；不能套用上表的寄存器型 RAM 资源/时序。新工程为 `de2_115_large/riscv_fir_de2_large.qpf`。

## Step20 r1 的用户实际编译

r1 已完成用户全编译和只读审阅，实际为 7464 LE、3718 寄存器、393216 存储位、48 块 M9K（32 块数据 RAM、16 块初值 ROM）和 14 个 9 位乘法器元素。四个 FIR 乘法通道保留；25 MHz 最差 setup/hold +9.726/+0.152 ns，未约束摘要均为零。0 关键警告、27 普通警告归档。新版相对旧 p4 的 LE 减少约 73.5%，但程序、镜像和长度也变化，属于工程版本比较。见[实现记录](../reports/step20-large-block/quartus-validation.json)。当前等待用户下载与实物观察，尚非板上成对性能结果。


## Step21 同一镜像九组计时

[新工程](step21-board-benchmark-guide.md)的四次整套功能仿真已完成，涵盖 36 项计数显示、独立外部时钟秒表、等待敏感性及 9 项错误控制。用户编译已完成并经只读审阅：14,171 LE、3,778 寄存器、262,144 存储位、32 块 M9K、14 个 9 位乘法器元素，四个 FIR 通道保留。共享数据 RAM 为 8192×32 同钟真双口，RAM Summary 没有另列 M9K ROM。25 MHz setup/hold 最差 +10.184/+0.181 ns，18 项检查均非负，未约束摘要全零；66 引脚匹配，无关键警告。见[实际报告](../reports/step21-board-benchmark/quartus-validation.json)，SOF 已另存并核对 SHA256；用户已概括确认下载后行为符合预期，独立逐项数字另行记录。

完整的匹配实验、当前版本资源和证据范围现汇总于[结果分析](project-results.md)。本次 step21 反馈见[用户原话](../reports/step21-board-benchmark/board-observation.json)。
