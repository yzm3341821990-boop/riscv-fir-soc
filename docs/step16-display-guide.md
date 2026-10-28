# 第十六步：在数码管上看 FIR 输出和程序周期

用户已反馈新版可用；八个输出、周期和复位的逐项视频待补。完整环境与复现见[运行指南](quickstart.md)，拍摄见[录制指南](demo-recording.md)。

新版已经完成 ModelSim 仿真和 Quartus 全编译。原 LED 版本保存在原目录 `F:\CodexWorkspace\outputs\riscv-fir-soc\de2_115`，新版独立保存在 `de2_115_display`，本次没有自动操作 Programmer。

## 你现在只需下载这个新文件

保持开发板通电，先把 SW0、SW1、SW2、SW3 都拨到 0。

1. 在 Quartus 打开 **Tools → Programmer**，保留已经识别成功的 USB-Blaster 和 JTAG 模式。
2. 选中原 SOF 所在那一行，点击 **Change File…**，换成下面的新 SOF。
3. 勾选 **Program/Configure**，点击 **Start**，等到成功结束。
4. 查看八位数码管，从 HEX7 读到 HEX0；第一项应为 `00002000`。

```text
F:\CodexWorkspace\outputs\riscv-fir-soc\de2_115_display\output_files\riscv_fir_de2_display.sof
```

新工程入口为 `F:\CodexWorkspace\outputs\riscv-fir-soc\de2_115_display\riscv_fir_de2_display.qpf`。需要重新编译时，用 File → Open Project 打开它，再 Processing → Start Compilation。不要误选原 LED 工程的 SOF。

## 拨码与显示对应关系

SW3=0 时，SW2..SW0 按二进制选择输出编号。SW0 权值 1，SW1 权值 2，SW2 权值 4。

| SW2 SW1 SW0 | 输出编号 | 32 位十六进制显示 | 对应有符号整数 |
| --- | ---: | --- | ---: |
| 000 | 0 | 00002000 | 8192 |
| 001 | 1 | 00003000 | 12288 |
| 010 | 2 | FFFFA800 | -22528 |
| 011 | 3 | 00004400 | 17408 |
| 100 | 4 | FFFFD000 | -12288 |
| 101 | 5 | 00003C00 | 15360 |
| 110 | 6 | FFFFE200 | -7680 |
| 111 | 7 | FFFFF800 | -2048 |

这些是本固件的期望显示值。用户已反馈基本显示可用，八项逐一对应的实物记录由后续视频补齐。负数使用完整 32 位补码显示，前面的 F 正常。七段上的 b、d 是小写字形。

SW3=1 时显示程序周期数，当前仿真结果为 **0000046B（1131 拍）**，其余三位开关不影响该模式。计数从 CPU 获释开始，包含 C 配置、硬件工作、轮询与检查，直到板级终止监测；不包含初值装载。它不是 32 抽头 FIR 内核单独的拍数，也不是第十四步基准区间，因此不能把该数直接换成先前的加速比。

按住 KEY0 时数码管空白，松开后重跑并重新显示；执行期间也为空白。发生错误/超时显示 EEEEEEEE。LEDR0/1 常亮、LEDR2 灭、LEDR3 闪的正常定义保持。

## 已执行的验证与边界

实际 ModelSim 检查包含全部 16 个译码字形、未知输入消隐、四次完整启动/复位、32 项输出选择检查、周期独立计时、完成后冻结和错误显示。六项故意引入的段极性、数据捕获、选择顺序、倍频计数、停止计数和符号扩展错误都被运行断言发现，见[仿真报告](../reports/step16-display/simulation-validation.json)。

Quartus Lite 17.0 对参考 EP4CE115F29C7 完成综合、布局布线、汇编和时序：27,451 LE、11,567 寄存器、66 个引脚；25 MHz 最差 setup/hold slack 为 +7.710/+0.180 ns。全部 66 个实际拟合引脚和电压逐项核对，未约束时钟/端口计数为零，0 critical warnings；15 项普通 warnings 保留。见[实现报告及 SOF 哈希](../reports/step16-display/quartus-validation.json)。

数码管跨 JP7=2.5 V、JP6=3.3 V 及固定电压组，配置依据[官方手册](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf)表 4-1/4-4/4-8、[引脚表](../fpga/de2_display/pins.json)和先前实物照片。开关两级同步仅用于人眼观察选择，不控制 CPU 或 FIR。LED/HEX 是人眼观察输出，约束排除其外部采样路径；内部时钟路径正常分析。同步可靠性没有数值 MTBF 声明。

第一版 LED/KEY0 行为已由用户反馈符合预期，数码管新版也已反馈可用。简短反馈未逐项列出八个数值、周期和复位次数，见[观察记录](../reports/documentation/board-observation.json)。本次没有烧写配置 Flash；SOF 临时配置断电后通常需要重新下载。

## 复现

仓库根目录运行 `python -m tools.prepare_de2_display` 和 `python -m tools.run_de2_display`。在生成的英文工程目录运行 `quartus_sh --flow compile riscv_fir_de2_display`，回到仓库根目录运行 `python -m tools.collect_de2_display`。

演示时先拍 SW3=0 的两个正常值和一个负值，再拨 SW3=1 展示周期数，最后按 KEY0 展示复位重跑。视频与板上逐项观察另行记录。
