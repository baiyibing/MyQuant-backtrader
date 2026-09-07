# 方案：将 live trading 的历史日线数据获取统一到回测数据管道

> **关联**: [INV-2026-0515-001](../../knowledge/incidents/INV-2026-0515-001-fund-daily-perf-failed-analysis.md)  
> **参考文档**:
> - [INV-2026-0515-001 fund_daily 根因分析与修复方案](../../knowledge/incidents/INV-2026-0515-001-fund-daily-perf-failed-analysis.md)
> - [回测数据回填总结](../../backtest/data/daily_data_backfill_summary.md)
> - [Parquet + DuckDB 双模读取器方案](../../backtest/data/parquet_duckdb_dual_mode_reader_plan.md)
> - [DuckDB Scheme A vs B 基准测试](../../backtest/data/duckdb_scheme_a_vs_b_benchmark_plan.md)
> - [流通股时间维度方案](../../backtest/data/float_shares_time_dimension_plan.md)
> **状态**: ✅ 已实施（2026-05-16）  
> **实施位置**: `common/integrations/duckdb_daily_bars_adapter.py`（DuckDBDailyBarsProxy）  
> **集成点**: `oskh_core/decision_market_data_port.py:resolve_decision_market_data_read_port_for_lt()`  
> **配置**: `DAILY_BARS_SOURCE=duckdb`（ENV > YAML > 默认 qmt）  
> **关联实施**: `oskh_data/` 重构（[plan-refactor](#)）  
> **日期**: 2026-05-16

## Context

INV-2026-0515-001 已确认 `fund_daily` 的 154 条 PERF_FAILED 根因是代码后缀丢失 + QMT 实时查询不稳定。但更深层的问题是：**对于 T-1 及以前的日线数据（不可变数据），live trading 每次仍然穿透到 QMT xtdata 实时 API**，而回测侧已经有成熟的本地数据管道（QMT 下载 → Parquet → DuckDB，单标的查询仅 0.016s）。

核心思路：将 live trading 的**历史日线读取**从 "QMT 实时 API" 切换到 "本地 DuckDB/Parquet"，与回测共用一个数据底座。

---

## 1. 现状对比

| 维度 | Live Trading（当前） | Backtest（目标方向） |
|------|---------------------|---------------------|
| 数据源 | `xtdata.get_market_data()` 实时 QMT API | 本地 Parquet + DuckDB |
| T-1 日线获取 | 每次穿透 QMT（~50-500ms，不稳定） | `StockDataReader.read_stock()` → DuckDB（0.016s，可靠） |
| 历史深度 | QMT 可用范围 | 1990-12-21 ~ 今（35 年） |
| 数据刷新 | 无本地缓存 | `backfill_daily_data.py` 每日增量下载 |
| 调整类型 | front/back/none（实时切换） | front/back/none（分目录存储） |
| 跨进程 | Redis qmt_ops → executor → QMT | 进程内直接读文件系统 |

---

## 2. 已有基础设施（可直接复用）

### 2.1 回测侧 — 数据存储与读取
- **Parquet 存储**：`stock_data/period=1d/dividend_type={front,back,none}/symbol={code}/data.parquet`（~5,525 只 A 股，2026-05-15 已完成 1990 年以来的全量回填）
- **DuckDB 持久化**：`stock_data.duckdb`（scheme B，1,057 MB，含索引），单标的查询 **0.016s**，全市场日快照 **2.84s**
- **统一读取器**：`backtest/stock_data_reader.py:StockDataReader`（3 模式：parquet/duckdb/duckdb_persistent），方法 `read_stock(symbol, start_time, end_time, period, adjust_type, columns) -> DataFrame`
- **每日刷新**：`backtest/backfill_daily_data.py` 批量下载 + 重建 DuckDB

### 2.2 Live Trading 侧 — 协议注入点
- **读端口协议**：`oskh_core/decision_market_data_port.py:DecisionMarketDataReadPort` — 定义 `stock_daily_bars(symbol, start_date, end_date, adjust) -> Dict`
- **注入点**：`live_trading_broker.py:1484` — `resolve_decision_market_data_read_port_for_lt(lt, cfg)` 返回 `_md_port`，已支持通过 `lt_module._decision_market_data_read_port` 注入自定义实现
- **序列化**：`oskh_core/fund_daily_bars_serialize.py` — `fund_daily_bars_records_from_df(df) -> List[Dict]` / `fund_daily_bars_list_to_dataframe(bars) -> DataFrame`，已在 executor 和 broker 两侧使用
- **Redis 协议**：`common/integrations/qmt_market_ops_protocol.py:OP_STOCK_DAILY_BARS` — 操作码已定义

---

## 3. 方案设计

### 3.1 核心模式：代理（Proxy），非整口替换

**原方案问题**：`DecisionMarketDataReadPort` 包含 `full_tick`、`stock_asset`、`trade_calendar_range`、`limit_info`、`stock_positions` 等多个方法。将整个 port 替换成只实现了 `stock_daily_bars` 的 provider 会在运行期因缺方法而崩溃。

**修正方案**：创建 `DuckDBDailyBarsProxy`，包装已有的 `DefaultDecisionMarketDataReadPort`，**仅拦截 `stock_daily_bars()` 和 `stock_daily_bars_cfg_only()` 两个方法**，其余方法透传到原 port。

```python
class DuckDBDailyBarsProxy:
    """代理 DefaultDecisionMarketDataReadPort，仅接管日线查询，其余透传。"""

    def __init__(self, delegate: DecisionMarketDataReadPort, reader: StockDataReader,
                 trading_clock): ...
    
    # 拦截：走 DuckDB（T-1 及以前）或 fallback QMT
    def stock_daily_bars(self, *, symbol, start_date, end_date, adjust, trace_id, ...): ...
    def stock_daily_bars_cfg_only(self, *, symbol, start_date, end_date, adjust, trace_id, ...): ...

    # 透传：所有其他方法直接委托给 self._delegate
    def full_tick(self, *args, **kwargs): return self._delegate.full_tick(*args, **kwargs)
    def full_tick_cfg_only(self, *args, **kwargs): return self._delegate.full_tick_cfg_only(...)
    def limit_info(self, *args, **kwargs): return self._delegate.limit_info(...)
    def trade_calendar_range(self, *args, **kwargs): return self._delegate.trade_calendar_range(...)
    def stock_asset_cfg_only(self, *args, **kwargs): return self._delegate.stock_asset_cfg_only(...)
    def stock_positions(self, *args, **kwargs): return self._delegate.stock_positions(...)
    def stock_positions_cfg_only(self, *args, **kwargs): return self._delegate.stock_positions_cfg_only(...)
```

### 3.2 注入点：覆盖 broker 和 MA provider 两条路径

**路径 1 — broker 路径**（`live_trading_broker.py:daily_basic` → `_md_port.stock_daily_bars()`）：  
在 `resolve_decision_market_data_read_port_for_lt()` 中，当 DuckDB 模式开启时，将返回的 port 用 `DuckDBDailyBarsProxy` 包装后返回。覆盖注入点 `lt_module._decision_market_data_read_port`。

**路径 2 — MA provider 路径**（`live_trading_ma_indicator_provider.py` → `_port.stock_daily_bars_cfg_only()`）：  
MA provider 通过 `resolve_decision_market_data_read_port_for_lt(strategy_config, cfg=strategy_config)` 创建自己的 port 实例。**在 `resolve_*` 函数内部统一包装**，确保无论哪个调用方拿到的 port 都经过 DuckDB 代理。两条路径均被覆盖。

**关键**：代理发生在 `resolve_decision_market_data_read_port_for_lt()` 函数内部，不改变调用方的任何代码。

### 3.3 数据格式转换：time(ms) → YYYYMMDD 索引

`StockDataReader.read_stock()` 返回的 DataFrame 结构：
- 列：`symbol, time, open, high, low, close, volume, amount`
- `time` 列：毫秒 epoch 整数（如 `1747276800000`）
- 默认整数索引（0, 1, 2, ...）

`fund_daily_bars_records_from_df()` 的要求：
- 从 DataFrame **索引** 提取 YYYYMMDD 字符串
- 索引必须是 8 位数字字符串

**转换步骤**（在 proxy 内部完成）：
```python
def _df_to_bars_response(df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
    """将 StockDataReader 返回的 DataFrame 转换为 bars 响应格式。"""
    if df is None or df.empty:
        return {"ok": True, "data": {"bars": [], "symbol": symbol}}
    # 1. 将 time(ms) 列转为 YYYYMMDD 字符串索引
    df = df.copy()
    df["_date"] = pd.to_datetime(df["time"], unit="ms").dt.strftime("%Y%m%d")
    df = df.set_index("_date")
    df.index.name = None
    # 2. 重命名列以对齐 serializer 期望（lowercase）
    if "symbol" in df.columns:
        df = df.drop(columns=["symbol"])
    # 3. DataFrame → bars JSON
    bars = fund_daily_bars_records_from_df(df)
    return {"ok": True, "data": {"bars": bars, "symbol": symbol}}
```

### 3.4 路由矩阵：T-1 DuckDB / T+0 QMT / 失败回退

```
stock_daily_bars(symbol, start_date, end_date, adjust) → 响应

1. 判断 start_date/end_date 是否全部 ≤ 上一个交易日 (T-1)？
   ├─ 是 → 走 DuckDB 路径
   │        ├─ StockDataReader.read_stock(symbol, start, end, period='1d', adjust)
   │        │   └─ 成功 → _df_to_bars_response(df) → {"ok": True, ...}
   │        └─ 失败（DB 缺失/股票无数据）→ fallback 到 QMT qmt_ops
   │            └─ self._delegate.stock_daily_bars(...)
   └─ 否（含当日 T+0）→ 全部走 QMT qmt_ops
            └─ self._delegate.stock_daily_bars(...)
```

**交易日判定**：通过 `resolve_trading_clock_port_for_lt()` 获取当前交易日 `wall_calendar_date_yyyymmdd()`。请求日期的 `end_date`（或 `start_date` 若 `end_date` 缺失）与交易日比较。

**回退遥测**：DuckDB 失败回退到 QMT 时，记录 `duckdb_fallback` 事件（warning 级别，含 symbol/trace_id/原因），用于后续评估 DuckDB 覆盖率。

### 3.5 层次放置：`common/integrations/`，不透传 `oskh_core`

**原方案问题**：将 provider 放在 `oskh_core/` 并直接依赖 `backtest/stock_data_reader.py`（含 duckdb/pandas/文件布局），会把运行时域层和回测工具链耦合。

**修正**：
- **文件位置**：`common/integrations/duckdb_daily_bars_adapter.py`（集成适配层）
- `oskh_core/` **不引入新文件**，仅保留 `DecisionMarketDataReadPort` 协议
- `StockDataReader` 的导入通过延迟加载（`_lazy_stock_data_reader()`），避免 duckdb 依赖在未安装时阻塞进程启动

### 3.6 配置与门禁完整性

| 配置项 | 位置 | 说明 |
|--------|------|------|
| `DAILY_BARS_SOURCE` 环境变量 | `common/infra/constants.py:EnvVarKeys` | 新增 key，默认 `qmt`，可选 `duckdb` |
| `DAILY_BARS_DUCKDB_PATH` | 同上 | DuckDB 文件路径，默认 `stock_data.duckdb`（自动探测） |
| `DAILY_BARS_DUCKDB_MAX_STALENESS_DAYS` | 同上 | DuckDB 数据最大滞后天数，默认 2，超限告警 |
| runtime yaml | `config/runtime.local.yaml` 示例 | 添加上述三项的注释示例 |

**门禁脚本覆盖**：
- `run_common_package_contract_gates.py` — 验证 `common/integrations/` 新模块不违反导入边界
- 合约测试：验证 `DuckDBDailyBarsProxy` 实现 `DecisionMarketDataReadPort` 所有方法签名
- 回归：`DAILY_BARS_SOURCE=qmt`（默认）时全部现有测试通过

---

## 4. 实施步骤

### Step 1：创建 `common/integrations/duckdb_daily_bars_adapter.py`
- 实现 `DuckDBDailyBarsProxy` 类（代理模式，非整口替换）
- `__init__` 接收 `delegate: DecisionMarketDataReadPort` + `StockDataReader` + trading_clock
- `stock_daily_bars()` / `stock_daily_bars_cfg_only()` — 拦截，实现 §3.4 路由矩阵
- 其余所有方法 — `__getattr__` 透传到 `self._delegate`
- 包含 `_df_to_bars_response()` — 处理 time(ms) → YYYYMMDD 索引转换（§3.3）
- `StockDataReader` 通过延迟导入（避免 duckdb 硬依赖）
- 包含 `_is_t_minus_1_or_earlier(end_date, trading_date)` 交易日判定
- DuckDB 失败回退到 delegate 时记录 `duckdb_fallback` 遥测日志

### Step 2：在 `resolve_decision_market_data_read_port_for_lt()` 中统一注入
- 当 `DAILY_BARS_SOURCE=duckdb` 时，在 `oskh_core/decision_market_data_port.py` 的 `resolve_*` 函数中：
  1. 先创建 `DefaultDecisionMarketDataReadPort`
  2. 再用 `DuckDBDailyBarsProxy` 包装后返回
- **同时覆盖 broker 路径和 MA provider 路径**（两者都经过同一个 `resolve_*` 函数）
- 默认 `DAILY_BARS_SOURCE=qmt` 时行为完全不变

### Step 3：配置项落地
- `common/infra/constants.py:EnvVarKeys` — 新增 `DAILY_BARS_SOURCE`、`DAILY_BARS_DUCKDB_PATH`、`DAILY_BARS_DUCKDB_MAX_STALENESS_DAYS`
- `config/runtime.local.yaml` 示例 — 添加注释示例
- 启动时 DuckDB 新鲜度检查：若最新数据日期滞后超过 `MAX_STALENESS_DAYS`，告警并降级到纯 QMT 模式

### Step 4：数据刷新衔接
- 复用已有 `backfill_daily_data.py` 的日终回填流程
- 新增 `--rebuild-duckdb` flag 确保回填后自动重建 `stock_data.duckdb`
- live trading 不负责数据刷新，只消费已有 DuckDB

### Step 5：测试（四层）
1. **单元测试** — `test_duckdb_daily_bars_adapter.py`：
   - mock `StockDataReader`，验证 `stock_daily_bars()` 路由矩阵（T-1 → DuckDB，T+0 → delegate）
   - 验证 DuckDB 失败回退到 delegate
   - 验证非日线方法透传到 delegate
2. **集成测试** — 使用真实 `stock_data.duckdb` 验证 77 只个股日线查询
3. **回归测试** — `DAILY_BARS_SOURCE=qmt`（默认）全部现有测试通过
4. **门禁测试** — `run_common_package_contract_gates.py`：新模块不违反导入边界

---

## 5. 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `common/integrations/duckdb_daily_bars_adapter.py` | **新增** | DuckDB 日线代理（DuckDBDailyBarsProxy + 数据格式转换 + 路由矩阵） |
| `oskh_core/decision_market_data_port.py` | 修改 | 在 `resolve_decision_market_data_read_port_for_lt()` 中根据 `DAILY_BARS_SOURCE` 包装 proxy |
| `common/infra/constants.py` | 修改 | `EnvVarKeys` 新增 3 个配置 key |
| `config/runtime.local.yaml` | 修改 | 添加配置示例注释 |
| `backtest/stock_data_reader.py` | **不修改** | 直接复用 |
| `backtest/backfill_daily_data.py` | 轻微修改 | 新增 `--rebuild-duckdb` flag |
| `oskh_core/fund_daily_bars_serialize.py` | **不修改** | 直接复用 |
| `live_trading/live_trading_broker.py` | **不修改** | 通过 `resolve_*` 注入点透明切换 |
| `live_trading_ma_indicator_provider.py` | **不修改** | 通过 `resolve_*` 注入点透明切换（cfg_only 路径同样覆盖） |
| `tests/test_duckdb_daily_bars_adapter.py` | **新增** | 单元测试 + 路由矩阵验证 + 透传验证 |
| `scripts/run_common_package_contract_gates.py` | 验证 | 新模块不违反导入边界 |

---

## 6. 对 INV-2026-0515-001 方案的影响

| INV 方案 | 本方案与之的关系 |
|----------|----------------|
| P0-2（后缀格式修复） | **互补**：本方案从 DuckDB 读数据天然避开了后缀问题，但 QMT 路径（当日数据）仍需 P0-2 |
| 3.4（Redis/SQLite 缓存层） | **替代/升级**：本方案是缓存层的具体实现，用 DuckDB 替代了原方案中的 Redis+SQLite 双层缓存 |
| P1-3（涨停检查容错） | **降级为可选**：如果涨停检查走 DuckDB，则不再触发 QMT 异常，P1-3 的容错需求大幅降低 |
| P1-4（持仓代码清洗） | **仍需要**：DuckDB 中如缺少某只退市股票的日线数据，仍需要持仓代码清洗配合 |

---

## 7. 验证方式（四层）

1. **单元测试**（`test_duckdb_daily_bars_adapter.py`）：
   - mock StockDataReader，验证路由矩阵正确性
   - T-1 → DuckDB 路径生效，T+0 → delegate QMT 路径生效
   - DuckDB 失败 → fallback 到 delegate 并记录遥测日志
   - 非日线方法（full_tick / stock_asset / limit_info / trade_calendar_range）→ 全部透传到 delegate
2. **功能验证**：`DAILY_BARS_SOURCE=duckdb` 模式下运行涨停检查，确认 77 只个股全部返回有效日线数据（无 PERF_FAILED），且 broker 路径和 MA provider 路径均覆盖
3. **数据一致性验证**：同一股票同日期的 DuckDB 收盘价 vs QMT 收盘价，差异应 < 0.01
4. **回归 + 门禁**：
   - `DAILY_BARS_SOURCE=qmt`（默认）全部现有测试通过
   - `run_common_package_contract_gates.py`：新模块不违反 common → backtest 导入边界约束
