# 在 DE2-115 上运行 DSP6

DSP6 用自设计五级 RV32IM CPU 运行裸机 C。C 程序在板上生成 1 kHz 与 11 kHz 双音，连续调用四路 32 抽头 Q15 FIR，通过共享 32 KiB M9K RAM 传输数据。每块包含 225 个新点和 31 个历史点，最后一块补零。FPGA 用相同输入对比软件、冷调用和系数驻留三条路径，返回校验和与末尾 96 个有效点。[接口契约](step36-dsp-c-contract.md)

## 离线复核实测

在仓库根目录使用 Python 3.10 或更高版本运行以下命令。

```powershell
python -m pip install -r requirements-dsp6.txt
python -m tools.replay_dsp_capture
```

回放核对保存的 308 组 JTAG 请求与响应。独立 NumPy 整数卷积核对结果校验和与最后 96 点，C 程序在板上完成逐块比较。[实测 JSON](../reports/step36-dsp-c/observed-65536.json) · [审阅记录](../reports/step36-dsp-c/board-observation.json)

## 生成工程与运行

```powershell
python -m tools.prepare_de2_dsp --output build/dsp6 --firmware programs/dsp6
```

1. 在 Quartus Prime Lite 17.0 打开 `build/dsp6/riscv_cpu_dsp.qpf`，目标器件为 EP4CE115F29C7，顶层为 `de2_115_dsp_top`。执行全编译并检查 25 MHz 时序。
2. 用 USB-Blaster 和 Programmer 下载工程 `output_files` 中生成的 SOF，然后关闭 Programmer。
3. 让 `quartus_stp.exe` 可通过 PATH 找到，或者将环境变量 `QUARTUS_STP` 设置为它的完整路径。在同一终端启动控制台。

```powershell
$env:QUARTUS_STP = 'C:/intelFPGA_lite/17.0/quartus/bin64/quartus_stp.exe'
python -m tools.open_dsp_console --project build/dsp6
```

4. 在本地控制台点击“连接 DSP6”。用 451 点快速检查输出，选择 65,536 点可运行公开的实测用例。页面保存包含来源、周期与输出的 JSON。

`programs/dsp6` 包含实际使用的 ELF 和构建输入。若要重建固件，请将 Zig 0.13.0 加入 PATH 或设置 `RISCV_ZIG`。使用英文构建路径。

```powershell
python -m tools.build_dsp --output build/dsp6-firmware
python -m tools.prepare_de2_dsp --output build/dsp6-rebuilt --firmware build/dsp6-firmware
```

ModelSim 10.5b 的 RTL 联合仿真使用实际核心和厂商存储模型。设置 `MODELSIM_VSIM` 为 `vsim.exe` 的路径，运行 `python -m tools.run_dsp_cosim --project build/dsp6 --output build/dsp6-rtl --counts 1,451`。[RTL 验证记录](../reports/step36-dsp-c/rtl-bus-validation.json)

## 计时范围

软件、冷调用与驻留周期分别累计。冷调用包括系数装载，驻留调用复用系数。核心任务总时间还包括信号生成、逐块检查和结果整理。主机调用时间包括代码与数据上传、运行等待和读回检查，计时开始前已完成离线参考计算和连接。
