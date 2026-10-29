# 五级流水线首版契约（step17 / pipeline-fixed-memory-v1）

本阶段交付独立的五级 CPU 与回归环境。板上录制继续使用 step16 多周期 SoC。新 CPU 尚未接入 FIR MMIO、板级启动或 Quartus 工程，不沿用旧版资源、25 MHz 时序或 1131 拍数字。

## 指令与执行环境

沿用 [多周期 CPU 的 38 条指令语义](tiny-cpu-contract.md)：37 条 RV32I 加 MUL，独立 1 KiB 指令 ROM 与 1 KiB 小端数据 RAM、自然对齐访问、x0 恒零。无 CSR、标准 trap handler、完整 M 扩展、Cache 或中断。MUL 为单 EX 级组合乘法，其物理时序尚未验证。

## 五级时序

IF：同步 ROM 在 `imem_en=1` 的上升沿采样 `imem_addr`，沿后更新 `imem_rdata`，禁用时保持。该 ROM 输出寄存器就是 IF/ID 指令寄存器；CPU 同步保存对应 PC 与 valid，不能接组合 ROM。

ID：译码、异步读取寄存器、立即数扩展，在 ID/EX 中保存操作数与控制。WB 与 ID 同拍访问同一寄存器时，ID 显式取 WB 写回值。

EX：ALU/MUL、条件判断、跳转地址和访存地址检查。优先使用 EX/MEM 非 load 结果，再使用 MEM/WB 写回值旁路；旁路覆盖分支、JALR、store 数据和地址。跳转在 EX 决定，采用顺序取指，转移时清空两条年轻指令。

MEM：`dmem_req=1` 的上升沿无条件接受一次请求；同步 RAM 沿后给出读数据，store 同沿修改选中字节。没有 ready、可变等待或 FIR MMIO。MEM/WB 保存 load 的地址/宽度，与 RAM 返回值对齐。

WB：下一上升沿写寄存器并发出提交包。每条有效指令（含 store、branch 和 rd=x0）按顺序只提交一次。提交含 PC、指令、rd、value 和 next_pc；rd=0 时 value=0。启动后的第 5 个有效时钟沿首次提交；无暂停/转移的 N 条直线程序用 N+4 拍完成。

若 ID 读取 EX 中 load 的非零 rd，则冻结 PC/IF/ID 一拍，向 EX 插入空泡，随后从 WB 旁路 load 结果。rd=x0 或立即数字段的伪 rs2 不触发暂停。

## 故障与复位

EX 检出非法编码、无效访存或实际转移目标错误时，禁止该指令进入 MEM，清空年轻指令并停止取指。已在 MEM/WB 的年长指令继续完成，排空后才置 `fault=1`；fault_pc 指向被拒绝指令。不提交错误指令、不发送其访存、不写跳转链接。错误保持至复位。

顺序越过 ROM 末尾时禁止物理 ROM 读，传入一条带 PC 的取指错误标记，按上述规则排空；此项比旧内核只检查实际转移目标的边界更明确。

rst 高有效同步复位，清空全部 valid、提交、故障与寄存器，入口 PC=0；rst=1 时组合屏蔽 imem_en、dmem_req、byte_enable 和 RF 写使能。已接受的 store 保留，已读但未 WB 的 load 被取消；数据 RAM 不因 CPU 复位清空。

## 验收

沿用独立 Python ISA 模型的程序/提交/访存/最终 RAM/RF，新增针对旁路优先级、WB-ID 同拍、load-use、分支/store/JALR 依赖、错误路径副作用与排空的定向程序。检查每笔真实 RAM 请求，而非只检查最终结果；使用有限超时和受控 RTL 故障注入。另用直线程序检查首次提交与每拍提交，拒绝把多周期核换名当作流水线。

本阶段报告只证明功能仿真；没有综合、时序、烧录或新板级性能结论。
