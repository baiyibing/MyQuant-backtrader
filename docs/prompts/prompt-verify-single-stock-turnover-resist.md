# 单只股票换手阻力分步验算

## 用途

当需要**逐行理解**某只股票在指定截面的换手阻力是如何计算得出时，使用本流程。与全市场批量计算不同，本流程会打印每一步的中间量（curpdf、cumpdf、cyqk、turnover、布林带等），并可与已生成的全市场 CSV 交叉验证。

## 权威算法来源

- `docs/prompts/prompt-canonical-turnover-resistance.md` — Python 全市场计算流程
- `scripts/data/full_market_canonical_resist.py` — batch 模式（numba 批量三角分布）
- `qlib_cost/cyq.py` — `ChipFactor.get_cyqk_c()` 盈利占比提取
- `backtest/chip_algorithm.py` — `adapt_columns()` 股本适配

## 运行方式

### 方式一：一键脚本（推荐）

```bash
cd E:/PycharmProjects/OSkhQuant1.3
D:/anaconda3/envs/vanna311/python.exe scripts/gates/verify_single_stock_turnover_resist.py \
  --code 003816.SZ \
  --date 20260604
```

参数：
- `--code`：股票代码（如 `003816.SZ`）
- `--date`：截面日期 `YYYYMMDD`
- `--window`：筹码衰减窗口，默认 1000
- `--step`：价格步长，默认 0.01

脚本会自动搜索 `backtest_output/canonical_resist_batch_YYYYMMDD.csv` 或 `canonical_resist_rust_YYYYMMDD.csv` 进行交叉验证。

### 方式二：手动 Jupyter / REPL 分步

按下方「13 步验算流程」逐行执行，中间量完全等价于 `scripts/gates/verify_single_stock_turnover_resist.py` 的输出。

## 13 步验算流程

### Step 0：获取股本数据

从 `stock_data/free_float_shares.parquet` 查询 T 日和 T-1 日最新股本：

```sql
SELECT stock_code,
       ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY m_timetag DESC) AS rn,
       freeFloatCapital, circulating_capital
FROM read_parquet('stock_data/free_float_shares.parquet')
WHERE m_timetag <= '{target_date}'
QUALIFY rn = 1
```

若 `free_float_shares` 缺失，fallback 到 `stock_data/float_shares.parquet` 的 `FloatVolume`。

**关键中间量**：
| 名称 | 说明 |
|------|------|
| `circulating_capital_T` | T 日流通股本 |
| `circulating_capital_T_prev` | T-1 日流通股本 |
| `freeFloatCapital_T` | T 日自由流通股本 |
| `freeFloatCapital_T_prev` | T-1 日自由流通股本 |

### Step 1：读取日线

```python
from oskh_data.reader import StockDataReader
reader = StockDataReader()
df = reader.read_stock(code, period='1d', adjust_type='front')
```

使用 **前复权** 日线（`period=1d`, `adjust_type=front`）。

### Step 2：确定窗口

取截面日期及之前的所有数据，再取最近 `window + 1` 个交易日：

```python
df_t = df[df.index.normalize() <= target]
unique_dates = df_t.index.normalize().unique()
extended_dates = unique_dates[-(window + 1):]   # 需要 window+1 天
```

> 为什么 `window + 1`？因为 T 窗口需要 window 天，T-1 窗口也需要 window 天，且两个窗口相差 1 天，因此总共需要 window+1 天的原始数据。

### Step 3：构造计算数组

```python
arr_raw = df_w[['close', 'high', 'low', 'vol']].values.astype(np.float64)
```

`arr_raw` shape: `(window+1, 4)`，列顺序：**close, high, low, vol**。

### Step 4：价格网格

```python
from qlib_cost.distribution_of_chips import make_price_grid
xs = make_price_grid(min_p, max_p, step=0.01)
```

- `min_p` = 窗口内最低价的 `low.min()`
- `max_p` = 窗口内最高价的 `high.max()`
- 网格长度通常在 200~500 之间

### Step 5：逐日三角分布 curpdf

使用 `_batch_triang_curpdf`（numba 加速）计算每一天的筹码分布：

```python
curpdfs = _batch_triang_curpdf(close, high, low, vol, xs)
# shape: (window+1, n_bins)
```

**三角 PDF 规则**（与 `qlib_cost/distribution_of_chips.py` 对齐）：
- 正常日（`high > low`）：三角分布，peak = close，support = [low, high]
- 涨跌停日（`high == low`）：全部集中到 close 对应 bin
- 归一化：`pdf / sum(pdf) * vol`（不是 `pdf * vol / sum(pdf)`）

**验证点**：`curpdfs[d].sum()` 应严格等于当日 `vol`。

### Step 6：分割 T 窗口与 T-1 窗口

```python
curpdf_t     = curpdfs[1:, :]   # 去掉第 0 天，共 window 天
curpdf_prev  = curpdfs[:-1, :]  # 去掉最后一天，共 window 天
```

### Step 7：逐日换手率（4 组）

```python
vol_arr = arr_raw[:, 3]
turnover_circ_t_arr    = vol_arr * 100.0 / circulating_capital_T
turnover_circ_prev_arr = vol_arr * 100.0 / circulating_capital_T_prev
turnover_free_t_arr    = vol_arr * 100.0 / freeFloatCapital_T
turnover_free_prev_arr = vol_arr * 100.0 / freeFloatCapital_T_prev
```

注意：4 组换手率使用**同一组 vol_arr**，只是分母（股本）不同。

### Step 8：衰减累积 cumpdf

核心公式（canonical 指数衰减）：

```
cumpdf[0] = curpdf[0] * turnover[0]
cumpdf[i] = cumpdf[i-1] * (1 - turnover[i]) + curpdf[i] * turnover[i]
```

使用 `_batch_cumpdf_4way` 一次性计算 4 个 cumpdf：

```python
cumpdf_circ_t, cumpdf_circ_prev, cumpdf_free_t, cumpdf_free_prev = \
    _batch_cumpdf_4way(
        curpdf_t, curpdf_prev,
        turnover_circ_t_arr[1:], turnover_circ_prev_arr[:-1],
        turnover_free_t_arr[1:], turnover_free_prev_arr[:-1]
    )
```

> `turnover_circ_t_arr[1:]` 对应 curpdf_t 的 window 天，`turnover_circ_prev_arr[:-1]` 对应 curpdf_prev 的 window 天。

### Step 9：提取 cyqk

```python
from qlib_cost import cyq
cyqk = cyq.ChipFactor(close_price, pd.Series(cumpdf, index=xs)).get_cyqk_c()
```

`cyqk` = 当前收盘价以下的筹码占比（盈利筹码占比）。

需分别计算 4 个 cyqk：
- `cyqk_circ_t`：T 日、流通股本口径
- `cyqk_circ_prev`：T-1 日、流通股本口径
- `cyqk_free_t`：T 日、自由流通股本口径
- `cyqk_free_prev`：T-1 日、自由流通股本口径

### Step 10：获利筹码变化

```python
profit_chip_diff_circ = cyqk_circ_t - cyqk_circ_prev
profit_chip_diff_free = cyqk_free_t - cyqk_free_prev
```

### Step 11：T 日换手率

仅取 T 日（最后一天）的 vol 计算：

```python
vol_t = arr_raw[-1, 3]
turnover_circ_t = vol_t * 100.0 / circulating_capital_T
turnover_free_t = vol_t * 100.0 / freeFloatCapital_T
```

### Step 12：换手阻力

```python
turnover_resistance_circ = profit_chip_diff_circ / turnover_circ_t
turnover_resistance_free = profit_chip_diff_free / turnover_free_t
```

**物理意义**：
- 正值 = 获利筹码占比上升但换手率极低（筹码锁定上涨）
- 负值 = 获利筹码占比下降（套牢盘松动），绝对值越大偏离越严重

### Step 13：布林带

```python
close_series = pd.Series(arr_raw[:, 0])
bb_mid   = close_series.rolling(20).mean().iloc[-1]   # 20 日均线
bb_std   = close_series.rolling(20).std().iloc[-1]    # ddof=1（样本标准差）
bb_upper = bb_mid + 2.0 * bb_std
bb_lower = bb_mid - 2.0 * bb_std
bb_position = (close_t - bb_lower) / (bb_upper - bb_lower)
bb_width    = (bb_upper - bb_lower) / bb_mid
```

## v1.1 注意事项（2026-06-07）

- 价格网格使用 `make_price_grid(min_p, max_p, step)`（`qlib_cost/distribution_of_chips.py`），**禁止**直接调用 `np.arange(min_p, max_p + step, step)`——后者重复加法产生 IEEE-754 累积误差，导致边界 bin 在 `xs <= close` 比较时翻转
- 与 Rust 精度对齐：同等参数下（`--free-float-policy warn-zero`）4595 只全 diff=0
- 自由流通股本缺失时默认 `warn-zero`（填 0 继续）；`skip` 跳过该股票（与 Rust 行为一致）

边界：
- 不足 20 天：fallback 全部数据的 mean/std
- 上轨 ≤ 下轨：`bb_position = 0.5`
- 中轨 ≤ 0：`bb_width = 0.0`

## 与全市场 CSV 交叉验证

脚本执行完毕后会自动搜索以下文件进行逐字段对比：

```
backtest_output/canonical_resist_batch_YYYYMMDD.csv   # Python batch 输出
backtest_output/canonical_resist_rust_YYYYMMDD.csv    # Rust 输出
```

18 列全部应一致（浮点误差 < 1e-9）。若出现差异，按上述 13 步逐级排查。

## 常见排查方向

| 差异列 | 排查重点 |
|--------|----------|
| `cyqk_T` / `cyqk_T_1` | 检查 `cumpdf` 是否使用了正确的 turnover 数组（T vs T-1、流通 vs 自由流通） |
| `turnover` / `turnover_free` | 检查股本查询日期是否为 T 日、vol 是否取最后一天 |
| `turnover_resistance` | 检查 profit_chip_diff 和 turnover 的口径是否配对（流通 vs 自由流通不能混用） |
| `bb_*` | 检查 `rolling(20).std()` 是否为 ddof=1（pandas 默认），且数据条数是否 ≥ 20 |
| 全部不一致 | 检查 `arr_raw` 的列顺序是否为 `[close, high, low, vol]`，以及 window 是否为 `window+1` |

## 输出示例

```
========================================
Step 12: 换手阻力 = profit_chip_diff / turnover_T
========================================
circ  = -0.098748 / 0.002606 = -37.8982
free  = -0.273008 / 0.015229 = -17.9268

========================================
与 CSV 输出对比
========================================
对比文件: backtest_output/canonical_resist_batch_20260604.csv
  close                 ✅ 验算 4.51  vs CSV 4.51
  cyqk_T                ✅ 验算 0.8190  vs CSV 0.8190
  ...
  turnover_resistance_free ✅ 验算 -17.9268  vs CSV -17.9268
```

---

*编码：UTF-8（无 BOM）。最后更新：2026-06-04。*
