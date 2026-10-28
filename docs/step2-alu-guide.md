# 第二步：在 ModelSim 中运行第一个 CPU 模块

当前实现为 VHDL-93 的 32 位组合 ALU，支持 ADD、SUB、AND、OR、XOR、SLL、SRL、SRA、SLT 和 SLTU。精确语义见 [ALU 契约](alu-contract.md)。

## 现在在窗口里做什么

在 ModelSim 底部的 Transcript 找到 `ModelSim>`，在提示符后输入下面这一行，再按 Enter。不要把 `ModelSim>` 本身复制进去。

```tcl
do {F:/CodexWorkspace/outputs/riscv-fir-soc/alu32/baseline/run_alu_gui.do}
```

这是本机已生成的仿真工作副本。脚本会进入仿真目录、编译 VHDL、加载测试平台、加入波形并执行全部测试。旧版 ModelSim 的运行副本放在英文路径，源码仍位于原项目目录。

成功时，Transcript 应包含以下输出。**这些是运行结果示例，不要作为命令输入。**

```text
ALU32_PASS vectors=4880
ALU32_GUI_READY: first 16 hand-derived vectors are visible.
```

并出现 Wave 波形窗口，先显示前 16 ns 的手算例子。完整仿真结束时间为 4880 ns，这不是实际 FPGA 运算耗时。

## 波形里看哪些信号

| 信号 | 含义 |
| --- | --- |
| test_index | 当前测试序号，从 1 开始 |
| alu_op | 内部操作选择，十六进制 0～9 为有效运算 |
| a、b | 两个 32 位输入，以十六进制显示 |
| expected | Python/手算向量给出的期望结果 |
| result | VHDL ALU 实际计算结果 |
| finished | 全部向量成功检查后为 TRUE |

首先对照 `expected` 和 `result`；每条向量等待 1 ns 后自动断言二者一致。切换输入时可能有 delta cycle 更新，所以检查点由 testbench 规定。

特别观察这几段：

| 时间区间 | 运算 | 期望结果 |
| --- | --- | --- |
| 0～1 ns | FFFFFFFF + 00000001 | 00000000 |
| 1～2 ns | 7FFFFFFF + 00000001 | 80000000 |
| 7～8 ns | 80000000 逻辑右移 1 位，op=6 | 40000000 |
| 8～9 ns | 80000000 算术右移 1 位，op=7 | C0000000 |
| 9～10 ns | FFFFFFFF 与 1 有符号比较，op=8 | 00000001 |
| 10～11 ns | FFFFFFFF 与 1 无符号比较，op=9 | 00000000 |

上述时间只是为了方便观察，ALU 由组合逻辑构成；最终电路延迟要通过 Quartus 的实现与时序分析取得。

## 文件对应关系

- `rtl/cpu/alu_pkg.vhd`：定义内部运算编码。
- `rtl/cpu/alu32.vhd`：可综合的 ALU 电路描述。
- `sim/tb/tb_alu32.vhd`：仅用于仿真的输入激励、结果断言和结束标记。
- `model/alu.py`：Python 位向量参考。
- `tools/generate_alu_vectors.py`：16 条手算例子、2304 条边界组合和 2560 条固定种子随机向量。
- `tools/run_alu.py`：批处理编译、功能仿真及 SRA 故障注入检查。
- `reports/step2-alu/`：当前版本的验证报告和日志。

## 修改源码后重新生成工作副本

在项目根目录执行：

```powershell
& 'C:\Users\33418\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tools.run_alu --build-dir 'F:\CodexWorkspace\outputs\riscv-fir-soc\alu32'
```

然后回到 ModelSim，再执行前面的 `do` 命令。直接在生成的英文目录里改文件会在下次运行工具时被覆盖，正式修改应写回 `rtl/` 等项目源文件。

其他电脑需要 Python 3.10+ 和 ModelSim，可使用 `--modelsim-bin` 指定模拟器目录，`--build-dir` 指定英文工作目录。Python 参考测试可独立运行，无需模拟器。

故障注入会把临时副本的 SRA 故意改成逻辑右移，要求在第 9 条向量报 `ALU32_MISMATCH` 并非零退出；项目中的正式 RTL 不受该修改影响。临时错误源码会清理，失败日志作为验证证据保存。

本阶段完成的是 ALU 功能仿真。后续先做寄存器组，再连接译码、PC 与指令执行通路。
