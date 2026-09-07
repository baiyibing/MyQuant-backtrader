# Rust vs Python 换手阻力精度差异 — 根因分析报告（定稿）

**日期**: 2026-06-01
**关联 Prompt**: `docs/prompts/prompt-rust-python-precision-investigation.md`

> 本报告综合 Expert P（静态代码分析，5 根因假说）与 Qoder（实测验证，逐环节对比）两份独立排查，对所有论断给出实验判决。

---

## 1. 问题

Rust 版和 Python 版全市场换手阻力计算：4594 只共同股票中，2000+ 只 cyqk 差异超 1e-6，最大差 0.039。

| 股票 | Rust cyqk_T | Python cyqk_T | 差异 |
|------|-------------|---------------|------|
| 002374.SZ | 0.5872 | 0.5481 | 0.0391 |
| 000727.SZ | 0.9019 | 0.8641 | 0.0378 |
| 000088.SZ | 0.1599 | 0.1964 | 0.0365 |

资本数值（`circulating_capital` / `FloatVolume`）完全一致，差异来自算法实现层面。

---

## 2. 排查方法

按 prompt 要求对 3 只股票逐环节对比：

1. **窗口对齐**：T/T-1 窗口起止日期、K 线条数
2. **curpdf（三角分布）**：逐日对比三角分布向量
3. **cumpdf（衰减累积）**：对比递推累积筹码分布
4. **cyqk**：对比 winner/total

关键方法：在 Python 中用 numba 精确复刻 Rust 算法，与 Python 原生算法在**同一运行时**下对比，排除跨语言 f64 行为差异。

工具：
- Rust: `turnover-resist/src/debug_precision.rs`
- Python: `scripts/legacy/debug_precision.py`

---

## 3. 逐环节对比结果

| 环节 | 结果 | 差异量级 |
|------|------|---------|
| 窗口对齐 | 完全一致（1001 union_bars，T/T-1 各 1000 天） | 0 |
| curpdf 算法 | Rust/Python 算法完全等价（max diff = 0） | 0 |
| cumpdf 算法 | Rust/Python 算法完全等价（max diff = 0） | 0 |
| **cyqk（不同网格）** | **219 vs 220 winner bins** | **0.039** |
| cyqk（相同网格） | 完全一致（diff ~1e-16） | 0 |

**结论**：算法本身无差异。差异唯一来源是**价格网格构造方式不同**。

---

## 4. 根因：`np.arange` 浮点累加误差导致边界 bin 翻转

### 4.1 两种网格构造方式

Python 旧代码（`full_market_canonical_resist.py:297`）：

```python
xs = np.arange(min_p, max_p + step, step)   # 重复加法，误差累积
```

Rust（`algorithm.rs:303`）和 `make_price_grid`：

```rust
let xs = (0..n).map(|i| min_p + i as f64 * step);  // 逐点乘法，无累积
```

### 4.2 误差机制

`step = 0.01` 在 IEEE-754 binary64 中无法精确表示（二进制无限循环小数）。`np.arange` 通过 `current += step` 重复加法生成序列，每次加法引入一次舍入。`min_p + i * step` 每点独立计算（一次乘法 + 一次加法），误差不累积。

对 002374.SZ（498 个网格点），两种方式有 **481/498** 个点的 IEEE-754 表示不同。

### 4.3 临界 bin 翻转

收盘价 `close = 3.78`，网格点 x[219]（理论值 1.59 + 219×0.01 = 3.78）：

```
close (parquet 实际值)  = 3.78000000000000024869  hex: 3e0ad7a3703d0e40
xs[219] make_price_grid = 3.78000000000000024869  hex: 3e0ad7a3703d0e40  → ≤ close  TRUE  ✓
xs[219] np.arange       = 3.78000000000000202505  hex: 420ad7a3703d0e40  → ≤ close  FALSE ✗
```

`np.arange` 的 219 次重复加法累积了 +1.78e-15 的误差，使 x[219] 略高于 close，被排除出 winner 累加。该 bin 承载 ~26000 cumpdf 权重，经 `winner/total` 归一化后贡献 cyqk 差值 **0.0391**。

### 4.4 三只股票验证

| 股票 | np.arange 边界值 | Rust 边界值 | close | 方向 | Winner bins 差 |
|------|-----------------|------------|-------|------|---------------|
| 002374.SZ | 3.78000000000000**20** | 3.78000000000000**02** | 3.78000000000000**02** | py 多排除 1 bin | +1 |
| 000727.SZ | 2.929999999999999**3** | 2.929999999999999**7** | 2.929999999999999**7** | py 多排除 1 bin | +1 |
| 000088.SZ | 4.4799999999999**86** | 4.4800000000000**00** | 4.47999999999999**95** | py 多包含 1 bin | -1 |

### 4.5 为什么 2000+ 只受影响

每只股票的 close 和网格范围不同，只要任意网格点恰好落在 close 的比较边界附近，`np.arange` 的舍入误差就能翻转 `<=` 结果。概率上约一半股票至少有一个临界 bin 受影响。

---

## 5. Expert P 五根因假说 — 交叉验证判决

Expert P 通过静态代码分析提出 5 个根因假说。以下逐一给出实验判决。

### #1（P0）：Rust 对 T/T-1 窗口使用同一个 capital

> **判决：❌ 不是 0.039 差异的根因。但代码观察正确，是独立潜在 bug。**

实测三只差异最大股票：

```
002374.SZ: circ_cap_T = 1,085,209,283  circ_cap_T-1 = 1,085,209,283  same=True
000727.SZ: circ_cap_T = 4,529,566,980  circ_cap_T-1 = 4,529,566,980  same=True
000088.SZ: circ_cap_T = 3,162,885,710  circ_cap_T-1 = 3,162,885,710  same=True
```

三只股票的 T/T-1 capital 完全相同，即使 capital 不变，仅切换网格构造就能让 cyqk 从 0.5481 变为 0.5872（diff=0.0391）。故 #1 不是本次差异的主因。

**但 Rust 确实存在此问题**：`compute_cyqk_from_curpdfs` 对 T 和 T-1 传入同一个 `circ_cap`，而 Python 使用 `circ_cap_prev`。在季报更新日 capital 变化时会产生额外差异。建议后续修复。

### #2（P1）：winner/total 计算顺序不同

> **判决：❌ 不是差异源。实测差异 < 1e-16。**

Python（`ChipFactor.get_winner`）：先 `cumpdf/total` 归一化，再 `[mask].sum()`。Rust（`calc_cyqk`）：先累加 raw winner，再 `winner/total`。数学上等价，实测差异在机器精度级别，可忽略。

### #3（P1）：Volume i64 vs f64

> **判决：❌ 不是差异源。无实测影响。**

curpdf 归一化后 sum 完全匹配（max diff = 0），turnover 公式两端一致。parquet 中 volume 为整数，`i64` 读取无损。

### #4（P2）：数据起止日期范围不同

> **判决：⚠️ 理论存在，实测未触发。**

Python 使用 `window*2 = 2000` 日历天，Rust 使用 3000 天。但两端均通过 `keep_rows`/`tail` 截取尾部数据。对三只测试股票验证窗口完全一致。

### #5（P2）：涨跌停 bin 定位 round vs trunc

> **判决：❌ 不是差异源。**

Python batch 版（`_batch_triang_curpdf`）和 Rust（`calc_single_day_curpdf`）均使用 `round`。旧版 `calc_triang_pdf` 用 `int()`（trunc），但不在批量计算路径中。三只测试股票未触发涨跌停情形。

---

## 6. 判决汇总

| 来源 | 假说 | 优先级 | 判决 | 说明 |
|------|------|--------|------|------|
| Expert P #1 | T/T-1 capital 不分 | P0 | ❌ 非根因，但属实 | capital 恰好相同；code observation 正确，是独立 bug |
| Expert P #2 | winner/total 计算顺序 | P1 | ❌ | 实测 diff < 1e-16 |
| Expert P #3 | Volume i64 vs f64 | P1 | ❌ | 无影响 |
| Expert P #4 | 数据日期范围 | P2 | ⚠️ | 理论可能，实测未触发 |
| Expert P #5 | 涨跌停 round vs trunc | P2 | ❌ | 均用 round，不适用 |
| **Qoder** | **np.arange 浮点累加** | **P0** | **✅ 唯一根因** | **IEEE-754 hex 交叉验证确认** |

---

## 7. 修复

### 核心修复

```diff
# scripts/data/full_market_canonical_resist.py
- xs = np.arange(min_p, max_p + step, step)
+ from qlib_cost.distribution_of_chips import make_price_grid
+ xs = make_price_grid(min_p, max_p, step)
```

### 全局替换清单

| 文件 | 替换数 | 状态 |
|------|-------|------|
| `scripts/data/full_market_canonical_resist.py` | 1 | ✅ 已修 |
| `qlib_cost/distribution_of_chips.py` | 4 + `make_price_grid` 定义 | ✅ 已修 |
| `qlib_cost/cyq.py` | 1 | ✅ 已修 |
| `backtest/chip_algorithm.py` | 3 | ✅ 已修 |
| `scripts/data/full_market_equal_weight_resist.py` | 1 | ✅ 已修 |

### 验证

| 股票 | Rust cyqk_T | 修复前 Python | 修复后 Python |
|------|------------|-------------|-------------|
| 002374.SZ | 0.5872 | 0.5481 | **0.5872** ✓ |
| 000727.SZ | 0.9019 | 0.8641 | **0.9019** ✓ |
| 000088.SZ | 0.1599 | 0.1964 | **0.1599** ✓ |

**全市场端到端验证**（4594 只共同股票）：cyqk_T、cyqk_T_1、turnover_resistance、turnover_resistance_free 四项指标全部精确匹配（diff = 0）。详见 [`rust-python-e2e-verification-2026-06-01.md`](rust-python-e2e-verification-2026-06-01.md)。

---

## 8. 附带发现（非本次差异源）

### 8.1 Rust T-1 窗口应使用 T-1 日 capital — ✅ 已修复

**问题**：Rust `compute_cyqk_from_curpdfs` 对 T 和 T-1 传入同一个 `circ_cap`，而 Python 对 T-1 使用 `circ_cap_prev`。在 capital 变更日（季报更新）附近会产生额外差异。

**修复**（2026-06-01）：
- `turnover-resist/src/algorithm.rs`：`compute_cyqk_from_curpdfs` 签名从 `float_shares: f64` 改为 `float_shares_t: f64, float_shares_t1: f64`，T 和 T-1 窗口分别使用各自的 scale
- `turnover-resist/src/main.rs`：新增 `ff_map_prev`（T-1 日 capital map），`process_one_stock` 接受 `ff_info_prev` 参数，分别提取 `circ_cap_t` / `circ_cap_t1` 和 `fc_t` / `fc_t1` 传给 `compute_cyqk_from_curpdfs`

**验证**：修复后 3 只测试股票 cyqk_T 和 cyqk_T_1 与 Python 完全一致。

### 8.2 cyqk 归一化顺序差异可忽略

Python 先除后加，Rust 先加后除。实测差异 < 1e-16。

---

## 9. 经验教训

1. **`np.arange` 用于价格网格是反模式**：浮点误差线性累积，需要确定性跨语言一致时必须用 `min_p + i * step`
2. **跨语言精度对比应先消除网格差异**：在 Python 侧复刻 Rust 算法 + Rust 网格，快速排除算法差异
3. **浮点比较边界是精度 bug 高发区**：`xs <= close` 对 1.8e-15 的误差敏感，代码审查应重点检查

---

## 10. 调试工具

```bash
# Rust
cd turnover-resist && cargo run --release --bin debug-precision -- --code 002374.SZ --date 20260525

# Python
D:/anaconda3/envs/vanna311/python.exe scripts/legacy/debug_precision.py --code 002374.SZ --date 20260525
```

---

**合并来源**: Expert P（5 根因假说）+ Qoder（实测验证，IEEE-754 定位）+ Qoder 详细版（完整排查过程）
**版本**: 4.0（§8.1 Rust T-1 capital 已修复，Python/Rust 全量对齐验证通过）
