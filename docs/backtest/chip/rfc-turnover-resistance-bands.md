# 换手阻力布林带（TR-Bollinger）实现方案 — 评审稿 v9

> 基于仓库既有换手阻力基础设施的增量方案。  
> 状态：可批准实施 · v9 修订（专家 C 二轮评审闭环；四专家评审全部通过）  
> v8→v9 修订依据：[专家 C 二轮评审](#22-修订记录v8v9专家-c-二轮评审)

---

## 1. 背景与目标

### 1.1 用户原始诉求

- 想用**换手阻力**（而非收盘价）计算布林带；
- 把每只股票的每日换手阻力**持久化**，供后续复用、节约计算时间。

### 1.2 与现有能力的关系

仓库已具备完整换手阻力实现，但：

- 当前布林带是基于 `close` 的**价格布林带**；
- 换手阻力仅以**每日截面 CSV** 形式存在（`canonical_resist_batch_{date}.csv`、`chip_daily_{date}.csv`），没有按 `(stock_code, trade_date)` 组织的统一时序表；
- Rust PyO3 FFI 已于 2026-06-07 交付（`oskh_core/turnover_resist_bridge.py`，单次全市场计算 ~27s）。

### 1.3 关键风险前置（v3 新增）

仓库内存在**至少三种不同筹码窗口**的 TR 计算路径，混用会导致 TR 序列不可比：

| 来源 | 默认窗口 | 典型输出 | 语义 |
|---|---|---|---|
| `oskh_core/turnover_resist_bridge.py` (Rust PyO3 FFI) | **1000** 日 | `compute_turnover_resist()` | **Canonical（生产/持久化）** |
| `scripts/full_market_canonical_resist.py` | **1000** 日 | `canonical_resist_batch_{date}.csv` | **Canonical（同 Rust）** |
| `backtest/daily_chip_logger.py` | **80** 日 | `chip_daily_{date}.csv` | **Legacy（回测专用）** |
| `backtest/chip_factor_analysis.py` | **80** 日 (`WINDOW_DAYS`) | 回测因子截面 | **Legacy（已验证选股规则）** |

**代码证据**：`full_market_canonical_resist.py:579` → `default=1000`；`daily_chip_logger.py:53` → `WINDOW_DAYS=80`；`chip_factor_analysis.py:66` → `WINDOW_DAYS=80`。v3 误将 full_market 标为 80 日，v5 已修正。

`turnover_resistance` 对筹码窗口高度敏感（见 `turnover_resistance_algorithm.md` §4.7，80 vs 1000 窗口 cyqk 可差 0.28 量级）。**同一因子名、不同回看窗 → 回测与实盘信号分叉**——这是 A 股量化实践的典型坑。本方案通过：① Schema 的 `window` + `source` + `free_float_policy` 三列审计字段 + **`window` 纳入主键** + 计算前强制校验来保证 TR 布林带不会被不同窗口数据污染。

#### Canonical vs Legacy 窗口声明（v5 新增，写死）

本方案建立后，仓库内存在**两种不同窗口的 TR 因子**。必须在 SSOT 文档中显式声明，避免混用：

| 因子来源 | 窗口 | 语义 | 用途 |
|---------|------|------|------|
| `turnover_resistance_daily.parquet`（本方案） | **1000 日** | **Canonical TR** | 生产持久化 + TR BB + 盘后信号 |
| `chip_factor_analysis.py` / `daily_chip_logger.py` | **80 日** | **Legacy TR** | 回测验证（已有 `resist_bb` 规则基于此） |

**纪律**：
1. 凡引用「换手阻力」必须标注 window（如 `TR_1000` / `TR_80`）；
2. `Store` 查询默认 `window=1000`，调用方需显式 `window=80` 才可读 legacy 数据（如果回填了 80 日数据）；
3. **`|阻力|>20` 阈值在 1000 日窗口下不可直接套用**（`chip_factor_analysis.py:320` 的 `resist_bb` 规则基于 80 日窗口标定）。TR BB 信号（`TR_BREAKOUT` 等）是 1000 日窗口下的**新因子**，需独立回测验证。

**Step 5（chip_factor_analysis 接入）修订**：不修改现有 `resist_bb` 规则默认行为。新增规则名如 `resist_tr_bb_1000`，读 `Store.load_series(window=1000)`。迁移期并行对照两个版本。

**回测接入数据流**（P1-2 闭环）：`chip_factor_analysis.py:328-405` 的回测框架（`multiround_backtest`）逐日遍历 backtrader bars，现场计算 `derived_chip_factors()` → `turnover_resistance`（80 日窗口）+ `bb_position(close)`（价格 BB）。要接入 1000 日 TR BB，最小可行方案：

```python
# backtest/chip_factor_analysis.py 新增
from oskh_data.turnover_resistance_store import TurnoverResistanceStore

def load_tr_bb_from_store(code: str, trade_date: str) -> dict | None:
    """读取预计算的 1000 日 TR BB 字段（无历史时返回 None）。"""
    store = TurnoverResistanceStore()
    df = store.load_series(code, end_date=trade_date, n=1)
    if df.empty or pd.isna(df.iloc[-1]["tr_bb_position"]):
        return None
    row = df.iloc[-1]
    return {
        "tr_bb_position": row["tr_bb_position"],
        "tr_bb_upper": row["tr_bb_upper"],
        "tr_bb_lower": row["tr_bb_lower"],
    }

# 在 multiround_backtest 的因子计算循环中追加：
tr_bb = load_tr_bb_from_store(code, today_str)
if tr_bb:
    factor["tr_bb_position"] = tr_bb["tr_bb_position"]
    # 组合规则：price BB position + TR BB 突破
    factor["resist_tr_bb_1000"] = (
        abs(factor["turnover_resistance"]) > 20
        and factor["bb_position"] >= 0.5
        and tr_bb["tr_bb_position"] > 0.5
    )
```

回测时 Store 内至少需 20 天历史（预热期），不足 20 天返回 None（跳过该信号）。

### 1.4 本方案目标

新增「换手阻力布林带」指标及配套持久化层：

- 每日盘后通过 Rust PyO3 FFI 计算全市场 TR 截面 → 追加到 Parquet 时序表；
- 基于该时序表计算 N 日布林带（代码路径：**Python `pandas rolling` 统一计算**）；
- 写入持久化表，供策略/回测直接查询；
- **Rust 保持现状**：只输出当日 TR 截面；TR BB 不内联到 Rust `engine.rs`（避免架构冲突，见 §4.3）。

---

## 2. 现状基线（已核对 SSOT + 源码）

| 项 | 现状 | 来源 |
|---|---|---|
| 换手阻力公式 | `(cyqk_today - cyqk_yesterday) / turnover_today` | [`turnover_resistance_algorithm.md`](turnover_resistance_algorithm.md) §2.1 |
| Python canonical 入口 | `backtest/chip_algorithm.py:compute_crossday_turnover_resistance` | 源码 L692 |
| Rust 高性能实现 | `turnover-resist/src/engine.rs:process_one_stock` | 源码 L48 |
| **Python PyO3 桥接** | `oskh_core/turnover_resist_bridge.py:compute_turnover_resist()` | 源码 L70（v1.0, 2026-06-07） |
| 当前价格布林带 | `MA(close, 20) ± 2σ` | `turnover-resist/src/bollinger.rs` / `backtest/chip_algorithm.py:bb_position` |
| 当前选股规则 | `\|阻力\|>20 & price_BB_position>=0.5`（两个独立指标组合） | `backtest/chip_factor_analysis.py:318` |
| 每日截面输出 | `canonical_resist_batch_{date}.csv`（18 列，含 TR 双口径 + price BB） | `full_market_canonical_resist.py` |
| 每日 chip 日志 | `chip_daily_{date}.csv`（含 `turnover_resistance` 字段） | `daily_chip_logger.py:224` |
| 统一时序表 | **无** | — |
| `free_float_policy` | `warn-zero`（默认）/ `skip` / `fail`。Rust + Python 行为一致 | v1.1 对齐（2026-06-07） |
| 网格构造 | `make_price_grid`（`min_p + np.arange(n) * step`），与 Rust 逐点一致 | v1.1 修复 |

**窗口差异说明**：`compute_turnover_resist`（Rust FFI）和 `full_market_canonical_resist.py` 默认 `window=1000`；`daily_chip_logger` 和 `chip_factor_analysis` 使用 `WINDOW_DAYS=80`。时序表**禁止混用不同窗口的数据**。

---

## 3. 方案概述

### 3.1 核心思路（v3 重构）

**不重新计算每只股票的历史筹码分布，也不将 TR BB 内联到 Rust。** 改为：

1. 每日 Rust FFI 输出当日 TR 截面（已有能力，27s/日）；
2. Python 将截面累积为时序表；
3. Python `pandas rolling(20)` 统一计算 TR BB；
4. 策略/回测直接读表。

```
每日收盘后                             已有资产
═══════════                            ════════
Rust PyO3 FFI ──→ 全市场 TR 截面       oskh_core/turnover_resist_bridge.py
  (27s/日, 5500 只, 18 列)             compute_turnover_resist(date=T, window=1000)
      │
      ▼
追加到 Parquet ──→ turnover_resistance_daily 表
      │
      ▼
Python pandas ──→ rolling(20).mean/std  → TR BB
      │
      ▼
策略/回测 ←── TurnoverResistanceStore.load_series()
```

**为什么 TR BB 不由 Rust 内联计算**：

- `turnover-resist/src/engine.rs:process_one_stock` 是**单日截面**管线，没有自然的历史 TR 序列来源；
- 若要在 Rust 内联计算 TR BB，需要传入过去 19 日 TR（改造 CLI/PyO3 接口）或滚动重算历史筹码分布（性能回到数小时级）；
- Python `pandas rolling` 对 5500 行 × 60 列的时序表计算 TR BB 为**秒级**，完全满足需求；
- **保持 Rust 侧只做它最擅长的事**（筹码分布 + 单日 TR），不侵入已有架构。

### 3.2 TR 布林带公式

```
middle = MA(tr_series, period)
upper  = middle + nbdev × σ
lower  = middle - nbdev × σ
position = (tr_last - lower) / (upper - lower)
width    = (upper - lower) / |middle|
```

与价格布林带公式完全一致，仅输入序列从 `close` 替换为 `turnover_resistance`。

### 3.3 新增模块（v3 修正归属）

```
oskh_data/                              # 持久化层（数据 I/O，与 oskh_data/reader.py 同类）
  turnover_resistance_store.py        # Parquet 表 + UPSERT + 查询 + rolling TR BB

backtest/
  chip_turnover_resistance_bands.py   # Python: TR 时序缓存 + 策略信号接口

scripts/
  compute_turnover_resistance_bands.py # 盘后全市场批量入口（MVP 版）
  backfill_turnover_resistance_bands.py # 历史回填入口（MVP 版）

turnover-resist/src/
  bollinger.rs                        # [已有] 价格布林带（不改动）
  engine.rs                           # [不改动] Rust 保持现状
```

### 3.4 不改动（避免影响现有生产路径）

- `backtest/chip_algorithm.py` 中的 `compute_crossday_turnover_resistance` 与 `bb_position`
- `oskh_core/turnover_resist_bridge.py` 当前接口（`compute_turnover_resist()` 18 列不变）
- `turnover-resist/src/engine.rs`（Rust 不扩展 TR BB）
- `scripts/full_market_canonical_resist.py` 当前输出格式

**CSV 与 Parquet 表同步声明**（S2）：CSV（`canonical_resist_batch_{date}.csv`）与 Parquet 表同源——均为 Rust FFI `window=1000` 输出，数值应完全一致。Parquet 表为主查询路径，CSV 为可读备份。如两者数值不一致，以 Parquet 表为准，排查 `upsert_daily` 实现或 `pd.read_csv` 类型转换。

---

## 4. 详细设计

### 4.1 数据流（v3 重构）

```
Step 1: 每日 TR 截面计算
─────────────────────────
Rust PyO3 FFI:
  results = compute_turnover_resist(
      date="YYYYMMDD",
      window=1000,              # 硬编码！不依赖任何 CLI/函数签名默认值，防止未来默认值变更导致口径漂移
      free_float_policy="warn-zero"
  )
  # → list[dict] 5500 rows × 18 cols

Python CLI fallback (PyO3 不可用时):
  subprocess: turnover-resist.exe --date YYYYMMDD --window 1000 --free-float-policy warn-zero
  → CSV → pd.read_csv

**FFI → Schema 列名映射**（P0-5 闭环）：

Rust `OutputRow` 通过 serde 重命名输出 JSON；`upsert_daily` 必须在写入前做 normalize。
代码证据：`turnover-resist/src/types.rs:71` → `#[serde(rename = "cyqk_T")]`；
L74 → `cyqk_T_1`；L89 → `freeFloatCapital`。

| FFI/CSV 列名 | Schema 列名 | 类型 | 映射方式 |
|-------------|------------|------|---------|
| `date` | `trade_date` | STR | 直接重命名 |
| `stock_code` / `stock_name` / `close` | 同名 | STR/F64 | 直通 |
| `cyqk_T` | `cyqk_t` | F64 | 重命名（小写 T） |
| `cyqk_T_1` | `cyqk_t_1` | F64 | 重命名（小写 T） |
| `freeFloatCapital` | `free_float_capital` | F64 | 重命名（snake_case） |
| `turnover_resistance` / `turnover_resistance_free` / ... | 同名 | F64 | 直通 |

验收：mock FFI dict 传入 → `upsert_daily` → Parquet 列全覆盖（P2-3 单测）。

Step 2: 追加到 Parquet
─────────────────────────
store = TurnoverResistanceStore()
store.upsert_daily(trade_date="YYYYMMDD", rows=results, window=1000)
# Parquet 不可变写时复制：读全量 → concat 新行 → drop_duplicates(subset=unique_keys) → 重写文件
# 330K 行 × 30 列 ≈ 每次重写 <5s；并发写入由 filelock 守护

Step 3: 计算 TR 布林带（盘后批量）
──────────────────────────────────
对每只股票:
  df = store.load_series(stock_code, end_date="YYYYMMDD", n=60)

  # 口径一致性校验（P0-1 闭环；默认严格模式 → ValueError）
  if df["window"].nunique() != 1:
      raise ValueError(f"窗口口径不一致: {df['window'].unique()}")
  if df["free_float_policy"].nunique() != 1:
      raise ValueError(f"股本政策不一致: {df['free_float_policy'].unique()}")
  if df["source"].nunique() != 1:
      raise ValueError(f"计算来源不一致: {df['source'].unique()}")

  tr_bb = tr_bollinger_bands(df["turnover_resistance"], period=20)
  tr_bb_free = tr_bollinger_bands(df["turnover_resistance_free"], period=20)

Step 4: 写回布林带字段
─────────────────────────
store.update_bands(stock_code, trade_date, tr_bb, tr_bb_free)
# Parquet 不可变：读全量 → 修改目标行 tr_bb_* 列 → 重写文件（~5s）
# 单日全量 5500 股：建议走 update_bands_batch()（§4.2.2 批量路径），一次重写替代 5500 次单股重写
```

**关键设计决策**：TR 布林带计算作为**独立步骤**（Step 3-4），而非嵌入每日 TR 计算（Step 1）。理由：

- TR 布林带需要 20 天历史，新上市股票前 19 天无法计算；
- 布林带参数（period/nbdev）可能需要回测调优，独立计算便于重新生成；
- 历史回填时可以只做 Step 1-2（TR 截面入库），延后 Step 3-4。

### 4.2 Python 实现：TR 布林带计算（v3 修正 min_periods）

```python
# backtest/chip_turnover_resistance_bands.py

import pandas as pd
import numpy as np


def tr_bollinger_bands(
    tr_series: pd.Series,
    period: int = 20,
    nbdev: float = 2.0,
    ddof: int = 1,
) -> dict:
    """Compute turnover-resistance Bollinger Bands.

    Args:
        tr_series: TR values sorted by date ascending (oldest first).
        period: rolling window (default 20, same as price BB).
        nbdev: number of standard deviations (default 2.0).
        ddof: degrees of freedom for std (default 1 = sample std,
              consistent with pandas .std(ddof=1)).

    Returns:
        dict with tr_bb_upper/middle/lower/position/width.
        If insufficient non-NaN data: upper/middle/lower=NaN, position=0.5, width=NaN.
    """
    # 至少需要 period 个有效（非 NaN）值才能计算有意义的 BB
    valid = tr_series.dropna()
    if len(valid) < period:
        return {
            "tr_bb_upper": float("nan"),
            "tr_bb_middle": float("nan"),
            "tr_bb_lower": float("nan"),
            "tr_bb_position": 0.5,
            "tr_bb_width": float("nan"),
        }

    # 使用 pandas rolling 对齐标准金融时序行为
    roll = tr_series.rolling(window=period, min_periods=period)
    ma = roll.mean().iloc[-1]
    std = roll.std(ddof=ddof).iloc[-1]

    upper = ma + nbdev * std
    lower = ma - nbdev * std
    last_tr = tr_series.iloc[-1]

    # 不截断 position——与 Rust bollinger.rs 和 chip_algorithm.py:bb_position 保持一致。
    # TR 超出布林带上/下轨本身就是信号（突破/跌破），截断会丢失信号强度信息。
    # 代码证据: Rust bollinger.rs:55-59 无截断; Python bb_position L840-851 无截断。
    if pd.notna(last_tr) and upper > lower:
        position = (last_tr - lower) / (upper - lower)
    else:
        position = 0.5

    # S1: TR 可以为 0 或接近 0（横盘、停牌），此时 width 会发散为极大值。
    # 用 abs(ma) < 1e-8 守护，输出 NaN 而非 0.0（NaN 对策略侧的意义更明确：该数据点不可信）。
    width = (upper - lower) / abs(ma) if abs(ma) > 1e-8 else float("nan")

    return {
        "tr_bb_upper": round(float(upper), 4) if pd.notna(upper) else float("nan"),
        "tr_bb_middle": round(float(ma), 4) if pd.notna(ma) else float("nan"),
        "tr_bb_lower": round(float(lower), 4) if pd.notna(lower) else float("nan"),
        "tr_bb_position": round(float(position), 4),
        "tr_bb_width": round(float(width), 4) if pd.notna(width) else float("nan"),
    }
```

**min_periods 策略**：`rolling(window=period, min_periods=period)`，即窗口内必须全是有效值（允许 NaN 存在，但参与计算的非 NaN 数必须 ≥ period）。这与停牌/数据缺失场景对齐：如果 20 天内有 3 天停牌（TR=NaN），则滚动结果仍为 NaN，策略侧按中性（position=0.5）处理。

#### TR BB vs 价格 BB 语义差异（P0-6 闭环）

以下差异表为 SSOT 级别的明确定义。TR BB 是自定义因子（对可正可负、无固定量纲的 `turnover_resistance` 做布林带），业内少见，必须在文档写清 interpretability。

| 维度 | 表内价格 BB（Rust bollinger.rs） | TR BB（本方案 Python rolling） | 差异理由 |
|------|-------------------------------|------------------------------|---------|
| **position** | 不截断 [0,1] | **不截断**（v4 已修正，与 Rust 一致） | TR 超出上下轨本身就是信号（突破/跌破） |
| **ddof** | 1（样本标准差） | 1（pandas 默认） | TR BB 与 Rust 一致。**注意**：`chip_algorithm.py:bb_position` 使用 `np.std()` 默认 ddof=0（总体标准差），与表内 `bb_*`（Rust ddof=1）**不是同一指标**。本方案不依赖表内 `bb_*` 做新信号；统一 ddof 属独立 PR |
| **窗口** | 最近 period 根连续 close，无 NaN 概念 | `rolling(min_periods=period)`，允许 NaN 跳过 | TR 序列可能因停牌产生 NaN；价格 close 在 A 股极少缺失 |
| **width 分母** | `mean > 0` 用 middle | `abs(ma) > 1e-8`，否则 NaN | TR 可为 0 或负（`profit_chip_diff / turnover`），价格 close 永远 >0 |
| **经济学解释** | BB 突破 → 价格相对近期波动率极端 | TR BB 突破 → **相对近期 Δcyqk/turnover 极端**（筹码锁定/交换强度的布林带） | TR 无量纲，不可与价格 BB 直接对比 |
| **NaN/停牌** | 无（价格极少缺失） | 缺失日不 forward-fill TR（避免伪造换手）；`rolling` 窗口缩短或 NaN | A 股停牌常见；全市场截面以 Rust 输出为准（跳过股不入库） |

**默认策略信号口径**（D1 闭环）：`turnover_resistance` 主列是**流通股本口径**（与 `chip_factor_analysis` 已有 `resist_bb` 规则一致）。默认信号用 `tr_bb_*`，`tr_bb_free_*` 仅研究/对照，避免策略层 if-else 漂移。

#### Step 3 批量路径（P0-7）

§4.1 Step 3 的「对每只股票 load_series」是逐股循环路径（N+1 查询）。对全市场 5500 只股票，Parquet 读取本身向量化很快（`pd.read_parquet()` → `groupby('stock_code').rolling(20)` 秒级完成），但 N 次函数调用有开销。建议批量路径：

```python
# 批量：一次读取全市场最近 60 天数据 → groupby rolling → 批量写回
df = store.load_recent_cross_section(n_days=60)
bb_results = (
    df.sort_values(["stock_code", "trade_date"])
      .groupby("stock_code")[["turnover_resistance", "turnover_resistance_free"]]
      .rolling(window=20, min_periods=20)
      .agg(["mean", "std"])
      # → compute upper/lower/position/width per stock
)
store.update_bands_batch(bb_results)
```

性能预估：5500 股 × 60 天 ≈ 330K 行，Parquet → DataFrame + groupby rolling → 全量 TR BB < **30s**。与 Rust FFI 的 27s 合计单日全链 <1min。可选也提供单股 `load_series` 作为查询接口，盘后批量用上述路径。

### 4.3 Rust 实现：保持现状（v3 删除 Phase 5）

**v2 方案**：计划 Phase 5 扩展 Rust `engine.rs` 输出 `tr_bb_*` 字段。  
**v3 修正**：**不在 Rust 侧实现 TR BB**。

理由：
1. `process_one_stock` 是单日截面，无历史 TR 序列；
2. 传入历史 TR 需改造 CLI/PyO3 接口，侵入已有稳定管线；
3. Python `rolling` 计算成本已足够低（秒级），无性能瓶颈；
4. **小团队精力应聚焦在"数据正确性"而非"双语言重复实现"**。

Rust 侧唯一可能的未来扩展（非本方案范围）：在 `turnover-resist/src/cli.rs` 中新增一个**批量历史模式**（读入历史 TR 序列文件，输出 TR BB），但此扩展不改动 `engine.rs` 单日管线。

### 4.4 持久化存储（v4：Parquet + 跟随现有 `stock_data/` 目录）

**存储格式：Parquet**（非 DuckDB）。理由：
- 仓库已使用 Parquet 作为标准数据格式（`stock_data/float_shares.parquet`、`free_float_shares.parquet`、日线 `stock_data/period=1d/.../data.parquet`）；
- Rust `turnover-resist` 通过 Polars 读写 Parquet，Parquet 是 optional feature（`duckdb = ["dep:duckdb"]`），默认**不编译**；
- 本方案数据量：~5,500 行/日 × 60 天 ≈ 330K 行，Parquet 文件 ~几 MB。`pd.read_parquet()` 全量加载 + 过滤单只股票 <0.1s，性能完全够用；
- 避免引入新的数据库引擎依赖。

**存储路径**：`stock_data/turnover_resistance_daily.parquet`（跟随现有 `stock_data/stock_data_front.parquet`、`stock_data/stock_data_back.parquet`、`stock_data/*.parquet` 的既有目录约定）。

**Schema**（Parquet 列定义清单）：

| 列名 | 类型 | 说明 |
|------|------|------|
| `stock_code` | STR | 股票代码 |
| `trade_date` | STR | 交易日 YYYYMMDD |
| `stock_name` | STR | 中文简称 |
| `close` | F64 | 收盘价 |
| `cyqk_t` / `cyqk_t_1` | F64 | T/T-1 获利筹码比例 |
| `profit_chip_diff` | F64 | 盈筹变化 |
| `turnover` / `turnover_free` | F64 | 双口径换手率 |
| `turnover_resistance` / `turnover_resistance_free` | F64 | **双口径换手阻力** |
| `circulating_capital` / `free_float_capital` | F64 | 双口径股本（`free_float_capital` 来自 FFI `freeFloatCapital`，经 normalize 重命名为 snake_case） |
| `tr_bb_upper` / `tr_bb_middle` / `tr_bb_lower` | F64 | **TR 布林带上/中/下轨**（Step 3 写入） |
| `tr_bb_position` / `tr_bb_width` | F64 | **TR 布林带位置/宽度**（Step 3 写入） |
| `price_bb_upper` / `price_bb_middle` / `price_bb_lower` | F64 | 价格布林带（保留对照） |
| `price_bb_position` / `price_bb_width` | F64 | 价格布林带位置/宽度 |
| `window` | I64 | **审计**：筹码窗口（固定 1000） |
| `source` | STR | **审计**：`canonical_rust` / `canonical_python` / `chip_daily` |
| `free_float_policy` | STR | **审计**：`warn-zero`（固定） |
| `updated_at` | F64 | `wall_now_s()`（对齐 `common/infra/timekeeping.py`） |

**唯一性约束**（P0-4 闭环）：`(stock_code, trade_date, window)` 只允许一行。`upsert_daily` 在 `window` 不一致时必须 fail-fast（抛 `ValueError`），拒绝静默覆盖。

> 注：以上为 Parquet 列定义清单（非 SQL DDL）。Parquet 无 CREATE TABLE/INDEX 语义，列名和类型在 `pd.DataFrame.to_parquet()` 时由 pandas dtype 自动推导；唯一性由 `upsert_daily` 应用层保证。

**Schema 变更说明（v2→v3）**：

| 变更 | 理由 |
|------|------|
| 基础字段对齐 Rust FFI 18 列 | `compute_turnover_resist()` 已输出全部字段，直接落盘，不取舍 |
| `price_bb_*` 改回 `bb_*` | 与既有代码（Rust/Python/CSV）命名一致，避免调用方困惑 |
| 新增 `cyqk_t_1`、`circulating_capital`、`free_float_capital`、`stock_name` | 补齐 Rust FFI 输出，支持后续口径校验和审计 |
| 新增 `window` 列 | **P0-1 闭环**：TR BB 计算前强制校验 rolling 窗口内的 window/source/free_float_policy 唯一性 |
| 新增 `tr_bb_free_*` 5 列 | **D1 闭环**：双口径都存，与 Rust 双口径输出对齐 |
| `source` + `free_float_policy` + `window` 三列 + 联合索引 | 防止多来源混入后口径漂移；查询时可通过索引快速过滤 |
| 模块归属 `oskh_data/` | **P1-3 闭环**：`oskh_data` 是数据 I/O 层（与 `reader.py` 同类） |

### 4.5 每日流水线（v3 重构）

```
收盘后
  │
  ▼
scripts/compute_turnover_resistance_bands.py --date YYYYMMDD
  │
  ├── Step 1: compute_turnover_resist(
  │           date=YYYYMMDD,
  │           window=1000,              # 固定！与 canonical 对齐
  │           free_float_policy="warn-zero"
  │       )
  │       Rust PyO3 FFI (~27s) 或 CLI fallback
  │
  ├── Step 2: store.upsert_daily(trade_date, rows, window=1000)
  │       UPSERT 到 turnover_resistance_daily
  │
  ├── Step 3: 对每只股票 load_series(n=60)
  │       口径一致性校验（source/window/free_float_policy）
  │       tr_bollinger_bands(period=20, min_periods=20)
  │
  └── Step 4: store.update_bands(stock_code, trade_date, tr_bb, tr_bb_free)
  │       UPDATE tr_bb_* / tr_bb_free_* 字段（仅对当日行）
  │
  ▼
次日策略/回测通过 TurnoverResistanceStore.load_series() 毫秒级读表
```

---

## 5. 接口设计（v3 修正模块路径）

### 5.1 生产查询接口

```python
from oskh_data.turnover_resistance_store import TurnoverResistanceStore

store = TurnoverResistanceStore()

# `n=60` = 最近 60 个**交易日**（trade_date 行），非自然日。缓冲 = period(20) + 40 交易日。
# 若股票连续 skip（缺 bar/股本不足），返回稀疏序列——`rolling` 按行序滚动（与价格 BB 对停牌日处理一致）。
# 读某股票最近 N 日 TR 时序（含布林带）
# 默认严格模式：口径不一致 → 抛 ValueError（宁可不产出，不产出错误数据）
# 可选宽松模式：load_series(strict=False) → log warning + 返回空 DataFrame
df = store.load_series(
    stock_code="000001.SZ",
    end_date="20260606",
    n=60,
)

# 读取指定日期全市场截面（含 TR BB）
df = store.load_cross_section(trade_date="20260606")

# 读取指定日期 TR BB 突破上轨的股票
df = store.load_bb_breakout(trade_date="20260606", band="upper")
```

### 5.2 策略信号示例

```python
latest = df.iloc[-1]  # 最近一个交易日

# 换手阻力突破自身布林上轨 → 筹码锁定强度达到近期极端
if latest["turnover_resistance"] > latest["tr_bb_upper"]:
    signal = "TR_BREAKOUT"

# 换手阻力跌破自身布林下轨 → 筹码交换极度充分
elif latest["turnover_resistance"] < latest["tr_bb_lower"]:
    signal = "TR_BREAKDOWN"

# ── 以下为 TR_1000 的**无参信号**（MVP），不依赖跨窗口阈值 ──
# TR BB 突破/跌破是相对自身布林带的纯统计信号，无需外部阈值标定。
# ⚠️ |TR|>20 是 80 日窗口 Legacy 阈值（chip_factor_analysis.py:320），
#    禁止直接套用于 TR_1000。TR_1000 的组合阈值需独立回测后填入。
```

**MVP 信号范围**：`TR_BREAKOUT` / `TR_BREAKDOWN`（相对 TR 自身 BB 的无参阈值）。组合信号（`|TR|>X & tr_bb_position>Y`）的 X/Y 阈值待 1000 日窗口全市场 TR 分布标定（§8 验收项）后填入，不阻塞 MVP。

**可选增强信号 `TR_SQUEEZE`**（不阻塞 MVP，Phase 4+ 按需实现）：当 `tr_bb_width` 创近期（如 60 日）新低时，表示 TR 波动率压缩，布林带收窄，突破即将到来——这是布林带策略中最经典的信号之一（Bollinger Squeeze）。实现方式：`store.load_series(n=120)` 取 `tr_bb_width` 列，`rolling(60).min()` 判定是否为近期低点。

---

## 6. 性能估算（v3 修正）

| 项目 | v1 估算 | v2 修正 | v3 修正 | 说明 |
|---|---|---|---|---|
| 单日全市场 TR 截面 | Python 30-90 min | Rust PyO3 FFI ~27s（热） | **同 v2** | 基于 [`turnover-resist-bridge-selection.md`](turnover-resist-bridge-selection.md) benchmark |
| 全市场 TR BB 计算 | — | **<1 min** | **同 v2** | pandas `rolling(20).mean/std` 对 5500 行 × 60 列 DataFrame ~秒级 |
| 历史回填（60 交易日） | 数小时 | **~30 min**（60 × 27s Rust） | **~27 min**（Rust FFI 重跑） 或 **直接导入已有 CSV** | v3 建议：若已有 CSV 口径一致（window=1000），直接导入；若 CSV 是 80 窗口，**必须用 Rust 重跑**，禁止混用 |
| 存储增量 | ~5,500 行/日 | 同左 | 同左 | Parquet 700 万行（5 年）~几百 MB |

**v1→v3 核心变化**：不再每只股票重新计算 42 次筹码分布；Rust 保持现状只做单日截面；TR BB 全由 Python `rolling` 计算。

### 6.1 历史回填策略（v3 修正）

- **方案 A（有条件使用）**：仅当已有 `canonical_resist_batch_{date}.csv` 的 `window` 明确为 **1000** 时，可直接 Parquet 导入。若 CSV 来自 `full_market_canonical_resist.py` 默认参数（window=80），**禁止导入**。
- **方案 B（推荐，最保险）**：用 Rust CLI 按日期批量重跑 60 天：`for date in dates; do turnover-resist.exe --date $date --window 1000 ...; done`。60 天 × 27s ≈ 27 分钟，口径 100% 一致。
- **幂等性保障**：使用 `INSERT OR REPLACE`（UPSERT），同一 `(stock_code, trade_date)` 重复跑不产生重复行。每次回填前输出 `已存在 N 行 / 本次覆盖 M 行` 统计。可选 `--skip-existing` 参数跳过已有行（断点续传）。
- **回填窗口**：60 个交易日即可满足 TR BB（20 天）的计算 + 40 天缓冲。不需要回填全量历史。

---

## 7. 风险与待决策事项（v3 更新）

### 7.1 待评审决策（v3 更新）

| # | 问题 | v1 推荐 | v2 推荐 | v3 推荐 | 变更理由 |
|---|---|---|---|---|---|
| D1 | 布林带基于哪个口径？ | A 为主，C 兼容 | C（两者都存） | **C（两者都存）** | 不变。Schema 已补齐 `tr_bb_free_*` 5 列 |
| D2 | 布林带周期？ | 20 日 | 20 日 | **20 日** | 不变。与价格 BB 一致，`period` 参数可配 |
| D3 | 标准差 ddof？ | 1 | 1 | **1** | 不变。pandas `.std()` 默认 ddof=1，Rust `bollinger.rs` 默认 ddof=1，三者一致 |
| D4 | 存储位置？ | `stock_data/` | `data/` | **`stock_data/turnover_resistance_daily.parquet`** | 跟随既有 `stock_data/` 目录（与 `stock_data_front.duckdb` 等同级） |
| D5 | Rust 是否同步实现 TR BB？ | Python 先，Phase 2 移植 | Python + Rust 双实现同时进行 | **Python 单路径；Rust 不扩展** | v3 修正：Rust `engine.rs` 单日截面无历史 TR 来源，内联实现不可行。删除 Phase 5 |
| D6 | 是否保留价格布林带？ | 保留 | 保留 | **保留** | 不变。兼容现有策略 + 对照 |

### 7.2 技术风险（v3 更新）

1. **历史回填口径一致性（P0-1 已闭环）**：Schema 新增 `window` + `source` + `free_float_policy` 三列 + `idx_tr_source_window` 联合索引。`load_series()` 计算 TR BB 前强制校验 rolling 窗口内（period=20 行）的 `window`/`source`/`free_float_policy` 三列唯一性，不一致则抛 `ValueError`（严格模式）。
2. **NaN/停牌处理（P2-1 已闭环）**：`rolling(window=20, min_periods=20)`，不足 20 个有效值时返回 NaN + position=0.5。策略侧按中性处理。
3. **模块归属（P1-3 已闭环）**：`TurnoverResistanceStore` 归属 `oskh_data/`（Parquet 读写属数据 I/O 层，与 `oskh_data/reader.py` 同类）。
4. **与现有 CSV 输出的关系**：新增 Parquet 表后，`canonical_resist_batch_{date}.csv` 保留作为可读备份。CSV 无 `window` 列时**不得作为回填源**（与 P0-1 修正联动）。
5. **Parquet 路径与环境变量**（P1-2）：路径 `stock_data/turnover_resistance_daily.parquet` 可由 env `TURNOVER_RESIST_BANDS_PATH` 覆盖（对齐 `TURNOVER_RESIST_DATA_DIR` / `oskh_data` base_dir 模式）。Parquet 是派生数据，可随时从 Rust FFI 重算（源真相是 Rust + parquet），runbook 注明「重建命令」。
6. **流水线事务边界**（P1-3）：Step 1-2（TR 截面入库）与 Step 3-4（TR BB 更新）之间可能中断，模拟阶段可接受。但 `load_series()` 查询接口应规定：`tr_bb_middle IS NULL` 时策略**跳过该信号**（不打中性/假值）。**MVP Schema 必含 `bands_computed_at` 列**（`wall_now_s()`，NULL 表示 Step 3-4 未完成）。`load_cross_section` / 策略侧：`bands_computed_at IS NULL` → **不产生 TR BB 信号**（skip，非 position=0.5 假中性——0.5 会被误当成「中轨附近可交易」）。
7. **补算/断点续传**（P2-1）：若 Step 3 中途崩溃，次日运行 `compute_turnover_resistance_bands.py` 时 Step 1 发现当日 TR 截面已存在，可能跳过全流程。应支持 `--backfill-bands-only` 模式：跳过 Step 1-2，只扫描当日 `tr_bb_middle IS NULL` 的股票，补算 Step 3-4。

---

## 8. 验收标准（v5 更新：专家 C P2-3 补充）

- [ ] `oskh_data/turnover_resistance_store.py`：upsert 单日截面（`(stock_code, trade_date, window)` 唯一性保证）、`load_series()` 返回时序 DataFrame；
- [ ] `oskh_data/turnover_resistance_store.py`：口径校验（`window`/`source`/`free_float_policy` 三列一致），不一致抛 `ValueError`（严格模式）；
- [ ] `backtest/chip_turnover_resistance_bands.py`：`tr_bollinger_bands()` 与手工 `rolling(20).mean/std` 计算结果一致（单测：正常序列、NaN 序列、不足 20 天序列）；
- [ ] **FFI dict → Schema 列映射单测**（P0-5）：mock FFI 返回的 JSON dict 经 `upsert_daily` 后 Schema 24 列全覆盖，无空列；
- [ ] **window=80 与 window=1000 同日冲突测试**（P0-4）：`upsert_daily` 在 window 不一致时抛 `ValueError`，拒绝静默覆盖；
- [ ] **TR BB 与手工 groupby rolling 全市场抽样对齐**（P2-3）：≥10 股 × 20 日；
- [ ] **`load_series` 口径不一致返回 `ValueError` 单测**（严格模式）；
- [ ] `scripts/compute_turnover_resistance_bands.py`：单日全市场跑通（Rust PyO3 FFI → Parquet → TR BB），写入 `stock_data/turnover_resistance_daily.parquet`；
- [ ] `scripts/backfill_turnover_resistance_bands.py`：历史回填 60 交易日，幂等（`--skip-existing`），口径一致（`window=1000`）；
- [ ] 策略/回测能通过 `TurnoverResistanceStore.load_series()` 毫秒级读取历史 TR 时序；
- [ ] SSOT 文档更新：`docs/backtest/chip/turnover_resistance.md` 索引页新增 TR-Bollinger 子页面 + Canonical vs Legacy 窗口声明（P0-3）；**去掉 `daily_chip_logger` 的 canonical 称谓，改为 Legacy TR_80**；
- [ ] `.gitignore` 确认覆盖 `stock_data/turnover_resistance_daily.parquet`（派生数据不入库）；
- [ ] contract gates：模块在 `oskh_data/` → 至少跑定向 pytest + `verify_repo_python_syntax.py`；若触达 `oskh_core/turnover_resist_bridge.py` 映射，加 `tests/test_turnover_resist_bridge.py`。**不必默认跑全量 `run_common_package_contract_gates.py`**（该门禁主要覆盖 common/oskh_db/oskh_core 变更）；
- [ ] **1000 窗口 TR 分布标定**（P2-2）：回填 60 天后，输出全市场 `turnover_resistance` 分布统计（P50/P90/P95/P99/|TR|>20 覆盖度）。`|阻力|>20` 阈值基于 80 日窗口标定（`chip_factor_analysis.py:320`），在 1000 日窗口下不可直接套用——需评估覆盖度后决定是否调整阈值。**不是阻塞项，但必须在首次实盘使用前完成**。

---

## 9. 实施计划（v3：双选项供决策）

### 选项 A：激进 MVP 版（推荐，符合"未上线+小团队"约束）

> 一天内交付可用版本。不改 Rust、不改既有策略、只新增 Python 模块。

| 阶段 | 工作项 | 预计工时 |
|---|---|---|
| Step 1 | `oskh_data/turnover_resistance_store.py` — Parquet schema + UPSERT + 查询 + 口径校验 | 0.5 d |
| Step 2 | `backtest/chip_turnover_resistance_bands.py` — TR BB `rolling` 计算 + 单测 | 0.25 d |
| Step 3 | `scripts/backfill_turnover_resistance_bands.py` — 批量跑 60 天 Rust FFI → 入库 → 算 TR BB | 0.25 d |
| Step 4 | `scripts/compute_turnover_resistance_bands.py` — 每日增量入口 | 0.25 d |
| Step 5 | （Phase 2：独立 PR）`backtest/chip_factor_analysis.py` 接入 `resist_tr_bb_1000` 规则 + IC/多轮回测 | 0.5 d |
| Step 6 | SSOT 文档更新 + contract gates | 0.25 d |
| **合计** | | **~1.75 d** |

**MVP 交付物**：
- 60 天历史 TR 时序 + TR BB 已入库；
- 每日增量流水线可跑通；
- 策略可读取 `tr_bb_position` 做信号增强；
- Rust 零改动，既有代码零侵入。

### 选项 B：分阶段版（保守，v2 遗产）

若评审人要求保留 Rust 扩展可能性，可按 v2 原 Phase 1-4 实施（Python 部分），Phase 5（Rust 扩展）无限期冻结。工时约 2d，但交付价值与 MVP 相同。

---

## 10. 关键设计理由（v3 更新）

### 为什么用"每日截面累积"而非"每只股票滚动重算"

1. **性能**：Rust PyO3 FFI 计算全市场 TR 截面 ~27s；每只股票重算 42 次筹码分布 ~数小时。差距 ~20-50×。
2. **复用已有资产**：`compute_turnover_resist` 已输出全部 18 列；口径统一（`window=1000`）。
3. **数据一致性**：同日所有股票使用同一次计算（同一股本数据源、同一参数）。
4. **增量更新友好**：每天只跑当日截面 → 追加一行。

### 为什么 TR BB 只由 Python 计算

1. **Rust 单日截面架构限制**：`process_one_stock` 无历史 TR 序列来源，内联实现需改造 CLI/PyO3 接口或滚动重算历史筹码分布（不可行）。
2. **Python 计算成本足够低**：5500 只股票 × 60 天时序，`rolling(20)` 秒级完成。
3. **小团队精力分配**：聚焦"数据正确性"（口径一致性、NaN 处理、审计字段），而非"双语言重复实现"。

### 为什么 Schema 必须对齐 Rust FFI 18 列

1. **不丢数据**：Rust 已算好的字段（`bb_*`、`cyqk_t_1`、`circulating_capital` 等）直接落盘，零成本；
2. **命名一致**：`bb_*` 与既有代码（Rust/Python/CSV）命名一致，避免调用方困惑；
3. **审计完整**：`cyqk_t_1` 支持后续手工核对当日 TR 计算；`circulating_capital` 支持追溯股本口径。

### 为什么 `window=1000` 固定

1. `compute_turnover_resist`（Rust FFI）默认 `window=1000`，与 canonical 定义一致；
2. `turnover_resistance_algorithm.md` §4.7 明确指出：1000 日衰减模型与市面常见 120 日等权模型差距巨大（cyqk 差 0.28）。若混入 80 窗口数据，TR BB 完全失真；
3. 若未来需要 80 窗口 TR BB，应建独立表（`turnover_resistance_daily_window80`），而非混用同表。

---

## 11. 评审人关注清单（v3 更新）

请评审人重点确认：

1. **P0-1 口径一致性闭环**（`window` + `source` + `free_float_policy` 三列 + 强制校验）是否充分；
2. **D5 修正**（Rust 不扩展 TR BB，Python 单路径）是否可接受；
3. **Schema 对齐 Rust FFI 18 列**是否过度冗余，或有遗漏字段；
4. **模块归属 `oskh_data/`** 是否符合仓库模块职责划分；
5. **实施选项 A（激进 MVP，~1.75d）** vs 选项 B（分阶段，~2d）的倾向；
6. `stock_data/turnover_resistance_daily.parquet` 路径是否符合仓库数据治理规范。

---

## 12. 参考文件链接

| 文件 | 用途 |
|------|------|
| [`turnover_resistance.md`](turnover_resistance.md) | 换手阻力 SSOT 索引页 |
| [`turnover_resistance_algorithm.md`](turnover_resistance_algorithm.md) | 算法完整文档（公式链、窗口差异分析 §4.7） |
| [`turnover_resistance_runbook.md`](turnover_resistance_runbook.md) | 运行手册（参数速查） |
| [`turnover-resist-bridge-selection.md`](turnover-resist-bridge-selection.md) | PyO3 vs CLI 桥接选型 benchmark |
| [`Rust-Python换手阻力精度差异—权威根因分析报告.md`](Rust-Python换手阻力精度差异—权威根因分析报告.md) | `np.arange` 网格修复根因 |
| [`../../oskh_core/turnover_resist_bridge.py`](../../oskh_core/turnover_resist_bridge.py) | PyO3 FFI 桥接（v1.0） |
| [`../../../turnover-resist/src/engine.rs`](../../../turnover-resist/src/engine.rs) | Rust 核心计算引擎 |
| [`../../../turnover-resist/src/bollinger.rs`](../../../turnover-resist/src/bollinger.rs) | Rust 价格布林带 |
| [`../../backtest/chip_factor_analysis.py`](../../backtest/chip_factor_analysis.py) | 选股规则 RULES |
| [`../../backtest/daily_chip_logger.py`](../../backtest/daily_chip_logger.py) | 每日截面 CSV 输出（WINDOW_DAYS=80） |
| [`../../../scripts/full_market_canonical_resist.py`](../../../scripts/full_market_canonical_resist.py) | Python canonical 全市场入口（默认 window=1000） |

---

## 13. 关键修订理由汇总（v2→v3）

| 评审意见 | v3 修订动作 | 理由 |
|---|---|---|
| P0-1：窗口口径不一致风险 | Schema 新增 `window` + `source` + `free_float_policy` 三列 + 联合索引；`load_series()` 强制校验 | 防止不同来源 CSV（80 日 vs 1000 日）混用导致 TR BB 失真 |
| P1-1：Schema 与 Rust FFI 不对齐 | 基础字段补齐 18 列；`price_bb_*` 改回 `bb_*` | 与既有代码命名一致，不丢已有计算结果 |
| P1-2：Rust 内联 TR BB 不可行 | **删除 Phase 5**；明确 TR BB 仅由 Python `rolling` 计算 | `process_one_stock` 是单日截面，无历史 TR 来源 |
| P1-3：模块归属错误 | `oskh_data/` → **`oskh_db/`** | AGENTS.md 约定 `oskh_db` 为持久化层 |
| P2-1：NaN 处理未细化 | `rolling` 显式设置 `min_periods=period` | 与停牌/数据缺失场景对齐 |
| P2-2：D1 与 Schema 不一致 | Schema 新增 `tr_bb_free_*` 5 列 | 双口径都存，与 Rust 双口径输出对齐 |
| 激进一次到位 | 给出**选项 A（MVP，~1.75d）**和选项 B（分阶段） | 未上线+小团队，优先最小可用路径 |

---

## 14. 修订记录（v4→v5：专家 C 评审）

| 意见 | 核验 | v5 修订 | 依据 |
|------|------|---------|------|
| **P0-1** full_market 默认窗口 | ✅ 确认：源码 L579 `default=1000` | 修正 §1.3 表格（80→1000）；重写 §6.1 CSV 导入条件 | `full_market_canonical_resist.py:579` |
| **P0-2** "21 日"术语不自洽 | ✅ 确认 | 全文替换为 `period=20 + 缓冲` | — |
| **P0-3** 1000 vs 80 语义冲突 | ✅ 确认：`chip_factor_analysis.py:66` `WINDOW_DAYS=80` | 新增 §「Canonical vs Legacy 窗口声明」（写死）；Step 5 改为新规则分支 `resist_tr_bb_1000` | `chip_factor_analysis.py:66`；`turnover_resistance_algorithm.md` §4.7 |
| **P0-4** PK 不含 window | ✅ 确认 | `(stock_code, trade_date, window)` 唯一性约束；`upsert_daily` window 不一致时 fail-fast | — |
| **P0-5** FFI 列名映射未定义 | ✅ 确认：`types.rs:71` `cyqk_T`；L89 `freeFloatCapital` | 新增 §4.1 FFI→Schema 列名映射表（6 列）；验收新增 mock FFI dict 单测 | `turnover-resist/src/types.rs:71,74,89` |
| **P0-6** TR BB vs 价格 BB 语义差异 | ✅ 确认（v4 已修正 position，仍有 width/ddof/NaN/econ 差异） | 新增 §4.2.1 语义差异表（6 维度：position/ddof/window/width/econ/NaN） | `bollinger.rs:55-59`；`chip_algorithm.py:840-851` |
| **P0-7** 逐股循环 vs 秒级 | ✅ 确认 | 新增 §4.2.2 批量路径（groupby rolling 全量 <30s） | — |
| **P1-1** 模块归属 | 已在 v4 修正为 `oskh_data/` | 无需变更 | — |
| **P1-2** 路径 env override | 合理 | 新增 `TURNOVER_RESIST_BANDS_PATH` env + 备份/重建 runbook 一句 | — |
| **P1-3** 事务边界 | 合理 | §7.2 新增：`tr_bb_middle IS NULL` → 策略跳过；可选 `bands_computed_at` 列 | — |
| **P2-1** 默认口径 | 合理 | §4.2.1 新增：默认 `tr_bb_*`（流通股本口径），`tr_bb_free_*` 仅对照 | — |
| **P2-3** 验收补充 | 合理 | §8 新增 4 项单测（FFI mapping、window 冲突、抽样对齐、严格模式） | — |

## 16. 修订记录（v5→v6：内部矛盾修正）

全文一致性扫描，修正 v5 遗留的 5 处多版本描述未同步问题 + 2 项实施建议：

| 项 | 问题 | 修正 |
|----|------|------|
| C1 | §1.2 L82 称 full_market 默认 80 日，与 §1.3（1000 日）矛盾 | 改为：full_market 和 Rust FFI 默认 1000 日；daily_chip_logger 和 chip_factor_analysis 使用 80 日 |
| C2 | 模块路径 `oskh_db`/`oskh_data` 全文不一致（6 处） | 全局统一为 `oskh_data/`（Parquet 读写属数据 I/O 层） |
| C3 | D4/§11 路径仍写 `data/turnover_resistance.parquet`，与 §4.4 `stock_data/...` 矛盾 | 全部统一为 `stock_data/turnover_resistance_daily.parquet` |
| C4 | §12 L669 full_market 标注为 window=80，与 P0-1 修正矛盾 | 改为 window=1000 |
| C5 | §4.4 同时存在 Parquet 列定义表和 SQL DDL（v3 遗留） | 删除 SQL DDL，保留列定义表 + 唯一性约束文字说明 |
| S1 | `freeFloatCapital` 列名映射不明确 | Schema 列名统一 `free_float_capital`，标注来自 FFI `freeFloatCapital` normalize |
| S2 | CSV/Parquet 同步责任未声明 | 新增 §3.4 声明：同源（Rust FFI window=1000），Parquet 为主，CSV 为备份 |

## 18. 修订记录（v6→v7：专家 K 评审）

| 意见 | 核验 | v7 修订 |
|------|------|---------|
| **P0-1** 文档内部矛盾 | ✅ 确认。已在 v6 修正 C1-C5。专家 K 与 v6 评审结论一致 | 无新增修改 |
| **P1-1** Parquet UPSERT/UPDATE 语义冲突 | ✅ 确认。Parquet 不可变写时复制，与 SQL UPSERT/UPDATE 语义不同 | §4.1 Step 2/4 注释明确写清 Parquet 实际行为（read→merge→dedup→rewrite，~5s）；建议走 `update_bands_batch()` 批量重写 |
| **P1-2** chip_factor_analysis 回测接入路径 | ✅ 确认。v5 只有一句话"Step 5 接入"，未给出数据流 | 新增 `load_tr_bb_from_store()` 辅助函数 + 组合规则 `resist_tr_bb_1000` 伪代码；不足 20 天历史返回 None 跳过 |
| **P1-3** §4.2.2 批量路径伪代码 | ✅ 确认。`groupby().rolling().agg()` 返回 MultiIndex，后续计算需 pivot/merge | 维持示意性代码（评审稿级别够用）；实施时补充完整实现 |
| **P2-1** --backfill-bands-only 补算模式 | ✅ 合理 | §7.2 新增 #7：`--backfill-bands-only` 模式跳过 Step 1-2，只补算 tr_bb_middle IS NULL 的股票 |
| **P2-2** 1000 窗口 |TR|>20 阈值未标定 | ✅ 合理（`chip_factor_analysis.py:320` 基于 80 日窗口） | §8 新增验收项：回填后输出全市场 TR 分布统计（P50/P90/P95/P99 + 覆盖度）；首次实盘前必须完成阈值标定 |
| **P2-3** window=1000 硬编码 | ✅ 合理 | §4.1 Step 1 注释改为"硬编码！不依赖任何默认值" |

## 20. 修订记录（v7→v8：专家 P 二轮评审）

| 上轮编号 | v7→v8 状态 | 核验 |
|---------|-----------|------|
| C1-C3（v3 阻塞项） | ✅ 保持闭环 | v6/v7 未引入回归 |
| S1-S5（v3 建议项） | ✅ 保持闭环 | — |
| **M1** 窗口描述矛盾 | ✅ 已在 v6 C1 修正 | §2 L82 已改 |
| **M2** 模块归属矛盾 | ✅ 已在 v6 C2 修正 | 全文统一 `oskh_data/` |
| **M3** 路径矛盾 | ✅ 已在 v6 C3 修正 | 全文统一 `stock_data/` |
| **M4** SQL DDL 遗留 | ✅ 已在 v6 C5 修正 | Parquet 列定义表 + 约束说明 |
| **M5** 列名矛盾 | ✅ 已在 v6 S1 修正 | 统一 `free_float_capital` |
| **I1** 阈值注释 | v8 新增 | §5.2 阈值行加注释标注 80 日窗口标定来源 |
| **I2** bands_computed_at | 已在 v7 §7.2 记载为可选列 | 不阻塞 MVP |

## 22. 修订记录（v8→v9：专家 C 二轮评审）

| 意见 | 核验 | v9 修订 |
|------|------|---------|
| **M1-M5**（文档自相矛盾） | ✅ 已在 v6 修正 | 无新增修改 |
| **P2-1** ddof 误称为「三者一致」 | ✅ 确认：`chip_algorithm.py:bb_position` 使用 `np.std()` 默认 ddof=0，与 Rust ddof=1 **不一致** | §4.2.1 差异表修正：ddof 行改为「TR BB 与 Rust 一致；chip_algorithm ddof=0 是另一指标」 |
| **P2-2** n=60 未定义交易日/自然日 | ✅ 合理 | §5.1 新增注释：n=60 = 最近 60 个 trade_date 行（交易日），非自然日 |
| **P2-3** 稀疏序列（skip 股） | ✅ 合理 | §5.1 新增：若股票连续 skip，返回稀疏序列——`rolling` 按行序滚动 |
| **P2-4** bands_computed_at 应 MVP 必需 | ✅ 合理 | §7.2 升级为 MVP Schema 必含列；NULL → skip 信号（非 position=0.5） |
| **P2-5** SSOT turnover_resistance.md 仍称 daily_chip_logger "canonical" | ✅ 合理 | §8 验收项新增「去掉 daily_chip_logger 的 canonical 称谓，改为 Legacy TR_80」 |
| **P3-2** Step 5 范围收紧 | ✅ 合理 | §9 Step 5 从 MVP 降为 Phase 2（独立 PR）；MVP 仅交付 Store + 脚本 + 单测 + SSOT |
| **P3-5** contract gates 范围 | ✅ 合理 | §8 改为定向 pytest + 语法门禁，不跑全量 contract gates |
| **§5.2** |TR|>20 与 §1.3 冲突 | ✅ 确认（会亏大钱类错误） | §5.2 删除 TR_ABOVE_MID_STRONG 示例；MVP 信号仅 TR_BREAKOUT/TR_BREAKDOWN |

## 23. 修订记录（历史版本）

| 版本 | 日期 | 修订内容 |
|------|------|---------|
| v1 | 2026-06-07 | 初始评审稿 |
| v2 | 2026-06-07 | P0-1: 路径重构（Python 42 次筹码分布 → Rust PyO3 FFI 每日截面累积）<br>P0-2: 性能估算修正（27s vs 数小时）<br>P1-1: `free_float_policy` 显式声明 + Schema 审计列<br>P1-2: ddof 事实错误修正<br>P1-3: 存储位置 `stock_data/` → `data/`<br>P2-1~4: 历史回填策略、CSV 关系、口径选择理由<br>新增: Python + Rust 双实现设计、关键设计理由、参考文件链接<br>工时: 5d → 2.5d |
| v3 | 2026-06-07 | **P0-1 闭环**: 新增 `window` 列 + 口径一致性强制校验<br>**P1-1 闭环**: Schema 对齐 Rust FFI 18 列；`price_bb_*` → `bb_*`<br>**P1-2 闭环**: 删除 Phase 5 Rust 扩展；明确 Python 单路径<br>**P1-3 闭环**: 模块归属 `oskh_data/` → `oskh_db/`<br>**P2-1 闭环**: `rolling(min_periods=period)` 显式声明<br>**P2-2 闭环**: 新增 `tr_bb_free_*` 5 列<br>新增: 激进 MVP 选项 A（~1.75d）vs 分阶段选项 B<br>新增: §13 关键修订理由汇总表 |

---

*文档创建时间：2026-06-07 · v3 修订：同日*  
*待评审人批复后更新为"已批准"状态并进入实施阶段。*
