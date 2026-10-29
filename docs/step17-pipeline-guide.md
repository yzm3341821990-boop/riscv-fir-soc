# 第十七步：独立五级流水线 CPU

这一步让现有 38 条指令在五级 CPU 上执行，交付功能仿真文件。正在录制的 DE2-115 演示仍使用 step16 的多周期 SoC。本次新核尚未接 FIR MMIO、板级显示或 Quartus 引脚顶层。

## 文件与结构

- [CPU RTL](../rtl/cpu/pipeline_cpu.vhd)
- [时序、旁路、故障与复位契约](pipeline-cpu-contract.md)
- [独立自检查 testbench](../sim/tb/tb_pipeline_cpu.vhd)
- [准备和回归工具](../tools/run_pipeline_cpu.py)
- [ModelSim 波形脚本](../sim/modelsim/run_pipeline_gui.do)
- [本阶段验证报告](../reports/step17-pipeline/validation.json)

```mermaid
flowchart LR
    IF[IF 同步 ROM] --> ID[ID 译码与寄存器读取]
    ID --> EX[EX ALU / MUL / 控制转移]
    EX --> MEM[MEM 同步 RAM]
    MEM --> WB[WB 写回与提交]
    MEM -. 非 load 旁路 .-> EX
    WB -. 旁路 .-> EX
    WB -. 同拍读写旁路 .-> ID
    EX -. load-use 暂停 / 转移清空 .-> ID
```

无暂停时，第一条指令在第 5 拍提交，之后可每拍完成一条。紧邻 load 的真实依赖暂停一拍；EX 中采用的分支/JAL/JALR 产生两拍空泡。MUL 在 EX 组合执行，物理时序需要后续 Quartus 实现确认。

2026-10-29 的 ModelSim 10.5b / VHDL-93 回归已通过 **216 项场景、6483 条提交、1029 笔 CPU 访存**，包括原 188 个程序与 28 个流水线专用场景；10 项受控 RTL 错误全部被执行断言拒绝。Python 完整检查的 213 项测试也通过，记录见[本阶段 Python 报告](../reports/step17-pipeline/python/validation.json)。

| 功能仿真场景 | 提交数 | CPU 有效时钟数 | 暂停 / 转移清空次数 |
| --- | ---: | ---: | --- |
| 20 条独立 ADDI | 20 | 24 | 0 / 0 |
| load 后立即相加 | 4 | 9 | 1 / 0 |
| JAL 跳过 store 与非法字 | 2 | 8 | 0 / 1 |
| 已编译 C 数组求和 | 64 | 98 | 8 / 12 |
| 已编译 software_fir 用例 | 713 | 833 | 0 / 59 |

这里的 CPU 有效时钟数从释放复位到最后提交，包含流水线填充，排除 RAM 初始化。software_fir 是 step11 软件内核程序；833 与 step14 完整调用的 2044 拍、step16 显示的 1131 拍有不同固件或区间，不能混算成加速比。

## 准备文件

在项目根目录运行：

```powershell
python -m tools.run_pipeline_cpu --prepare-only --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/pipeline_view
```

此命令只生成 ASCII 路径下的 RTL 副本、独立期望轨迹和 ModelSim 批处理文件。无需修改现有 Quartus 工程，也不用重新下载开发板。

在 ModelSim 的 Transcript 按顺序输入下面三行。`PIPE_GUI_READY` 是脚本打印的输出，不是需要手动输入的命令。

```tcl
set pipeline_directory {F:/CodexWorkspace/outputs/riscv-fir-soc/pipeline_view}
set pipeline_case_name pipe_load_use
do {F:/大三科目工作区域/riscv-fir-soc/sim/modelsim/run_pipeline_gui.do}
```

若旧 ModelSim 不能从中文目录读取脚本，先把上述 run_pipeline_gui.do 复制到 pipeline_view 目录，再将最后一行改为 ASCII 的完整路径。脚本会先卸载旧仿真再切换目录，避免之前遇到的 “Cannot change directory while a simulation is in progress”。

## 怎样看波形

初始化 RAM 的 256 拍与复位会出现在左侧；脚本默认缩放到 2550～2800 ns 的 CPU 活动区间。

`pipe_load_use` 的指令与提交值如下，PC 都用十六进制：

| 提交 PC | 指令 | rd / 写回值 |
| --- | --- | --- |
| 00 | ADDI x1,x0,7 | x1 = 00000007 |
| 04 | SW x1,0(x0) | rd=0、value=0，RAM[0]=7 |
| 08 | LW x2,0(x0) | x2 = 00000007 |
| 0C | ADD x3,x2,x2 | x3 = 0000000E |

`stall` 恰好拉高一拍，对应 PC/IF/ID 保持并向 EX 注入空泡。实际 RAM 请求只有一次写、一次读。最终日志应为 `retired=4 cycles=9 requests=2 stalls=1 flushes=0`，并打印 `PIPE_GUI_READY`。

查看直线吞吐时，把 pipeline_case_name 改为 `pipe_throughput` 后重跑 `do`：20 条独立 ADDI 在 24 拍内提交；从首次有效提交开始，commit_valid 连续 20 拍为 1。查看跳转清空时使用 `pipe_jal_wrong_path`：错误路径中的 SW 与非法字都不会产生副作用。

## 重跑完整功能验证

```powershell
python -m tools.run_pipeline_cpu --modelsim-bin E:/quartus/modelsim_ase/win32aloem --build-dir F:/CodexWorkspace/outputs/riscv-fir-soc/pipeline_check --report-dir build/pipeline-report
```

工具运行全部旧程序、新增流水线场景、复位场景和受控故障注入。每条提交、每笔同步 RAM 请求、最后的 x1～x31、全部 256 个 RAM 字以及复位后的 RAM 保持均有检查。旧测试向量的 inject_reset 标记不原样套用：新流水线的复位时机由独立场景定义。

诊断单项可增加 `--case pipe_load_use`；单项运行不执行故障注入，不等价于完整回归通过。报告只证明功能仿真，主频、资源、板上加速比和新的周期显示值需后续系统接入与实现后取得。

后续工作是添加 FIR 系统适配、重新测量同一软件/硬件的周期，再提供独立 Quartus 工程由用户编译。现有视频和多周期报告保留各自版本。
