# 流水线 FIR SoC（step18 / pipeline-fir-soc-v1）

本步把 step17 五级 CPU 接入既有 FIR MMIO 与共享 RAM，并生成独立的 DE2-115 数码管工程。Quartus 综合、布局布线、时序与下载由使用者执行，不能沿用第一版多周期 SoC 的时序和资源数字。

## CPU 与总线

pipeline_cpu 增加默认 false 的 ENABLE_FIR_MMIO 泛型。默认实例仍只访问 1 KiB RAM；系统显式置 true 后额外接受 0x40003000～0x40003FFF 的自然对齐 LW/SW。该页的 LB/LBU/LH/LHU/SB/SH、非对齐访问及其他高地址仍进入排空式 FAULT，不发请求、不提交错误指令。

其余指令和流水线规则见 [CPU 契约](pipeline-cpu-contract.md)。指令 ROM 只在 imem_en=1 时更新，禁用时保持。数据 RAM 与 MMIO 都在请求接受沿更新读输出，在 WB 沿被消费。读响应来源必须按接受沿保存，不能用下一条指令的组合地址选择；允许相邻 RAM/MMIO 读写。

CPU 数据端无可变等待；FIR DMA 的 ready/rvalid、任务缓冲所有权、舍入/饱和、复位与错误语义沿用 [MMIO 契约](fir-mmio-contract.md)。CPU 可以每拍发一次合法访问，不能因流水线重复执行 START 或系数写入。

## 提交、结束与观察

逐条提交包含寄存的 commit_next_pc。仿真在 commit_valid 且 commit_next_pc=_program_end 后停钟；不以提前取到 END_PC 作为完成证据。真实请求在 MEM 接受、提交在 WB 报告，因此日志允许年幼指令请求先于年长指令的同沿提交；独立回放按实际事件顺序维护 RAM/MMIO，并按顺序提交验证 ISA。

基准沿用 step14 的同一固件、编译器、数据布局、七组输入、三种模式和两种 DMA 等待策略。区间是软件写入 marker=1 与 marker=2 的实际接受沿之差；系数预装载成本、内部 FIR CYCLES、整程序时钟分别记录。新旧 CPU 的周期不能推断物理耗时改善，后者还依赖各自实现主频。

## 板级版本

50 MHz 输入实际二分频为 25 MHz；沿用已核对的 66 个 DE2-115 引脚与 JP7=2.5 V、JP6=3.3 V 参考配置，完整器件号仍由使用者核对。同步装载全部 256 个 RAM 初值后释放 CPU。新的完成监测读取提交记录，并保留 C done、errors、8 次实际 DMA 输出和看门狗检查。

SW3=0 时 SW2..SW0 选择实际 DMA 写回快照，八个值与第一版相同。SW3=1 显示新版本整段自检的有效 core-clock 边沿数，包含启动后的流水线填充和终端观察边沿，排除复位及初值装载；具体期望数由独立外部时钟 stopwatch 验证后填入指南。KEY0 重载 RAM 并重新运行。显示完成后冻结；错误显示 EEEEEEEE。

## 验收与证据

先验证 MMIO 访问保护，再运行 C 自检和 42 组匹配基准的完整 CPU/DMA 轨迹回放，最后检查板级启动、输出选择、计数、复位和错误路径。对 ROM enable、响应来源、访问保护、提交 next_pc、结束判断等实施受控错误注入；编译错误不算捕获。默认 CPU 指令回归也须重新运行。
