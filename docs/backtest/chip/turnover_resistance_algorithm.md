# 换手阻力（Turnover Resistance）完整技术文档

> 本文档从顶层公式逐层展开到最底层 numba 数学实现，覆盖数据准备、筹码分布、跨日衍生、回测框架及使用指南。
> 
> 索引：[chip/README.md](README.md)  
> 手算核对（填数样例）：[turnover_resistance_handcheck_300834_20260327.md](turnover_resistance_handcheck_300834_20260327.md)（300834.SZ / 20260327）  
> 相关源码路径：
> - `backtest/chip_algorithm.py`
> - `qlib_cost/cyq.py`
> - `qlib_cost/distribution_of_chips.py`
> - `backtest/chip_factor_analysis.py`
> - `backtest/daily_chip_logger.py`
> - `backtest/filter_chip_stocks.py`
> - `scripts/full_market_chip_resist.py`
> - `scripts/spot_check_chip_factors.py`
> - `stock_data/float_shares.parquet`、`stock_data/free_float_shares.parquet`（流通股本）

---

## 1. 概述

**换手阻力**衡量的是：在当日换手率的作用下，获利筹码比例发生了多大的变化。

直觉上：
- 如果股价上涨、获利筹码大增，但换手率很低 → **筹码锁定**，抛压被"阻力"挡住 → 换手阻力**高**
- 如果股价上涨、获利筹码大增，同时换手率也很高 → **筹码充分交换**，新旧换手顺畅 → 换手阻力**低**
- 横盘时盈筹差 ≈ 0 → 换手阻力 ≈ **0**

---

## 2. 核心公式

### 2.1 换手阻力

$$
\boxed{
\text{换手阻力} = \frac{\text{当日获利筹码比例} - \text{上一日获利筹码比例}}{\text{当日换手率}}
}
$$

### 2.2 完整公式链

$$
\text{turnover\_resistance} = \frac{\text{cyqk\_today} - \text{cyqk\_yesterday}}{\text{turnover\_today}}
$$

其中：

$$
\text{turnover\_today} = \frac{\text{volume} \times 100}{\text{float\_shares}}
$$

$$
\text{cyqk} = \text{get\_winner}(\text{close}) = \sum_{\text{price} \le \text{close}} \frac{\text{cumpdf}(\text{price})}{\sum \text{cumpdf}}
$$

$$
\text{cumpdf}_i = \text{cumpdf}_{i-1} \times (1 - A \cdot \text{turnover}_i) + \text{curpdf}_i \times A \cdot \text{turnover}_i
$$

> 默认 $A=1.0$；$A$ 为换手率衰减系数倍率，可在 `calc_cumpdf` 中调整。$A=1$ 时与上式等价。

$$
\text{curpdf}_i(\text{price}) = \text{triang\_pdf}(\text{price}; c_i, \text{low}_i, \text{high}_i - \text{low}_i) \times \text{vol}_i
$$

$$
c_i = \frac{\text{close}_i - \text{low}_i}{\text{high}_i - \text{low}_i}
$$

---

## 3. 完整调用链路

```
用户脚本 / 回测框架
    │
    ├─ scripts/full_market_chip_resist.py      全市场批量计算
    ├─ scripts/spot_check_chip_factors.py      随机抽样 Spot Check（无 --stock 参数）
    ├─ backtest/chip_factor_analysis.py        多轮回测 + 滚动 IC
    ├─ backtest/daily_chip_logger.py           每日截面 canonical（含 ARC/VRC/SRC/KRC）
    └─ backtest/filter_chip_stocks.py          按阻力+BB 条件筛选全市场
        │
        ▼
    backtest/chip_algorithm.py
        │
        ├─ adapt_columns(df, stock_code, as_of_date, use_free_float)  数据准备 + 换手率估算
        │   ├─ use_free_float=False → _get_float_shares(stock_code, date)
        │   │     date → free_float_shares.parquet → circulating_capital
        │   │     None → float_shares.parquet → FloatVolume
        │   ├─ use_free_float=True  → _get_free_float_shares(stock_code, date)
        │   │     → free_float_shares.parquet → freeFloatCapital（无 fallback）
        │   └─ _estimate_turnover(volume, float_shares)
        │       turnover = (volume * 100) / float_shares
        │   → 返回 arr (N, 5): [close, high, low, vol, turnover_rate]
        │
        ├─ daily_chip_distribution(arr, "triang")
        │   └─ qlib_cost/cyq.py: calc_dist_chips(arr, "triang")
        │       ├─ 对每行调用 calc_curpdf(close, high, low, vol, min_p, max_p)
        │       │   └─ calc_triang_pdf(...)  或  calc_uniform_pdf(...)
        │       │       └─ triang_pdf(x, c, loc, scale)   (numba 加速)
        │       └─ calc_cumpdf(curpdf, turnover, A=1.0)   (numba 加速)
        │   → 返回 cumpdf (pd.Series, index=价格, values=筹码量)
        │
        ├─ hybrid_chip_distribution(daily_arr, minute_today_arr)  [分钟线场景]
        │   历史日线三角 PDF + 当日分钟线量价直方图
        │
        ├─ cyq.ChipFactor(close, cumpdf)
        │   ├─ get_cyqk_c()  →  get_winner(close)
        │   ├─ get_asr()     →  活动筹码
        │   ├─ get_ckdw()    →  成本重心
        │   └─ get_prp()     →  价格相对位置
        │
        ├─ derived_chip_factors(cyqk_today, cyqk_yesterday, turnover_today)
        │   profit_chip_diff = cyqk_today - cyqk_yesterday
        │   turnover_resistance = profit_chip_diff / turnover_today
        │   → {"profit_chip_diff", "turnover_ratio", "turnover_resistance"}
        │
        └─ 运维 CSV（full_market / spot_check）
            compute_crossday_turnover_resistance → derived_chip_factors
            CSV 列 turnover_1d / turnover_resist 与 canonical 对齐
```

---

## 4. 各层详细展开

### 4.1 数据准备层

#### 4.1.1 `adapt_columns`

**源码**：`backtest/chip_algorithm.py:175-199`

```python
def adapt_columns(
    df: pd.DataFrame,
    stock_code: str = None,
    as_of_date: Optional[pd.Timestamp] = None,
    use_free_float: bool = False,
) -> np.ndarray:
    """
    适配 backtrader DataFrame → cyq 期望的 (N, 5) 数组。
    列名映射：volume → vol；无 turnover_rate 时从流通股本估算。

    stock_code: 必填（P0-18）
    as_of_date: 按该日期查历史股本（防前视），None=当前快照
    use_free_float: False=流通股本(circulating_capital)，True=自由流通股本(freeFloatCapital)

    返回 np.ndarray: [close, high, low, vol, turnover_rate]
    """
    df = df.rename(columns={"volume": "vol"})
    if "turnover_rate" not in df.columns:
        if use_free_float:
            float_shares = _get_free_float_shares(stock_code, date=as_of_date)
        else:
            float_shares = _get_float_shares(stock_code, date=as_of_date)
        df["turnover_rate"] = _estimate_turnover(df["vol"].values, float_shares)
    return df[["close", "high", "low", "vol", "turnover_rate"]].values
```

> **调用方式**：流通股本换手阻力 `adapt_columns(df, code, date, use_free_float=False)`；自由流通股本换手阻力 `adapt_columns(df, code, date, use_free_float=True)`。两个值可分别传给 `turnover_chip_factors` 得到两套阻力指标。

#### 4.1.2 `_estimate_turnover`

**源码**：`backtest/chip_algorithm.py:143-169`

```python
def _estimate_turnover(volume: np.ndarray, float_shares: float = None) -> np.ndarray:
    """turnover_rate = (volume * 100) / float_shares；返回比例 0~1。"""
    if float_shares is None:
        # 仅窄路径：无流通股本入参时回退 100 亿并 warning（见 §4.1.3）
        logger.warning(
            "_estimate_turnover using 100亿 default float_shares; "
            "turnover_rate may be significantly distorted for small-cap stocks"
        )
        fs = float(_FLOAT_SHARES_DEFAULT)  # 10_000_000_000
    else:
        fs = float_shares
    return (volume.astype(np.float64) * 100.0) / fs
```

| 变量 | 单位 | 来源 |
|------|------|------|
| `volume` | **手** | DataFrame 原始列（A 股 1 手 = 100 股） |
| `float_shares` | **股** | `_get_float_shares` → `free_float_shares.parquet` 或 `float_shares.parquet` |
| `turnover_rate` | **比例 0~1** | `(volume × 100) / float_shares` |

**主路径**（`adapt_columns` → `_get_float_shares` / `_get_free_float_shares`）**不会**落到 100 亿默认；100 亿仅用于显式传入 `float_shares=None` 的调用方。

#### 4.1.3 股本查询（两个函数，双口径，P0-18 fail-close）

**源码**：`backtest/chip_algorithm.py`

```python
def _get_float_shares(stock_code=None, date=None) -> float:
    """流通股本（circulating_capital / FloatVolume）。"""
    # date is not None → free_float_shares.parquet → circulating_capital
    # date is None     → float_shares.parquet → FloatVolume

def _get_free_float_shares(stock_code=None, date=None) -> float:
    """自由流通股本（freeFloatCapital）。"""
    # date is not None → free_float_shares.parquet → freeFloatCapital
    # date is None     → raise ValueError（无实时来源）
    # 查不到 → raise ValueError（不回退 FloatVolume，不同口径）
```

| 场景 | `_get_float_shares` | `_get_free_float_shares` |
|------|---------------------|--------------------------|
| 回测 `date='2023-06-15'` | `free_float_shares.parquet` → `circulating_capital` | `free_float_shares.parquet` → `freeFloatCapital` |
| 实时 `date=None` | `float_shares.parquet` → `FloatVolume` | **raise ValueError**（`get_instrument_detail` 不返回此字段） |
| 查不到 | **`raise ValueError`** | **`raise ValueError`**（不回退 FloatVolume） |

`float_shares.parquet` 仅实时交易 `date=None` 时兜底 `FloatVolume`。回测全部从 `free_float_shares.parquet`（385K 行/5,522 只/2001~2026）取。

---

### 4.2 筹码分布层

#### 4.2.1 `daily_chip_distribution`

**源码**：`backtest/chip_algorithm.py:205-218`

```python
def daily_chip_distribution(arr: np.ndarray, method: str = "triang") -> pd.Series:
    """
    日线筹码分布：使用三角/均匀 PDF 假设。
    直接委托给 qlib_cost 的 calc_dist_chips()。
    
    Args:
        arr: adapt_columns() 输出 (N, 5) 数组
        method: "triang" 或 "uniform"
    
    Returns:
        pd.Series, index=price, values=chip volume
    """
    return cyq.calc_dist_chips(arr, method=method)
```

#### 4.2.2 `hybrid_chip_distribution`

**源码**：`backtest/chip_algorithm.py:298-360`

```python
def hybrid_chip_distribution(daily_arr, minute_today_arr, step=0.01):
    """
    混合筹码分布：历史日线三角 PDF + 当日分钟线量价累积。
    §10.4.2 方案 A — 日线定框架，分钟线只做当日新开仓成本的微调。
    """
    # 价格网格：覆盖日线 + 分钟线的完整范围
    max_p = max(float(np.nanmax(daily_arr[:, 1])),
                float(np.nanmax(minute_today_arr[:, 0])))
    min_p = min(float(np.nanmin(daily_arr[:, 2])),
                float(np.nanmin(minute_today_arr[:, 0])))
    
    # 停牌/异常：价格范围无效时返回空 Series（P1-5）
    if max_p <= min_p:
        logger.warning(
            f"hybrid_chip_distribution: 日线+分钟线价格范围为空 "
            f"(max={max_p} <= min={min_p})，可能停牌或数据异常"
        )
        return pd.Series(dtype=float, name="cumpdf")
    
    xs = np.arange(min_p, max_p + step, step)
    n_days = len(daily_arr)
    curpdfs = np.zeros((n_days, len(xs)), dtype=np.float64)

    # 历史日（0 到 n_days-2）：三角 PDF
    for i in range(n_days - 1):
        curpdfs[i] = cyq.calc_curpdf(
            float(daily_arr[i, 0]), float(daily_arr[i, 1]),
            float(daily_arr[i, 2]), float(daily_arr[i, 3]),
            min_p, max_p, step, method="triang",
        )

    # 当日（最后一"天"）：分钟线量价直方图
    today_close = minute_today_arr[:, 0]
    today_vol = minute_today_arr[:, 3]
    today_pdf = np.zeros(len(xs), dtype=np.float64)
    for j in range(len(today_close)):
        if np.isnan(today_close[j]) or today_vol[j] <= 0:
            continue
        idx = int((today_close[j] - min_p) / step)
        if 0 <= idx < len(xs):
            today_pdf[idx] += today_vol[j]
    if today_pdf.sum() > 0:
        today_pdf /= today_pdf.sum()
    curpdfs[n_days - 1] = today_pdf

    # 换手率：历史日用日线值，当日用日线值
    turnover = daily_arr[:, 4].copy()

    cum_vol = cyq.calc_cumpdf(curpdfs, turnover)
    return pd.Series(cum_vol, index=xs, name="cumpdf")
```

**混合模式 vs 纯日线模式**：

| 模式 | 历史日 | 当日 | 适用场景 |
|------|--------|------|---------|
| `daily_chip_distribution` | 三角 PDF | 三角 PDF | 纯日线回测 |
| `hybrid_chip_distribution` | 三角 PDF | 分钟线量价直方图 | 分钟线实时/半日 |

`hybrid_chip_distribution` 在 `max_p <= min_p`（停牌/异常）时返回**空 Series**（P1-5），下游 `ChipFactor` 可能得到 `NaN` 因子。

> 换手率：历史日使用日线 `turnover_rate`（`daily_arr[:, 4]`），当日同样使用日线换手率而非分钟线累计换手率。原因是分钟线成交量需累计到日级才能计算换手率，而 `daily_arr` 已提供准确的日换手率，避免分钟数据截断导致失真。

---

#### 4.2.3 `minute_chip_distribution`

**源码**：`backtest/chip_algorithm.py:224-292`

分钟线筹码分布：用每分钟的实际 `(close, volume)` 构建直方图，跳过三角/均匀 PDF 假设。直接遍历分钟线序列做 decay 累积（未按日期分组；跨日时历史分钟线会被过小的分钟换手率衰减）。

```python
def minute_chip_distribution(arr, step=0.01, stock_code=""):
    close = arr[:, 0]   # 分钟 close
    vol = arr[:, 3]     # 分钟 volume
    turnover = arr[:, 4]

    min_p = float(np.nanmin(close))
    max_p = float(np.nanmax(close))
    if np.isnan(min_p) or np.isnan(max_p) or max_p <= min_p:
        # P1-5 fix: 记录原因（停牌/一字板/数据异常）
        label = f"{stock_code} " if stock_code else ""
        logger.warning(
            f"{label}价格全部相同 (max={max_p} <= min={min_p})，"
            f"可能原因：停牌、一字板涨跌停、或数据异常"
        )
        return pd.Series(dtype=float, name="cumpdf")

    price_bins = np.arange(min_p, max_p + step, step)
    cumpdf = np.zeros(len(price_bins), dtype=np.float64)
    decay = turnover.copy()
    diff = 1.0 - decay

    for i in range(len(close)):
        if np.isnan(close[i]) or vol[i] <= 0:
            continue
        idx = int((close[i] - min_p) / step)
        if idx < 0:
            idx = 0
        elif idx >= len(price_bins):
            idx = len(price_bins) - 1
        curpdf = np.zeros(len(price_bins), dtype=np.float64)
        curpdf[idx] = vol[i] * decay[i]
        if i == 0:
            cumpdf = curpdf
        else:
            cumpdf = cumpdf * diff[i] + curpdf

    total = cumpdf.sum()
    if total > 0:
        cumpdf /= total
    return pd.Series(cumpdf, index=price_bins, name="cumpdf")
```

#### 4.2.4 `adj_minute_chip_distribution`

**源码**：`backtest/chip_algorithm.py:363-402`

复权因子校正后的分钟线筹码分布。流程：
1. `get_adj_factor()` 查询该标的首日累积复权乘数
2. 价格列（close/high/low）乘复权因子，量列不变
3. 调用 `minute_chip_distribution()` 计算

```python
def adj_minute_chip_distribution(arr, stock_code, date, step=0.01):
    factor = get_adj_factor(stock_code, date, strict=True)
    if pd.isna(factor):
        raise ValueError(f"factor is NaN for {stock_code} @ {date}")
    if factor == 1.0:
        # 无复权差异，直接走原始路径避免拷贝
        return minute_chip_distribution(arr, step=step)
    arr_adj = arr.copy()
    arr_adj[:, 0] = arr[:, 0] * factor   # close
    arr_adj[:, 1] = arr[:, 1] * factor   # high
    arr_adj[:, 2] = arr[:, 2] * factor   # low
    return minute_chip_distribution(arr_adj, step=step)
```

---

### 4.3 纯数学层（qlib_cost）

#### 4.3.1 `calc_dist_chips`

**源码**：`qlib_cost/cyq.py:85-139`

```python
def calc_dist_chips(arr, method, step=0.01):
    """
    计算筹码分布。
    
    Args:
        arr: (N, 5) 数组 [close, high, low, vol, turnover_rate]
        method: "triang" | "uniform" | "turn_coeff"
                （"turn_coeff" 为换手率系数法，本因子主路径不用）
        step: 价格步长（元）
    
    Returns:
        pd.Series: index=price, value=vol（累积筹码分布）
    """
    method = method.lower()
    
    if method in {"triang", "uniform"}:
        try:
            max_p = np.nanmax(arr[:, 1])
            min_p = np.nanmin(arr[:, 2])
            xs = np.arange(min_p, max_p + step, step)
            
            # 对每行 K 线计算当日筹码分布
            curpdf = np.apply_along_axis(
                lambda x: calc_curpdf(x[0], x[1], x[2], x[3], min_p, max_p, step, method),
                1, arr,
            )
            
            # 换手率衰减累积
            cum_vol = calc_cumpdf(curpdf, arr[:, 4])
            return pd.Series(cum_vol, index=xs)
        except Exception as e:
            logger.warning(f"calc_dist_chips failed: {e}")
            return pd.Series(dtype=float, name="cumpdf")
```

#### 4.3.2 `calc_curpdf`

**源码**：`qlib_cost/cyq.py:20-58`

```python
def calc_curpdf(
    close: float, high: float, low: float, vol: float,
    min_p: float = None, max_p: float = None, step: float = 0.01, method: str = "triang"
) -> np.ndarray:
    """计算当日的 curpdf（单根 K 线的筹码分布）。"""
    method = method.lower()
    if method == "triang":
        return calc_triang_pdf(close, high, low, vol, min_p, max_p, step)
    elif method == "uniform":
        return calc_uniform_pdf(close, high, low, vol, min_p, max_p, step)
    else:
        raise ValueError("method must be triang or uniform")
```

#### 4.3.3 `calc_cumpdf`（换手率衰减累积）

**源码**：`qlib_cost/cyq.py:61-82`

```python
@jit(nopython=True)
def calc_cumpdf(curpdf: np.ndarray, turnover: np.ndarray, A: float = 1.0) -> np.ndarray:
    """
    计算 N 日累计的 cumpdf（numba 加速）。
    
    Args:
        curpdf: (N_days, N_prices)  逐日筹码分布
        turnover: (N_days,)          逐日换手率
        A: 系数（默认 1.0）
    
    递推公式：
        cumpdf_i = cumpdf_{i-1} × (1 - turnover_i) + curpdf_i × turnover_i
    """
    decay = turnover * A
    diff = 1 - decay
    
    mul_array = (curpdf.T * decay).T
    size = len(turnover)
    cumpdf = np.empty(size)
    for i in range(size):
        cumpdf = cumpdf * diff[i] + mul_array[i] if i else curpdf[i] * decay[i]
    return cumpdf  # 形状 (N_prices,)：最终一日的价格维度累积分布
```

> **返回值**：不是「按日期的数组」，而是递推结束后的 **单日价格向量**（长度 = 价格网格点数）。`calc_dist_chips` 再将其包装为 `pd.Series(index=xs)`。
>
> ⚠️ **源码历史 bug（已修复）**：函数签名与 docstring 均已修正为返回 `np.ndarray`（形状 `(N_prices,)`）。旧版本曾误写 `-> float` 且 docstring 写 `Returns: float`，实际运行时返回的是 `np.ndarray`。

**递推公式含义**：

$$
\text{cumpdf}_i = \text{cumpdf}_{i-1} \times (1 - A \cdot \text{turnover}_i) + \text{curpdf}_i \times A \cdot \text{turnover}_i
$$

> 默认 $A=1.0$；完整代码见 `calc_cumpdf(curpdf, turnover, A=1.0)`。

| 项 | 含义 |
|----|------|
| $\text{cumpdf}_{i-1} \times (1 - \text{turnover}_i)$ | 历史筹码留存部分（昨天筹码今天没换手，继续留下） |
| $\text{curpdf}_i \times \text{turnover}_i$ | 当日新筹码加入部分（今天换手了多少，就有多少新筹码按当日价格分布进来） |

> 这是**历史换手衰减模型**的核心：筹码不会永久存在，每天按换手率比例被"洗"掉一部分。

#### 4.3.4 `calc_triang_pdf`（三角分布）

**源码**：`qlib_cost/distribution_of_chips.py:108-153`

```python
def calc_triang_pdf(close, high, low, vol, min_p=None, max_p=None, step=0.01):
    """
    三角分布：假设当日成交量在 [low, high] 区间内呈三角分布，
    峰值在 close，向 high/low 两侧线性衰减。
    
    涨跌停日（high == low）：成交量全部集中在 close 一个价格点。
    """
    if (min_p is None) or (max_p is None):
        min_p, max_p = low, high

    # 涨跌停特殊处理
    if high == low:
        x = np.arange(min_p, max_p + step, step)
        pdf = np.zeros_like(x, dtype=np.float64)
        idx = int((close - min_p) / step)
        if 0 <= idx < len(x):
            pdf[idx] = 1.0
        return pdf * vol

    # c = (close - low) / (high - low)  → 三角分布众数位置（0~1）
    c = np.divide(close - low, high - low)
    x = np.arange(min_p, max_p + step, step)
    
    pdf = triang_pdf(x, c, loc=low, scale=high - low)
    return pdf / np.sum(pdf) * vol
```

**三角分布 PDF 核心**（numba 加速）：

**源码**：`qlib_cost/distribution_of_chips.py:52-105`

```python
@jit(nopython=True)
def triang_pdf(x, c, loc, scale):
    """
    自定义三角分布概率密度函数。
    
    c: 众数位置（0~1），loc: 下限，scale: 长度
    峰值在 peak = loc + scale * c
    """
    pdf = np.empty_like(x)
    
    # 边界安全检查：非法参数返回 NaN
    if (c > 1 or c < 0) or (scale < 0):
        return pdf * np.nan
    
    peak = loc + scale * c
    upper = loc + scale
    square_scale = scale ** 2

    for i in range(len(x)):
        if loc <= x[i] <= peak:
            # 上升沿：从 low 线性上升到 peak
            if c == 0:
                # 峰值在左边界：整个分布退化为从 peak 下降到 upper 的直线
                pdf[i] = 2 * np.divide(upper - x[i], square_scale)
            elif c == 1:
                # 峰值在右边界：整个区间都是上升沿
                pdf[i] = 2 * np.divide(x[i] - loc, square_scale)
            else:
                pdf[i] = 2 * np.divide(x[i] - loc, c * square_scale)
        elif peak < x[i] <= upper:
            # 下降沿：从 peak 线性下降到 high
            pdf[i] = 2 * np.divide(upper - x[i], square_scale * (1 - c))
        else:
            pdf[i] = 0.0
    return pdf
```

**几何意义**：

```
        ▲ 筹码密度
        │    /\
        │   /  \
        │  /    \
        │ /      \
        │/        \
        └──────────► 价格
        low   close  high
              ↑
           峰值 = loc + scale×c = close（c 由 OHLC 决定，仅当 close 在区间中点时三角对称）
```

#### 4.3.5 `calc_uniform_pdf`（均匀分布）

**源码**：`qlib_cost/distribution_of_chips.py:165-204`

```python
def calc_uniform_pdf(close, high, low, vol, min_p=None, max_p=None, step=0.01):
    """
    平均分布：假设当日成交量在 [low, high] 区间内均匀分布。
    涨跌停日同理，集中在 close。
    """
    if (min_p is None) or (max_p is None):
        min_p, max_p = low, high

    if high == low:
        # 涨跌停：集中在 close
        ...

    x = np.arange(min_p, max_p + step, step)
    pdf = uniform_pdf(x, loc=low, scale=high - low)
    return pdf / np.sum(pdf) * vol
```

> 实际回测默认用 `triang`（三角），`uniform` 仅作对照。
>
> ⚠️ **源码历史 bug（已修复）**：`calc_uniform_pdf` 曾调用 `uniform_pdf(x, loc=close, scale=high - low)`，导致均匀分布范围错误（应为 `[low, high]`，而非 `[close, close+high-low]`）。当前主分支已修正为 `loc=low`。

---

### 4.4 因子提取层

#### 4.4.1 `ChipFactor` 类

**源码**：`qlib_cost/cyq.py:145-157`

```python
class ChipFactor:
    def __init__(self, close: float, cumpdf: pd.Series):
        self.close = close          # 当前收盘价
        self.cumpdf = cumpdf        # 过去 N 日的累积筹码分布
        self.cumpdf.index.names = ["price"]
        self.cumpdf.name = "cumpdf"
```

#### 4.4.2 `get_cyqk_c`（盈利占比）

**源码**：`qlib_cost/cyq.py:176-185`

```python
def get_cyqk_c(self) -> float:
    """
    盈利占比 = 当前价位以下的筹码分布占比 = getwinner(close)
    
    当盈利占比很高时，大部分投资者处于盈利状态，股票面临抛售压力。
    当盈利占比很低时，股价处于历史较低价位，上涨空间较大。
    """
    return self.get_winner(self.close)
```

#### 4.4.3 `get_winner`（核心）

**源码**：`qlib_cost/cyq.py:221-237`

```python
def get_winner(self, price: float) -> float:
    """
    计算某一价位的获利比例。
    
    原理：对 cumpdf 归一化后，累加 price 以下的筹码比例。
    """
    tot_cnt = self.cumpdf.sum()        # 总筹码数
    if tot_cnt <= 0 or len(self.cumpdf) == 0:
        return float("nan")            # P0-17：空/损坏分布，禁止静默 0
    
    acc_cum = self.cumpdf / tot_cnt    # 归一化 → 概率密度
    
    # 价格 ≤ 给定 price 的筹码占比
    # （即：在该价位买入的人现在获利了）
    return acc_cum[acc_cum.index <= price].sum()
```

**图示**：

```
筹码密度 ▲
        │     ╱╲
        │    ╱  ╲
        │   ╱    ╲
        │  ╱      ╲
        │ ╱        ╲________
        └────────────────────► 价格
                 ↑
              close（当前价）
        ←──────┘
        这部分筹码的价格 < close
        → 买入成本低于现价 → 获利
        → get_cyqk_c = 这部分筹码占总筹码的比例
```

#### 4.4.4 其他因子

**源码**：`qlib_cost/cyq.py`

| 方法 | 含义 | 公式 |
|------|------|------|
| `get_asr()` | 活动筹码 | 当前价位 ±10% 区间筹码占比 |
| `get_ckdw()` | 成本重心 | `(平均成本价 - 最低成本价) / (最高成本价 - 最低成本价)` |
| `get_prp()` | 价格相对位置 | `(当前价格 - 平均成本) / 平均成本` |
| `get_cost(ratio)` | 成本价位 | 给定累计获利比率对应的价位 |

---

### 4.5 跨日衍生层

#### 4.5.0 `compute_chip_factors`（上游入口）

**源码**：`backtest/chip_algorithm.py:408-465`

从 backtrader DataFrame 计算 4 个筹码分布因子的**规范入口**。

```python
def compute_chip_factors(
    df: pd.DataFrame,
    method: str = "triang",
    data_freq: str = "1d",
    stock_code: str = None,
    daily_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Args:
        df: backtrader DataFrame（close, high, low, volume）
        method: 日线模式用 "triang" 或 "uniform"；分钟线模式忽略
        data_freq: "1d" 或 "1m"
        stock_code: **必填**（P0-18）；用于 _get_float_shares
        daily_df: 日线前复权 DataFrame（仅 data_freq="1m" 时需要）
                  用于 hybrid_chip_distribution 定框架
    Returns:
        dict: cyqk_c, asr, ckdw, prp
    """
```

**分钟线路径**：`data_freq="1m"` 时，需传入 `daily_df`（日线前复权），用 `hybrid_chip_distribution(daily_arr, minute_arr)` 计算。纯分钟线筹码分布（无 daily_df）已弃用，因为除权日存在价格断裂。

> 设计意图：`hybrid_chip_distribution` 用日线历史定框架 + 当日分钟线量价做微调，而非纯分钟线独立计算。这样既保留历史筹码衰减的连续性，又用真实分钟成交细化当日新开仓成本分布。

#### 4.5.1 `derived_chip_factors`

**源码**：`backtest/chip_algorithm.py:601-627`

```python
def derived_chip_factors(
    cyqk_today: float, cyqk_yesterday: float, turnover_today: float
) -> dict:
    """
    跨日衍生 chip 因子。
    
    Args:
        cyqk_today: 当日获利筹码比例（ChipFactor.get_cyqk_c()）
        cyqk_yesterday: 上一日获利筹码比例
        turnover_today: 当日换手率（比例，0-1）
    
    Returns:
        dict: profit_chip_diff, turnover_ratio, turnover_resistance
    """
    profit_chip_diff = cyqk_today - cyqk_yesterday     # 当日盈筹差
    if turnover_today > 0:
        turnover_resistance = profit_chip_diff / turnover_today
    else:
        turnover_resistance = 0.0

    return {
        "profit_chip_diff": round(profit_chip_diff, 6),       # 盈筹差
        "turnover_ratio": round(turnover_today, 6),            # 换手率
        "turnover_resistance": round(turnover_resistance, 4),  # 换手阻力
    }
```

#### 4.5.2 截面阻力统一入口 `compute_crossday_turnover_resistance`

**源码**：`backtest/chip_algorithm.py:636-694`

`full_market_chip_resist.py`、`spot_check_chip_factors.py`、`daily_chip_logger` 及 `filter_chip_stocks` 的 canonical 统一包装。内部自动切分"今日窗口"与"昨日窗口"，调用 `adapt_columns` → `daily_chip_distribution` → `ChipFactor` → `derived_chip_factors`，避免各脚本重复实现窗口切片逻辑。

```python
def compute_crossday_turnover_resistance(
    df: pd.DataFrame, stock_code: str, window: int = 1000, method: str = "triang"
) -> dict:
    """
    今日窗口：最近 window 个交易日（含 T）；
    昨日窗口：再往前 window 日（含 T-1）。
    分母为今日窗口 adapt_columns 末行 turnover_rate（arr_t[-1, 4]）。
    """
    as_of_t = pd.Timestamp(unique_dates[-1]).normalize()
    mask_t = df.index.normalize().isin(unique_dates[-window:])
    df_t = df.loc[mask_t]
    arr_t = adapt_columns(df_t, stock_code=stock_code, as_of_date=as_of_t)
    dist_t = daily_chip_distribution(arr_t, method=method)
    cf_t = cyq.ChipFactor(float(arr_t[-1, 0]), dist_t)
    cyqk_today = cf_t.get_cyqk_c()
    turnover_today = float(arr_t[-1, 4])

    # 昨日窗口（需至少 window+1 个交易日）
    prev_dates = unique_dates[-(window + 1):-1]
    as_of_y = pd.Timestamp(prev_dates[-1]).normalize()
    mask_y = df.index.normalize().isin(prev_dates)
    df_y = df.loc[mask_y]
    arr_y = adapt_columns(df_y, stock_code=stock_code, as_of_date=as_of_y)
    dist_y = daily_chip_distribution(arr_y, method=method)
    cf_y = cyq.ChipFactor(float(arr_y[-1, 0]), dist_y)

    derived = derived_chip_factors(cyqk_today, cf_y.get_cyqk_c(), turnover_today)
    return {
        "cyqk_c": _fmt_cyqk(cyqk_today),
        "cyqk_c_yesterday": _fmt_cyqk(cf_y.get_cyqk_c()),
        "profit_chip_diff": derived["profit_chip_diff"],
        "turnover_ratio": derived["turnover_ratio"],
        "turnover_resistance": derived["turnover_resistance"],
    }
```

> **双数据源对齐**：此函数写入 CSV 的 `turnover_ratio` / `turnover_resistance` 与 `derived_chip_factors` 直接输出值完全一致（同源码、同舍入位）。运维脚本旧版「`vol×100/静态 float_shares`」分母已废弃。

---

#### 4.5.3 直观解释

| 场景 | 分子（盈筹差） | 分母（换手率） | 换手阻力 |
|------|--------------|--------------|---------|
| 大涨 + 低换手 | 获利筹码大增 | 换手很小 | **高阻力** → 抛压小，筹码锁定 |
| 大涨 + 高换手 | 获利筹码大增 | 换手很大 | **低阻力** → 筹码充分交换 |
| 横盘 + 任何换手 | 盈筹差 ≈ 0 | — | **≈ 0** → 无方向 |
| 负值 | 获利筹码减少（套牢增加） | — | **负阻力** → 空头阻力 |

`derived_chip_factors` **不**过滤 `cyqk` 为 `NaN` 的情况；若筹码分布为空（停牌、一字板、数据异常导致 `get_cyqk_c()` 返回 `NaN`），则 `profit_chip_diff = NaN - NaN = NaN`，进而 `turnover_resistance = NaN`。下游过滤规则（`|resist|>20`）会自动排除 `NaN` 行。

> 边界：`turnover_today = 0` 或 `NaN` 时，`if turnover_today > 0` 为 `False`，返回 `turnover_resistance = 0.0`（不是 `NaN` 或 `Inf`）。若需区分"零换手"与"无效换手"，应在调用方额外判断。

---

### 4.5.4 换手率半衰期因子 `turnover_chip_factors`

**源码**：`backtest/chip_algorithm.py:471-503`

基于广发证券多因子 alpha 系列报告 #27 的换手率半衰期模型。不需要 OHLC 分布假设，仅需换手率和收盘价。

```python
def turnover_chip_factors(
    turnover_rate: np.ndarray, close: np.ndarray, window: int = 60
) -> dict:
    """
    Returns:
        dict: arc, vrc, src, krc
    """
    if len(turnover_rate) < window or len(close) < window:
        return {"arc": np.nan, "vrc": np.nan, "src": np.nan, "krc": np.nan}
    tr = np.asarray(turnover_rate[-window:], dtype=np.float64).flatten()
    cl = np.asarray(close[-window:], dtype=np.float64).flatten()
    arc, vrc, src, krc = tco.calc_distribution_of_chips(tr, cl, window)
    return {"arc": float(arc), "vrc": float(vrc), "src": float(src), "krc": float(krc)}
```

| 因子 | 含义 |
|------|------|
| `arc` | 平均换手率衰减成本 |
| `vrc` | 换手率变异系数 |
| `src` | 换手率偏度 |
| `krc` | 换手率峰度 |

在 `daily_chip_logger.py` 和 `rolling_ic` 中均有输出。

### 4.6 截面日定义与换手率数据一致性

#### 4.6.1 截面日（T vs T-1）

在**固定评估日 T**（目标交易日）上，规范语义为：

| 窗口 | 交易日范围 | 用于 |
|------|------------|------|
| **今日** `today_win` | 最近 `window`（默认 1000，≈4 年）个交易日，**含 T** | `cyqk_today = ChipFactor(close_T, dist_T).get_cyqk_c()` |
| **昨日** `yest_win` | 最近 `window` 根 K 线，**含 T-1、不含 T** | `cyqk_yesterday`（收盘价取 T-1） |
| **当日换手** | T 日 `turnover_rate` | `arr_t[-1, 4]` 或 `derived["turnover_ratio"]` |

与 `backtest/daily_chip_logger.py` 一致：取 `window+1` 根日线，`head(window)` / `tail(window)` 实现相邻两日滚动。
实现约束：**T-1 定义为“前一个交易日”**，不得用日历日 `T-1day` 代替（节假日会导致窗口错位）。

**回测选股**（`chip_factor_analysis.multiround_backtest`、`filter_chip_stocks.py`）：在 `BACKTEST_START`（或 `--date`）**单日截面**计算上述因子并过滤，**不是**持仓期内每日重算阻力。

**量纲**：`turnover_resistance = Δcyqk / turnover`，二者均为比例（0~1），结果无量纲；`|阻力|>10` 等阈值需结合全市场分布理解，非百分比。

#### 4.6.2 换手率双数据源（对齐必读）

| 入口 | 分子 cyqk | 分母 turnover |
|------|-----------|----------------|
| **`derived_chip_factors`**（回测、`daily_chip_logger`） | `ChipFactor` + 80 日分布 | **`arr_t[-1, 4]`**（`adapt_columns` → history/parquet） |
| **`full_market_chip_resist` / `spot_check`** 的 `turnover_resist` | `ChipFactor` + 80 日分布 | **`compute_crossday_turnover_resistance`** → `arr_t[-1,4]` / `derived["turnover_ratio"]` |

运维脚本 CSV 的 **`turnover_1d` 现已写入 canonical `turnover_ratio`**（与 `turnover_resistance` 同源）。`turnover_5d_avg` / `turnover_20d_avg` 仍为静态 parquet 粗算，仅作参考。

历史对比：若用旧版「`vol×100/静态 float_shares`」分母，在 history 与 parquet 分叉日会与 canonical 不一致；可用 `verify_turnover_resistance_alignment.py` 抽检。

> **窗口内换手列语义**：`adapt_columns` 未传 `as_of_date` 时，`_get_float_shares` 返回单一 `float_shares` 值，整列 `turnover_rate` 均按该股本估算。这意味着**窗口内所有历史日的换手率也使用同一股本**，而非各自历史日的真实股本。对送转股频繁的小盘股，早期 K 线的 `turnover_rate` 会有系统性偏差。若需逐日精确，应扩展为逐日查 `free_float_shares.parquet`。

#### 4.6.3 列名对照

| Python dict（`derived_chip_factors`） | 全市场/Spot CSV | `filter_chip_stocks` |
|--------------------------------------|-----------------|----------------------|
| `turnover_resistance` | `turnover_resist` | `resist` |
| `profit_chip_diff` | `cyqk_c_diff` | — |
| `turnover_ratio` | `turnover_1d`（脚本侧，见 §6） | `turnover_ratio` |

---

### 4.7 与市面筹码分布指标的差异对比

> **本节背景**：用户将本仓库的 `cyqk_c` 与招商证券 APP 的"获利盘比例"对比，发现 300834.SZ / 20260327 的数值差距巨大（本仓库 **0.3532** vs 招商证券 **0.632**）。经排查，差异**不是 bug**，而是**算法模型的根本不同**。

#### 4.7.1 核心差异：换手率衰减模型 vs 等权重累加

| 维度 | 本仓库 canonical | 市面常见 APP（招商证券等） |
|------|-----------------|--------------------------|
| **历史筹码处理** | **换手率衰减模型** — 历史筹码每天按 `turnover_rate` 比例被"洗掉" | **等权重累加** — 所有历史日筹码同等重要，不随时间衰减 |
| **经济学假设** | 筹码会"过期"：若日均换手 2%，40 个交易日后老筹码基本换完 | 筹码永久存在：3 个月前的成交与今日同等重要 |
| **窗口大小** | **1000 个交易日**（`window = 1000`，≈4 年） | **约 100~130 个交易日**（实测招商约 116~122 日） |
| **公式** | `cumpdf_i = cumpdf_{i-1} × (1 - A·turnover_i) + curpdf_i × A·turnover_i` | `cumpdf = Σ curpdf_i`（直接求和） |
| **适用场景** | 量化交易、短周期 alpha 因子（广发/国君研报路径） | 技术分析、长线成本分布展示 |

#### 4.7.2 数值对比（300834.SZ / 20260327）

| 算法 | 窗口 | cyqk_T | cyqk_T-1 | 与招商差距 |
|------|------|--------|----------|-----------|
| **Canonical（本仓库）** | 80 日 + 衰减 | **0.3532** | **0.0643** | 极大 |
| 等权重无衰减 | 100 日 | 0.5969 | 0.1650 | 较大 |
| 等权重无衰减 | **116 日** | **0.6227** | **0.2028** | **最接近** |
| 等权重无衰减 | 122 日 | **0.6325** | 0.2170 | T 日几乎一致 |

**结论**：招商证券的算法 ≈ **等权重累加约 116~122 个交易日**的三角分布，**不使用换手率衰减**。

#### 4.7.3 为什么差距这么大？

以 300834 为例：

- T 日大涨 **+7.57%**，换手率仅 **1.67%**
- **Canonical（衰减模型）**：历史筹码被大量"洗掉"，留存筹码少 → 当日新增筹码占比高 → `cyqk_T = 0.3532`（仅 35% 筹码在收盘价下方）
- **招商（无衰减）**：历史筹码全部保留，3~4 个月交易堆积 → 大量低价筹码仍在下方 → `cyqk_T ≈ 0.632`（63% 筹码在收盘价下方）

#### 4.7.4 对比实现：`compute_equal_weight_cyqk`

**源码**：`backtest/chip_algorithm.py:700-777`

为便于与市面指标对齐验证，本仓库提供无衰减的等权重实现：

```python
from backtest.chip_algorithm import compute_equal_weight_cyqk

eq = compute_equal_weight_cyqk(df, "300834.SZ", window=120, method="triang")
# eq["cyqk_c"] ≈ 0.6293（与招商 0.632 接近）
```

与 canonical 的差异：
1. 不使用 `calc_cumpdf` 的换手率衰减
2. 直接 `np.sum(curpdfs, axis=0)` 等权重累加
3. 默认窗口 120 日（可调）

**使用建议**：
- **量化选股** → 使用 canonical `compute_crossday_turnover_resistance`（衰减模型更符合交易现实）
- **与市面 APP 对齐验证** → 使用 `compute_equal_weight_cyqk`（仅供对比，不用于生产信号）

> ⚠️ 本仓库的回测框架、选股规则、IC 检验均基于 **换手率衰减模型** 的 canonical 路径。若改用无衰减模型，阻力阈值（`|resist|>20` 等）需重新校准。

---

### 附录 B：`TurnoverChipFactor` Indicator

**源码**：`backtest/chip_indicator.py:191-274`

backtrader `bt.Indicator` 子类，专用于输出换手率半衰期因子（ARC/VRC/SRC/KRC）。无需 OHLC 分布假设，仅依赖收盘价和换手率。

```python
class TurnoverChipFactor(bt.Indicator):
    lines = ("arc", "vrc", "src", "krc")
    params = (
        ("period", 60),
        ("stock_code", ""),
    )
```

在策略中引用：`self.turnover_chip.arc[0]` 等。数据不足 `period` 时返回 NaN。

**turnover_rate fallback**：当 backtrader 数据中不存在 `turnover_rate` line（全 NaN）时，`TurnoverChipFactor.next()` 会自动用 `volume` + `_get_float_shares(stock_code)` 重新估算换手率。若 `stock_code` 未提供，则回退 100 亿默认值并记录 warning；若查不到股本，`_get_float_shares` 会抛 `ValueError`，被外层异常捕获后返回 NaN。

---

*文档整理于 2026-05-24；2026-05-24 二次审计修订：§4.1 P0-18、§4.2 筹码分布边界安全、§4.3 PDF 边界/triang_uniform 片段、§4.5 类型注解/窗口保护、§4.6 截面/换手率一致性、§5.2 bb_position 统一实现、§5.3 ChipSellStrategy 参数/NaN 保护、§5.4 行号同步、§6 CLI/输出列、§8 索引扩展/附录 B TurnoverChipFactor。2026-05-24 三次审计修订：§4.5.2 新增 `compute_crossday_turnover_resistance` canonical 统一入口、§5.4 硬编码 `80` 修正为 `WINDOW_DAYS`、§4.5/§4.6 行号与源码同步。2026-05-24 四次修订：§4.7 市面筹码分布指标差异对比 + `compute_equal_weight_cyqk` 对比实现。*
