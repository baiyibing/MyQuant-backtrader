# 利用本地 DuckDB 接口取 `pre_close` 等历史价 — 可行性评估

> **日期**：2026-06-04（**2026-06-05 实施同步**）
> **状态**：评估完成；**C.1 + C.2 + B2 已落地** — 实施与验收见综合方案 v19.1
>
> ⚠️ **修正说明（2026-06-04 晚，综合四方意见后）**：本初稿存在以下已知错误，**实施细节以最终综合方案为准**：
>
> | 错误点 | 初稿错误内容 | **正确内容** | 来源 |
> |-------|-------------|------------|------|
> | **复权类型** | `dividend_type=front` | **`adjust_type='none'`** + `stock_data_none.duckdb` | 专家 P |
> | **交易日历** | 未识别（默认走 xtdata 或 DuckDB `time` 推导） | **PMC**（`oskh_core/trading_calendar_xshg_cache.py`，~1μs） | 用户洞察 |
> | **数据入口** | 未区分生产/回测 | 生产用 **`oskh_data/reader.py`**；回测用 `backtest/stock_data_reader.py` | 专家 C |
>
> **权威依据**：[`../operations/csv-live/limit-info-pre-close-final-synthesis.md`](../operations/csv-live/limit-info-pre-close-final-synthesis.md)（**v19.1**，已实施）
>
> 本初稿保留的**有效部分**：
> - §1 本地数据能力盘点（基础设施现状）
> - §2 字段可取性矩阵（`pre_close` 派生方式、涨跌停价派生规则）
> - §3 实测性能数据（DuckDB 加速比）
> - §4 适用场景评估（A/B/D 场景推荐度）
> - §5 与 miniqmt 链路的关系（"补充而非替代"定位）

**关联**：
- **最终综合方案（权威）**：[`../operations/csv-live/limit-info-pre-close-final-synthesis.md`](../operations/csv-live/limit-info-pre-close-final-synthesis.md)
- 数据层方案：[`parquet_duckdb_dual_mode_reader_plan.md`](parquet_duckdb_dual_mode_reader_plan.md)
- 性能基准：[`duckdb_scheme_a_vs_b_benchmark_plan.md`](duckdb_scheme_a_vs_b_benchmark_plan.md)
- 实施计划（含已知错误，见最终综合方案）：[`../operations/csv-live/pre-close-duckdb-preheat-plan.md`](../operations/csv-live/pre-close-duckdb-preheat-plan.md)
- 综合方案（实盘 limit_info 优先级）：[`../operations/csv-live/limit-info-duckdb-pre-close-solution.md`](../operations/csv-live/limit-info-duckdb-pre-close-solution.md)

---

## 0. 评估结论（TL;DR）

| 维度 | 结论 |
|------|------|
| 本地接口能否取 `pre_close` | ✅ 能；DuckDB `LAG(close, 1)` 派生 |
| 能否替代 miniqmt 实时链路 | ❌ 盘中不可替代（新鲜度 T+1） |
| 能否用于盘前预热 / 回测 | ✅ **强烈推荐**（可消除首扫 ~150ms 冷启动） |
| 性能基准是否已测 | ✅ 有实测（见 §3）：单股 357×、全市场截面 3.52× |
| ROI 最高的应用 | **盘前 LIMIT_INFO 预热**（~1 天，消除首扫冷启动） |

---

## 1. 已有本地数据能力

### 1.1 基础设施

| 组件 | 位置 | 说明 |
|------|------|------|
| 统一读取层 | `backtest/stock_data_reader.py` | 三模式：`parquet` / `duckdb`（内存）/ `duckdb_persistent` |
| Benchmark 脚本 | `benchmark/duckdb_benchmark.py` | 已实测 §3 性能数据 |
| 数据源 | `stock_data/period=1d/dividend_type=front/symbol=*/data.parquet` | 5,525 股 × ~12 GB；列 `time/open/high/low/close/volume/amount` |
| 持久化库 | `stock_data.duckdb`（需 `python backtest/stock_data_reader.py --build` 生成） | 索引化单股点查 |

### 1.2 目录与 schema

```
stock_data/
├── period=1d/
│   ├── dividend_type=front/    # 前复权（推荐）
│   ├── dividend_type=back/
│   └── dividend_type=none/
└── period=1m/
    └── dividend_type=none/
```

每文件 schema：

| 列 | 类型 | 说明 |
|----|------|------|
| `time` | int64 ms | UNIX 毫秒时间戳 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | int64 | 成交量 |
| `amount` | float | 成交额 |

> **`pre_close` / `up_limit` / `down_limit` 不是原生列**，需派生（见 §2）。

---

## 2. 字段可取性矩阵

| 字段 | 原生列 | 派生方式 | 派生代价 |
|------|--------|---------|---------|
| `close`（当日收盘） | ✅ | — | 无 |
| `open`（今日开盘） | ✅ | — | 无 |
| **`pre_close`（昨收）** | ❌ | `LAG(close, 1) OVER (PARTITION BY symbol ORDER BY time)` | 极低（DuckDB 原生窗口函数） |
| `up_limit`（涨停价） | ❌ | `ROUND(pre_close × 1.10, 2)`（主板）/ `× 1.20`（科创/创业板）/ `× 1.05`（ST）/ `× 1.30`（北交所） | 中（需板块规则表） |
| `down_limit`（跌停价） | ❌ | 同上，对称 | 中 |
| 除权调整后昨收 | ⚠️ | `dividend_type=front` 已含复权，但需验证与 broker 口径一致 | 中 |

### 2.1 SQL 示例（DuckDB 原生窗口函数）

```sql
SELECT
    symbol,
    time,
    close                       AS close_today,
    open                        AS open_price,
    LAG(close, 1) OVER (
        PARTITION BY symbol
        ORDER BY time
    )                           AS pre_close
FROM read_parquet(
    'stock_data/period=1d/dividend_type=front/*/data.parquet',
    hive_partitioning=1
)
WHERE symbol IN ('000001_SZ', '600519_SH')
  AND time BETWEEN $start_ts AND $end_ts
ORDER BY symbol, time
```

### 2.2 涨跌停价派生规则（待建 lookup）

| 板块 | 涨停 / 跌停幅度 | symbol 识别 |
|------|----------------|------------|
| 主板（沪深） | ±10% | `000xxx` / `001xxx` / `600xxx` / `601xxx` / `603xxx` / `605xxx` |
| 创业板 | ±20% | `300xxx` / `301xxx` |
| 科创板 | ±20% | `688xxx` / `689xxx` |
| ST / *ST | ±5% | 需外部 ST 名单（建议复用 `risk_blacklist` 或盘前公告源） |
| 北交所 | ±30% | `8xxxxx` / `4xxxxx` |
| 新股上市首日 | 特殊规则 | 需 IPO 日期 lookup |

> 派生涨跌停价**可能与 broker 实际口径有小差异**（除权/新股/停牌复牌），实盘前需与 `xtdata.get_instrument_detail` 对照一轮。

---

## 3. 实测性能数据（摘自 `parquet_duckdb_dual_mode_reader_plan.md` §9.2）

| 场景 | parquet 基线 | duckdb_persistent | 加速比 |
|------|-------------|-------------------|--------|
| 全市场 1 天截面 | 1× | 3.52× | **3.52×** |
| 全市场 1 年历史 | 1× | 2.86× | **2.86×** |
| 聚合查询 | 1× | 11.47× | **11.47×** |
| **单股 10 年历史点查**（~2.5K 行） | 5.83s | **0.016s** | **357×** |

**关键推论**：

- **30 股 LIMIT_INFO 预热**：DuckDB 点查 <50ms（vs 当前 Redis 首扫 ~150ms 冷启动，见 [`../operations/csv-live/limit-info-performance-evaluation.md`](../operations/csv-live/limit-info-performance-evaluation.md)（如有）或相关评估）
- **全市场 gap_down 回测**：DuckDB 全市场截面查询 ~3.52× 加速，足够支持历史遍历

---

## 4. 适用场景评估

| 场景 | 可行性 | 性能 | 推荐度 |
|------|--------|------|--------|
| **A. 回测 / 离线 bench 构造 `pre_close`** | ✅ 完全可行 | 单股 0.016s；全市场截面 3.52× | ⭐⭐⭐⭐⭐ |
| **B. 盘前预热 `LIMIT_INFO` 缓存**（消除首扫冷启动） | ✅ **推荐** | 30 股点查 <50ms | ⭐⭐⭐⭐⭐ |
| **C. 盘中实时卖扫替代 xtquant** | ❌ 不可行 | 盘中 `close` 滞后；涨跌停价需实时 broker 状态（封板/开板） | ❌ |
| **D. `gap_down` 策略离线验证**（P4 已落地，缺回测） | ✅ 完全可行 | 历史 `(pre_close, open_price)` 一次性拉取 | ⭐⭐⭐⭐⭐ |
| **E. 涨跌停价离线构造** | ⚠️ 部分可行 | 需板块规则 + ST 名单；复牌/除权日需额外处理 | ⭐⭐⭐ |
| **F. `limit-up-open` 离线效果评估** | ✅ 可行 | 历史 `close_T-1` vs `open_T` 构造「昨日涨停今日开板」样本 | ⭐⭐⭐⭐ |

---

## 5. 与当前 miniqmt 链路的关系

| 维度 | 当前链路（Redis `qmt_ops`） | 本地 DuckDB |
|------|---------------------------|-------------|
| 数据新鲜度 | 实时（盘中 tick） | **T+1**（收盘后更新） |
| 涨跌停价来源 | Executor `xtdata.get_instrument_detail` 直传 `up_limit/down_limit` | 派生（规则 × `pre_close`），**可能偏离实际**（除权/特殊板块） |
| 适用时段 | 盘中 | 盘前 / 盘后 / 回测 |
| 性能瓶颈 | Redis 往返（首轮 ~150ms） | 无（本地磁盘 + SQL） |
| 用途 | 实盘决策 | 预热 / 校验 / 回测 |

**核心结论**：DuckDB 是 **xtquant 的补充，不是替代**。定位：

- **盘前**：用 DuckDB 预热 `LIMIT_INFO` L1 缓存
- **盘中**：仍走 Redis `qmt_ops` → xtquant（但 L1 缓存已命中，免首轮冷启动）
- **盘后**：用 DuckDB 跑 `gap_down` / `limit-up-open` 离线评估

---

## 6. 风险与限制

| 风险 | 严重度 | 应对 |
|------|--------|------|
| **除权日 `pre_close` 口径偏差** | 🟡 中 | `dividend_type=front` 已含复权，但需与 broker `pre_close` 字段做一轮对照（建议写入 `daily_data_backfill_summary.md`） |
| **派生涨跌停价与实际不一致**（ST 名单 / 新股首日 / 停牌复牌） | 🟡 中 | 仅用于预热（非决策）；盘中由 xtquant 真实值覆盖；偏差告警走 `eod_reconcile` |
| **盘前数据未更新**（昨日 parquet 未回灌） | 🟡 中 | 预热前校验 `time` 列最大值 ≥ T-1 交易日；未满足则降级为不预热（走原 Redis 路径） |
| **DuckDB persistent 库未构建** | 🟢 低 | `backtest/stock_data_reader.py --build` 一次性构建；缺库时自动降级为 parquet 模式 |

---

## 7. 建议动作（按 ROI 排序）

### ⭐ 1. 盘前 LIMIT_INFO 预热（强烈推荐，~1 天）

**思路**：`main.py bootstrap` 阶段用 DuckDB 取昨日 `close` → `pre_close`；按板块规则算 `up_limit` / `down_limit`；写入 `decision_tick_cache.L1_LIMIT_INFO`（TTL=300s 覆盖开盘到首次卖扫）。

**收益**：
- 消除首扫 ~150ms 冷启动
- 降低对 Executor 首轮压力
- 无需 Executor 改动

**实施计划**：详见 [`../operations/csv-live/pre-close-duckdb-preheat-plan.md`](../operations/csv-live/pre-close-duckdb-preheat-plan.md)

### ⭐ 2. 离线 `gap_down` 回测验证（强烈推荐）

**思路**：用 DuckDB 构造历史 `(pre_close, open_price)` 对，验证 `_maybe_gap_down_sell` 在历史行情下的触发率 / 误触发 / 收益。

**收益**：P4 `gap_down` 已落地（`trade_decision/presets.py:314-337`），缺离线评估数据。

### ⭐ 3. `limit-up-open` 离线效果评估

**思路**：DuckDB 取 `close_T-1` 触达涨停 + `open_T < close_T-1` 构造"昨日涨停今日开板"样本；对照实际 `INTENT_LIMIT_UP_OPEN_SELL` 触发。

### ⭐ 4. 复用 Benchmark 数据（可选）

`benchmark/duckdb_benchmark.py` 已实测性能；直接复用 `StockDataReader` API，不重复造轮子。

---

## 8. 与 Step 2 / Mock 收官的关系

| 项 | 关系 |
|----|------|
| Step 2（sell-rules binding） | **不冲突**；DuckDB 预热只作用于 L1 缓存写，不进入 `sell_decision_kernel` 决策逻辑 |
| Mock 离线收官 | **不依赖**；Mock 收官 Phase 0–7 不需要 DuckDB 预热（已 Phase 0–4 完成） |
| 实盘前优化项 | ✅ **建议归入实盘前 checklist**（与 fuse 启用并列） |

---

*维护：DuckDB 历史价取数可行性评估；SSOT 索引「DuckDB pre_close 可行性」。*
