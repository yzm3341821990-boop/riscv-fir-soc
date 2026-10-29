# 第十九步：1 / 2 / 4 路 FIR 并行计算与匹配比较

这一步将已经上板的单路 FIR 扩展为可选的 1、2、4 路 MAC，在同一五级 CPU、同一 C 固件和相同输入下验证。CPU、RAM 地址、MMIO 寄存器、定点舍入和结果显示均不变。三种配置分别生成工程，用户负责 Quartus 编译和下载。

## 已有实质变化

`rtl/fir/fir_serial.vhd` 新增 `MAC_LANES` 泛型。P 路在每个 MAC 边沿并行计算 P 个不同抽头，先将各乘积符号扩展至 40 位，再通过两层归约累加。32 抽头的运算边沿分别为 32、16、8；只在最后一组之后进行一次舍入与饱和。输出反压、清历史、系数写入优先级及复位取消规则不变。接口细节见[并行契约](parallel-fir-contract.md)。

参数从顶层 `FIR_LANES` 传到 SoC、MMIO 和运算核。默认 1 路，原始串行接口仍可使用。保留 `fir_serial` 的历史实体名以兼容原工程，不代表只能执行单路运算。

## 实际运行的周期结果

条件为 32 抽头、N=8、base 数据、无额外 DMA 等待；每一项来自真实执行的 trace 和两笔已接受 marker 写入的沿差。

| 配置 | 软件完整调用 | 硬件冷调用（含系数配置） | 系数驻留调用 | 软件 / 驻留调用 | 硬件内核 CYCLES | 板级整段自检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 路 | 769 | 590 | 331 | 2.323× | 297 | 694 |
| 2 路 | 769 | 462 | 203 | 3.788× | 169 | 562 |
| 4 路 | 769 | 398 | 139 | 5.532× | 105 | 502 |

四路相对单路，驻留调用的周期比为 331/139=2.381×；首次冷调用为 590/398=1.482×。配置和总线开销限制了完整调用收益，所以不以四个乘法通道推断系统四倍加速。

周期性 DMA 等待时，base 的单/双/四路冷调用为 606/462/406，驻留调用为 347/203/147。双路本次轨迹恰好未落在阻塞相位；不能据此宣称等待永远无开销。

![实际完整调用周期](../artifacts/step19/parallel-fir-complete-call.png)

七组输入 × 三种调用模式 × 两种等待策略 × 三种路数，共 126 次匹配执行。跨路数核对相同 CPU、编译配置、每种模式固件、初始 RAM 与布局哈希，并要求软件周期完全一致。原始数据见[逐次测量](../reports/step19-parallel-fir/measurements.csv)、[对照 CSV](../reports/step19-parallel-fir/comparison.csv)及[完整验证报告](../reports/step19-parallel-fir/validation.json)。

上述表格均为功能仿真周期。2026-10-29 用户随后完成 p4 编译与板上验证：四路的实际资源、时序及概括反馈已归档在[实现记录](../reports/step19-parallel-fir/quartus-p4-validation.json)与[观察记录](../reports/step19-parallel-fir/board-p4-observation.json)。完整调用的板上成对计时尚未执行；不能把概括上板确认当作 126 次基准的实物测量。

四路 p4 占 **28,130 LE、11,965 寄存器、1,792 存储位、14 个 9 位乘法器元素**，Fitter 中确认四个 FIR 乘法通道。实际 25 MHz 最差 setup/hold 为 **+11.166/+0.119 ns**；0 错误、0 关键警告、27 条普通警告，66 个引脚与电压标准一致，未约束摘要各项为零。

## 交付工程

| 路数 | 工程路径 | SW3=1 的仿真预期 |
| --- | --- | --- |
| 1 | `F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_parallel/p1/riscv_fir_de2_p1.qpf` | `000002B6`，694 拍 |
| 2 | `F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_parallel/p2/riscv_fir_de2_p2.qpf` | `00000232`，562 拍 |
| 4 | `F:/CodexWorkspace/outputs/riscv-fir-soc/de2_115_parallel/p4/riscv_fir_de2_p4.qpf` | `000001F6`，502 拍 |

建议先编译 p4。三者顶层都是 `de2_115_pipeline_top`；QSF 用 `set_parameter -name FIR_LANES P` 固定顶层泛型，清单同时记录该值，板级仿真使用相同参数。参考器件 EP4CE115F29C7，输入 50 MHz、真实二分频核心 25 MHz，沿用 66 个已核对引脚与电压配置。`reference-images/` 仅是镜像生成中间目录，打开上表的根目录 QPF。

编译后先检查 Flow Summary、setup/hold、未约束摘要及 Critical Warning。新 `.sof` 位于该工程自己的 `output_files/`，例如 p4 的 `output_files/riscv_fir_de2_p4.sof`。确认这些结果再由用户下载，遇到时序不通过时保留报告，不直接调整时钟或掩盖路径。

SW3=0 时八个结果仍为 `00002000`、`00003000`、`FFFFA800`、`00004400`、`FFFFD000`、`00003C00`、`FFFFE200`、`FFFFF800`。LEDR0/1 亮、LEDR2 灭、LEDR3 闪；KEY0 按住空白，松开重载 RAM 并重跑。SW3=1 显示上表整段自检计数，不是基准完整调用或 FIR 内核计数。

旧 step18 工程和 SOF 保留于原目录。工程生成器拒绝覆盖已经包含 `.sof` 的目录；重新生成时选择新目录，以保留用户编译证据。

## 可复现验证

在仓库根目录，Python 3.10+：

```powershell
python -m tools.run_parallel_fir
python -m tools.run_fir_accel --build-dir C:/fpga/serial-regression --report-dir build/serial-regression
python -m tools.run_step1 --report-dir build/python-check
```

默认调用本机 `E:/quartus/modelsim_ase/win32aloem/vsim.exe`；其他机器通过 `--modelsim-bin` 指向 ModelSim 目录，用 `--build-dir` 选择英文路径。脚本只运行功能仿真，不调用 Quartus。

自行生成某一板级工程：

```powershell
python -m tools.prepare_de2_parallel --lanes 4 --output C:/fpga/riscv_fir_p4
```

核级测试逐样本检查 signed16 输出和 signed40 原始累加器，覆盖 72 个场景、5565 个主流输出样本及各配置的协议测试。受控错误包括漏算 lane、复用错误系数、负积零扩展、窄累加、漏掉最后一组、忽略反压与 MAC 中复位，分别在 2/4 路注入并要求失败。非法 3/8 路配置必须拒绝。MMIO 另覆盖错误配置、重复任务、最后写回被阻塞和执行中复位，完整 RAM 内容也会检查。

三种板级配置分别进行四次启动/复位、32 项输出选择、七段极性、计数保持与独立外部时钟秒表检查。单路兼容性回归要求保持 694 拍。历史 step18 源码与 SOF 哈希、用户上板原话已单独归档；本轮新工程只声称已完成实际运行的验证阶段。

## 当前实现记录与下一项

p4 的编译与时序已经核对，用户回答“是和你预期的一样”，支持四路版本板上结果符合预期；没有从这句话推断独立逐项读数或视频。SOF SHA256 为 `c0efccc055cbd7df08efb14a10806ee11ee663522825047e7b0e32dcffd309c8`，实际编译的 RTL 与已验证候选的文件哈希一致。原始报告保存在 reports/step19-parallel-fir/quartus/p4/。

双路 p2 已由用户编译并通过 25 MHz 时序（28,130 LE、10 个 9 位乘法器元素，setup/hold +10.152/+0.152 ns），见[双路报告](../reports/step19-parallel-fir/quartus-p2-validation.json)。同版本 p1 也已编译完成（28,122 LE、8 个 9 位乘法器元素，setup/hold +11.572/+0.145 ns），1/2/4 路实际资源及时序对照现已齐全。旧 step18 单路记录可作为历史参考，但其 RTL 尚未参数化，不能冒充同一源码版本的受控面积扫描。当前实现比较的状态见[成组记录](../reports/step19-parallel-fir/implementation-comparison.json)。新内容仍保存在本地，未上传 GitHub，也未选择许可证。
