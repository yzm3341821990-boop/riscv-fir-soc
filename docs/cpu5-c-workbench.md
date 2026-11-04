# CPU5 C 工作台

CPU5 提供独立的通用裸机 C 运行环境。自设计五级 RV32IM 核心运行上传的 ELF，指令存储为 16 KiB，数据 RAM 为 32 KiB。应用可读取整数数组，输出整数数组和短文本。DSP6 使用独立镜像和控制台运行随仓库附带的 FIR 基准。

```powershell
python -m tools.prepare_de2_app --output build/cpu5 --firmware programs/cpu5-examples
```

在 Quartus Prime Lite 17.0 打开 `build/cpu5/riscv_cpu_app.qpf` 并完成编译和下载。把 Zig 0.13.0 和 `quartus_stp.exe` 加入 PATH，也可分别设置 `RISCV_ZIG` 和 `QUARTUS_STP` 为可执行文件路径。在仓库根目录启动工作台。

```powershell
python -m tools.open_app_console --project build/cpu5
```

先载入整数算法、矩阵或软件 FIR 示例。离线检查用 ISA 模型验证 ELF 与输出。连接 CPU5 后可上传、执行和回读。应用接口定义在 `firmware/app_runtime/cpu5.h`。[CPU5 头文件](../firmware/app_runtime/cpu5.h)

Python SDK 支持同一次连接内运行多组输入。默认命令执行离线参考，使用 `--hardware --project build/cpu5` 可由用户明确开启板上任务。[SDK 示例](../examples/cpu5_sdk/call_cpu.py)

```powershell
python -m tools.cpu5_sdk --output build/cpu5-runs
```
