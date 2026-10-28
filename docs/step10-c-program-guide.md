# 第十步：运行真正编译出来的 C 程序

本页保留第十步的 C 求和示例与历史结果。当前已在 [第十一步](step11-software-fir-guide.md) 加入 MUL 并运行软件 FIR；求和示例继续可用，最新回归写入 [第十一步报告](../reports/step11-software-fir/validation.json)。

本步沿用已有的 37 种指令，将 C 程序交给 Clang 交叉编译，再将 ELF 导出为指令 ROM 与数据 RAM 镜像，由真实 CPU RTL 执行。示例包括带负数的 16 位数组、循环、函数调用/返回、栈和全局变量。CPU 核与 data_ram 的 RTL 未作修改；testbench 增加了初始 RAM 装载器。

## 在 ModelSim 中运行

在底部 Transcript 输入这一条命令：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu/baseline/run_c_gui.do}
```

脚本会卸载旧仿真、编译并运行。默认显示 2560～4620 ns，游标位于 4596 ns。前 2560 ns 是 testbench 在 CPU 复位期间写入初始 RAM；默认窗口从装载结束处开始，便于直接看 C 程序执行。

| 波形 | 最终值 | 含义 |
| --- | --- | --- |
| C_result | 55 | C 全局变量 result |
| C_done | 1 | C 程序设置的完成标志 |
| a0_return | 55 | main 的返回值，寄存器 x10 |
| sp | 1024 | 返回后恢复的栈指针，寄存器 x2 |
| ra | 0000000C（十六进制） | 返回到启动代码的地址，寄存器 x1 |
| retired_count | 64 | 实际完成的指令次数 |
| finished | TRUE | testbench 检查完成 |

上述结果及计数按十进制显示，ra、PC 和机器码按十六进制显示。Transcript 应自动出现 `TINYCPU_PASS retired=64 warmup=0`、`TINYCPU_MEMORY_PASS requests=13 warmup_requests=0`，最后是 `TINYCPU_C_GUI_READY result=55 done=1 sp=1024 retired=64.`。这些是输出，不用作为命令再次输入。

## C 程序算了什么

源码在 [main.c](../firmware/c_array_sum/main.c)。输入是八个有符号 short：12、−3、25、−10、7、−2、30、−4，和为 55。

main 调用 sum_samples，循环读取这些 16 位数并累加；返回后写 result=55、done=1，再将 result 作为返回值。数组是 volatile，函数带 noinline，且构建关闭循环展开，因此保留真实 RAM 读取、循环和调用。已逐条确认运行中发生八次 LH，提交值依次为 12、−3、25、−10、7、−2、30、−4。把初始 RAM 换成全零时，同一机器码算出 0，说明结果依赖运行时数据。

编译器输出的可读汇编在 [main.s](../programs/c_array_sum/main.s)。其中 call、ret、mv、li、beqz、bnez 是汇编别名或伪指令，汇编/链接后使用现有的 ADDI、AUIPC、JALR、BEQ/BNE 等编码。ELF 内没有新增 CPU 指令，也没有链接标准库或编译器运行库。

当前代码共 29 条静态机器指令，循环使它们实际提交 64 次。CPU 接受 13 笔访存：八次采样读取，栈的保存/恢复，以及 result/done 的写入和 result 的读回。按 [RISC-V 整数调用约定](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/)，x1 为 ra、x2 为 sp、x10 为 a0，标准栈保持 16 字节对齐。本例启动代码设置 sp=1024，main 分配 16 字节栈帧，在地址 1020 保存 ra，返回前恢复 ra 与 sp。

## ELF 与内存布局

| 项目 | 字节地址 | 作用 |
| --- | --- | --- |
| _start | 0 | 汇编启动入口，先设置栈再调用 main |
| sum_samples | 16 / 0x10 | C 求和函数 |
| main | 52 / 0x34 | C 主函数 |
| _program_end | 116 / 0x74 | 本次有限仿真的结束边界 |
| samples | 512 / 0x200 | 八个 16 位输入，占 16 字节 |
| result | 528 / 0x210 | 32 位输出，对应 RAM bank(132) |
| done | 532 / 0x214 | 完成标志，对应 RAM bank(133) |
| _stack_top | 1024 / 0x400 | 初始 SP；实际存储地址位于它下面 |

[link.ld](../firmware/c_array_sum/link.ld) 为本示例保留 512 字节代码区与 RAM 地址 512～1023。底层指令 ROM 和数据 RAM 仍各有 1 KiB，且为独立空间。上面的代码区限制是本固件链接布局；并未把硬件 ROM 缩小。链接脚本为栈保留至少 128 字节，当前栈帧只用 16 字节。

[start.S](../firmware/c_array_sum/start.S) 设置栈指针并进入 main。main 返回后，启动代码跳到 _program_end；testbench 在对应提交后停止时钟。这里没有操作系统退出服务或硬件 HALT，继续提供时钟时 CPU 会读取后续 ROM 内容。

ELF 的初始化数据和 BSS 由 testbench 装载，不是由 CPU 启动代码从指令 ROM 复制。装载器在 rst=1 时通过真实 data_ram 端口写入 256 个字，包含 samples 初值及 BSS 的零；CPU 的请求与提交在这期间必须禁止。装载完成后再施加两拍复位并执行程序。装载的 256 笔写入单独记录，不能混进 CPU 的 13 笔访存。

## 编译与复现

固定工具链为 Zig 0.13.0 附带的 Clang 18.1.6。Windows 便携版本位于 `F:/CodexWorkspace/tools/zig-0.13.0/zig-windows-x86_64-0.13.0/zig.exe`；官方压缩包 SHA-256 为 `d859994725ef9402381e557c60bb57497215682e355204d754ee3df75ee3c158`。没有修改系统 PATH。

使用 riscv32-freestanding、generic_rv32、ILP32、O1、无标准库、小数据区大小为零、关闭指令松弛和循环展开。已查询该版本 generic_rv32 的 CPU 特性，仅为 32bit；生成汇编标记 rv32i2p1，ELF 没有 RVC/浮点 ABI 标志。不能直接使用该工具链的 baseline_rv32，它包含当前 CPU 尚未实现的扩展。

在项目根目录运行 `python -m tools.build_c_demo` 可重新编译，也可用 `--zig` 和 `--build-dir` 指定其他位置。完整命令、编译器哈希、源码哈希、符号地址和产物哈希保存在 [manifest.json](../programs/c_array_sum/manifest.json)。工具代码见 [build_c_demo.py](../tools/build_c_demo.py) 和 [elf32.py](../tools/elf32.py)。

检查入库的文件包括 [program.elf](../programs/c_array_sum/program.elf)、[program.hex](../programs/c_array_sum/program.hex)、[initial_memory.txt](../programs/c_array_sum/initial_memory.txt) 和可读汇编。不同构建目录的再次编译必须逐字节一致；实际结果见 [编译复现报告](../reports/step10-c-program/compiler-reproducibility.json)。文本产物统一 LF，.gitattributes 固定文本行尾及 ELF 二进制属性。

日常 Python 测试和 ModelSim 回归直接读取已校验的入库产物，无须在每次运行时下载或调用编译器。源码或编译工具脚本发生变化而没有重建时，会拒绝使用旧镜像。导出文件还须与 ELF 的实际内容一致；仅改一份 hex 不能绕过检查。构建工具只支持本示例约定的静态 ELF 布局，不是通用 ELF 装载器。

## 验证范围

运行 `python -m tools.run_cpu --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu` 会连同所有历史用例检查 C 程序，报告写入 [本步验证报告](../reports/step10-c-program/validation.json)。testbench 逐条比对 PC、机器码、目标寄存器和值、下一 PC、请求地址/方向/掩码/数据，并比较全部实际 RAM 和复位后的保留状态。编译成功与最终显示 55 都不能替代这些检查。

保留 21 项 RTL 故障注入，并加入两项固件初始化故障：破坏输入初值、遗漏 SP 初始化。前者须由真实 RAM 读取检查拒绝；后者保留正确 SP 要求，并将参考记录中的指令身份改为被注入的机器码，确保由执行值比较拒绝，而非把输入文件不一致误算为执行验证。

本次验证通过 165 个 ModelSim 程序用例、163 项 Python 测试和 24 次加载切换；核对 1102 次提交、270 笔 CPU RAM 请求，初始 RAM 装载另计 256 笔写入。21 项 RTL 故障及 2 项固件初始化故障全部被执行检查拒绝。两次不同目录的 C 编译产物逐字节一致。

本步没有综合、布局布线、时序或上板数据。示例只验证当前内核在上述有限内存、初始化和裸机调用约定下运行这个 C 程序，不宣称支持任意 C 程序、完整 C 库、完整 RV32I 异常环境、中断或操作系统。后续 FIR 软件可在此基础上加入乘法能力和驱动。
