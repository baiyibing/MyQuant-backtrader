# Canonical 换手阻力全市场计算（双口径）

## 用途

使用 canonical（换手率衰减）算法计算全市场筹码换手阻力，**同时输出两个口径**：

| 口径 | 分母 | 列名 |
|------|------|------|
| 流通股本 | `circulating_capital` | `turnover_resistance` / `turnover` |
| 自由流通股本 | `freeFloatCapital` | `turnover_resistance_free` / `turnover_free` |

股本数据来源：`stock_data/free_float_shares.parquet`（miniQMT Capital 财务表，385K 行/5,522 只/2001~2026）。

## 运行命令

### Python

**必须**加 `PYTHONUNBUFFERED=1`，否则多进程 stdout 被缓冲，看起来像卡住：

```bash
cd "E:/PycharmProjects/OSkhQuant1.3"
PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260525 \
  --sort-by free \
  --free-float-policy warn-zero \
  --target-date-policy strict
  # 默认输出：backtest_output/canonical_resist_batch_20260525.csv
```

### Rust CLI（高性能）

```bash
cd "E:/PycharmProjects/OSkhQuant1.3"
/e/rust-targets/release/turnover-resist.exe \
  --date 20260525 \
  --sort-by free \
  --free-float-policy warn-zero \
  --output backtest_output/canonical_resist_rust_20260525.csv
```

### Rust PyO3 FFI（Python 内直接调用，0.2μs 启动）

```python
from oskh_factors.bridge.turnover_resist import compute_turnover_resist

results = compute_turnover_resist(
    date="20260525",
    data_dir="stock_data",
    free_float_policy="warn-zero",
)
# → list[dict] with stock_code, cyqk_T, turnover_resistance, bb_upper, ...
```

参数：
- `--date YYYYMMDD`：截面日期
- `--window 1000`（默认）：筹码衰减窗口（交易日数），不足自动用全部。1000≈4 年自然日
- `--step 0.01`（默认）：价格步长，一分钱
- `--sort-by free|circulating`（默认 `free`）：排序口径
- `--free-float-policy warn-zero|skip|fail`（默认 `warn-zero`）：缺自由流通股本时策略。**Python + Rust 参数一致**（v1.1 对齐）
  - `warn-zero`：缺数据时 freeFloatCapital=0，继续计算（默认，向后兼容）
  - `skip`：跳过该股票（Rust/ Python 行为一致）
  - `fail`：报错退出
- `--target-date-policy strict|last-available`（默认 `strict`，v1.2 新增）：目标日期不存在时的策略。**默认 `strict` 与 Rust 对齐**
  - `strict`：目标日期不存在则跳过该股票
  - `last-available`：使用最新可用日期计算（旧行为，与 Rust 不对齐）
- `--output`：输出 CSV 路径
- `--workers N`（默认 CPU-1）：并行进程数。设为 1 可串行调试（仅 Python）
- `--batch-start` / `--batch-end`：分批处理索引（仅 Python）

> **动态窗口与最小交易日（v1.2 对齐 Rust）**：当可用交易日不足 `window+1` 时，Python `batch` 方法会自动缩短窗口使用全部可用数据；当可用交易日少于 20 天时，会跳过该股票（与 Rust `insufficient_bars` 行为一致）。

**精度对齐**（v1.1）：Python 已修复 `np.arange` 浮点累积误差（`make_price_grid` 改用 `min_p + np.arange(n) * step`，与 Rust `min_p + i * step` 逐点 IEEE-754 一致）。同等参数下 Rust/Python 输出 ≥4595 只全 diff=0。验证：`D:/anaconda3/envs/vanna311/python.exe scripts/gates/verify_rust_python_alignment.py --date YYYYMMDD --free-float-policy warn-zero`

**性能**（2026-05-31 优化后）：
- Python: 4 次 `_canonical_cyqk` 合并为 1 次 curpdf 计算 + 4 次 cumpdf（numba jit），~3x 单核加速。多进程并行（默认 CPU-1），~8x 额外加速。全市场 ~5500 只：预计 **2–5 分钟**（原 10–30 分钟）
- Rust CLI: Polars + Rayon 并行，全市场 ~5500 只：**~27s（热缓存）/ ~64s（冷）**
- Rust PyO3 FFI: 同上性能 + 免子进程启动开销（39ms → 0.2μs）

**输出**：18 列 CSV，按 `|turnover_resistance_free|`（自由流通股本口径换手阻力绝对值）降序排列。

## 算法确认

`scripts/data/full_market_canonical_resist.py` 即 canonical（换手率衰减）算法：

1. `oskh_data.reader.StockDataReader.read_stock(code, period="1d", adjust_type="front")` 读取日线
2. `backtest.chip_algorithm.adapt_columns(df, code, as_of_date, use_free_float=False)` 适配流通股本口径
3. `backtest.chip_algorithm.adapt_columns(df, code, as_of_date, use_free_float=True)` 适配自由流通股本口径
4. `qlib_cost.cyq.calc_dist_chips(arr, method="triang", step=0.01)` 三角核衰减计算筹码分布
5. `qlib_cost.cyq.ChipFactor.get_cyqk_c()` 提取 cyqk 指标
6. `turnover_resistance = (cyqk_T - cyqk_T-1) / turnover_T`（双口径各算一次）
7. 布林带：20 日均线 ± 2×标准差
8. 股票中文名：从 `stock_data/float_shares.parquet` 的 `name` 列查表

## 等权衰减 vs 不等权衰减（canonical）

### 不等权（canonical，衰减模型）

```python
for i in range(N):
    decay = turnover[i] * A          # 当日换手率 × 系数
    cumpdf = cumpdf * (1 - decay) + curpdf[i] * decay
```

每一天的成交量分布 `curpdf[i]` 按其**当日换手率**加权累加，且历史分布被 `(1 - decay)` 逐日衰减。换手率越高 → 该日筹码权重越大 → 旧筹码被"洗掉"越快。这是一个**指数衰减**过程，换手率是衰减速率。

**效果**：1000 天前某天换手率 0.5%，那天的筹码几乎已被洗光；昨天换手率 10%，昨天的筹码在当前分布中占比很大。

### 等权重（无衰减）

```python
cum_vol = np.sum(curpdfs, axis=0)   # 直接求和
```

每一天的三角分布简单相加，**不乘换手率，不做衰减**。第 1 天和第 1000 天的权重完全一样。

### 对比

| | 不等权（canonical） | 等权重 |
|---|---|---|
| 公式 | `cumpdf × (1-turnover) + curpdf × turnover` | `Σ curpdf[i]` |
| 权重 | 换手率高 → 权重大，旧筹码衰减快 | 每天平权 |
| 物理直觉 | 换手 = 筹码交换速度 | 不考虑筹码交换 |

## 仓库实现的全部筹码算法

核心代码在 `qlib_cost/cyq.py` L61-82（`calc_cumpdf`）。

| 算法 | 分布模型 | 衰减 | 窗口 | 对应脚本/方法 |
|------|---------|------|------|-------------|
| **triang + 衰减** | 三角分布（mode=close） | turnover 加权衰减 | 1000 日 | `calc_dist_chips(method="triang")` → `calc_cumpdf` → `full_market_canonical_resist.py` |
| **uniform + 衰减** | 均匀分布（high-low 内平权） | turnover 加权衰减 | 1000 日 | `calc_dist_chips(method="uniform")` → `calc_cumpdf` |
| **turn_coeff** | 无价格分布，仅换手系数 | 换手率调整系数 | 无窗口 | `calc_dist_chips(method="turn_coeff")` → `calc_adj_turnover` |
| **等权重 triang** | 三角分布 | **无衰减** | 120 日 | `full_market_equal_weight_resist.py` — 逐日 `calc_curpdf("triang")` 后 `np.sum` |

`full_market_canonical_resist.py` 用的是第 1 种（triang + turnover 衰减），即 canonical 算法。

## 前置依赖

```bash
D:/anaconda3/envs/vanna311/python.exe -c "from qlib_cost import cyq; from backtest.chip_algorithm import adapt_columns; import oskh_data.reader; print('imports OK')"
```

## 输出列

| 列 | 说明 |
|----|------|
| stock_code | 股票代码 |
| stock_name | 中文简称（从 float_shares.parquet 查表） |
| date | 截面日期 |
| close | 收盘价（分位，两位小数） |
| cyqk_T | T 日 cyqk（获利筹码占比，流通股本口径） |
| cyqk_T_1 | T-1 日 cyqk（流通股本口径） |
| profit_chip_diff | 获利筹码变化 cyqk_T - cyqk_T-1（流通股本口径） |
| turnover | T 日换手率（**流通股本**口径：vol×100 / circulating_capital） |
| turnover_resistance | 换手阻力（**流通股本**口径）：profit_chip_diff / turnover |
| turnover_free | T 日换手率（**自由流通股本**口径：vol×100 / freeFloatCapital） |
| turnover_resistance_free | 换手阻力（**自由流通股本**口径） |
| circulating_capital | 流通股本（股） |
| freeFloatCapital | 自由流通股本（股） |
| bb_upper | 布林上轨（20 日，2σ） |
| bb_middle | 布林中轨（20 日均线） |
| bb_lower | 布林下轨 |
| bb_position | 布林位置 (close-lower)/(upper-lower)，0~1 |
| bb_width | 布林带宽 (upper-lower)/middle |

按 `|turnover_resistance_free|`（自由流通股本口径换手阻力绝对值）降序排列。

## 关联文档

- [../backtest/chip/turnover_resistance_algorithm.md](../backtest/chip/turnover_resistance_algorithm.md) — 换手阻力完整技术规格（算法文档）
- [../backtest/chip/README.md](../backtest/chip/README.md) — 筹码因子文档索引

## 推荐执行流程

任何代码修改后，**必须**按此顺序执行，禁止直接全量：

1. **小批量冒烟测试**（~30 秒）
   ```bash
   PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
     --date 20260616 --sort-by free --free-float-policy warn-zero --target-date-policy strict \
     --workers 1 --batch-start 0 --batch-end 10 \
     --output backtest_output/canonical_resist_smoke.csv
   ```
   检查：不报错、输出 10 行、核心列数值合理。

2. **全量 Python 计算**（2-5 分钟）
   ```bash
   PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
     --date 20260616 --sort-by free --free-float-policy warn-zero --target-date-policy strict \
     --output backtest_output/canonical_resist_batch_20260616.csv
   ```

3. **全量 Rust 计算**（1-2 分钟）
   ```bash
   /e/rust-targets/release/turnover-resist.exe \
     --date 20260616 --sort-by free --window 1000 --step 0.01 \
     --output backtest_output/canonical_resist_rust_20260616.csv
   ```

4. **Python/Rust 全市场对齐验证**  
   使用下面“与 Rust 对齐验证”脚本。若行数不同，按“异常排查”处理。

## 与 Rust 对齐验证

```bash
D:/anaconda3/envs/vanna311/python.exe -c "
import pandas as pd
py = pd.read_csv('backtest_output/canonical_resist_batch_YYYYMMDD.csv', encoding='utf-8-sig')
rust = pd.read_csv('backtest_output/canonical_resist_rust_YYYYMMDD.csv', encoding='utf-8-sig')
print(f'Python: {len(py)} rows, Rust: {len(rust)} rows')
m = py.merge(rust, on='stock_code', how='outer', indicator=True)
print(m['_merge'].value_counts())
common = m[m['_merge'] == 'both']
for col in ['cyqk_T', 'cyqk_T_1', 'turnover_resistance', 'turnover_resistance_free']:
    diff = (common[f'{col}_x'] - common[f'{col}_y']).abs()
    print(f'{col}: max_diff={diff.max():.6e}, diff_rows={(diff > 1e-10).sum()}')
py['abs'] = py['turnover_resistance_free'].abs()
rust['abs'] = rust['turnover_resistance_free'].abs()
top_b = set(py.sort_values('abs', ascending=False).head(1000)['stock_code'])
top_r = set(rust.sort_values('abs', ascending=False).head(1000)['stock_code'])
print(f'Top-1000 overlap: {len(top_b & top_r) / len(top_b):.4f}')
"
```

**验收标准**：
- Python 与 Rust 行数相同
- `cyqk_T`, `cyqk_T_1`, `turnover_resistance`, `turnover_resistance_free` 的 `max_diff < 1e-10`
- Top-1000 重叠率 = 100%
- `turnover` / `turnover_free` 允许 1e-6 四舍五入差异
- `bb_middle` / `bb_position` 允许微小浮点差异

## 异常排查

| 现象 | 可能原因 | 处理 |
|------|---------|------|
| Python 运行几分钟后仍无输出 | stdout 被缓冲 | 立即停止，加上 `PYTHONUNBUFFERED=1` 重跑 |
| Python 看起来“卡住”，想切单进程 | 不要切。单进程全市场 1-4 小时 | 优先确认是否加了 `PYTHONUNBUFFERED=1`；再检查 `ps -W` 是否有 python 子进程在跑 |
| Python 行数 < Rust 行数 | 窗口/目标日期/free_float 策略未对齐 | 确认 Python 使用 `--target-date-policy strict`、动态窗口已启用、`--free-float-policy warn-zero` |
| Python 行数 > Rust 行数 | Python 跳过了 Rust 没跳过的股票（如上市 <20 天） | 通常是正常的；若要求完全一致，检查 Python 是否应用了最小 20 交易日过滤 |
| 核心列差异 > 1e-10 | 算法实现不一致 | 停止，对比单只股票中间量，检查 `make_price_grid`、三角 PDF、衰减公式 |
| 辅助列（布林带）有差异 | 浮点精度或窗口端点差异 | 可接受，不影响使用 |

## 注意事项

- 全市场 ~5500 只股票，优化后预计 **2-5 分钟**（`--workers` 默认 CPU-1）
- 历史不足 1000 天的股票：有多少算多少（<20 个交易日才跳过）
- 约 5000+ 只有效结果（含次新股）
- 输出路径 `backtest_output/` 目录会自动创建
- `turnover_resistance` 正值 = 获利筹码占比上升但换手率极低（筹码锁定上涨），负值 = 获利筹码占比下降（套牢盘松动）
