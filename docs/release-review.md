# 当前成果审阅清单

本候选将原多周期版本发展为五级 CPU + 块 FIR 的可复现项目，包含 step19～21 的实现证据及 step22 的读者入口。其范围是当前已实现模块与实验，后续完整 M、CSR/异常、音频、连续流没有作为完成项。

## 交付范围

| 原方案主线 | 对应交付 |
| --- | --- |
| 数值契约与独立参考 | Q15/40 位累加、舍入/饱和、模型、向量和受控错误检查 |
| 自设计 CPU 与 C 软件 | 五级指令子集 CPU、旁路/暂停/清空、ISA 轨迹/RF/RAM 核对、C FIR |
| FIR 与软硬件接口 | 1/2/4 路 MAC、MMIO、共享 RAM、DMA、协议与复位检查 |
| DE2-115 实现 | 原始 Quartus 报告、66 引脚/电压约束、25 MHz 时序和固定 SOF 身份 |
| 对照实验 | 同版 step19 并行度资源扫描，step20/21 长块周期与九组计时 |
| 展示与复现 | 当前首页、架构/运行/拍摄指南、数据/图表生成器、冻结清单 |

## 当前证据

- [250 项 Python 检查](../reports/step22-project-summary/python/validation.json)：模型、工具、向量和故障检查；不是 ISA 合规认证。
- [45 组 C 执行](../reports/step20-large-block/system-validation.json)：2080791 条提交，每例全 RAM/32 寄存器与 CPU/DMA 轨迹核对。
- [九组板级计时功能验证](../reports/step21-board-benchmark/validation.json)：四次完整扫描、36 项显示、独立秒表及等待敏感性，9 项受控错误。
- [当前 Quartus](../reports/step21-board-benchmark/quartus-validation.json)：14,171 LE、32 M9K、4 个 FIR 乘法通道；18 项时序检查、未约束全零、66 引脚匹配。
- [当前板上反馈](../reports/step21-board-benchmark/board-observation.json)：用户原话“ok，符合预期，继续吧”，作为整体行为接受。独立数字、视频、Programmer 日志、物理多次重启记录均未代填。

## 发布前可审阅内容

当前 README 为主要展示页；旧入口保存在 `docs/*-v0.1.md` 与 `docs/readme-before-step22.md`。原始报告和最初源码/工程压缩包保留，未重新编译或覆盖已验证硬件。

[结果分析](project-results.md)区分仿真周期、静态实现数据和用户观察。1024 点约 35.95×/36.65× 为保存的周期所计算的比值，比较对象是本项目 C 基线，尚无独立数字抄录支持的板上计时表。

用户已授权将这份候选更新到现有公开 GitHub 仓库，许可证未指定。视频可随后补充；当前没有空视频链接或伪造媒体。发布后还需要本次实际提交对应的 CI 与文件回读，见[发布流程](github-publishing.md)。

## 本轮文件核对

[相对本地第一版冻结包的代码/文档/固件差异](../reports/step22-project-summary/changes-since-v0.1.csv)仅比较本地快照，上传前仍需核对远端是否有新提交。[最终交付检查](../reports/step22-project-summary/delivery-audit.json)记录当前输入、图表、旧镜像及文档链接核对。

本次发布来源与仅涉及元数据的调整见[发布说明](publication-note.md)。新提交的文件和 CI 由上传后核对，历史报告中的待办按各报告生成时刻解读。
