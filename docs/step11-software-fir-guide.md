# 第十一步：MUL 与 CPU 软件 Q15 FIR

本文保留第十一步的软件比较基线；最新进度见[第十二步独立 FIR 硬件核](step12-fir-accelerator-guide.md)。

本步在原有 37 种指令上加入 MUL，当前共 38 种。Clang 编译的 C FIR 在自设计 CPU 上读取采样与系数、执行乘加、统一舍入和饱和，最后把结果写回 RAM。它是后续专用 FIR 加速器的软件比较基线；当前 FIR 由 CPU 软件执行。

## 在 ModelSim 中运行

在底部 Transcript 输入这一条命令：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu/baseline/run_fir_gui.do}
```

脚本卸载旧设计、编译并运行，默认显示初始 RAM 装载完成后的程序过程。游标停在 24726 ns，能同时查看最终输出、计数与完成标志。

| 波形 | 最终值（十进制） |
| --- | --- |
| y0 | 8192 |
| y1 | 12288 |
| y2 | −22528 |
| y3 | 17408 |
| y4 | −12288 |
| y5 | 15360 |
| y6 | −7680 |
| y7、a0_return | −2048 |
| C_done | 1 |
| sp | 1024 |
| retired_count | 713 |
| MUL_operations | 36 |
| finished | TRUE |

y0～y7 直接观察真实 RAM 中的有符号 16 位切片；地址和游标配置由编译清单生成。它们是 Q15 原始整数，除以 32768 才是归一化幅值，例如 y0=8192 对应 0.25。

Transcript 应自动出现 `TINYCPU_PASS retired=713 warmup=0`、`TINYCPU_MEMORY_PASS requests=104 warmup_requests=0` 和 `TINYCPU_MULTIPLY_PASS operations=36`，最后打印 `TINYCPU_FIR_GUI_READY` 与八个输出。这些是输出，不要再次作为命令输入。

## FIR 的计算与数值规则

输入八个有符号 Q15 整数：16384、32767、−32768、8192、−16384、24576、0、−8192。32 个系数的前四个为 16384、−8192、4096、2048，其余为零。

每个输出计算 `A[n] = Σ H[k]·X[n−k]`，其中 k=0～31，块开始前的采样视为零。h[0] 对应当前输入，不输出尾部，八个输入产生八个输出。因为本例只有八个输入，k>n 的项均为零，程序只执行 1+2+…+8=36 次有效乘法；本例能触达 h[0]～h[7]，后续长块测试还需覆盖更远的历史抽头。

两个 signed short 相乘的完整结果能放入 signed int；乘法后转入 64 位 C 累加变量，不对中间乘积舍入。32 抽头的合法输入范围也落在既定的 signed40 数值范围内。最后按绝对值加 16384 后右移 15 位，实现最近舍入、半格远离零；恢复符号后饱和到 −32768～32767。该规则完全沿用 [fir-q15-block-v1](numeric-contract.md)。

本例舍入前的八个 Q30 累加值为：268435456、402636800、−738189312、570421248、−402655232、503316480、−251658240、−67108864。C 程序将这些值也写入 RAM，检查器同时核对原始累加值和最终输出，避免最终饱和掩盖中间溢出。

## MUL 的实现范围

MUL 使用 opcode=0110011、funct7=0000001、funct3=000，取两个 32 位寄存器乘积的低 32 位，不产生算术溢出异常。低位结果对有符号和无符号乘法一致，RTL 用 64 位 unsigned 中间积再取低位。定义依据是 [RISC-V M 规范](https://docs.riscv.org/reference/isa/v20240411/unpriv/m-st-ext.html)。

新增 [mul32.vhd](../rtl/cpu/mul32.vhd) 与原十操作 ALU 并行，译码后在 CPU 写回通路选择乘法结果。MUL 沿用三拍取指、锁存、执行流程，没有新增乘法流水线。组合 32×32 乘法是否映射到 DSP、需要多少资源、能满足什么主频，均须后续 Quartus 综合与时序验证；10 ns 仿真时钟不是板卡主频证据。

本步只实现 M 扩展中的 MUL。MULH、MULHSU、MULHU、DIV/DIVU、REM/REMU 仍进入教学用 FAULT，不能称为完整 RV32IM 或完整 Zmmul。编译器为生成 MUL 启用了 m 特性，构建工具会逐条拒绝 ELF 中其他 M 编码，当前只交付已审计的这份固件。

## C、ELF 与 RAM 布局

- [main.c](../firmware/c_fir_q15/main.c) 是实际 C FIR 源码，samples、coefficients 和输出均为 volatile，保留真实内存读写。
- [main.s](../programs/c_fir_q15/main.s) 是 Clang 的可读汇编；[program.elf](../programs/c_fir_q15/program.elf) 和 [manifest.json](../programs/c_fir_q15/manifest.json) 保存机器码、符号与构建哈希。
- 复用上一阶段的启动代码和链接脚本，代码放在指令 ROM 低 512 字节；数据与栈使用数据 RAM 的 512～1023。镜像仍由 testbench 在复位期间装载。

| 对象 | 字节地址 | 内容 |
| --- | --- | --- |
| samples | 512 / 0x200 | 8×signed16 输入 |
| coefficients | 528 / 0x210 | 32×signed16 系数 |
| accumulators | 592 / 0x250 | 8×signed64 原始累加值 |
| outputs | 656 / 0x290 | 8×signed16 结果 |
| done | 672 / 0x2A0 | 完成标志 |
| _stack_top | 1024 / 0x400 | 初始及恢复后的 SP |

代码为 90 条静态机器指令，基准输入动态提交 713 次，其中 MUL 36 次，CPU 接受 104 笔 RAM 请求。程序为 C 的 64 位运算组合使用现有 32 位指令，没有新增 64 位指令。初始 RAM 装载的 256 笔写入单独统计；结束由 testbench 停钟，不是硬件 HALT。

## 检查与复现

同一份机器码分别运行基准、冲激、正负半格舍入、正向极值、负向极值、零输入、零系数七组 RAM 镜像。每组都与第一步的 Python FIR 比对八个最终输出和八个原始累加值，再逐条检查 CPU 提交及访存。正向极值的最后一个累加值为 2^33=8589934592，可检查超过 32 位的进位；负向极值检查符号扩展与负饱和。

MUL 另检查零、负数、32 位回绕、最高输入位、rd=rs1/rs2、x0/x31、依赖、访存、复位及保留编码。独立 Python 移位相加实现核对随机乘法，避免只把同一乘法表达式作为唯一答案。

重新编译用 `python -m tools.build_fir_demo`；CPU 回归用 `python -m tools.run_cpu --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu`；全部 Python/FIR 数值检查用 `python -m tools.run_step1`。固定工具链仍为 Zig 0.13.0 / Clang 18.1.6，两个独立构建目录的产物逐字节一致，见 [复现报告](../reports/step11-software-fir/compiler-reproducibility.json)。日常回归读取已校验的入库产物，无须重新下载编译器。

本次验证通过 188 个 ModelSim 程序、173 项 Python 测试和 27 次加载切换；核对 6376 次提交、1000 笔 CPU RAM 请求和 311 次 MUL。24 项 RTL 故障与 2 项固件初始化故障全部被发现。7 组软件 FIR 的逐点输出和原始累加值均与既定 Q15 参考一致。初始 RAM 装载另计 2048 笔；70 个 FAULT 用例完成复位检查。故障注入每项使用一个能暴露该错误的用例。

本步完整用例、源码 SHA-256、软件 FIR 输出/累加值及故障注入在 [验证报告](../reports/step11-software-fir/validation.json) 与 [ModelSim 日志](../reports/step11-software-fir/modelsim.log)。MUL_operations 是 testbench 对实际提交指令的计数，不是已实现的硬件性能计数器或 CSR。

当前成果是 CPU 软件 FIR 与功能仿真基线。专用 FIR 加速器、长块与持续流测试、资源与时序结果、真实加速比和上板行为仍需后续实现并独立验证。
