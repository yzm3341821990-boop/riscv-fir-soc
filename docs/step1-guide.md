# 第一步：建立可以检查硬件的 FIR 参考答案

这一步的成果是一套可运行的 Python 数值模型、边界测试和测试数据。后面 CPU 执行 C 程序、FIR 硬件执行同一任务时，都必须产生与这套数据一致的输出。

## 先理解三个量

- `X[n]`：第 n 个输入样本，n 从 0 开始。
- `H[k]`：第 k 个滤波器系数，k 从 0 开始；H[0] 对应当前样本。
- `Y[n]`：当前输出，是当前输入与过去 31 个输入分别乘系数后的和。

硬件不存储小数点本身。本项目把 0.5 写成整数 16384，因为 `16384 / 32768 = 0.5`。两个这样的整数相乘，得到的乘积需要除以 `2^30` 才是其真实值；输出再转换回 15 个小数位。

完整规则见 [数值契约](numeric-contract.md)。

## 一个可以手算的例子

只让前三个系数非零：`h=[0.5,-0.25,0.125]`，其余 29 个为零；输入 `x=[0.5,0.25,-0.25,0]`，开始前历史为零。

| n | 运算 | 实数输出 | Q15 输出整数 |
| --- | --- | --- | --- |
| 0 | 0.5×0.5 | 0.25 | 8192 |
| 1 | 0.5×0.25 - 0.25×0.5 | 0 | 0 |
| 2 | 0.5×(-0.25) - 0.25×0.25 + 0.125×0.5 | -0.125 | -4096 |
| 3 | 0.5×0 - 0.25×(-0.25) + 0.125×0.25 | 0.09375 | 3072 |

在项目根目录运行：

```python
from model.fixed_fir import fir_block

x = [16384, 8192, -8192, 0]
h = [16384, -8192, 4096] + [0] * 29
result = fir_block(x, h)
print(result.outputs)       # (8192, 0, -4096, 3072)
print(result.accumulators)  # 原始乘加结果，尚未舍入
```

先看懂这个例子，再查看 `model/fixed_fir.py` 中的 `fir_block()`，就能对应当前样本、历史样本和乘加循环。

## 在 Windows 上复现

数值模型与所有自动检查只需要 Python 3.10 或以上，不需要 NumPy、SciPy 或开发板。PowerShell 示例：

```powershell
Set-Location 'F:\大三科目工作区域\riscv-fir-soc'
python -m tools.run_step1
```

若 `python` 没有加入 PATH，本机已验证的解释器为：

```powershell
& 'F:\CodexWorkspace\.codex-deps\electronics-science\Scripts\python.exe' -m tools.run_step1
```

完整检查会运行单元/集成测试、重新生成并逐字节比对向量、用独立有理数实现审计向量，再注入三类错误检查测试是否失败。报告保存在 `reports/step1/validation.json`，完整日志也在该目录。

单独执行各阶段：

```powershell
python -m unittest discover -s tests -v
python -m tools.generate_vectors
python -m tools.verify_vectors vectors
python -m tools.check_mutations
```

`generate_vectors` 会覆盖它负责生成的同名文件。修改模型后，应查看测试结果和向量变化，再把更新的文件纳入版本管理。

## 观察滤波示例

可选绘图依赖：`python -m pip install -r requirements-visualization.txt`。使用已有 Matplotlib 环境即可直接运行：

```powershell
python -m tools.plot_demo
```

输出位于 `artifacts/step1/`：PNG/SVG 图、逐样本 CSV 和 JSON 参数/指标。

示例采样率 48 kHz，输入包含 1 kHz 与 11 kHz，使用 32 抽头 Hamming 窗低通滤波器，设计截止频率 4 kHz。幅频响应展示整个频段；两个输入频点仅用于示范。11 kHz 避开了当前量化系数在 12 kHz 的偶然精确零点，使幅度测量具有代表性且能与理论响应核对。

图的第一部分观察输入与输出；第二部分比较浮点设计系数与 Q15 系数的频率响应；第三部分检查输出舍入误差。第三部分的浮点参考使用相同的量化输入和系数，因此只反映最终舍入；与原始浮点设计的总量化误差另列在 JSON 中。

时间图中的输出含滤波器自身的 15.5 样本群延迟。误差是样本结果的数值误差，不是硬件测得的信噪比；衰减数值也不表示整段阻带都达到同样指标。

## 你现在需要掌握的内容

1. 能根据前三个系数和四个输入手算上述输出。
2. 能解释 16 位整数怎样表示 0.5，以及为什么乘积有 30 个小数位。
3. 能解释负半格为什么舍入为 -1、输出为什么需要饱和。
4. 能从 `vectors/positive_ties/trace.csv` 对照 `expected.hex` 看懂一组结果。

这四点会直接用于后续 C 软件与 FIR RTL。当前阶段的验证范围是 Python 数值行为；CPU、总线时序、FPGA 综合及上板测试在后续阶段执行。
