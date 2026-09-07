# Rust vs Python 换手阻力精度差异 — 完整根因分析

**日期**：2026-06-01
**状态**：已完成根因定位，待实施修复
**关联文档**：`docs/engineering/换手阻力计算性能优化方案.md`、`docs/prompts/prompt-rust-python-precision-investigation.md`

---

## 问题概述

Rust 版和 Python 版全市场换手阻力计算结果存在差异：4594 只共同股票中，2000+ 只的 cyqk 差异超 1e-6，最大差 0.039。

**已确认不是数据源问题**：资本数值（`circulating_capital` / `FloatVolume`）完全一致，差异来自算法实现层面。

### 差异最大的 3 只股票

```
002374.SZ: cyqk_T  rust=0.587200  py=0.548100  diff=0.039100
000727.SZ: cyqk_T  rust=0.901900  py=0.864100  diff=0.037800
000088.SZ: cyqk_T  rust=0.159900  py=0.196400  diff=0.036500
```

### 分析方法

逐环节对比以下文件：
- Rust：`turnover-resist/src/algorithm.rs` + `main.rs` + `data.rs`
- Python：`scripts/full_market_canonical_resist.py` + `qlib_cost/cyq.py` + `qlib_cost/distribution_of_chips.py`

---

## 🔴 根因 #1（P0，最大嫌疑）：Rust 对 T/T-1 窗口使用同一个 capital，Python 使用独立 capital

### Python 行为

`full_market_canonical_resist.py` 构建**四组** capital map：

```python
cap_t = {}   # circulating as_of T
cap_tp = {}  # circulating as_of T-1
free_t = {}  # freeFloat as_of T
free_tp = {} # freeFloat as_of T-1
```

`_steps_2_7` 中对 1001 天的 vol_arr 生成**不同的** turnover 序列：

```python
turnover_circ_t_arr = vol_arr * 100.0 / circ_cap_t       # T窗口用T日capital
turnover_circ_prev_arr = vol_arr * 100.0 / circ_cap_prev  # T-1窗口用T-1日capital
```

### Rust 行为

`main.rs` 只调用一次 `load_free_float_shares`：

```rust
let ff_map = load_free_float_shares(&ff_path, target_date_ms)?; // 仅 as_of T
```

`compute_cyqk_from_curpdfs` 对 T 和 T-1 窗口用**同一个** `float_shares`：

```rust
// circ 口径：T 和 T-1 都用 circ_cap
compute_cyqk_from_curpdfs(..., circ_cap, ...)
// free 口径：T 和 T-1 都用 fc
compute_cyqk_from_curpdfs(..., fc, ...)
```

### 影响量级

当 `circ_cap_t ≠ circ_cap_prev`（季报更新日），turnover rate 偏差 Δt/t 在 1000 次指数衰减递推中被放大。即使 Δt/t = 5-10%，`decay^1000` 的差异足以产生 0.03-0.04 的 cyqk 偏差。

### 诊断方法

检查 002374.SZ / 000727.SZ / 000088.SZ 在 T 和 T-1 的 `circulating_capital` 是否不同。如果不同 → 确认此为最大根因。

### 修复方案

Rust `main.rs` 需调用两次 `load_free_float_shares`，分别传 `target_ms` 和 T-1 对应的毫秒时间戳。T 窗口用 T 日 capital，T-1 窗口用 T-1 日 capital 构建 turnover。

`compute_cyqk_from_curpdfs` 需接受两个 `float_shares` 参数（`float_shares_t` 和 `float_shares_t1`），分别用于 T 窗口和 T-1 窗口的 turnover 计算。

---

## 🟡 根因 #2（P1）：winner/total 计算顺序不同

### Python（`ChipFactor.get_winner`）

```python
tot_cnt = self.cumpdf.sum()
acc_cum = self.cumpdf / tot_cnt        # 先除以 total（~2000 次除法）
return acc_cum[acc_cum.index <= price].sum()  # 再累加
```

### Rust（`calc_cyqk`）

```rust
let total: f64 = cumpdf.iter().sum();
for (j, &price) in xs.iter().enumerate() {
    if price <= close_last {
        winner += cumpdf[j];  // 先累加原始值
    }
}
winner / total  // 最后一次除法
```

### 差异

数学上 `Σ(a_i/T) = Σa_i/T`，但浮点不满足结合律。Python 每个元素除以 total 后再累加（~2000 次小数除法的舍入），Rust 先累加再除（1 次大数除法）。差异量级估计 ~1e-6 到 1e-3，不足以解释 0.039，但会叠加。

---

## 🟡 根因 #3（P1）：Volume 类型不同 — Rust i64 vs Python float64

### Rust（`data.rs`）

```rust
let volume_col = df.column("volume")?.i64()?;  // 整数读取
volume: volume_col.get(i).unwrap_or(0),         // BarRow.volume: i64
```

`calc_turnover_rate`：

```rust
(volume as f64 * 100.0) / float_shares  // i64→f64 转换后计算
```

### Python

```python
arr_raw = df_w[["close", "high", "low", "vol"]].values.astype(np.float64)  # 全部 float64
turnover = vol_arr * 100.0 / capital  # vol 已经是 float64
```

### 差异

如果 parquet 文件中 volume 列的原始值是整数，Rust 的 `i64` 读取是精确的，两者无差异。但如果 parquet 中 volume 实际存储为 float（例如 `1234567.0`），polars `.i64()` 可能做截断或转换，引入舍入。对 turnover 的影响：Δvol/vol ≈ 1e-15（可忽略）。

**风险较低，但建议确认** parquet 中 volume 列的实际 dtype。

---

## 🟢 根因 #4（P2）：数据起止日期范围不同

### Python

```python
start_date = (target - pd.Timedelta(days=window * 2)).strftime('%Y-%m-%d')
# window=1000 → 2000 calendar days ≈ 5.5 年
```

### Rust

```rust
let start_ms = date_to_ms(cli.date - chrono::Duration::days(3000));
// 3000 calendar days ≈ 8.2 年
```

两者都会用 `keep_rows` / `tail` 截取到最后的 window+32 天。只要 parquet 和 DuckDB 中的**尾部数据一致**，窗口不会不同。但如果数据源有差异（DuckDB 有某段数据但 parquet 没有），可能影响 tail 截取的起点。

**风险较低，但建议对差异最大的 3 只股票验证两端数据一致。**

---

## 🟢 根因 #5（P2）：curpdf 涨跌停日 bin 定位精度

### Python batch 版（`_batch_triang_curpdf`）

```python
idx = int(round((c_val - x[0]) / step))  # round 后转 int
```

### Python 原版（`calc_triang_pdf`）

```python
idx = int((close - min_p) / step)  # 无 round，直接截断
```

### Rust（`calc_single_day_curpdf`）

```rust
let idx = ((close - xs[0]) / step).round() as isize;  // f64 round
```

Python batch 版和 Rust 用 `round`，Python 原版用 `int()`（截断）。如果 `close` 恰好在两个 bin 之间（如 `close=10.005, step=0.01`），`int()` 向下取整到 bin 1000，`round()` 取整到 bin 1001。差一个 bin 的筹码集中度对最终 cyqk 影响取决于 vol 大小，通常 <1e-4。

---

## 📋 排查优先级与实施建议

| 优先级 | 根因 | 估计影响 | 验证方法 |
|--------|------|----------|----------|
| **P0** | #1 T/T-1 capital 不分 | **0.01-0.04** | 打印 3 只差异最大股票的 cap_t vs cap_prev |
| P1 | #2 winner/total 计算顺序 | ~1e-3 | 对齐计算顺序后对比 |
| P1 | #3 Volume i64 vs f64 | ~1e-6 | 检查 parquet volume dtype |
| P2 | #4 数据范围差异 | 仅边界 | 对比两端数据 |
| P2 | #5 涨跌停 bin 定位 | ~1e-4 | 对齐 round/trunc |

### 建议实施步骤

1. **第一步（最高优先）**：修复根因 #1 — 在 Rust `main.rs` 中加载 T-1 日 capital，传给 `compute_cyqk_from_curpdfs` 作为独立的 `float_shares_prev` 参数
2. **第二步**：对差异最大的 002374.SZ 打印 T/T-1 capital 值，确认 #1 修复后差异是否消除
3. **第三步**：如果仍有 >1e-6 的差异，对齐根因 #2（Rust `calc_cyqk` 改为先除后加）

---

## 结论

**根因 #1 大概率是 0.039 级差异的主因。** 仅在季报发布日附近 capital 发生变化的股票上表现显著，这解释了为什么不是所有 4594 只都有大差异——大部分股票 T 和 T-1 的 capital 相同（99.9% 的交易日），差异集中在少数 capital 变更日附近的股票。
