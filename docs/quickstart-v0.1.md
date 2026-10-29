> 本页保留 step22 整理前的开发记录，数字和待办按当时阶段解读。当前入口见[项目首页](../README.md)。

# 运行指南

本页保留多周期数码管版本 `de2-display-v1` 的复现步骤。五级流水线已上板版本见[第十八步指南](step18-pipeline-soc-guide.md)，当前新增 1/2/4 路并行候选见[第十九步指南](step19-parallel-fir-guide.md)。源码和生成工具随仓库提供，Quartus 编译、生成 SOF 与下载由使用者执行。原 LED 版本与分阶段学习示例见[开发记录](development-history.md)。

## 1. 环境与入口

| 用途 | 本项目已使用的环境 | 是否必需 |
| --- | --- | --- |
| 模型与项目生成 | Python 3.10+；本机报告使用 Python 3.12 | 必需 |
| RTL 仿真 | ModelSim Intel FPGA Starter Edition 10.5b，VHDL-93 | 运行 RTL 测试时必需 |
| FPGA 实现 | Quartus Prime Lite 17.0.0 Build 595，安装 Cyclone IV E 器件支持 | 编译 FPGA 时必需 |
| 重编裸机 C | Zig 0.13.0 / Clang 18.1.6 | 修改固件后才需要 |
| 数值示例绘图 | requirements-visualization.txt 中的 Matplotlib | 可选 |

核心 Python 检查只用标准库。仓库内含已经生成的 C 固件 ELF、ROM/RAM 镜像及编译清单，首次生成 Quartus 工程无需重编 C。

所有 `python -m ...` 命令从仓库根目录执行。推荐把生成的 ModelSim、Quartus 工程放到仓库之外的英文路径；不要直接在安装目录工作。

## 2. 先运行软件检查（可选）

```powershell
python -m tools.run_step1 --report-dir build/local-check
```

它运行 Python 测试、向量重现检查、独立定点参考审计与受控错误检查。报告中的 RTL/综合阶段不因此自动变为通过。

## 3. 生成可直接打开的 Quartus 工程

以下用 `C:\fpga\riscv_fir_display` 举例，可换成你自己的英文目录：

```powershell
python -m tools.prepare_de2_display --output C:/fpga/riscv_fir_display
```

脚本复制 RTL，按已验证 ELF 生成程序和 RAM 初值 ROM，生成引脚设置、SDC、QPF/QSF 及哈希清单。它不调用 Quartus，不连接或编程开发板。

在 Quartus 中依次选择：

1. **File → Open Project…**，打开 `C:\fpga\riscv_fir_display\riscv_fir_de2_display.qpf`。
2. 确认顶层是 `de2_115_display_top`，参考器件为 `EP4CE115F29C7`。
3. **Processing → Start Compilation**。
4. 查看 Flow Summary 和 TimeQuest：完整编译成功之外，还应检查 setup/hold、SDC 警告及未约束路径。

成功后，SOF 在生成目录的 `output_files\riscv_fir_de2_display.sof`。仓库内 `fpga/de2_115` 的旧 QPF 是 LED 工程模板，不能代替上面的完整生成工程。

本机现有入口：

```text
F:\CodexWorkspace\outputs\riscv-fir-soc\de2_115_display\riscv_fir_de2_display.qpf
```

## 4. 接线与下载

参考目标是 Terasic DE2-115 / Cyclone IV E。完整芯片型号应与工程设置匹配；当前参考编译用 F29/C7，不能从 JTAG 的共用 IDCODE 推断封装及速度等级。照片核对过 JP7=2.5 V、JP6=3.3 V，新板或改过跳线的板卡需重新核对。

1. 接配套电源并打开红色电源按钮。
2. USB 线连接标着 **BLASTER** 的方形接口。它邻近红色电源按钮；相邻的 DEVICE 口用于另一种功能。
3. RUN/PROG 开关置 **RUN**。
4. Quartus **Tools → Programmer → Hardware Setup…**，选择 USB-Blaster；Mode 使用 **JTAG**。
5. 首次使用可 Auto Detect；需要选择型号时选择与实物相符的器件。已有旧 SOF 条目时选中那一行并 **Change File…**。
6. 选择这次生成的 `riscv_fir_de2_display.sof`，勾选 **Program/Configure**，点击 **Start**，记录成功结果。

该流程配置 FPGA 的 SRAM；本项目尚无配置 Flash 固化的验证记录。断电后可能回到 Flash 中原有配置，继续演示时重新下载本 SOF。

## 5. 操作与预期显示

SW3=0：SW2..SW0 按二进制选择输出编号。SW0 权值 1，SW1 权值 2，SW2 权值 4。八位数码管按 HEX7→HEX0 阅读，显示 32 位十六进制。

| SW2 SW1 SW0 | 输出编号 | 数码管 | 有符号整数 |
| --- | ---: | --- | ---: |
| 000 | 0 | 00002000 | 8192 |
| 001 | 1 | 00003000 | 12288 |
| 010 | 2 | FFFFA800 | -22528 |
| 011 | 3 | 00004400 | 17408 |
| 100 | 4 | FFFFD000 | -12288 |
| 101 | 5 | 00003C00 | 15360 |
| 110 | 6 | FFFFE200 | -7680 |
| 111 | 7 | FFFFF800 | -2048 |

负数前面的 F 是补码符号扩展。七段字形中的 b、d 为小写形状。

SW3=1：显示整段自检程序周期数，当前仿真预期为 **0000046B = 1131 拍**。包含 CPU 配置、FIR 工作、轮询、结果检查和程序终止监测，排除初值装载；具体边沿定义见[显示契约](de2-display-contract.md)。它不等于 FIR 内核 CYCLES，也不是基准测试的完整调用区间。

按住 **KEY0** 时数码管空白，松开后重跑，恢复当前开关所选择的内容。正常状态是 LEDR0/1 亮、LEDR2 灭、LEDR3 闪；错误或超时显示 EEEEEEEE。运行很快，人眼通常看不到执行中的中间状态。

## 6. 常见问题

| 现象 | 下一项检查 |
| --- | --- |
| Hardware Setup 没有 USB-Blaster | 先确认配套电源、BLASTER 接口、可传数据的 USB 线和电脑直连 USB 口；再看 Windows 是否枚举出设备 |
| 设备管理器出现 USB-Blaster 但有驱动错误 | 使用当前 Quartus 附带的 `drivers\usb-blaster` 驱动目录，按厂商安装说明处理具体错误 |
| 下载成功但数码管无变化 | 确认下载的是 display 工程的 SOF，观察 LEDR3 心跳、松开 KEY0、核对开关状态 |
| 显示 EEEEEEEE 或 LEDR2 亮 | 保存当前现象、SOF 路径/哈希和 Programmer 信息，按 KEY0 重试并记录是否重现 |
| 周期不是 0000046B | 先记录实际数值；核对固件、顶层和计时区间是否改变，不能直接解释为速度提升或下降 |

引脚和电压来自[Terasic 官方手册](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf)表 4-1/4-4/4-8，版本内的逐引脚表在 [pins.json](../fpga/de2_display/pins.json)。

## 7. 开发者可选复现

RTL 仿真，不进行 Quartus 编译：

```powershell
python -m tools.run_de2_display --modelsim-bin E:/quartus/modelsim_ase/win32aloem --build-dir C:/fpga/display_sim
```

仿真会重写相应仿真报告。历史报告需要保留时先备份；源码、工具或参数变化后，应重新生成与当前版本对应的证据。

完成用户自己的 Quartus 编译后，从仓库根目录收集该工程报告：

```powershell
python -m tools.collect_de2_display --project-dir C:/fpga/riscv_fir_display
```

收集工具核对源码、ROM、实际引脚/电压和时序，记录 SOF 哈希；它不执行编译或下载。
