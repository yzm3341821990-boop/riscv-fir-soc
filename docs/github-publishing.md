# GitHub 发布准备

当前是本地整理好的 v0.1 文档与源码快照，未创建远端仓库、提交、推送或发布 Release。

## 可用介绍

标题：**RISC-V CPU + Fixed-point FIR Accelerator on DE2-115**

英文短描述：

> An educational VHDL RISC-V CPU and fixed-point FIR accelerator on DE2-115, with bare-metal C, reproducible tests, cycle comparisons, and board result displays.

中文短描述：

> 基于 DE2-115 的自设计多周期 RISC-V CPU 与 32 抽头定点 FIR 加速器，包含裸机 C 驱动、独立数值参考、系统仿真、周期对照、Quartus 实现记录和数码管演示。

建议 topics：`risc-v`、`fpga`、`vhdl`、`fir-filter`、`cyclone-iv`、`hardware-software-codesign`。

## 当前可展示的内容

- CPU 支持 37 种 RV32I 指令加 MUL，能够运行项目裸机 C 固件。
- 32 抽头 signed16 Q15 FIR，40 位累加、明确舍入与饱和规则。
- CPU 配置 MMIO、硬件读写共享 RAM、C 与板级监测器检查结果。
- 在参考器件上通过 25 MHz 时序；保存资源、警告、源码与 SOF 哈希。
- 八个结果的数码管选择、完整自检程序周期计数、KEY0 重跑。
- 同一 CPU 条件下的软件/硬件仿真周期比较。

五级流水线、完整 RV32IM、标准异常环境、实时音频和板上实测加速比尚未实现或验证，发布介绍保留这些边界。

## 视频回来后补齐

1. 按[录制指南](demo-recording.md)核对视频中的开关、数值、周期和复位行为。
2. 保存实际观察表，标明测过的项目和未拍到的项目，不用期望值代填。
3. 在 artifacts/demo/ 中整理封面或演示媒体，README 再加入真实可用的展示链接。
4. 如录屏含 Programmer 页面，保留 SOF 文件名、目标和成功信息，和当前哈希清单一起记录。

## 发布前仍需确定

- **代码许可证**：当前没有 LICENSE 文件，项目尚未指定许可证；本次未代选。外部来源见 [THIRD_PARTY.md](../THIRD_PARTY.md)。
- **仓库名称和可见性**：创建远端仓库时由项目拥有者确定。
- **媒体与实测表**：原始视频收到后再补，不放假封面或空视频链接。

源码快照应包含 model/、rtl/、firmware/、programs/、fpga/、sim/、tests/、tools/、vectors/、docs/、reports/、artifacts/ 和 .github/。programs/ 中的 ELF 和镜像是首次复现所需的小型固件产物，保留它们。

Quartus 安装、ModelSim 安装、工作库、db/incremental_db/output_files 和 Python 缓存不作为源码上传。历史原始日志保留本地路径，这是工具运行证据的一部分，上传前可按需要查看；本次未重写或伪造日志。

发布后再取得真实 GitHub Actions 结果、仓库 URL 和提交/标签身份，更新到验证页。目前 README 的 CI 状态只描述已有配置。
