# GitHub 发布状态

本次提交更新自设计五级 CPU、1/2/4 路 FIR、32 KiB M9K 与同一镜像九组计时。发布来源为用户已审阅并明确授权的 step22 源码快照，见[来源与差异](publication-note.md)。第一版多周期历史及原始证据保留。

## 已发布的第一版记录

原公开仓库为 [yzm3341821990-boop/riscv-fir-soc](https://github.com/yzm3341821990-boop/riscv-fir-soc)。第一版提交 `75b34a2269f7f33e99fa38d10d37d7824fdc1cf7` 的 [Actions 记录](https://github.com/yzm3341821990-boop/riscv-fir-soc/actions/runs/40790245986)通过 Python 3.10/3.12 检查，该状态仅属于历史提交。

## 本次更新与验证范围

当前 README、[结果分析](project-results.md)、[运行说明](quickstart.md)和[审阅清单](release-review.md)包含本版展示入口。功能源码、C/ELF/初始镜像、仿真与检查工具、数据/图表、原始报告和用户上板原话一并保留。独立数字抄录、Programmer 日志及视频尚未收到；本次没有虚构媒体或板上加速比。

本版实际 CI 需以[当前 Actions](https://github.com/yzm3341821990-boop/riscv-fir-soc/actions)为准。工作流检查 Python 模型、向量、导出与工具，不宣称运行了 Quartus、厂商 RTL 仿真或物理板卡。上传后核对本次实际提交身份、文件树及 CI，并把发布回读记录保存在本地交付目录。

未创建重复仓库、未强推或创建 Release 标签。未选择或添加 LICENSE，来源边界见 [THIRD_PARTY.md](../THIRD_PARTY.md)。Quartus/ModelSim 安装、厂商库、工作数据库和 SOF 二进制不属于本源码树；已核对的本地 SOF 单独保留。
