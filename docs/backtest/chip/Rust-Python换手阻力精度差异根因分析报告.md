# Rust vs Python 换手阻力精度差异根因分析报告

**日期**: 2026-06-01
**相关 Prompt**: `docs/prompts/prompt-rust-python-precision-investigation.md`

---

## 1. 问题概述

Rust 版和 Python 版全市场换手阻力计算结果存在差异：4594 只共同股票中，2000+ 只的 cyqk 差异超 1e-6，最大差异 0.039。

差异最大的 3 只股票：

| 股票 | Rust cyqk_T | Python cyqk_T | 差异 |
|------|-------------|---------------|------|
| 002374.SZ | 0.5872 | 0.5481 | 0.0391 |
| 000727.SZ | 0.9019 | 0.8641 | 0.0378 |
| 000088.SZ | 0.1599 | 0.1964 | 0.0365 |

**已确认不是数据源问题**：资本数值（`circulating_capital` / `FloatVolume`）完全一致（均为 1,085,209,283），差异来自算法实现层面。

---

## 2. 排查方法

按照 prompt 中的排查方案，对差异最大的股票 002374.SZ 逐环节对比中间输出：

1. **窗口对齐**：确认 T/T-1 窗口覆盖的交易日完全一致
2. **curpdf（三角分布）**：逐日对比三角分布计算结果
3. **cumpdf（衰减累积）**：对比递推累积后的筹码分布
4. **cyqk**：对比 winner/total 计算结果

使用已有的 debug 工具：
- Python: `scripts/debug_precision.py --code 002374.SZ --date 20260525`
- Rust: `turnover-resist/target/release/debug-precision --code 002374.SZ --date 20260525`

同时将 Rust 算法在 Python 中用 numba 精确复刻，与 Python 批量算法在**相同 Python 运行时**下逐环节对比，排除跨语言浮点行为差异。

---

## 3. 排查过程与发现

### 3.1 窗口对齐 → 无差异

| 项目 | Python | Rust | 一致性 |
|------|--------|------|--------|
| union 窗口日期范围 | 2022-04-06 ~ 2026-05-25 | 2022-04-06 ~ 2026-05-25 | ✅ |
| T 窗口起止日期 | 2022-04-07 ~ 2026-05-25 | 2022-04-07 ~ 2026-05-25 | ✅ |
| T-1 窗口起止日期 | 2022-04-06 ~ 2026-05-22 | 2022-04-06 ~ 2026-05-22 | ✅ |
| 窗口 K 线条数 | 1001 (union) / 1000 (per window) | 1001 / 1000 | ✅ |

### 3.2 curpdf（三角分布）→ Rust/Python 算法完全等价

将 `rust_calc_single_day_curpdf`（Rust `algorithm.rs:128-166` 的精确复刻）与 `py_batch_triang_curpdf`（Python 批量三角分布）在 Python 中逐日对比 1001 天：

```
curpdf Rust vs Python: max_diff=0.000000000000000e+00
diff_days(>1e-15)=0/1001
```

**结论**：curpdf 算法在 Rust 和 Python 之间完全等价，无任何差异。

### 3.3 cumpdf（衰减累积）→ 无差异

使用相同的 curpdf 输入，分别运行 Rust 衰减累积算法和 Python 衰减累积算法：

```
cumpdf_T  Rust vs Py(full):     max|diff|=0.000000000000000e+00
cumpdf_T  Rust vs Py(algo only): max|diff|=0.000000000000000e+00
cumpdf_T-1 Rust vs Py(full):     max|diff|=0.000000000000000e+00
cumpdf_T-1 Rust vs Py(algo only): max|diff|=0.000000000000000e+00
```

**结论**：cumpdf 递推累积算法完全等价，差异为零。

### 3.4 cyqk → 无差异

使用相同的 cumpdf 和价格网格：

```
Rust: winner=3.973e5 total=6.767e5 cyqk=0.5871860012
Py:   winner=3.973e5 total=6.767e5 cyqk=0.5871860012
|cyqk diff| = 5.55e-16 (机器精度级别)
```

**结论**：当使用相同网格时，cyqk 计算结果一致（差异在 f64 机器精度范围内）。

### 3.5 关键发现：旧/新 Python 算法路径对比

进一步对比旧算法路径（`cyq.calc_dist_chips`，使用 `make_price_grid`）和新批量算法路径（`_batch_triang_curpdf` + `_batch_cumpdf_4way`，使用 `np.arange`）：

```
OLD (cyq.calc_dist_chips)  cyqk_T = 0.5872  ← 与 Rust 一致
NEW (_batch_triang_curpdf) cyqk_T = 0.5481  ← 与 prompt 的 py 值一致
差异 = 0.0391
```

两个算法路径在**算法层面完全等价**，差异源于它们使用了**不同的价格网格构造方式**。

---

## 4. 根因分析

### 4.1 价格网格构造方式的差异

Python 批量代码（`full_market_canonical_resist.py:297`）使用：

```python
xs = np.arange(min_p, max_p + step, step)  # 重复加法累积
```

Rust（`algorithm.rs:303`）和 `make_price_grid`（`distribution_of_chips.py:13-21`）使用：

```rust
// Rust
let xs: Vec<f64> = (0..n_prices).map(|i| min_p + i as f64 * step).collect();
```

```python
# Python make_price_grid
n = int(np.ceil((max_p - min_p) / step)) + 1
return min_p + np.arange(n) * step  # 乘法，每点一次舍入
```

### 4.2 浮点误差累积机制

`step = 0.01` 在 IEEE-754 binary64 中**无法精确表示**（二进制无限循环小数：`0.009999999776482582...`）。

- **`np.arange`（重复加法）**：每加一次 `step` 产生一次舍入误差，498 次加法后累计误差达 **4.44e-15**
- **`min_p + i * step`（乘法）**：`i * step` 是一次乘法（一次舍入），再加 `min_p`（一次舍入），每点仅 2 次舍入

对 002374.SZ（498 个网格点），两种方式有 **481/498 个点**的 IEEE-754 表示不同。

### 4.3 临界 bin 的边界跨越

收盘价 `close = 3.78` 在 IEEE-754 中的精确值为 `3.78000000000000024869`（hex `3e0ad7a3703d0e40`）。

网格点 x[219]（理论值 = 1.59 + 219 × 0.01 = 3.78）：

| 构造方式 | x[219] IEEE-754 值 | hex | x[219] ≤ close? |
|----------|---------------------|-----|-----------------|
| `make_price_grid` | 3.780000000000000**24869** | `3e0ad7a3703d0e40` | ✅ **TRUE** |
| `np.arange` | 3.78000000000000**202505** | `420ad7a3703d0e40` | ❌ **FALSE** |

`np.arange` 的 219 次重复加法累积了 **1.78e-15** 的正向误差，使 x[219] 略高于 close，导致 `xs <= close` 比较将该 bin **排除**出 winner 累加。

该 bin（位于收盘价正下方）承载大量 cumpdf 权重，排除后 cyqk 从 0.5872 降至 0.5481（**差值 0.0391**），恰好等于 prompt 报告的差异。

### 4.4 关键验证

```
Python literal 3.78        = 3.77999999999999980460  (hex 3d0ad7a3703d0e40)
Parquet 文件中的 close      = 3.78000000000000024869  (hex 3e0ad7a3703d0e40) ← 与 xs219_correct 完全相等
xs219_correct (乘法)        = 3.78000000000000024869  (hex 3e0ad7a3703d0e40)
xs219_arange (重复加法)     = 3.78000000000000202505  (hex 420ad7a3703d0e40)

correct <= close → 3.780...24869 <= 3.780...24869 → TRUE  → bin 计入
arange  <= close → 3.780...202505 <= 3.780...24869 → FALSE → bin 排除
```

### 4.5 为什么影响 2000+ 只股票

每只股票都有自己独特的 `close` 和价格网格。只要某个网格点（不一定是 x[219]）恰好落在 `close` 的比较边界附近，`np.arange` 的舍入误差就可能导致该点的 `<=` 比较结果翻转。对于 4594 只共同股票，有一半左右（2000+）至少有一个临界 bin 受此影响。

### 4.6 排除的其他疑点

| 疑点 | 结论 |
|------|------|
| `triang_pdf` 边界条件（`c==0` vs `c<=0`） | 002374.SZ 的 c_param 均远离 0/1 边界，不影响 |
| 窗口切片（bar-based vs date-based） | 完全一致（均为最后 1000 个交易日） |
| 资本数值来源（parquet vs DuckDB） | 完全一致（circ_cap = 1,085,209,283） |
| `calc_cumpdf` 递推公式差异 | 公式完全等价，差异为 0 |
| turnonver rate 使用不同窗口资本 | 对 002374.SZ，T/T-1 资本相同，不影响 |
| 跨语言 f64 行为差异 | 排除：Rust 算法在 Python 中复刻后与 Rust 二进制输出完全一致 |

---

## 5. 修复方案

### 5.1 代码修改

`scripts/full_market_canonical_resist.py` 第 297 行：

```diff
-    xs = np.arange(min_p, max_p + step, step)
+    xs = make_price_grid(min_p, max_p, step)
```

并在文件头部添加导入：

```python
from qlib_cost.distribution_of_chips import make_price_grid
```

### 5.2 修复状态

修复已在 working copy 中应用（`git diff` 可见），**尚未提交**。

### 5.3 验证方法

```bash
# Python: 运行 debug 脚本，确认 cyqk 与 Rust 一致
D:/anaconda3/envs/vanna311/python.exe scripts/debug_precision.py --code 002374.SZ --date 20260525

# Rust: 运行 debug 二进制，确认 cyqk 与 Python 一致
cd turnover-resist && cargo run --release --bin debug-precision -- --code 002374.SZ --date 20260525

# 预期：cyqk_T = 0.5872（两者一致）
```

---

## 6. 经验教训

### 6.1 `np.arange` 用于价格网格是反模式

`np.arange(start, stop, step)` 内部使用重复加法，浮点误差随元素数量**线性累积**。对于需要**确定性跨语言一致**的价格网格，必须使用 `min_p + np.arange(n) * step`（乘法构造）。

`distribution_of_chips.py` 中的 `make_price_grid` 函数注释已明确指出此问题：

> 不使用 `np.arange(min_p, max_p + step, step)`，因为 arange 内部逐步累加 step 会产生与逐点乘法不同的浮点舍入，导致边界 bin 在 `xs[j] <= close` 比较时被错误包含或遗漏。

### 6.2 跨语言精度对比应先消除网格差异

本次排查中，debug 脚本（`debug_precision.py`）在 Python 侧同时复刻了 Rust 算法，并使用相同的 Rust 风格网格，从而快速排除了算法差异，将问题定位到网格构造。

### 6.3 浮点比较边界是精度 bug 的高发区

`xs <= close` 这类浮点比较对网格点的微小误差极其敏感。一个 1.8e-15 的误差（远小于任何"合理"容差阈值）就能完全改变比较结果，进而影响最终输出。

---

## 7. 相关文件

| 文件 | 角色 |
|------|------|
| `scripts/full_market_canonical_resist.py` | Python 生产批量代码（需修复） |
| `qlib_cost/distribution_of_chips.py` | `make_price_grid` 正确实现 |
| `turnover-resist/src/algorithm.rs` | Rust 核心算法（网格构造正确） |
| `scripts/debug_precision.py` | Python 精度排查 debug 工具 |
| `turnover-resist/src/debug_precision.rs` | Rust 精度排查 debug 工具 |
| `docs/prompts/prompt-rust-python-precision-investigation.md` | 排查需求 prompt |
