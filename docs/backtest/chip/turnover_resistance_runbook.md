## 5. 回测框架

### 5.1 选股规则 `RULES`

**源码**：`backtest/chip_factor_analysis.py:318-322`

```python
RULES = {
    "all":         {"label": "基准（无过滤）",
                    "filter": lambda df: df},
    "resist_bb":   {"label": "|阻力|>20 & BB中轨↑",
                    "filter": lambda df: df[(df["turnover_resistance"].abs() > 20) & (df["bb_position"] >= 0.5)]},
    "resist_bb10": {"label": "|阻力|>10 & BB中轨↑",
                    "filter": lambda df: df[(df["turnover_resistance"].abs() > 10) & (df["bb_position"] >= 0.5)]},
}
```

| 规则 | 含义 |
|------|------|
| `all` | 不加过滤，随机抽 `top_n` 只 → 作为基准 |
| `resist_bb` | **\|换手阻力\| > 20** 且 **布林带位置 ≥ 0.5（中轨之上）** |
| `resist_bb10` | **\|换手阻力\| > 10** 且 **布林带位置 ≥ 0.5** |

> 取 `abs` 是因为换手阻力可正可负。正值表示上涨时筹码锁定（抛压小），负值表示下跌时套牢盘增加。取绝对值只看"阻力强度"。

**阈值敏感性（研究缺口）**：`|阻力|>20` 与 `|阻力|>10` 的选取目前基于回测经验，尚未做全市场截面分位数标定。建议在使用前跑 `full_market_chip_resist.py` 或 `daily_chip_logger.py` 观察目标日期的全市场分布（如 P90/P95），再决定阈值。不同市场环境（牛/熊/震荡）下，同一阈值的覆盖股票数可能差异极大。

### 5.2 布林带位置

**源码**：`backtest/chip_algorithm.py` `bb_position()` — 统一实现；`filter_chip_stocks` / `chip_factor_analysis` 均通过 `from backtest.chip_algorithm import bb_position` 导入。

```python
def bb_position(close: np.ndarray, period: int = 20, nbdev: float = 2.0) -> float:
    """
    布林带位置：close 在布林带中的相对位置。
    0 = 下轨, 0.5 = 中轨, 1 = 上轨
    """
    if len(close) < period:
        return 0.5  # 数据不足时默认中轨
    ma = np.mean(close[-period:])
    std = np.std(close[-period:])
    upper = ma + nbdev * std
    lower = ma - nbdev * std
    band_width = upper - lower
    if band_width < 1e-8:
        return 0.5  # 除零保护（std=0，价格完全没波动）
    return float((close[-1] - lower) / band_width)
```

`bb_position >= 0.5` 表示股价在中轨之上 → **只做右侧**，不抄底。

### 5.3 回测策略 `ChipSellStrategy`

**源码**：`backtest/chip_factor_analysis.py:101-245`

```python
class ChipSellStrategy(bt.Strategy):
    """
    chip 因子选股 + 固定止盈/持仓期卖出 + 循环再买入。
    
    买入：chip 因子预热完成后等权全仓，卖出后现金重新分配到可用标的
    卖出：
      1. 盈利 ≥ 5% 止盈
      2. 持有 5 天强制卖出
      3. 无止损
    再买入：卖出次日，现金等权分配到未持仓标的
    """
    params = (
        ("take_profit", 0.05),   # 止盈 5%
        ("max_hold", 5),         # 最大持有天数
        ("t1_buy", False),       # T+1 open 买入
    )
```

**策略参数**：

| 参数 | 值 | 说明 |
|------|-----|------|
| 初始资金 | 1,000,000 | |
| 手续费 | 0.05% | |
| 止盈 | +5% | 盈利 5% 即卖出 |
| 最大持有 | 5 天 | 无论盈亏，5 天后强制卖出 |
| 止损 | 无 | 不设置止损 |
| 买入时机 | **T+1 open**（默认） | `t1_buy=False`：backtrader 默认 `Market` 订单，在 `next()` 中发出后于**下一根 bar open** 执行 |
| 买入时机 | **T 日收盘** | `t1_buy=True`：显式 `Close` 订单，当前 bar close 执行 |
| 仓位分配 | 等权 | 可用现金平均分配到所有可买标的 |
| 涨停过滤 | 是 | 涨停标的不买入 |
| 基准 | 沪深 300 | `BENCHMARK_CODE = "000300.SH"` |

> ⚠️ **参数名历史遗留**：`t1_buy=True` 字面像"T+1 买入"，实际语义却是"当日收盘买入"（`Close` 订单）。默认 `False` 才是常见的 T+1 open 行为。以表格中「说明」列语义为准，勿被参数名误导。

#### `_is_limit_up`（涨停判断）

```python
def _is_limit_up(self, d) -> bool:
    if len(d) < 2:
        return False
    prev_close = d.close[-1]
    if prev_close <= 0:
        return False
    current = d.close[0]
    change = (current - prev_close) / prev_close
    code = d._name or ""
    limit = 0.20 if code.startswith(("300", "301", "688")) else 0.098
    return change >= limit
```

- 主板/中小板：`limit = 0.098`（≈10%）
- 创业板（300/301）、科创板（688）：`limit = 0.20`（20%）

#### `load_data`（数据预热）

**源码**：`backtest/chip_factor_analysis.py:75-95`

```python
def load_data(reader, code, bars=120, from_date=None):
    df = reader.read_stock(code, period='1d', adjust_type='front')
    if df is None:
        return None
    df = df.rename(columns={"time": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
    df.set_index("datetime", inplace=True)
    # 过滤到 A 股交易日
    trading = _trading_days("2024-01-01", "2026-12-31")
    df = df[df.index.normalize().isin(trading.normalize())]
    if from_date is not None:
        start_ts = pd.Timestamp(from_date)
        pre_start = df[df.index < start_ts]
        post_start = df[df.index >= start_ts]
        warmup = pre_start.tail(WINDOW_DAYS) if len(pre_start) >= WINDOW_DAYS else pre_start
        df = pd.concat([warmup, post_start])
    if bars and len(df) > bars:
        df = df.tail(bars)
    return df
```

关键：**预热窗口** `warmup` 取回测起点前最多 80 根 bar；若历史数据不足 80 根，则取全部可用数据供 `ChipDistribution` warmup。

**买入时记录换手阻力**（`_distribute_cash` 方法内阻力计算片段 `L188-210`，完整方法 `L167-215`）：

```python
def _distribute_cash(self):
    for d in buyable:
        # 计算当前阻力值并记录到日志
        resist_str = ""
        try:
            cyqk_now = float(self._chips[d].cyqk_c[0])
            cyqk_prev = self._prev_cyqk.get(d)
            if cyqk_prev is not None and not np.isnan(cyqk_now) and not np.isnan(cyqk_prev):
                diff = cyqk_now - cyqk_prev
                try:
                    tr_val = float(_estimate_turnover(np.array([d.volume[0]]))[0])
                    if tr_val > 0:
                        resist = diff / tr_val
                        resist_str = f"|resist|={abs(resist):.1f}"
                except Exception:
                    pass
            self._prev_cyqk[d] = cyqk_now
        except Exception:
            pass
        
        if self.p.t1_buy:
            self.buy(data=d, size=size, exectype=bt.Order.Close)
            self._log_trade("BUY", d, price, size, f"Close {resist_str}")
        else:
            self.buy(data=d, size=size)
            self._log_trade("BUY", d, price, size, f"NextOpen {resist_str}")
```

> **注意**：此处 `_estimate_turnover(volume)` **未传入** `float_shares` / `stock_code`，会走 **100 亿默认**（见 §4.1.2）。`resist_str` 仅写入**交易日志**，与选股截面的 `derived_chip_factors` **不是同一套换手率**；小盘股日志中的 `|resist|` 可能失真，勿与回测 RULES 阈值直接对比。日志标签 `Close` / `NextOpen` 与 `t1_buy` 语义一致（非历史误导的 `T+1open` 字面）。

### 5.4 多轮回测流程

**`multiround_backtest`** → `backtest/chip_factor_analysis.py:328-405`

- **标的池**：对传入的 `codes` **全量**计算截面因子（非每轮重抽 200 只）；`--sample 200` 在 `main()` 入口对全市场代码**一次性**随机抽样后传入。
- **每轮随机性**：仅当某规则过滤后标的数 `> top_n` 时，用 `rng.choice` 抽 `top_n` 只进入 `run_backtest`。

```python
def multiround_backtest(reader, codes, top_n, rounds, bars, t1_buy=False):
    for rnd in range(rounds):
        pool = sorted(codes)
        pool_factors = []
        for code in pool:
            df = load_data(reader, code, from_date=BACKTEST_START)
            
            # 今日因子
            today_win = df[df.index <= today_end].tail(WINDOW_DAYS)
            arr_t = adapt_columns(today_win, stock_code=code)
            dist_t = daily_chip_distribution(arr_t, method="triang")
            ct_t = float(arr_t[-1, 0])
            cf_t = cyq.ChipFactor(ct_t, dist_t)
            
            # 昨日因子
            yest_win = pre.tail(WINDOW_DAYS)
            arr_y = adapt_columns(yest_win, stock_code=code)
            dist_y = daily_chip_distribution(arr_y, method="triang")
            ct_y = float(arr_y[-1, 0])
            cf_y = cyq.ChipFactor(ct_y, dist_y)
            
            # 跨日衍生
            derived = derived_chip_factors(
                cf_t.get_cyqk_c(),
                cf_y.get_cyqk_c(),
                float(arr_t[-1, 4])
            )
            
            pool_factors.append({
                "stock_code": code,
                "turnover_resistance": derived["turnover_resistance"],
                "bb_position": bb_position(today_win["close"].values),
                ...
            })
        
        pool_df = pd.DataFrame(pool_factors)
        
        for rule_name, rule_info in RULES.items():
            filtered = rule_info["filter"](pool_df)
            fc = filtered["stock_code"].tolist()
            if len(fc) > top_n:
                fc = sorted(rng.choice(fc, size=top_n, replace=False))
            
            r = run_backtest(reader, fc, bars=bars, t1_buy=t1_buy)
```

**输出示例**（**示意性**，非固定回归基准；实际收益随样本与行情变化）：

```
=== Multi-Round Backtest (10 rounds, top 50, 60 bars) ===
  Rule                         Return      MaxDD    Sharpe   vs CSI300
  ------------------------- ------------ ---------- -------- ----------
  基准（无过滤）               +3.2%±1.5%    2.1%     0.85    -1.3%
  |阻力|>20 & BB中轨↑          +7.8%±2.1%    1.8%     1.42    +3.3% ★
  |阻力|>10 & BB中轨↑          +5.1%±1.8%    1.9%     1.10    +0.6%

  CSI 300 同期收益: +4.5%
  vs 随机基准 (return=+3.2%):
  |阻力|>20 & BB中轨↑          ΔRet=+4.6%  ΔCSI300=+3.3% ★
```

### 5.5 滚动 IC

**`rolling_ic`** → `backtest/chip_factor_analysis.py:411-478`

每隔 `step_days`（默认 20 天）取一次截面，计算各因子与未来 20 天收益的 Spearman 秩相关系数。

```python
def rolling_ic(reader, codes, lookback=365, step_days=20):
    for t in range(lookback, len(all_dates), step_days):
        target_date = all_dates[t]
        for code in codes:
            win = df.iloc[t - WINDOW_DAYS : t]
            arr = adapt_columns(win, stock_code=code)
            dist = daily_chip_distribution(arr, method="triang")
            ct = float(arr[-1, 0])
            cf = cyq.ChipFactor(ct, dist)
            
            # 换手率半衰期因子
            tr_arr = arr[:, 4]
            cl_arr = arr[:, 0]
            tcf = turnover_chip_factors(tr_arr, cl_arr, window=min(60, len(tr_arr)))
            
            # 20 天后收益（用 get_indexer 精确定位截面日，防非交易日跳空）
            idx_t = df.index.get_indexer([target_date], method="ffill")[0]
            if idx_t + 20 < len(df):
                fwd20 = (float(df.iloc[idx_t + 20]["close"]) - ct) / ct
            else:
                fwd20 = np.nan
            
            factors["cyqk_c"].append(cf.get_cyqk_c())
            factors["asr"].append(cf.get_asr())
            factors["ckdw"].append(cf.get_ckdw())
            factors["prp"].append(cf.get_prp())
            factors["arc"].append(tcf["arc"])
            factors["vrc"].append(tcf["vrc"])
            factors["src"].append(tcf["src"])
            factors["krc"].append(tcf["krc"])
            factors["fwd"].append(fwd20)
        
        # Spearman 秩相关系数（循环 8 个因子；样本不足 30 时填充 NaN）
        for fac in ["cyqk_c", "asr", "ckdw", "prp", "arc", "vrc", "src", "krc"]:
            if len(factors[fac]) >= 30:
                ic, p = spearmanr(factors[fac], factors["fwd"])
                ic = round(ic, 4)
                p = round(p, 4)
            else:
                ic, p = np.nan, np.nan
```

> 注意：滚动 IC 中**没有直接测试 `turnover_resistance`**，因为它是跨日衍生量（需要 t-1 和 t 两个截面），而 IC 截面是单点因子检验。

---

## 6. 脚本使用指南

**数据读取器**：运维脚本使用 `oskh_data.reader.StockDataReader`（DuckDB 持久化）；回测框架使用 `backtest.stock_data_reader.StockDataReader`。二者接口相近，勿混为同一模块。

### 6.1 全市场计算

**脚本**：`scripts/full_market_chip_resist.py`

```bash
# 默认日期 20260515
D:/anaconda3/envs/vanna311/python.exe scripts/full_market_chip_resist.py

# 指定日期 + 输出 CSV
D:/anaconda3/envs/vanna311/python.exe scripts/full_market_chip_resist.py \
    --date 20260522 --output full_market.csv

# 自定义筹码窗口（默认 80，需 window+1 个交易日）
D:/anaconda3/envs/vanna311/python.exe scripts/full_market_chip_resist.py \
    --date 20260522 --window 80
```

**`compute_bollinger`**：布林带计算使用 `roll.std(ddof=0)`（总体标准差），与样本标准差 `ddof=1` 不同。

**主要输出列**（见脚本 `rows.append`；阻力经 `compute_crossday_turnover_resistance`，**无** 单独 `asr`/`ckdw`/`prp`）：

`stock_code`, `close`, `volume_1d_手`, `volume_5d_avg_手`, `turnover_1d`, `float_shares_亿`, `cyqk_c_today`, `cyqk_c_yesterday`, `cyqk_c_diff`, `turnover_resist`, `resist_abs`, `support_abs`, `boll_mid`, `boll_upper`, `boll_lower`, `boll_width`, `boll_pct_b`

`turnover_1d` = canonical `turnover_ratio`；`turnover_resist` = `turnover_resistance`（§4.6.3）。`boll_pct_b` ≠ `bb_position`（算法不同）。

### 6.2 Spot Check（随机抽样）

**脚本**：`scripts/spot_check_chip_factors.py`

> **无 `--stock` 参数**；从 `float_shares.parquet` 全市场列表中按 `--samples` / `--seed` 随机抽样。

```bash
# 默认：日期 20260515，随机 100 只，seed=42
D:/anaconda3/envs/vanna311/python.exe scripts/spot_check_chip_factors.py

# 指定日期、样本量、输出路径
D:/anaconda3/envs/vanna311/python.exe scripts/spot_check_chip_factors.py \
    --date 20260522 --samples 50 --seed 42 --output spot_check.csv

# 自定义筹码窗口
D:/anaconda3/envs/vanna311/python.exe scripts/spot_check_chip_factors.py \
    --date 20260522 --window 80 --samples 20
```

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--date` | "20260515" | 目标日期 YYYYMMDD |
| `--samples` | 100 | 随机抽样数量 |
| `--seed` | 42 | 随机种子（固定可复现） |
| `--window` | 1000 | 筹码计算窗口（交易日，≈4年） |
| `--output` | None | 输出 CSV 路径 |

**主要输出列**（核心 + `compute_all_factors` 扩展）：

`stock_code`, `name`, `close`, `cyqk_c`, `asr`, `ckdw`, `prp`, `cyqk_c_yesterday`, `cyqk_c_diff`, `turnover_resist`, `resist_abs`, `support_abs`, `turnover_1d`, `turnover_5d_avg`, `turnover_20d_avg`, `volume_*`, `float_shares_亿`, `total_shares_亿`, `high_80d`, `low_80d`, `cost_p05`…`cost_p95`, `resist_dist_p90_pct`, `resist_dist_p95_pct`, `support_dist_p10_pct`, `concentration_90`, `concentration_70`, `winner_ratio`, `loser_ratio`, `close_chg_*_pct`。

`turnover_resist` / `turnover_1d` 与 canonical 一致（`compute_crossday_turnover_resistance`）；`turnover_5d_avg` / `turnover_20d_avg` 仍为静态 parquet 参考值。

### 6.3 因子分析（多轮回测 + 滚动 IC）

**脚本**：`backtest/chip_factor_analysis.py`（`backtest.stock_data_reader.StockDataReader`）

```bash
# 多轮回测 + 滚动 IC（默认 200 只抽样，10 轮，每轮选 top 50）
D:/anaconda3/envs/vanna311/python.exe backtest/chip_factor_analysis.py \
    --sample 200 --rounds 10 --top 50

# 仅做多轮回测（跳过滚动 IC）
D:/anaconda3/envs/vanna311/python.exe backtest/chip_factor_analysis.py \
    --skip-ic

# 仅滚动 IC（跳过多轮回测）
D:/anaconda3/envs/vanna311/python.exe backtest/chip_factor_analysis.py \
    --skip-backtest

# T+1 open 买入（默认行为，无参数；对应策略参数 t1_buy=False）
D:/anaconda3/envs/vanna311/python.exe backtest/chip_factor_analysis.py

# T 日收盘买入（显式 Close 订单；对应策略参数 t1_buy=True）
D:/anaconda3/envs/vanna311/python.exe backtest/chip_factor_analysis.py --t1
```

截面因子 dict 使用列名 **`turnover_resistance`**（与 §4.6.3 对照）。

**落盘 CSV**（`chip_factor_analysis` 的 `main()`，非 per-stock 因子表）：

| 文件 | 列（摘要） | 含 per-stock 阻力？ |
|------|------------|---------------------|
| `backtest_output/chip_multiround_{tag}.csv` | `n_stocks`, `total_return`, `max_drawdown`, `sharpe`, `bench_return`, `round`, `rule` | **否**（回合级收益） |
| `backtest_output/chip_trades_{tag}.csv` | 策略成交明细 | 日志中可有 `\|resist\|` 片段 |
| `backtest_output/chip_rolling_ic_{tag}.csv` | `date`, `ic_*`, `p_*`, `n_stocks` | **否** |

per-stock 截面因子仅在内存 `pool_factors` 中计算；导出请用 `daily_chip_logger` 或自行 dump。

### 6.4 每日截面日志（canonical）

**脚本**：`backtest/daily_chip_logger.py`

按交易日落盘 `profit_chip_diff`、`turnover_ratio`、`turnover_resistance`（经 `derived_chip_factors`），并含 `turnover_chip_factors` 的 ARC/VRC/SRC/KRC。适合作为**每日生产截面**的参考实现。

```bash
# 指定日期
D:/anaconda3/envs/vanna311/python.exe backtest/daily_chip_logger.py --date 20260513

# 分钟线模式（输出文件名带 `_1m` 后缀：chip_daily_20260513_1m.csv）
D:/anaconda3/envs/vanna311/python.exe backtest/daily_chip_logger.py --date 20260513 --freq 1m

# 自动定时：每 10 分钟检查一次，15:30 执行后退出
D:/anaconda3/envs/vanna311/python.exe backtest/daily_chip_logger.py --schedule
```

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--date` | 最新 stock_pool | stock_pool 日期 YYYYMMDD |
| `--freq` | "1d" | 数据频率：1d / 1m |
| `--schedule` | False | 自动定时模式 |

**输出字段**：
`stock_code`, `close`, `cyqk_c`, `asr`, `ckdw`, `prp`, `arc`, `vrc`, `src`, `krc`, `profit_chip_diff`, `turnover_ratio`, `turnover_resistance`, `turnover_mean`, **`signal`**（`cyqk_c>0.8` → `HIGH`，`<0.2` → `LOW`，否则空）

输出路径：`backtest_output/chip_daily_{date}.csv`（`--freq 1m` 时为 `chip_daily_{date}_1m.csv`）

### 6.5 全市场筛选

**脚本**：`backtest/filter_chip_stocks.py`

按 chip 因子条件筛选全市场股票，支持单日或日期区间。

```bash
# 单日筛选
D:/anaconda3/envs/vanna311/python.exe backtest/filter_chip_stocks.py --date 2026-03-01

# 日期区间（每个交易日输出一次）
D:/anaconda3/envs/vanna311/python.exe backtest/filter_chip_stocks.py \
    --start 2026-03-10 --end 2026-05-14

# 自定义阈值 + 仅正值
D:/anaconda3/envs/vanna311/python.exe backtest/filter_chip_stocks.py \
    --start 2026-03-10 --end 2026-05-14 --resist 15 --positive
```

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--resist` | 20.0 | 阻力绝对值阈值 |
| `--bb` | 0.5 | BB 中轨位置阈值 |
| `--date` | None | 单日筛选日期 |
| `--start` / `--end` | None | 区间起始/结束日期 |
| `--positive` | False | 仅保留阻力 > 0（正值） |

**过滤逻辑**：`abs(resist) > min_abs_resist and bb >= min_bb`

**输出列**：`date`, `code`, `close`, `resist`, `abs_resist`, `cyqk_today`, `cyqk_yesterday`, `turnover_ratio`, `bb_position`, `cyqk_c`, `asr`

输出：`backtest_output/chip_filter_{start}_{end}.csv`（日期中的连字符会被去除，例如 `chip_filter_20260301_20260514.csv`）

---

### 6.6 双路径对齐验证（§8）

**脚本**：`scripts/verify_turnover_resistance_alignment.py`

对比 **路径 A**（`daily_chip_logger` 等价内联）与 **路径 B**（`compute_crossday_turnover_resistance`，与 full_market/spot_check 相同）：

```bash
D:/anaconda3/envs/vanna311/python.exe scripts/verify_turnover_resistance_alignment.py \
    --date 20260515 --samples 20 --seed 42

# 可调阈值（默认 turnover 1e-4，阻力 0.05）
D:/anaconda3/envs/vanna311/python.exe scripts/verify_turnover_resistance_alignment.py \
    --date 20260515 --samples 50 --tol-turnover 1e-6 --tol-resist 0.01
```

输出摘要打印 P50/P95 偏差，并写入 `backtest_output/verify_turnover_resist_align_{date}.csv`。退出码：`0` 全部对齐，`2` 存在偏差。

**CSV 列**：`stock_code`, `turnover_canonical`, `turnover_ops`, `turnover_abs_diff`, `resist_canonical`, `resist_ops`, `resist_abs_diff`, `cyqk_t_abs_diff`, `cyqk_y_abs_diff`, `turnover_ok`, `resist_ok`

**20260515 运行结果**（20 只抽样，19 只有效，seed=42）：

| 指标 | 结果 |
|------|------|
| 换手率对齐（\|diff\| ≤ 1e-4） | **19/19** |
| 换手阻力对齐（\|diff\| ≤ 0.05） | **19/19** |
| turnover P50 / P95 / max | 0 / 0 / 0 |
| resist P50 / P95 / max | 0 / 0.0001 / 0.0001 |

CSV：`backtest_output/verify_turnover_resist_align_20260515.csv`

> 说明：当前样本下 history 与静态 parquet 一致，双轨无偏差。若日后 history 与静态表分叉，脚本会以退出码 2 标出换手率不一致标的。另跑 `spot_check`（5 只，4 有效）正常落盘。全市场大批量可再跑 `full_market_chip_resist.py --date 20260515` 做交叉核对。

### 6.7 手算核对表示例

按 §4.5.2 `compute_crossday_turnover_resistance` canonical 路径逐步拆解，供计算器复现核对：

- **填数样例**：[turnover_resistance_handcheck_300834_20260327.md](turnover_resistance_handcheck_300834_20260327.md)（`300834.SZ` / `20260327`，窗口 80 日，`triang`）
- **覆盖项**：`cyqk_T`、`cyqk_T-1`、盈筹差、**两种 turnover**（`float_shares_history` vs 静态 `float_shares.parquet`）、**两种换手阻力**（定义与 §4.6.2 一致）
- **手算范围**：流通股本、T 日换手率、盈筹差与阻力公式；80 日三角 PDF + `calc_cumpdf` 衰减以机器输出的 `cyqk` 为可核对终点（见样例 §五、§十检查清单）

### 6.8 TR 布林带 Parquet 流水线（Canonical TR_1000）

详见 [`turnover_resistance_tr_bollinger.md`](turnover_resistance_tr_bollinger.md)。

```bash
# 单日：Rust TR 截面 → Parquet → TR BB
D:/anaconda3/envs/vanna311/python.exe scripts/compute_turnover_resistance_bands.py --date YYYYMMDD

# 仅补 TR BB（截面已入库）
D:/anaconda3/envs/vanna311/python.exe scripts/compute_turnover_resistance_bands.py --date YYYYMMDD --backfill-bands-only

# 历史回填（默认 60 日历日 walk-back）
D:/anaconda3/envs/vanna311/python.exe scripts/backfill_turnover_resistance_bands.py --end-date YYYYMMDD --skip-existing
```

输出：`stock_data/turnover_resistance_daily.parquet`（可由 `TURNOVER_RESIST_BANDS_PATH` 覆盖）。

---

## 7. 参数速查表

### 7.1 阻力与换手率舍入（CSV 对比用）

| 路径 | `turnover` 小数位 | `turnover_resistance` 小数位 |
|------|-------------------|------------------------------|
| `derived_chip_factors` | 6 | 4 |
| 运维 CSV `turnover_1d` / `turnover_resist` | 6（= `turnover_ratio`） | 4（= `turnover_resistance`） |
| `filter_chip_stocks` 的 `resist` | 4（`turnover_ratio`） | 1（展示四舍五入） |

对比阻力时优先比 **`turnover_resistance` 列**；勿用旧版 2 位 `turnover_resist` 与 4 位 canonical 直接比。

| 参数 | 默认值 | 位置 | 说明 |
|------|--------|------|------|
| `WINDOW_DAYS` | 80 | `chip_factor_analysis.py` | 筹码分布回测窗口（交易日） |
| `--window`（canonical/full_market） | 1000 | `scripts/full_market_canonical_resist.py` | 全市场 canonical 计算窗口（交易日，约 4 年） |
| TR BB Parquet 路径 | `stock_data/turnover_resistance_daily.parquet` | `oskh_data/turnover_resistance_store.py` | 可由 `TURNOVER_RESIST_BANDS_PATH` 覆盖 |
| TR BB `window`（硬编码） | 1000 | `scripts/compute_turnover_resistance_bands.py` | Canonical TR；与 Legacy TR_80 禁止混表 |
| TR BB `period` | 20 | `backtest/chip_turnover_resistance_bands.py` | 与价格 BB 默认一致 |
| `--free-float-policy`（v1.1） | `warn-zero` | `full_market_canonical_resist.py` + `turnover-resist` (Rust) | 缺自由流通股本时：`warn-zero`=填0继续 / `skip`=跳过 / `fail`=报错。**Python/Rust 一致** |
| `BACKTEST_START` | "2026-03-01" | `chip_factor_analysis.py` | 回测起点 |
| `INITIAL_CASH` | 1,000,000 | `chip_factor_analysis.py` | 初始资金 |
| `COMMISSION` | 0.0005 | `chip_factor_analysis.py` | 手续费 |
| `BB_PERIOD` | 20 | `chip_factor_analysis.py` | 布林带窗口 |
| `BB_STD` | 2.0 | `chip_factor_analysis.py` | 布林带标准差倍数 |
| `step` | 0.01 | `calc_dist_chips` | 价格步长（元） |
| `method` | "triang" | `daily_chip_distribution` | PDF 方法：triang / uniform |
| `A` | 1.0 | `calc_cumpdf` | 换手率衰减系数倍率 |
| `BENCHMARK_CODE` | "000300.SH" | `chip_factor_analysis.py` | 沪深 300 基准 |
| `_FLOAT_SHARES_DEFAULT` | 100 亿 | `chip_algorithm.py` | **仅** `_estimate_turnover(None)` 等窄路径；`adapt_columns` 主路径 fail-close（§4.1.3） |

### 7.2 A 股交易现实口径（已建模 / 未建模）

| 项 | 当前状态 | 说明 |
|----|----------|------|
| 买入时点 | 已建模 | 默认 `t1_buy=False`，信号日下单，下一根 bar open 成交 |
| 卖出 T+1 限制 | 未建模 | 当前回测未显式限制“当日买入仓位不可当日卖出” |
| 手续费 | 已建模 | `COMMISSION=0.0005` |
| 卖出印花税 | 未建模 | 当前策略回测未计入 |
| 过户费 | 未建模 | 当前策略回测未计入 |
| 滑点 | 未建模 | 当前策略回测默认理想成交 |
| 涨停买入限制 | 已建模 | 主板/创业板/科创板已做阈值差异过滤 |
| 跌停卖出可成交性 | 未建模 | 暂未模拟“跌停难成交/不可成交” |

---

