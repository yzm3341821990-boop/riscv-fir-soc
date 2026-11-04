# RISC-V CPU + Q15 FIR SoC on DE2-115

自设计五级 RV32IM CPU 运行裸机 C。CPU5 工作台支持上传自写程序、读回整数数组与文本。DSP6 把 CPU、四路 Q15 FIR、DMA 和 32 KiB 共享 M9K RAM 集成在同一 FPGA 镜像中，允许一个 C 任务处理长信号。

## 65,536 点板上实测

DE2-115 的核心时钟为 25 MHz。该任务处理 292 个块。板上 C 程序逐块比较三条路径的输出，错误数为 **0**。主机独立计算得到相同的校验和 `727738349` 与最后 96 个有效输出。

| 路径 | 实测周期 | 累计计算时间 | 相对 CPU 软件 |
| --- | ---: | ---: | ---: |
| CPU 执行 C 软件 FIR | 34,130,645 | 1,365.226 ms | 1× |
| 四路 FIR 冷调用，含系数装载 | 1,096,460 | 43.858 ms | **31.13×** |
| 四路 FIR 驻留调用，复用系数 | 981,412 | 39.256 ms | **34.78×** |

整个板上任务耗时 **1.802 秒**，包括信号生成和检查。主机调用耗时 **4.695 秒**，包括上传、执行等待与读回。旧 LIV0 镜像的逐块传输实验保存了同样点数的 **320.608 秒**主机总耗时。两次记录使用各自的主机计时口径。[DSP6 原始记录](reports/step36-dsp-c/observed-65536.json) · [复核结果](reports/step36-dsp-c/board-observation.json) · [旧 LIV0 记录](reports/step35-large-signal/physical-65536/board-observation.json)

## 实现与复现

| 部分 | 入口 |
| --- | --- |
| DSP6 板上运行和离线重放 | [运行说明](docs/step36-dsp-c-guide.md) |
| CPU5 裸机 C 工作台和 Python SDK | [应用开发说明](docs/cpu5-c-workbench.md) |
| 32 抽头、历史保留和计时寄存器 | [DSP6 接口契约](docs/step36-dsp-c-contract.md) |
| RTL 联合仿真和逐提交检查 | [RTL 记录](reports/step36-dsp-c/rtl-bus-validation.json) · [控制台仿真预览](artifacts/step36/dsp6-rtl-preview.png) |
| 实际 Quartus 实现和时序 | [实现摘要](reports/step36-dsp-c/implementation-summary.json) |

Quartus 实际实现占用 17,155 个逻辑单元、48 块 M9K 和 14 个 9 位乘法器元素。66 个引脚与板级配置一致。33 项时序检查通过，最差 setup/hold 余量为 +9.194 / +0.135 ns。[实现摘要](reports/step36-dsp-c/implementation-summary.json)

已保存的实测可以直接离线复核。重放使用随仓库附带的 ELF 和 308 组 JTAG 请求与响应。

```powershell
python -m pip install -r requirements-dsp6.txt
python -m tools.replay_dsp_capture
python -m tools.prepare_de2_dsp --output build/dsp6 --firmware programs/dsp6
```

生成工程后，使用 Quartus Prime Lite 17.0 打开 `build/dsp6/riscv_cpu_dsp.qpf`。完整编译、下载、控制台启动和固件重建步骤见[运行说明](docs/step36-dsp-c-guide.md)。

## 目录与早期版本

`rtl/` 保存 CPU、SoC 和 FIR 的 VHDL 源码。`firmware/` 保存裸机 C 和运行时。`programs/dsp6/` 保存本次验证所用的 ELF 与构建输入。`model/`、`sim/`、`tests/` 和 `tools/` 提供检查与复现入口。

多周期 v0.1 与早期五级 CPU、并行度实验可从[开发历史](docs/development-history.md)和[此前的公开版本](https://github.com/yzm3341821990-boop/riscv-fir-soc/tree/3fd94a42334c2239110536dbc8d8643ff460612c)查阅。代码与依赖来源见[第三方说明](THIRD_PARTY.md)。
