# 第九步：读写字节、半字，保留相邻数据

本页保留第九步的示例与历史结果。当前已进入 [第十步：运行编译的 C 程序](step10-c-program-guide.md)；最新回归在 [第十步报告](../reports/step10-c-program/validation.json)。

前一步已实现 32 位常量与相对地址计算。本步新增 LB、LBU、LH、LHU、SB、SH，当前共支持 37 种指令。它们用于读取字符、16 位采样和 FIR 系数，或只修改内存中的一个字节。

## 运行示例

在 ModelSim 底部 Transcript 输入这一条命令：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu/baseline/run_subword_gui.do}
```

脚本先卸载旧设计，再编译并运行。默认显示 0～600 ns，游标位于 566 ns，此时寄存器写回及检查均已完成。无需先手动关闭旧仿真。

Transcript 应自动出现 `TINYCPU_PASS retired=16 warmup=0`、`TINYCPU_MEMORY_PASS requests=10 warmup_requests=0`，最后显示 `TINYCPU_SUBWORD_GUI_READY LB=FFFFFF81 LBU=00000081 LH=FFFF80FF LHU=000080FF RAM_byte64=ABCD557F retired=16.`。这些是输出，不要把它们再作为命令输入。

## 同一个字节，为什么会读出两个数

程序先将字 `80FF817F` 写入字节地址 64。项目采用小端布局：

| 字节地址（十进制） | 64 | 65 | 66 | 67 |
| --- | --- | --- | --- | --- |
| 初始内容（十六进制） | 7F | 81 | FF | 80 |

LB 与 LBU 都从地址 65 取出 81。LB 把它当作有符号 8 位数，最高位为 1，扩展得到 FFFFFF81，即 −127。LBU 把它当作无符号数，高位补零，得到 00000081，即 129。

LH 与 LHU 都从地址 66、67 取出半字 80FF。LH 扩展为 FFFF80FF，即 −32513；LHU 扩展为 000080FF，即 33023。这里的符号扩展规则来自 [RV32I 的 Load and Store 定义](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html)；小端布局是本项目执行环境的选择。

| 波形 | 最终值（十六进制） | 含义 |
| --- | --- | --- |
| x3 | FFFFFF81 | LB 结果，十进制 −127 |
| x4 | 00000081 | LBU 结果，十进制 129 |
| x5 | FFFF80FF | LH 结果，十进制 −32513 |
| x6 | 000080FF | LHU 结果，十进制 33023 |
| x9、RAM_byte64 | ABCD557F | 部分写入后读回的完整字 |
| x10 | 0000007F | 最低地址字节保持原值 |
| x11 | 000000AB | 最后读取最高地址字节 |
| retired_count | 16（十进制） | 实际完成的指令次数 |
| finished | TRUE | 检查完成 |

脚本还加入 `LB_signed` 和 `LBU_unsigned` 两行，直接显示 −127 与 129。x3～x6 保存的是修改内存之前读到的结果，后续 store 不会自动改变这些寄存器。

## 只写选中的字节

程序随后执行 `sb x7,1(x1)`，只把地址 65 的字节改成 55；再执行 `sh x8,2(x1)`，只把地址 66/67 改成 CD/AB。

| 操作 | 字节 64 | 字节 65 | 字节 66 | 字节 67 | 完整 32 位字 |
| --- | --- | --- | --- | --- | --- |
| 初始 SW | 7F | 81 | FF | 80 | 80FF817F |
| SB 写入 55 | 7F | 55 | FF | 80 | 80FF557F |
| SH 写入 ABCD | 7F | 55 | CD | AB | ABCD557F |

x8 的完整值是 1234ABCD，SH 只使用低 16 位 ABCD。两次部分写入都保留最低地址的 7F；最后 x9 读回 ABCD557F，x10 再确认低字节仍为 7F。完整程序见 [subword_demo.S](../programs/subword_demo.S)，机器码见 [subword_demo.hex](../programs/subword_demo.hex)。

`byte_enable` 波形用四位二进制显示。SW 的掩码是 1111；本例 SB 选中字节位置 1，为 0010；SH 选中位置 2/3，为 1100。写总线数据分别为 80FF817F、00005500、ABCD0000。没有请求时，掩码为 0000，写数据也归零，这是正常的空闲行为。

## 波形关键时刻

| CPU 上升沿 | 动作 |
| --- | --- |
| 135 ns | SW 保存初始字 80FF817F |
| 175 ns | LB 写回 x3=FFFFFF81 |
| 215 ns | LBU 写回 x4=00000081 |
| 255 ns | LH 写回 x5=FFFF80FF |
| 295 ns | LHU 写回 x6=000080FF |
| 355 ns | SB 将完整字改为 80FF557F |
| 445 ns | SH 将完整字改为 ABCD557F |
| 485 ns | LW 写回 x9=ABCD557F |
| 565 ns | 最后一条 LBU 写回 x11=000000AB |
| 566 ns | testbench 完成检查，retired_count=16 |

每条 load 仍经历四拍，store 三拍；程序共 16 条指令、7 次读取、3 次写入。testbench 在上升沿后等 1 ns 才检查并打印提交，因此日志中对应的提交时间晚 1 ns。

请求和掩码应在接受沿之前观察。例如在 354 ns 可见 SB 的 req=1、byte_enable=0010；在 444 ns 可见 SH 的 1100。接受沿后 CPU 状态变化，请求与掩码会清零。RAM 内容则在接受沿更新。这样可以同时检查“写了哪里”和“相邻数据有没有保留”。

## 实现与检查

[tiny_cpu.vhd](../rtl/cpu/tiny_cpu.vhd) 按访问宽度检查对齐，生成掩码和移位后的写数据，再从完整读字中选取字节/半字并扩展。[data_ram.vhd](../rtl/cpu/data_ram.vhd) 按 byte_enable 修改选中的字节，读取仍返回完整 32 位字。没有 CPU 软件读改写步骤。

提交轨迹仍为五列 PC/指令/rd/值/下一 PC。访存轨迹升级为四列 `MODE BYTE_ADDRESS BUS_DATA BYTE_ENABLE`：读数据是 RAM 返回的完整包含字，提交数据才是扩展后的值。testbench 检查请求沿的方向、原始字节地址、写数据和掩码，并检查同步读返回值与最终 RAM。

测试覆盖四个字节位置、两个半字位置、符号边界、x0、寄存器别名、地址回绕、负偏移、RAM 末尾、未对齐/越界/保留编码无副作用，以及复位取消 LB/LH 写回并保留先前部分写入。Python 还使用独立 bytearray 与 int.from_bytes 对混合随机访问逐笔交叉检查。

本次本地验证：164 个 ModelSim 程序通过，1038 次提交、257 笔 RAM 请求核对一致，21 项定向 RTL 故障全部被发现；153 项 Python 测试和 21 次加载切换通过。证据限于功能仿真，Quartus 综合、资源、时序和板级结果仍待验证。其中 1028 次为主程序提交，10 次为复位预执行；251 笔为主程序请求，6 笔为预执行。63 个 FAULT 用例完成复位检查。每项故障注入选用一个能暴露对应错误的用例。

完整结果与源码哈希见 [本步报告](../reports/step9-subword/validation.json)，实际仿真输出见 [ModelSim 日志](../reports/step9-subword/modelsim.log)。在项目根目录运行 `python -m tools.run_cpu --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu` 可重建英文路径下的副本并运行 CPU 回归；`python -m tools.run_step1` 执行全部 Python 测试与原 FIR 数值检查。`python -m tools.check_modelsim_switch --include-cpu` 检查加载切换和数值完成，不检查 GUI 窗口渲染。

## 当前边界

数据 RAM 仍为 1 KiB。字节地址可为 0～1023；半字必须偶数且最大为 1022；整字必须四字节对齐且最大为 1020。无效访问进入教学用 FAULT，不发请求、不提交、不修改内存；没有未对齐拆分或标准异常处理。

37 种指令不等于完整 RV32I 执行环境：FENCE、ECALL/EBREAK、CSR、乘除、中断和流水线仍待实现。程序由 testbench 按预期提交数结束，没有新增 HALT。当前是 Python 与 RTL 功能仿真证据，Quartus 综合、字节使能的 M9K 推断、时序和上板行为需分别验证。
