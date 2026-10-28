# 第七步：让 CPU 执行循环，计算 1+…+10

最新 [第十步](step10-c-program-guide.md) 已运行编译的裸机 C 示例；本页保留对应历史阶段的学习内容及限制。

本页为历史阶段示例。当前已加入 [第九步的字节与半字读写](step9-subword-guide.md)；原程序和加载命令继续可用，当前能力以 CPU 契约和最新报告为准。

本页保留第七步的循环示范与历史验证范围。当前已进入 [第八步：32 位常量与相对地址](step8-upper-immediate-guide.md)，下面的循环示范继续可用。

前一步已经把计算结果存进 RAM、再读回来。这一步给 CPU 加上条件分支和跳转，使它能够改变下一条指令的地址，重复执行一段程序。后续的软件 FIR 要逐个处理样本、遍历系数，循环是必需的基础。

本步新增 BEQ、BNE、BLT、BGE、BLTU、BGEU、JAL、JALR，共支持 29 种指令。演示先用 BLT 完成一个容易核对的任务：把 1 到 10 累加得到 55，存入 RAM 字节地址 64，再读回 x4。JAL/JALR 的返回地址和间接跳转由自动测试单独检查。

## 在 ModelSim 中打开演示

在窗口底部 Transcript 的提示符后，只输入下面这一条命令：

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu/baseline/run_loop_gui.do}
```

脚本会卸载旧设计，再切换目录、编译、运行并加入波形；无需手动关闭前一个 ALU、寄存器组或 CPU 仿真。默认显示 0～1100 ns，游标在最后一次读回及检查完成后的 1076 ns。

Transcript 应自动显示 `TINYCPU_PASS retired=35 warmup=0`、`TINYCPU_MEMORY_PASS requests=2 warmup_requests=0`，最后显示 `TINYCPU_LOOP_GUI_READY sum=55 RAM_byte64=55 x4=55 retired=35.`。这些是程序输出，**不要把 PASS 或 GUI_READY 行当作命令输入**。出现红色 Error/Failure 时，应保留对应错误行排查，不能仅凭已有波形判断运行通过。

## 先看最后的结果

脚本把 x1～x4 和 RAM 数据设为十进制显示，PC 与指令仍使用十六进制。

| 波形 | 最终值 | 含义 |
| --- | --- | --- |
| x1 | 11 | 循环计数器；加完 10 后已自增到 11 |
| x2 | 11 | 循环结束比较值 |
| x3 | 55 | 累加结果 |
| RAM_byte64 | 55 | 存入字节地址 64 的结果 |
| x4 | 55 | 从 RAM 读回的结果 |
| retired_count | 35 | 实际完成的指令次数 |
| finished | TRUE（1076 ns） | testbench 已完成预期检查并停止时钟 |

55 的十六进制是 `00000037`，因此在 `commit_value` 看到 37 也表示相同结果。数据地址 64 的十六进制是 `00000040`；内部 RAM 使用 32 位字数组，所以它对应 `bank(16)`，不是 `bank(64)`。

CPU 在 1075 ns 写回 x4=55，testbench 在 1076 ns 检查完成后更新 retired_count=35 并将 finished 设为 TRUE。默认游标位于 1076 ns，可以一起检查这些最终值。

## 这八条指令做了什么

源程序见 [loop_demo.S](../programs/loop_demo.S)，对应机器码见 [loop_demo.hex](../programs/loop_demo.hex)。

| 指令地址 PC（十六进制） | 指令 | 作用 |
| --- | --- | --- |
| 00 | `addi x1, x0, 1` | 从 1 开始计数 |
| 04 | `addi x2, x0, 11` | 把结束比较值设为 11 |
| 08 | `addi x3, x0, 0` | 累加器清零 |
| 0C | `add x3, x3, x1` | 把当前计数加入总和 |
| 10 | `addi x1, x1, 1` | 计数加 1 |
| 14 | `blt x1, x2, loop` | 若 x1 小于 x2，回到地址 0C |
| 18 | `sw x3, 64(x0)` | 把总和保存到 RAM |
| 1C | `lw x4, 64(x0)` | 从 RAM 读回总和 |

`BLT` 按有符号数比较两个寄存器。这里比较的都是小正数；条件成立时，从该条分支地址 `0x14` 加上字节偏移 −8，得到 `0x0C`，重新做加法。条件不成立时，从 `0x14` 前进到 `0x18`，开始保存结果。语义依据见 [RISC-V RV32I 的控制转移说明](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html)。

每轮先累加、再让计数器加 1，最后比较。因此计数器是 10 时仍会执行一次加法，随后变为 11；`11 < 11` 不成立，退出循环。x3 依次变成 1、3、6、10、15、21、28、36、45、55。

程序文件只有八条指令，但其中三条循环体执行十遍：三条初始化 + 三条×十轮 + 两条访存 = 35 次提交。分支总共执行十次，其中九次跳回，一次向前。这就是“程序有几条指令”与“运行时执行多少次”的区别。

## 再看 CPU 如何跳回

关注 `Completed instruction` 分组：`commit_valid=1` 表示刚完成一条指令，`commit_pc` 是这条指令原来的地址。循环期间它依次出现 `0C → 10 → 14 → 0C`，重复这个过程。当前 `PC` 在同一个提交沿已经更新为下一条地址，不能把沿后的 PC 当作刚完成指令的地址。

| 时刻 | 观察点 |
| --- | --- |
| 135 ns | 第一次 ADD 完成，x3=1 |
| 165 ns | 计数器自增，x1=2 |
| 195 ns | 第一次 BLT 完成；2<11，当前 PC 跳回 0C |
| 945 ns | 最后一次 ADD 完成，x3=55 |
| 975 ns | 计数器自增到 11 |
| 1005 ns | 最后一次 BLT 完成；11<11 不成立，当前 PC 变为 18 |
| 1035 ns | SW 被接受，RAM_byte64=55 |
| 1065 ns | LW 读请求被接受，RAM 随后返回 55 |
| 1075 ns | LW 写回 x4=55，完成第 35 次提交 |

表中是 CPU 的上升沿动作时刻。testbench 在沿后等待 1 ns 再检查并打印提交，所以日志的对应时间是 136、196、1006、1076 ns 等；这一差值来自检查等待。

如果要逐条看，把波形放大到 120～210 ns；如果要看循环退出，放大到 930～1080 ns。只需要拖动波形游标，不用重新运行程序。

`next_PC_preview` 是组合计算的预览，只在 EXECUTE（state=2）提交沿之前解释。提交后 PC 或源寄存器已改变，旧指令仍可能让预览重新计算，所以它不是保存下来的跳转记录。初学时先看 `commit_pc` 与沿后的 `PC` 即可。

普通运算、分支、跳转和 SW 均经历取指请求、指令锁存、执行三个上升沿。LW 还要等待同步 RAM 返回并写回，多一个上升沿；这保留了上一步已经验证的同步存储时序。

## 代码和验证入口

新增的 [imm_b.vhd](../rtl/cpu/imm_b.vhd)、[imm_j.vhd](../rtl/cpu/imm_j.vhd) 负责从分散的指令位中拼接分支、直接跳转偏移；[decode_tiny.vhd](../rtl/cpu/decode_tiny.vhd) 识别指令；[tiny_cpu.vhd](../rtl/cpu/tiny_cpu.vhd) 根据比较结果选择下一 PC，并为 JAL/JALR 写入 PC+4。

[Python 指令模型](../model/tiny_cpu.py) 按 PC 执行相同机器码，生成包含下一 PC 的五列参考轨迹。testbench 独立保存预期 PC，按它索引 ROM，并逐条检查完整提交、下一地址、实际寄存器与逐笔访存；不能只检查最终的 55。受控故障注入进一步检查错误 RTL 能否被同一检查器发现。

在项目根目录运行 `python -m tools.run_cpu --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/tiny_cpu` 可重新生成运行副本并执行完整 ModelSim 回归；运行 `python -m tools.check_modelsim_switch --include-cpu` 检查旧设计尚未卸载时切换各演示的脚本行为。切换检查使用控制台模式，不代表已经检查了 GUI 窗口渲染。

本步历史结果、源码 SHA-256、测试用例与故障注入记录在 [验证报告](../reports/step7-control-flow/validation.json)，对应完整输出在 [ModelSim 日志](../reports/step7-control-flow/modelsim.log)。上面的运行命令现在执行当前完整回归，最新结果写入 [第八步报告](../reports/step10-c-program/validation.json)。正式修改保存在项目目录，英文路径下的 baseline 是可重新生成的仿真副本。

第七步历史回归通过 97 个 ModelSim 程序用例，核对 600 次主程序提交及 6 次复位预执行提交，共 606 次，另核对 47 笔含预执行的 RAM 请求。35 个 FAULT 用例完成复位检查；12 项有意修改 RTL 的定向故障都被执行检查拒绝。对应 Python 检查通过 129 项测试；旧模块与各 CPU 示范之间的 15 次加载切换通过。故障注入每项选用能暴露该错误的用例，未声称每项都重跑 97 个程序。

## 当前边界

本核对实际发生的分支/跳转，要求目标在 1 KiB ROM 的四字节对齐地址范围内；错误目标进入教学用 FAULT。未采用的分支目标不检查。JALR 清除目标 bit 0 后仍须满足四字节对齐。这些规则及顺序执行至 ROM 末端的限制详见 [CPU 契约](tiny-cpu-contract.md)。

当前没有标准异常处理、完整 RV32I、C 运行环境或流水线；循环结束由 testbench 停止时钟，CPU 没有新增 HALT 指令。验证范围是 Python 与 RTL 功能仿真，Quartus 综合、存储器推断、资源、时序和 DE2-115 实机行为仍需后续独立验证。
