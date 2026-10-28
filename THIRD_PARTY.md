# 来源与依赖

当前 Python 定点模型、生成工具、检查器及测试是本项目为上述数值契约编写的实现，未引入外部 CPU 核或 FIR IP 源码。

| 项目 | 当前用途 | 是否为本项目的 CPU/FIR 硬件贡献 |
| --- | --- | --- |
| Python 标准库 | 整数计算、Fraction 独立检查、测试、文件及命令行 | 工具依赖 |
| Matplotlib 3.11.2 | 可选数值示例图，使用安装环境中的库，无库源码复制 | 可视化依赖 |
| [RISC-V ISA 规范 RV32I v2.1](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html) | 基础 37 种 RV32I 指令的语义与编码依据：19 种 ALU、8 种访存、6 种分支、JAL/JALR、LUI/AUIPC；字节/半字扩展与自然对齐语义于 2026-10-28 核对，小端为本项目环境选择，未复制外部实现代码 | 规范参考 |
| [riscv-opcodes 的 RV_I 编码表](https://github.com/riscv/riscv-opcodes/blob/master/extensions/rv_i) | 分支与跳转 opcode/funct3 编码交叉核对，2026-10-27；未复制生成器或实现代码 | 编码参考 |
| [RISC-V M v2.0](https://docs.riscv.org/reference/isa/v20240411/unpriv/m-st-ext.html) | MUL 的低 XLEN 位结果、其余乘除编码区分；2026-10-28 核对，仅实现 MUL，未复用外部 CPU 代码 | 指令规范参考 |
| [Zig 0.13.0](https://ziglang.org/download/0.13.0/release-notes.html) / Clang 18.1.6 | 本项目 C 与启动汇编的交叉编译工具；不在仓库中复制工具源码或链接其运行库。版本、特性、命令与产物哈希见编译清单 | 工具依赖 |
| [RISC-V psABI](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/) | ILP32、ra/sp/a0 调用约定、栈对齐与 ELF 机器类型参考；2026-10-28 核对整数调用约定 | ABI 参考 |
| [Terasic DE2-115 官方用户手册](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf) | 板级时钟、LED、按键、拨码和数码管引脚/电压依据；引脚表及手册哈希见 fpga/de2_display/pins.json | 硬件资料参考 |
| Spike / riscv-arch-test | 后续 CPU 验证候选，当前未集成、未运行 | 验证工具候选 |
| actions/checkout、actions/setup-python | GitHub Actions 工作流工具，当前只提供配置 | CI 工具依赖 |

外部代码若在后续被复制、修改或作为子模块引入，须在这里记录来源、版本、许可证、修改范围与用途；保留其原有许可文件。外部验证工具的成功运行也须保留版本和配置。

本项目代码许可证尚未选定，公开发布前确定。
