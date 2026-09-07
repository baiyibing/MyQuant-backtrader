# 本地 DuckDB/Parquet 替代 miniQMT 获取 pre_close 可行性分析

**文档编号**: FEASIBILITY-20260604-001
**日期**: 2026-06-04（**2026-06-05 实施状态同步**）
**状态**: ✅ 分析完成 — **降级路径已按综合方案落地**（见下方「实施后现状」）
**权威 SSOT（设计 + 验收）**: [`docs/operations/csv-live/limit-info-pre-close-final-synthesis.md`](../../operations/csv-live/limit-info-pre-close-final-synthesis.md)（v19.1）、[`limit-info-pmc-prev-trade-date-optimization.md`](../../operations/csv-live/limit-info-pmc-prev-trade-date-optimization.md)（v9.1）
**关联**: `hkcodex_miniqmt.py` → `get_limit_info()` | `oskh_data/reader.py` | `docs/backtest/data/parquet_duckdb_dual_mode_reader_plan.md`

> ⚠️ **历史文档说明**：本文撰写于实施前，§1.2 / §4.1 / 附录中的「走 xtdata」描述为**改前基线**。当前代码已替换为 PMC 日历 + DuckDB `adjust_type='none'`（含 xtdata fallback）。阅读实施细节请以 SSOT 为准；本文保留的数据能力盘点与性能估算仍有效。

### 实施后现状（2026-06-05）

| 函数 | 改前 | **现已实施** |
|------|------|-------------|
| `_get_prev_trade_date()` | `xtdata.get_trade_days()` | **`get_prev_trade_date_or_none`** → PMC（Layer 1.5 XSHG，~1μs）；失败 fallback xtdata |
| `_get_prev_close_dict()` | QMT K 线 | **`LIMIT_INFO_PREV_CLOSE_SOURCE=duckdb`** 时 DuckDB `scan_stocks`（`none`）；ST/新股/复牌走 QMT |
| 开关 | — | `OSKH_TRADE_CALENDAR_XSHG_CACHE` + `LIMIT_INFO_PREV_CLOSE_SOURCE`（见 `runtime.csv.prod.yaml`） |

---

## 1. 背景

### 1.1 涨停/跌停数据获取现状

系统中有两套涨停/跌停实现：

| 模块 | 用途 | 位置 |
|------|------|------|
| `backtest/LimitUpDownManager.py` | 回测 | 纯 Python 计算，基于代码前缀推断涨跌幅比例 |
| `hkcodex_miniqmt.py` → `get_limit_info()` | 实盘/仿真 | 通过 miniQMT 的 `xtdata.get_full_tick()` 获取交易所原生涨跌停价 |

### 1.2 实盘 `get_limit_info` 核心流程（约 320 行）

#### 主路径（tick 含 `upLimit`/`downLimit`）

```
1. 传入 stock_list + trading_date
2. xtdata.get_full_tick(stock_list)  ← 核心 I/O，一次批量取 tick
3. 从 tick 中提取:
   - upLimit（涨停价）、downLimit（跌停价）← 交易所直接计算好的
   - lastPrice（最新价）
   - stockStatus（交易状态）
4. 判断：|lastPrice - upLimit| < PRICE_TOL → 涨停
5. 返回 dict：{stock: {up_limit, down_limit, is_limit_up, is_limit_down, can_buy, can_sell, ...}}
```

#### 降级路径（tick 缺 `upLimit`/`downLimit`，如 miniQMT 标准版）

> **改前基线（2026-06-04 分析时）** — 下述 xtdata 双调用已在 2026-06-05 实施中替换；见文首「实施后现状」。

```
1. _get_prev_trade_date() → 取前一交易日 ← [改前] xtdata；[现已] PMC + fallback
2. _get_prev_close_dict() → 批量取前收 ← [改前] xtdata K 线；[现已] DuckDB none + fallback
3. _get_limit_pct(stock) → 按代码前缀推算涨跌幅比例：
   - 300/301 → 20%（创业板）
   - 688 → 20%（科创板）
   - 4/8开头 → 30%（北交所）
   - 00/60 → 10%（主板）
4. 计算：up_limit = round(anchor * (1 + pct), 2)
5. 标记 is_estimated=True，上层据此降级处理
```

### 1.3 调用方

- **`executor_stream/execute_signal_timed_stages.py`**：执行信号时获取涨跌停，有 L1 缓存
- **`executor_stream/qmt_sync_ops.py`**：处理 Redis `LIMIT_INFO` 操作，走批量调用
- **`executor_stream/stream_executor.py`**：路由 `OP_LIMIT_INFO` 操作

---

## 2. 性能瓶颈评估

### 2.1 已有的优化（做得不错的部分）

1. ✅ `get_full_tick` 是批量调用，不是逐个股票请求
2. ✅ Executor 侧有 L1 缓存，同一信号不会重复调 miniQMT
3. ✅ 全市场路径（`stock_list=None`）已用环境变量门闸保护
4. ✅ `xtdata` 调用走专用 Worker 线程 + RLock 保护，有 Prometheus 直方图监控
5. ✅ 全流程 PerfTimer 分阶段埋点，可观测性好

### 2.2 潜在瓶颈（按严重程度排序）

| # | 瓶颈 | 严重程度 | 说明 |
|---|------|---------|------|
| **1** | `get_full_tick` I/O 延迟 | **中** | miniQMT C++ SDK 内部实现决定，Python 层无法优化。对 50~200 只股票批量取 tick，实测通常 200ms~1s |
| **2** | 降级路径的双重 xtdata 调用 | **中** | `estimate_missing=True` 时额外调用 `_get_prev_trade_date` + `_get_prev_close_dict`，在标准版 miniQMT 上会命中 |
| **3** | `_resolve_stock_status_policy()` 每次调用都解析配置 | **低** | 每次调用都读 ENV + split 字符串 + set 构造，但开销极小（~μs 级） |
| **4** | 每 stock 的 dict 构造含重复的 `sorted()` 列表 | **低** | `tradeable_status_values`/`uncertain_status_values` 对所有股票相同，但每只股票都 `sorted()` 一次 |
| **5** | `_extract_limit_row_gap_fields` 每股多次 try/except | **极低** | 防御性编码风格，性能影响可忽略 |

### 2.3 降级路径详情

当 tick 缺 `upLimit`/`downLimit`（如 miniQMT 标准版），`get_limit_info` 走以下路径：

```
_get_prev_trade_date(trading_date)     ← xtdata 调用 1: 获取前一个交易日 (~100-200ms)
_get_prev_close_dict(missing, prev_date) ← xtdata 调用 2: 批量取前收 (~200ms-1s)
  └─ _get_market_data_compat(stock_list, '1d', date, date, ['close'])
     └─ xtdata.get_market_data()      ← 网络 I/O 到 QMT 服务器
```

**两条 xtdata 调用合计 ~300ms-1.2s**（取决于股票数量和 QMT 响应速度）。

### 2.4 真正的瓶颈在哪？

**结论：Python 侧计算几乎不构成瓶颈，真正的 I/O 瓶颈在 miniQMT SDK 层。**

- 对执行路径（每次下单查几只股票）：`get_full_tick` 一次调用 ~200ms，完全可接受
- 对批量路径（50~200 只）：单次 `get_full_tick` ~500ms-1s，加上降级路径可能 ~2s
- 对全市场路径（5000+）：已门闸保护，不会在实盘意外触发

---

## 3. 本地数据基础设施

### 3.1 已就绪的资源

| 资源 | 路径 | 状态 |
|------|------|------|
| 日线 Parquet | `stock_data/period=1d/dividend_type=none/symbol=*/data.parquet` | ✅ 5,525 只股票 |
| DuckDB 不复权 | `stock_data/stock_data_none.duckdb` | ✅ 1,057 MB |
| DuckDB 前复权 | `stock_data/stock_data_front.duckdb` | ✅ 1,057 MB |
| `StockDataReader` | `backtest/stock_data_reader.py` | ✅ 已实现三种模式 |
| Benchmark | `benchmark/duckdb_benchmark.py` | ✅ 已验证 |

### 3.2 已有性能数据（实测）

来源：`docs/backtest/data/parquet_duckdb_dual_mode_reader_plan.md` §4.2

| 场景 | 方案 A (read_parquet) | 方案 B (.duckdb) | B/A 加速比 |
|------|----------------------|-------------------|-----------|
| 全市场 1 天截面（~5.5K 行） | 9.98s | **2.84s** | **3.52×** |
| 全市场 1 年历史（~1.4M 行） | 14.28s | **5.00s** | **2.86×** |
| 单股 10 年历史（~2.5K 行） | 5.83s | **0.016s** | **357×** |
| 全市场聚合（AVG GROUP BY） | 4.94s | **0.43s** | **11.47×** |

DB 开销：1,057 MB（parquet 源 834 MB，膨胀 1.27×），建库 46 秒（5,525 只/日线 front）。

---

## 4. 本地替代方案设计

### 4.1 可替代的两个函数

> **状态**：✅ **已实施**（2026-06-05）。下表「当前实现」列为改前基线；「现已实施」见文首表。

| 函数 | 改前实现（基线） | 本地替代（分析建议） | **现已实施** |
|------|-----------------|-------------------|-------------|
| `_get_prev_trade_date()` (L1291) | `xtdata.get_trade_days()` | PMC 编排器（优于 DuckDB `time` 推导） | ✅ `get_prev_trade_date_or_none` + xtdata fallback |
| `_get_prev_close_dict()` (L1577+) | QMT K 线 | DuckDB `close` @ `prev_date`, `adjust_type='none'` | ✅ `oskh_core/limit_info_prev_close_local.py` + 开关 |

### 4.2 关键：用哪个复权类型？

**涨跌停计算必须用「不复权」(`none`) 的收盘价**。前复权/后复权价格会因除权除息而偏移，不反映真实交易价格。

本地已有 `stock_data_none.duckdb` ✅

### 4.3 实现方案示意

```python
# 在 hkcodex_miniqmt.py 的 get_limit_info 中增加本地降级路径

def _get_prev_close_from_local(stock_list, prev_date):
    """从本地 DuckDB/Parquet 获取前收盘价（零网络 I/O）"""
    from backtest.stock_data_reader import StockDataReader
    reader = StockDataReader(mode="duckdb_persistent", base_dir="stock_data")
    # 单次 SQL：SELECT symbol, close WHERE time = prev_date AND symbol IN (...)
    # 预计耗时：16ms（单股）~ 2.8s（全市场）
    df = reader.scan_stocks(
        stock_codes=stock_list,
        period="1d", adjust_type="none",
        start_time=prev_date, end_time=prev_date,
        columns=["close"]
    )
    return {row["symbol"]: row["close"] for _, row in df.iterrows()}
```

---

## 5. 可行性评估

### 5.1 优势

| 优势 | 说明 |
|------|------|
| **零网络延迟** | 本地 DuckDB ~16ms vs miniQMT 网络调用 ~300-1200ms |
| **不依赖 QMT 可用性** | 即使 QMT 连接断开，仍可估算涨跌停 |
| **已有完整基础设施** | `StockDataReader` + DuckDB persistent 已实现并 benchmark |
| **正确性有保证** | 同一数据源（miniQMT 下载的日线） |

### 5.2 风险与限制

| 风险 | 严重程度 | 缓解措施 |
|------|---------|---------|
| **数据时效性** | **中** | T 日交易时，T-1 收盘数据已在前一交易日收盘后下载。只要日终数据下载正常，pre_close 就是准确的 |
| **仅限降级路径** | **低** | 主路径（tick 含 upLimit/downLimit）不受益。但 miniQMT 标准版经常走降级路径 |
| **新股/新上市** | **低** | 本地可能缺少新股首日前的 K 线。但新股涨跌幅规则不同（首日无涨跌停），估算本来就标记 `is_estimated=True` |
| **ST 状态变更** | **中** | 本地日线只有 close，不知道当天是否 ST。但 `_get_limit_pct()` 不检查 ST（仅 backtest 版有 ST 检查） |
| **复权类型一致性** | **低** | 必须确保用 `adjust_type='none'`，文档已标注 |

### 5.3 性能对比预估

| 场景 | 当前（miniQMT 网络） | 优化后（本地 DuckDB） | 提升 |
|------|---------------------|---------------------|------|
| 10 只股票 prev_close | ~300ms | **~16ms** | **~18×** |
| 100 只股票 prev_close | ~600ms | **~50ms** | **~12×** |
| 500 只股票 prev_close | ~1.2s | **~200ms** | **~6×** |
| `_get_prev_trade_date` | ~100ms | **~5ms**（本地 SQL） | **~20×** |

---

## 6. 推荐实施方案

### 6.1 混合模式（本地优先 + miniQMT fallback）

```
estimate_missing 路径:
  1. 尝试本地 DuckDB 读取 pre_close
  2. 如果本地数据缺失（如新股、当天未下载），fallback 到 miniQMT
  3. 两种来源的结果都标记 is_estimated=True
```

### 6.2 实施步骤

| 步骤 | 内容 | 预估工作量 |
|------|------|-----------|
| 1 | 新增 `_get_prev_close_from_local()` 函数：复用 `StockDataReader.scan_stocks()` | 30 min |
| 2 | 修改 `_get_prev_close_dict()`：优先走本地，miss 时走 miniQMT | 30 min |
| 3 | 修改 `_get_prev_trade_date()`：可选，从本地日线数据的 `time` 列推导前一交易日 | 30 min |
| 4 | 增加开关：`HKCODEX_LIMIT_INFO_USE_LOCAL_DATA=1` 控制，默认关闭 | 15 min |
| 5 | 测试：对比本地 vs miniQMT 的 pre_close 结果一致性 | 30 min |

### 6.3 不建议做的

- ❌ **完全替代 miniQMT tick 的 upLimit/downLimit**：交易所计算的权威值不可替代
- ❌ **在主路径（tick 有 upLimit）时也走本地**：无必要，增加复杂度

---

## 7. 其他微优化建议（优先级低）

| # | 建议 | 收益 |
|---|------|------|
| 1 | 缓存 `_resolve_stock_status_policy()`：模块级变量 + TTL（60s） | 省 μs 级开销 |
| 2 | 共享 `tradeable_status_values` / `uncertain_status_values` 列表到循环外 | 省 N 次 sorted 调用 |
| 3 | 缓存 `_get_prev_trade_date()`：同一交易日内结果不变 | 省 1 次 xtdata 调用 |

---

## 8. 总结

| 维度 | 评估 |
|------|------|
| **可行性** | ✅ **高** — 基础设施已就绪，数据格式一致 |
| **收益** | 降级路径延迟降低 **6-18×**，仅对 tick 缺 upLimit 的场景生效 |
| **风险** | 中低 — 数据时效性需保证（日终下载正常即可） |
| **必要性** | **中** — 如果 miniQMT 是标准版（经常走 estimate_missing），值得做；如果是投研版（tick 有 upLimit），则不需要 |
| **工作量** | 约 **2-3 小时**（含开关、fallback、一致性测试） |

---

## 附录：代码位置索引

> 行号以 2026-06-05 主分支为准；降级路径调用点 **L1992**（非历史稿 L1934）。

| 文件 | 行号 | 说明 |
|------|------|------|
| `hkcodex_miniqmt.py` | L1184+ | `_get_limit_pct()` — 按代码前缀推算涨跌幅比例 |
| `hkcodex_miniqmt.py` | L1291 | `_get_prev_trade_date()` — **PMC 优先** + xtdata fallback |
| `hkcodex_miniqmt.py` | L1577 | `_get_prev_close_dict()` — **DuckDB 优先**（`LIMIT_INFO_PREV_CLOSE_SOURCE`）+ xtdata fallback |
| `oskh_core/limit_info_prev_close_local.py` | — | C.2 守门函数 + DuckDB scan |
| `oskh_core/trading_calendar_resolve.py` | L393 | `get_prev_trade_date_or_none` |
| `hkcodex_miniqmt.py` | L1703+ | `_extract_limit_row_gap_fields()` |
| `hkcodex_miniqmt.py` | L1731+ | `get_limit_info()` — 核心入口 |
| `hkcodex_miniqmt.py` | L2486 | `stk_limit()` — 遗留接口（已弃用） |
| `backtest/LimitUpDownManager.py` | L18 | 回测用涨跌停管理器 |
| `oskh_data/reader.py` | — | 生产读取层（C.2 / B2 预热） |
| `executor_stream/execute_signal_timed_stages.py` | L445 | `_get_limit_info_sync()` — Executor L1 缓存 |
| `executor_stream/qmt_sync_ops.py` | L303 | Redis `LIMIT_INFO` / `QUOTE_SNAPSHOT` |
