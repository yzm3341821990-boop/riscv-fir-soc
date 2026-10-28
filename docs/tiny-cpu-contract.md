# 最小指令执行通路契约

标识：`tiny-cpu-rv32i-mul-v7`。当前实现 37 种 RV32I 指令和 M 扩展中的 MUL，共 38 种。基础 ALU、访存和控制语义沿用 v6；MUL 与其他寄存器运算同为三拍，写回乘积低 32 位。尚无完整 M/Zmmul、标准异常环境或流水线。

第十三步新增可选 `ENABLE_FIR_MMIO` generic，默认 false，原模型和回归继续按 1 KiB RAM 边界运行。只有新 SoC 实例启用时，额外允许 0x40003000～0x40003FFF 的对齐 LW/SW；MMIO 字节/半字、非对齐和其他高地址仍 FAULT。精确外设行为见 [fir-mmio-1k-v1](fir-mmio-contract.md)。指令集和默认内核契约不变，不能把默认 Python `run_program()` 用作带 MMIO 任务的完整系统模型；系统由独立事务/提交重放检查。

## 指令与状态

寄存器形式 opcode=`0110011`，立即数形式 opcode=`0010011`：

| funct3 | 寄存器形式 | 立即数形式 |
| --- | --- | --- |
| 000 | ADD（funct7=00）/ SUB（funct7=20） | ADDI |
| 001 | SLL | SLLI |
| 010 | SLT | SLTI |
| 011 | SLTU | SLTIU |
| 100 | XOR | XORI |
| 101 | SRL（funct7=00）/ SRA（funct7=20） | SRLI（funct7=00）/ SRAI（funct7=20） |
| 110 | OR | ORI |
| 111 | AND | ANDI |

表中 funct7 用十六进制表示。寄存器形式除 SUB/SRA 外，funct7 必须为 00。SLLI 的 funct7 必须为 00；SRLI/SRAI 只允许表中的两种值。其他立即数运算的高七位属于立即数，不按 funct7 限制。

- 非移位的 I 型指令均把 12 位立即数符号扩展为 32 位。SLTIU 在符号扩展后按无符号数比较；逻辑运算的负立即数也保留扩展出的高位 1。
- 寄存器移位只取 rs2 的低五位；立即数移位只取指令 [24:20]。移位量范围 0～31。
- SRL/SRLI 的高位补 0，SRA/SRAI 的高位复制原符号位。SLT/SLTI 按有符号数比较；SLTU/SLTIU 按无符号数比较，结果为 0 或 1。
- 其他编码进入 FAULT；包含尚未实现的合法 RISC-V 指令。此处 FAULT 是教学内核的停止接口，不是已实现的 RISC-V 异常/特权机制。
- 运算保留低 32 位；x0 恒零。向 x0 的合法指令仍提交，提交记录的 rd=0、value=0。

load 的 opcode=`0000011`，store 的 opcode=`0100011`。load 用 I 型偏移，store 用 S 型偏移（指令 [31:25] 拼接 [11:7]），均符号扩展到 32 位。有效字节地址为 `(rs1 + offset) mod 2^32`。

| funct3 | load | store | 宽度与对齐 |
| --- | --- | --- | --- |
| 000 | LB：8 位符号扩展 | SB：写 rs2 低 8 位 | 1 字节，任意地址 |
| 001 | LH：16 位符号扩展 | SH：写 rs2 低 16 位 | 2 字节，偶数地址 |
| 010 | LW：完整 32 位 | SW：写完整 rs2 | 4 字节，地址为 4 的倍数 |
| 100 | LBU：8 位零扩展 | 保留，FAULT | 1 字节，任意地址 |
| 101 | LHU：16 位零扩展 | 保留，FAULT | 2 字节，偶数地址 |

load 的 funct3=011/110/111 和 store 的 funct3=011/100/101/110/111 进入 FAULT。任何 load 的 rd=x0 仍须执行真实请求及地址检查，只丢弃写回值。所有 store 不写普通寄存器，提交包 rd/value 均为 0；SB/SH 仅改变选中的字节，保留相邻字节。

### U 型立即数指令

LUI 的 opcode=`0110111`，AUIPC 的 opcode=`0010111`。两者都取指令 [31:12] 的完整 20 位作为 U 型数据，低 12 位补 0，形成 `U = instruction & 0xFFFFF000`。向 rd 写回后顺序前进到 PC+4，不访问数据 RAM。

- LUI 写入 `U`，可与有符号 12 位 ADDI 配合构造任意 32 位常量。低段为负时，需要相应调整上段；不能总把目标常量的高 20 位和低 12 位直接拼成两条指令。
- AUIPC 写入 `(该条 AUIPC 的地址 + U) mod 2^32`。基址是当前指令 PC，不是 PC+4，也不由已提交指令数量推算；在跳转后的非连续地址仍须使用实际 PC。
- 指令 [19:15] 和 [14:12] 都属于 U 型立即数，分别不代表 rs1 和 funct3。两种 opcode 下的所有 20 位取值均为合法编码，不因这些位的模式拒绝指令，也不读取普通源寄存器。
- rd=x0 时指令正常提交、推进 PC，但保持 x0=0，提交记录的 rd/value 均为 0。
- Python 的 `encode_lui(rd, imm20)` 与 `encode_auipc(rd, imm20)` 接受原始无符号 20 位字段 `0..0xFFFFF`，不接受已经左移的完整 32 位常量；布尔或非整数参数被拒绝。

RTL 使用 `imm_u` 拼接 U 值；LUI 的加法基址为 x0，AUIPC 的加法基址为当前 PC。U 型不新增状态，继续使用三拍提交。固定 ROM 中可达 PC 小于 1024，U 的低 12 位又为 0，因此当前整核程序不能制造 AUIPC 加法本身的 32 位进位回绕；高位/负偏移及后续 ADDI 的回绕检查不能被描述为已经观察到 AUIPC 自身溢出。

### 分支与跳转

条件分支 opcode=`1100011`，均比较执行前的 rs1、rs2，不写普通寄存器，提交包 rd/value 均为 0。

| funct3 | 指令 | 条件成立时转移 |
| --- | --- | --- |
| 000 | BEQ | rs1 等于 rs2 |
| 001 | BNE | rs1 不等于 rs2 |
| 100 | BLT | rs1 小于 rs2，有符号比较 |
| 101 | BGE | rs1 大于等于 rs2，有符号比较 |
| 110 | BLTU | rs1 小于 rs2，无符号比较 |
| 111 | BGEU | rs1 大于等于 rs2，无符号比较 |

funct3=`010` 或 `011` 不受支持，进入 FAULT。B 型立即数按 `inst[31] : inst[7] : inst[30:25] : inst[11:8] : 0` 拼成 13 位，再符号扩展到 32 位；可编码的字节偏移为 −4096～4094 的偶数。条件成立时，下一 PC 为 `(当前指令 PC + 偏移) mod 2^32`；否则为 PC+4。比较直接使用完整有符号/无符号操作数，不以相减结果的符号位替代有符号比较。

JAL 的 opcode=`1101111`。J 型立即数按 `inst[31] : inst[19:12] : inst[20] : inst[30:21] : 0` 拼成 21 位，再符号扩展；可编码的字节偏移为 −1048576～1048574 的偶数。下一 PC 为 `(当前指令 PC + 偏移) mod 2^32`，向 rd 写入当前指令 PC+4 作为返回地址。

JALR 的 opcode=`1100111`，仅接受 funct3=`000`。使用 12 位有符号 I 型字节偏移：先计算 `(执行前的 rs1 + 偏移) mod 2^32`，再清除目标地址 bit 0；目标不是相对 PC 计算。向 rd 写入当前指令 PC+4。即使 rd=rs1，也必须使用写回前的 rs1 计算目标。JAL/JALR 的 rd=x0 时仍跳转，只丢弃返回地址，提交包 rd/value 为 0。

当前仅实现 32 位指令，没有压缩指令，转移目标要求四字节对齐。**实际发生控制转移时**，CPU 在 EXECUTE 检查目标是否在固定 1 KiB ROM 内且四字节对齐，即合法目标为 0、4、…、1020；JALR 在清除 bit 0 后检查，因此 bit 1 仍为 1 的地址不合法。错误目标进入 FAULT，不提交、不写返回地址、不请求数据 RAM，PC 保持在该条分支/跳转处。条件不成立的分支只走 PC+4，不检查未使用的目标，因此未采用的 `+2` 或越界目标不会触发 FAULT。

这里对 ROM 越界目标的提前拒绝是本教学内核的有限存储停止策略，**不等价于标准指令访问异常在目标取指处发生的时机，也没有实现标准 trap handler**。检查仅覆盖实际转移目标；顺序执行 PC=1020 的合法指令仍可提交并令 PC=1024。若仿真继续取该地址，会由 testbench 的 ROM 地址检查报错，不能据此宣称内核已处理所有顺序取指越界。

PC、指令寄存器、控制和提交记录使用同一 clk，rst 是高有效同步复位。复位令 PC=0、指令寄存器为 NOP、状态为 FETCH_REQUEST、fault=0、commit_valid=0，并连接到寄存器组复位。

LUI/AUIPC、ALU、条件分支、JAL/JALR 与全部 store 使用三拍，全部 load 使用四拍。`debug_state` 为三位：

| 沿前状态 | 此上升沿的动作 | 沿后状态 |
| --- | --- | --- |
| FETCH_REQUEST=0 | 同步 ROM 采样 PC，随后更新数据 | FETCH_CAPTURE |
| FETCH_CAPTURE=1 | 锁存上一拍 ROM 返回的指令 | EXECUTE |
| EXECUTE=2 | 合法 ALU 指令写回、提交、PC+4 | FETCH_REQUEST |
| EXECUTE=2 | LUI 写回 U，或 AUIPC 写回当前 PC+U；提交、PC+4 | FETCH_REQUEST |
| EXECUTE=2 | 合法分支提交，按条件选择目标或 PC+4 | FETCH_REQUEST |
| EXECUTE=2 | 合法 JAL/JALR 写回返回地址、提交、更新 PC 为目标 | FETCH_REQUEST |
| EXECUTE=2 | 有效 store 请求被 RAM 接受，写 RAM、提交、PC+4 | FETCH_REQUEST |
| EXECUTE=2 | 有效 load 请求被 RAM 接受；沿后读数据可用，PC 保持 | LOAD_WRITEBACK |
| LOAD_WRITEBACK=3 | 从同步 RAM 返回值选取与扩展后写回、提交、PC+4 | FETCH_REQUEST |
| EXECUTE=2 | 不支持指令、无效访存或实际转移目标无效：禁止请求、写回与提交，PC 保持，fault=1 | FAULTED |
| FAULTED=4 | 保持 PC、寄存器与 RAM，无请求、无提交 | FAULTED，直到复位 |

外部 `imem_addr` 是当前 PC，`imem_rdata` 必须符合固定一拍的同步读响应。当前没有 ready/valid 或可变等待接口。取指请求和锁存分拍，避免把仿真组合 ROM 的行为误当成片上同步存储器行为。

## 数据 RAM 接口

单一 clk 域，RAM 为 256×32 位，即 1024 字节，映射到字节地址 0～1023。字节访问起始地址为 0～1023；半字为 0、2、…、1022；整字为 0、4、…、1020。地址超界或不满足本次宽度的自然对齐时，在 EXECUTE 进入教学用 FAULT：无请求、无写回、无内存修改、无 PC 推进。没有跨字拆分或未对齐访问支持，也没有标准 trap handler。

- `dmem_req=1` 表示在当前上升沿接受一笔请求，无 ready/backpressure。`dmem_we=1` 为写，为 0 时读。
- `dmem_addr` 是原始有效字节地址。RAM 使用 [9:2] 索引包含字，`lane=addr[1:0]` 选择字节。
- `dmem_be[3:0]` 是字节使能，bit 0 对应包含字中地址最低的字节。读写均给出本次宽度对应的掩码；req=0 时必须为 0000。SB/字节读为 `0001 << lane`，SH/半字读为 `0011 << lane`，整字为 1111。
- store 把 rs2 的低 8/16 位移到选中位置，其余写数据位为 0；SW 提供完整 rs2。RAM 的 byte_enable 端口只修改选中的字节，不通过 CPU 软件读改写实现部分写入。
- 每条有效 load/store 只在 EXECUTE 发送一次请求。复位、取指、LOAD_WRITEBACK、FAULT 均禁止请求和字节使能。
- RAM 在读请求接受沿更新完整 32 位 `dmem_rdata`。CPU 下一上升沿选取对应字节/半字，符号或零扩展后写回；所有 load 四拍，所有 store 三拍。无读请求时，读输出保持原值；写请求不更新读输出。
- RAM 数组初始为零，无清空 RAM 的复位端口。CPU 复位清除控制与寄存器，取消未写回的 load，保留此前已经完成的 SW/SB/SH。
- 第一次读请求前的 RAM 输出未定义，CPU 不在这之前消费它。块 RAM 推断、字节使能资源、初始化、M9K 使用均需 Quartus 综合验证。

本项目选择小端：字 `80FF817F` 在地址 A～A+3 的字节依次为 7F、81、FF、80。端序是本项目执行环境的选择，不表示 RISC-V 只能使用小端。程序 ROM 和数据 RAM 为独立空间，写数据地址 0 不改变 PC=0 的指令。

单独调用 data_ram 时，调用方须保证请求使用二进制、范围内的地址和合法掩码；RAM 本身不产生 FAULT。

## 提交与观察接口

`commit_valid` 是寄存的单拍脉冲；与之同时有效的 `commit_pc/instruction/rd/value` 描述刚完成的指令。PC 在同一个上升沿已更新为下一地址，因此应使用 commit_pc 解读该次提交，而不是把沿后的当前 PC 当成该条指令地址。

调试输出给出当前 PC、锁存指令、状态、译码寄存器地址、读口数据、立即数及 ALU 结果。组合 ALU 输出在寄存器写回后可能随输入更新；提交记录保留实际写回时的值。`debug_next_pc` 是组合的下一地址预览，应在 EXECUTE 沿前阅读；沿后 PC 或源寄存器已经变化，旧指令可能使预览重新计算，因此不能把它当作寄存的提交记录。对实际提交后的 PC，应读取沿后的 `debug_pc` 并与参考轨迹的 NEXT_PC 比较。

当前没有乘除、CSR、FENCE/ECALL 等系统指令、中断或流水线。程序结束由 testbench 在预期提交数之后停止时钟；ROM 其余位置填充 ADDI x0,x0,0，不提供专用停机指令。

## 本轮仿真

testbench 用文件初始化 256×32 位同步 ROM 模型，并实例化真实的 `data_ram` RTL。每个时钟上升沿后等待 1 ns 再检查寄存输出；从参考的当前 PC 索引 ROM 机器码、独立推导三/四拍时序，检查 PC、完整提交包、提交后的下一 PC 和最终 x1～x31 的实际存储值。参考 PC 由上一次核准的轨迹 NEXT_PC 推进，不能再用“提交次数×4”取指，也不从 DUT 的 `debug_next_pc` 获取预期地址。

提交轨迹每行五列：`PC INSTRUCTION RD VALUE NEXT_PC`；32 位字段使用八位十六进制，RD 使用十进制。Python 模型按 PC 索引程序，跳转或循环会改变后续取指位置；默认最多执行 4096 条，仍处于程序中却耗尽上限时抛出 RuntimeError，属于测试防死循环机制，不伪装成硬件 FAULT。模型到达提供的程序范围之外时结束有限运行；硬件 testbench 以对应预期提交数停止时钟。

测试集包括原三指令 demo、七指令移位/比较示范、19 种运算、负立即数和边界、移位 0/31 与寄存器移位量掩码、ADD/SUB 回绕、依赖、x0/x31、不支持的 opcode/保留 funct7/系统指令、合法前缀后的 FAULT、固定种子随机程序和中途复位。

访存测试包括地址 0/1020、正负 S 型偏移、32 位地址回绕、load 的 rd=rs1、store 的 rs1=rs2、写后读/覆盖、LW x0 的真实请求、对齐和越界错误、未实现访存形式及混合随机程序。独立 memory trace 比对接受沿的方向/地址/写数据，并在该沿后核对读返回值；不能仅凭最终寄存器正确就省略请求检查。

控制转移测试覆盖六种条件成立/不成立、负数与有符号边界、向后循环、JAL 返回地址与跳过非法字、JALR 清除 bit 0 和 rd=rs1、丢弃返回地址、四字节对齐和 ROM 范围边界、未采用目标免检、保留编码以及错误目标无写回副作用。`loop_demo` 的八条静态指令执行 35 次，循环内 BLT 九次跳回、一次向前，最终 x3/x4 与 RAM 字节地址 64 均为 55。

U 型测试使用独立机器码与字面结果检查 U 字段边界、最高位、低段符号、非零/跳转后的 PC、x0/x31、被立即数字段覆盖的伪源寄存器及数据依赖。`upper_demo` 的九条静态指令执行八次，先保存和读回 `0x12345678`，再通过 AUIPC/ADDI/JALR 跳过一条清零内存的 SW，最后仍读回同一常量。逐笔访存应仅出现一次写、两次读。

inject_reset 用例先在 FETCH_CAPTURE 前安排有效同步复位，再预执行前两条指令以产生非零寄存器，随后中断下一次取指并复位、从 PC0 重新核对冷启动轨迹。`reset_after_write` 让重新执行的首条指令读取此前写过的 x5，能检查 CPU 到寄存器组的复位连接。

`reset_pending_load` 在接受 LW 请求后、写回前复位，要求取消该提交并从 PC0 重新开始。每个用例结束后均比对全部 256 个实际 RAM 字，再施加 CPU 复位沿，检查 PC/state/fault/提交/RF/请求，并再次比对相同 RAM 内容。FAULT 用例也执行此检查。

字节/半字测试覆盖所有字节位置、两个半字位置、0/1022/1023 边界、符号位、保留编码、负偏移、地址回绕、x0/x31、寄存器别名和部分写入保留。独立 Python 字节数组检查混合随机访问。memory trace 每行四列：`MODE BYTE_ADDRESS BUS_DATA BYTE_ENABLE`；三个数值字段用十六进制。读 BUS_DATA 是包含字的完整 RAM 返回值，提交值则是选取与扩展后的结果；写 BUS_DATA 已移到对应字节位置。testbench 同时核对掩码、方向、地址、写数据及读返回值。

`reset_pending_lb` 和 `reset_pending_lh` 在部分写入完成、读请求接受后且写回前复位，检查取消提交与保留 RAM。原 `reset_pending_load` 继续检查 LW。此前将 LB/SH 当作未实现指令的两项测试，已替换为真正保留的 funct3=011 编码；旧阶段报告仍保留历史含义。

每个用例均有有限周期超时。故障注入检查器必须由真正的执行断言拒绝被修改的 RTL，不能把编译错误算作捕获逻辑错误。当前启用的注入项、每项所用测试以及退出码见 [第十一步验证报告](../reports/step11-software-fir/validation.json)；原阶段报告保留各自源码哈希与历史结果。

指令语义参考 [RISC-V RV32I 规范](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html)的整数运算、Control Transfer Instructions 与 Load and Store 章节。不支持的编码进入 FAULT 是本教学内核的约定，不能代替标准异常处理实现。

当前证据限于 RTL 功能仿真；同步 ROM 的 FPGA 存储推断、资源、时序和板级行为仍需在后续 Quartus 工程中验证。

## 第十步的编译 C 环境

CPU 指令语义仍为 v6，37 种指令，CPU 与 data_ram RTL 未改。C 示例采用固定 RV32I/ILP32 工具链及有界 ELF 布局，见 [第十步指南](step10-c-program-guide.md)。

testbench 的 INITIAL_MEMORY_FILE 泛型默认空字符串，旧用例保持原先零初始化和时间轴。C 用例产生 cases/c_array_sum/initial_memory.txt；cpu_helpers 根据 program 文件所在目录发现此文件后传入泛型，原 11 列 Tcl 用例格式不变。装载器在 CPU 复位期间通过同一 RAM 端口写入 256 个字，不能发出 CPU 请求或提交；随后切回 CPU，再执行两拍复位。C 的初始化数据和 BSS 零来自 ELF 导出的 RAM 镜像，启动汇编仅设置 SP 并调用 main。

装载器属于验证环境，尚未实现为 FPGA 启动硬件。CPU 单独复位保留 RAM，不会重新执行此装载过程，也不会自动清 BSS。镜像装载的 256 笔写入与 CPU 请求计数分开记录。链接后的 _program_end 边界和参考提交数控制 testbench 停钟，没有新增 HALT 指令。

## 第十一步的 MUL 与软件 FIR

MUL 的 opcode=0110011、funct7=0000001、funct3=000，读执行前的 rs1/rs2，向 rd 写入 32×32 乘积的低 32 位；保留 modulo 2^32 语义，不产生算术溢出异常。rd=x0 仍提交但丢弃值。MULH/MULHSU/MULHU/DIV/DIVU/REM/REMU 均未实现，进入既定 FAULT。原来以 MUL 作为非法 R 编码的测试，已改用真正保留的 funct7=0000010。

mul32 使用 64 位 unsigned 中间积，低 32 位等价于二补码有符号乘法低位；CPU 在 EXECUTE 选择其结果写回，不改变提交和复位时序。它是组合乘法器，未综合、未做时序检查，不宣称已使用 DSP 或达到了仿真时钟频率。

软件 FIR 沿用 fir-q15-block-v1：signed16 输入/系数、32 抽头、零历史、Q30 完整累加、最后半格远离零舍入并饱和为 signed16。C 用 signed64 表示合法 signed40 范围，32 位 CPU 通过多条指令完成宽累加。八样本示例只能触达前八个历史抽头；更长块和持续流仍需另行测试。

软件 FIR 的实际输出和累加器均存入 RAM；生成参考轨迹前，必须先将 C 指令模型结果逐点与独立 FIR 算术参考比对。七个输入镜像使用相同 ELF 机器码。testbench 的 multiply_count 只统计当前主运行的已核准 MUL 提交，复位时清零；它是仿真观察信号，不是硬件 CSR。更多范围与入口见 [第十一步指南](step11-software-fir-guide.md)。
