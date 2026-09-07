# DuckDB 方案 A vs 方案 B 性能对比方案

**文档编号**: PLAN-2026-0515-002
**日期**: 2026-05-15
**状态**: ✅ 已完成（v5，benchmark 已执行，结果已写入主方案 §4/§9）
**关联**: `parquet_duckdb_dual_mode_reader_plan.md`（主方案，已实现）

---

## 1. 背景

`parquet_duckdb_dual_mode_reader_plan.md` 推荐方案 A（DuckDB 直接读 parquet），方案 B（全量导入 `.duckdb` 持久化数据库）作为备选被放弃。但两者缺乏实际性能数据支撑。

本方案旨在写一个独立的 benchmark 脚本，量化对比两者，用数据决定是否值得维护方案 B。

**目标定位**：反证——B 必须有显著优势才值得引入数据副本和同步机制的维护成本。若无显著优势，则方案 A 已足够。

### 1.1 数据现状

| 维度 | 值 |
|------|-----|
| `period=1d` / front | 5,525 symbol，~834 MB |
| `period=1d` / back | 5,525 symbol，~838 MB |
| `period=1d` / none | 5,526 symbol，~837 MB |
| `period=1m` / none | 2,122 symbol，~4.9 GB |
| **总计** | ~18,698 个 parquet 文件，~12 GB |
| 每文件 schema | `time`(int64 ms), `open`, `high`, `low`, `close`, `volume`(int64), `amount` |
| 目录命名 | **下划线**：`symbol=000001_SZ`（DuckDB Hive 分区解析出的 symbol 列值即为 `000001_SZ`） |
| DuckDB 版本 | 项目环境 v1.5.2，最低要求 >= 0.8.0（`hive_partitioning` 支持） |

---

## 2. Benchmark 设计

### 2.1 新增文件

**`benchmark/duckdb_benchmark.py`** — 独立 benchmark 脚本，不依赖任何项目模块，自包含。

### 2.2 方案 B 持久化数据库构建

```python
# 所有传入 DuckDB SQL 的路径均转为绝对路径，避免相对路径依赖启动目录
# （若从 benchmark/ 子目录运行，相对路径会解析到 benchmark/stock_data/... → 不存在）
parquet_glob = str(project_root / 'stock_data' / 'period=1d' / 'dividend_type=front' / '*' / 'data.parquet')
# 结果如 'E:/PycharmProjects/OSkhQuant1.3/stock_data/period=1d/dividend_type=front/*/data.parquet'

# 若旧 .duckdb 文件存在，先删除再重建（DROP TABLE 不会收缩文件），确保大小反映实际数据量
db_path = project_root / 'stock_data.duckdb'
if db_path.exists():
    db_path.unlink()

con = duckdb.connect(str(db_path))
con.execute(f"""
    CREATE TABLE stock_data AS
    SELECT * FROM read_parquet('{parquet_glob}', hive_partitioning=1)
""")
# Hive 分区自动解析 symbol 列，值为下划线格式如 '000001_SZ'

# 建索引，确保 Q3 单股查询与方案 A 公平对比
# DuckDB 也会利用 zone map 加速 symbol 过滤
con.execute("CREATE INDEX idx_symbol ON stock_data(symbol)")
```

建库范围：
- 全量 `period=1d/dividend_type=front`（日线 front，最常用场景）
- `none` / `back` 不纳入（避免范围膨胀；若 front 结论不足以决策，再扩展）
- 分钟线不纳入（4.9 GB，导入耗时长；分钟线场景后续单独评估）

**预估导入开销**：5,525 文件 × 834 MB（snappy 压缩）→ 导入后 `.duckdb` 预计 **1.0~1.7 GB**（DuckDB 自有压缩，通常为原始 1.2×~2.0×），导入耗时 **2~5 分钟**（SSD）。若远超此范围（>3.4 GB 或 >10 min），报告中会标注异常。

**symbol 规范化前置步骤**：
benchmark 脚本启动时先探测实际目录命名风格，再决定是否需要 `REPLACE`：
```python
# 扫描全部 symbol= 前缀目录，确认命名风格一致，不一致则 fail-fast
data_dir = project_root / 'stock_data/period=1d/dividend_type=front'
all_symbol_dirs = [d for d in os.listdir(data_dir) if d.startswith('symbol=')]
if not all_symbol_dirs:
    raise RuntimeError(f"No symbol= directories found under {data_dir}")

has_underscore = [d for d in all_symbol_dirs if '_' in d]
has_dot = [d for d in all_symbol_dirs if '.' in d and '_' not in d]
# 若两种风格并存，fail-fast 让用户确认（不应出现在规范目录中）
if has_underscore and has_dot:
    raise RuntimeError(
        f"Mixed symbol naming detected: {len(has_underscore)} underscore + "
        f"{len(has_dot)} dot dirs. Please normalize first."
    )
style = 'underscore' if has_underscore else 'dot'

# 方案 B 建库后统一规范化为点号
if style == 'underscore':
    con.execute("UPDATE stock_data SET symbol = REPLACE(symbol, '_', '.')")
```
方案 A 在 `read_parquet` 查询中同样根据探测结果决定是否对 symbol 列做 `REPLACE`。

### 2.3 对比查询场景

| # | 场景 | 典型行数 | 代表业务 |
|---|------|---------|---------|
| Q1 | 全市场最新截面（1 天） | ~5,500 行 | `filter_chip_stocks.py` 单日筛选 |
| Q2 | 全市场 1 年历史（~250 天） | ~1.4M 行 | 因子回测全量加载 |
| Q3 | 单只股票 10 年历史 | ~2,500 行 | 单股回测 |
| Q4 | 全市场聚合（AVG close GROUP BY symbol） | ~5,500 行 | 截面统计/排名 |

**时间窗口统一 SQL 模板**（动态推导，保证可复现）：

所有场景使用 `MAX(time)` 动态推导最新交易日，再按毫秒偏移量截取窗口。> 注：模板中 parquet 路径为可读性简写，实际传入 DuckDB 的是 `project_root` 拼接后的绝对路径（见 §2.2）。

```sql
-- 方案 A 模板（read_parquet direct）
-- Q1: 全市场最新 1 天
SELECT symbol, time, open, high, low, close, volume, amount
FROM read_parquet('stock_data/period=1d/dividend_type=front/*/data.parquet',
                  hive_partitioning=1)
WHERE time >= (SELECT MAX(time) FROM read_parquet(...)) - 1*86400000

-- Q2: 全市场最近 250 天
SELECT ... FROM read_parquet(...)
WHERE time >= (SELECT MAX(time) FROM read_parquet(...)) - 250*86400000

-- Q3: 单只股票最近 2500 天
SELECT ... FROM read_parquet(...)
WHERE symbol = '000001.SZ'
  AND time >= (SELECT MAX(time) FROM read_parquet(...)) - 2500*86400000

-- Q4: 全市场聚合（与 Q1 同窗口）
SELECT symbol, AVG(close) as avg_close, ...
FROM read_parquet(...)
WHERE time >= (SELECT MAX(time) FROM read_parquet(...)) - 1*86400000
GROUP BY symbol
```

```sql
-- 方案 B 模板（查持久化表 stock_data）
-- Q1:
SELECT * FROM stock_data
WHERE time >= (SELECT MAX(time) FROM stock_data) - 1*86400000

-- Q2:
SELECT * FROM stock_data
WHERE time >= (SELECT MAX(time) FROM stock_data) - 250*86400000

-- Q3:
SELECT * FROM stock_data
WHERE symbol = '000001.SZ'
  AND time >= (SELECT MAX(time) FROM stock_data) - 2500*86400000

-- Q4:
SELECT symbol, AVG(close) as avg_close, ...
FROM stock_data
WHERE time >= (SELECT MAX(time) FROM stock_data) - 1*86400000
GROUP BY symbol
```

> `MAX(time)` 的子查询开销：`86400000` 为 1 天毫秒数（近似；实际按自然日截取即可，因为 benchmark 关注的是相对加速比而非精确交易日对齐）。
>
> **双口径报告**：为避免 `MAX(time)` 子查询开销掩盖纯查询引擎差异，benchmark 同时报告两组指标：
> - **E2E**（端到端）：`MAX(time)` 子查询 + 主查询一同计时，代表真实业务场景。**E2E 为最终 KEEP/ABANDON 判定依据**。
> - **FixedWindow**（纯查询）：先计算一次 `t_min`, `t_max`，后续所有 timed run 仅测主查询（WHERE time BETWEEN ? AND ?），用于诊断 MAX(time) 子查询开销分布。**FixedWindow 仅用于诊断，不参与最终判定**。
> - **delta**：`delta = E2E_median / FixedWindow_median`，表示 MAX(time) 子查询在端到端流程中引入的倍数开销。若 E2E 不达标但 FixedWindow 显著达标且 delta 大，说明瓶颈在动态日期推导而非 DuckDB 引擎本身，可作为后续优化参考。
>
> **方案 A 额外开销说明**：E2E 口径下，方案 A 的 `MAX(time)` 子查询需扫描 parquet 文件 footer，而方案 B 查表几乎无开销。方案 A 因此会在 E2E 口径下多出固定 overhead，但这是公平的——业务上确实需要确定时间窗口。FixedWindow 口径可剥离此差异。

**FixedWindow SQL 模板**（参数化查询，t_min/t_max 预先计算一次）：
```sql
-- 方案 A FixedWindow
SELECT symbol, time, open, high, low, close, volume, amount
FROM read_parquet('<absolute_path>/*/data.parquet', hive_partitioning=1)
WHERE time BETWEEN ? AND ?

-- 方案 B FixedWindow
SELECT * FROM stock_data WHERE time BETWEEN ? AND ?
```
> 参数通过 `con.execute(sql, [t_min, t_max])` 绑定，t_min/t_max 在 warmup 之前从 E2E 的 MAX(time) 子查询中获取，所有 FixedWindow timed run 复用同一对值。

### 2.4 计时方法

区分两种口径，分别报告：

| 口径 | 说明 | 操作 |
|------|------|------|
| **Cold start** | 新连接冷启动（同进程），模拟脚本每次独立运行 | 每个 timed run 前重建连接（方案 A 新建 `:memory:`，方案 B 重新 `duckdb.connect()`）。如需真冷启动（跨进程隔离 OS cache），需子进程逐次执行，不在本次范围 |
| **Warm run** | 同连接复用，模拟循环内多次查询 | 同一连接内连续执行，warmup 5 次后计时 10 次 |

每种口径、每种场景：
- warmup: 5 runs（discard）
- timed: 10 runs，取 **median** 和 **P95**

```python
import time, statistics, numpy as np

def benchmark_cold(make_query_fn, n_warmup=5, n_timed=10):
    """make_query_fn: () -> (con, query_fn) 工厂，每次调用新建连接并返回 (连接, 查询函数)"""
    times = []
    for i in range(n_warmup + n_timed):
        con, query_fn = make_query_fn()   # 新建连接 + 绑定查询
        t0 = time.perf_counter()
        query_fn(con)
        elapsed = time.perf_counter() - t0
        con.close()
        if i >= n_warmup:
            times.append(elapsed)
    return statistics.median(times), np.percentile(times, 95)

def benchmark_warm(con, query_fn, n_warmup=5, n_timed=10):
    for _ in range(n_warmup):
        query_fn(con)
    times = []
    for _ in range(n_timed):
        t0 = time.perf_counter()
        query_fn(con)
        times.append(time.perf_counter() - t0)
    return statistics.median(times), np.percentile(times, 95)
```

**注意**：cold start 口径下不主动清理 OS page cache（Windows 上需要管理员权限且影响全局），但每次新建连接已足以模拟"脚本独立运行"的典型场景。

**首次 cold run 标注**：cold start 的 10 次 timed run 中，首次是真冷（磁盘 I/O），后续 run 可能命中系统缓存。报告时会单独列出 **first cold run** 耗时，若与其他 cold run 差异 > 2×，说明系统缓存影响大，结论应以首次为准。

**异常处理策略**：单次 timed run 若抛出异常（timeout / OOM / DuckDB Error），记录为 `FAILED` 并终止该场景测试。连续 3 次失败则终止整个 benchmark，输出已收集的部分结果。

### 2.5 正确性校验

**每个 timed run 之后**对结果做断言，不一致则终止并报错：

| 校验项 | 方法 | 不通过处理 |
|--------|------|-----------|
| **行数一致** | `len(df_A) == len(df_B)` | 终止，报告差异 |
| **时间边界一致** | `min(time_A) == min(time_B) && max(time_A) == max(time_B)` | 终止 |
| **symbol 数量一致** | `df_A['symbol'].nunique() == df_B['symbol'].nunique()` | 终止（Q1/Q2/Q4） |
| **逐行数值一致** | 按 `['symbol', 'time']` 排序后，价格列（open/high/low/close/amount）逐行 `np.allclose(rtol=1e-10)`，volume(int64) 逐行精确 `==` | 终止 |
| **symbol 全为点号格式** | `df['symbol'].str.match(r'^\d{6}\.[A-Z]{2}$').all()` | 终止（确保规范化生效，且不会因 regex `.` 误匹配） |

校验代码示例：
```python
import numpy as np

def assert_equivalent(df_a, df_b, label):
    # 1. 行数
    assert len(df_a) == len(df_b), f"{label}: row count mismatch ({len(df_a)} vs {len(df_b)})"

    # 2. 时间边界
    assert df_a['time'].min() == df_b['time'].min(), f"{label}: time min mismatch"
    assert df_a['time'].max() == df_b['time'].max(), f"{label}: time max mismatch"

    # 3. symbol 校验（若有）
    if 'symbol' in df_a.columns:
        assert df_a['symbol'].nunique() == df_b['symbol'].nunique(), \
            f"{label}: symbol count mismatch"
        # 点号格式严格匹配 "6位数字.2位大写字母"，避免 regex '.' 误匹配下划线
        # 当前仅适用于 A 股（SH/SZ/BJ 均为 6 位数字）；若引入港股（5 位）需放宽
        pattern = r'^\d{6}\.[A-Z]{2}$'
        assert df_a['symbol'].str.match(pattern).all(), \
            f"{label}: A has unnormalized symbol: {df_a['symbol'].unique()[:5]}"
        assert df_b['symbol'].str.match(pattern).all(), \
            f"{label}: B has unnormalized symbol: {df_b['symbol'].unique()[:5]}"

    # 4. 逐行数值一致性（排序后对比，覆盖错位/抵消漏检）
    sort_keys = ['symbol', 'time'] if 'symbol' in df_a.columns else ['time']
    a = df_a.sort_values(sort_keys).reset_index(drop=True)
    b = df_b.sort_values(sort_keys).reset_index(drop=True)
    float_cols = ['open', 'high', 'low', 'close', 'amount']
    int_cols = ['volume']
    assert np.allclose(a[float_cols].values, b[float_cols].values, rtol=1e-10), \
        f"{label}: float column row-level mismatch (allclose failed)"
    assert (a[int_cols].values == b[int_cols].values).all(), \
        f"{label}: volume column row-level mismatch (exact equality failed)"

    # 5. 辅助定位：报告差异最大的行
    diff = np.abs(a[float_cols].values - b[float_cols].values)
    int_diff = np.abs(a[int_cols].values - b[int_cols].values)
    max_diff_idx = diff.max(axis=1).argmax()
    if diff.max() > 1e-6 or int_diff.max() > 0:
        raise AssertionError(
            f"{label}: max diff at row {max_diff_idx}: "
            f"A={a[float_cols + int_cols].iloc[max_diff_idx].to_dict()}, "
            f"B={b[float_cols + int_cols].iloc[max_diff_idx].to_dict()}"
        )
```

### 2.6 输出格式

```
======================================================================
DuckDB Scheme A (read_parquet direct) vs Scheme B (persistent .duckdb)
======================================================================
Data: period=1d, dividend_type=front, 5,525 symbols, ~834 MB parquet
DB: stock_data.duckdb = XXX MB, build time = XX min XX sec

--- E2E (end-to-end: MAX(time) subquery + main query) ---
--- Cold start (new connection each run) ---

Q1: Full market, 1 day snapshot (~5.5K rows)
  Scheme A: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Scheme B: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Speedup (B/A): X.Xx  [PASS/FAIL: threshold >=2.0x]

Q2: Full market, 1 year history (~1.4M rows)
  Scheme A: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Scheme B: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Speedup (B/A): X.Xx  [PASS/FAIL: threshold >=2.0x]

Q3: Single stock, 10 year history (~2.5K rows)
  Scheme A: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Scheme B: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Speedup (B/A): X.Xx  [PASS/FAIL: threshold 0.8x-1.2x]

Q4: Full market, AVG(close) GROUP BY symbol (~5.5K rows)
  Scheme A: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Scheme B: median=X.XXs, P95=X.XXs  (first cold: X.XXs)
  Speedup (B/A): X.Xx  [PASS/FAIL: threshold >=2.0x]

--- E2E Warm run (same connection, after warmup) ---

[同上格式]

--- FixedWindow (pre-computed t_min/t_max, main query only) ---
--- Cold start ---

Q1: Full market, 1 day snapshot
  Scheme A: median=X.XXs, P95=X.XXs
  Scheme B: median=X.XXs, P95=X.XXs
  Speedup (B/A): X.Xx

[Q2/Q3/Q4 同上格式]

--- FixedWindow Warm run ---

[同上格式]

======================================================================
Speedup comparison: E2E vs FixedWindow
  Q1: E2E=X.Xx  FixedWindow=X.Xx  (delta from MAX() overhead: X.Xx)
  Q2: E2E=X.Xx  FixedWindow=X.Xx  (delta from MAX() overhead: X.Xx)
  Q3: E2E=X.Xx  FixedWindow=X.Xx  (delta from MAX() overhead: X.Xx)
  Q4: E2E=X.Xx  FixedWindow=X.Xx  (delta from MAX() overhead: X.Xx)
======================================================================
CORRECTNESS: all 4 scenarios PASSED (row count / time bounds / symbol count / row-level allclose)
======================================================================

======================================================================
CONCLUSION
======================================================================
Scope: period=1d, dividend_type=front only. NOT applicable to 1m / none / back.

Speedup summary (E2E):
  Cold: Q1=X.Xx  Q2=X.Xx  Q3=X.Xx  Q4=X.Xx
  Warm: Q1=X.Xx  Q2=X.Xx  Q3=X.Xx  Q4=X.Xx

Speedup summary (FixedWindow):
  Cold: Q1=X.Xx  Q2=X.Xx  Q3=X.Xx  Q4=X.Xx
  Warm: Q1=X.Xx  Q2=X.Xx  Q3=X.Xx  Q4=X.Xx

DB overhead:
  File size: XXX MB (vs parquet source: 834 MB, ratio: X.Xx)
  Build time: XX min XX sec

Per-scenario thresholds (aligned with parquet_duckdb_dual_mode_reader_plan.md §8):
  Q1/Q2/Q4 (full market): >= 2.0x → acceptable
  Q3 (single stock): within [0.8x, 1.2x] → acceptable

Maintenance cost factors:
  - Data sync: must rebuild DB after each download session (daily ~1-2 min)
  - Failure recovery: if DB corrupts, rebuild from parquet (XX min)
  - Schema change: must drop and recreate table if parquet schema changes

Recommendation: [KEEP / ABANDON] Scheme B
Rationale: [automatically generated from results]
======================================================================
```

---

## 3. 判定标准

与 `parquet_duckdb_dual_mode_reader_plan.md` §8 对齐，**按场景分阈值**（所有加速比取自 E2E 口径，FixedWindow 仅用于诊断）：

| 场景 | 阈值 | 含义 |
|------|------|------|
| Q1 全市场截面 | B/A **≥ 2.0×** | 不达标则方案 B 无意义 |
| Q2 全市场 1 年 | B/A **≥ 2.0×** | 同上 |
| Q3 单只股票 | B/A 在 **[0.8×, 1.2×]** 内 | 单股场景两者应接近，超出区间说明有异常 |
| Q4 全市场聚合 | B/A **≥ 2.0×** | 同上 |

综合判定：

| 条件 | 决策 |
|------|------|
| 全市场场景（Q1/Q2/Q4）**至少 2 个** ≥ 2.0×，且 Q3 在 [0.8×, 1.2×]，且正确性全部通过 | **保留方案 B** |
| 全市场场景均 < 2.0× | **放弃方案 B** |
| 混合（部分达标、部分不达标） | **人工判断**，辅助规则：<br>• 若仅 1 个全市场场景达标但加速比 > 5×，其余接近 2× → 倾向保留<br>• 若 Q1/Q2/Q4 全部达标但 `.duckdb` 大小 > parquet 3× → 倾向放弃<br>• 若 Q3 落在 [0.8×, 1.2×] 外 → 检查索引是否正确建立，修复后重跑 |
| `.duckdb` 文件 > 原始 parquet 的 2× | 额外扣分，倾向放弃 |

---

## 4. 适用范围声明

**本 benchmark 结论仅对 `period=1d, dividend_type=front` 有效**。不自动外推到：

- `period=1d` 的其他复权类型（`none`, `back`）
- `period=1m` 分钟线（数据量大 6×，导入耗时和查询性能可能完全不同）
- 其他未测试的 period（`5m`, `1h`, `1w` 等）

若需要在其他 period/adjust 上决策，应单独运行 benchmark 并指定对应数据目录。

---

## 5. 目录结构与路径解析

```
benchmark/
  duckdb_benchmark.py    # 新增：独立 benchmark 脚本
```

脚本自包含，不引入项目依赖。

**路径解析策略**：脚本位于 `benchmark/` 子目录，数据在项目根目录的 `stock_data/`。脚本启动时自动探测项目根目录：

```python
# 向上匹配含 stock_data/ 的目录，返回最近的祖先
def find_project_root():
    p = Path(__file__).resolve().parent
    for ancestor in [p] + list(p.parents):
        if (ancestor / 'stock_data').is_dir():
            return ancestor
    raise RuntimeError("Cannot find project root (no stock_data/ found up to filesystem root)")
```

同时支持 `--data-dir` 参数覆盖：
```bash
python benchmark/duckdb_benchmark.py --data-dir D:/other/path/stock_data
```
若指定 `--data-dir`，`stock_data.duckdb` 默认放在 `--data-dir` 的父目录；若 `--data-dir` 本身已是根级目录，则放在当前工作目录。

方案 B 生成的 `stock_data.duckdb` 文件放在项目根目录（与 `stock_data/` 并列），加入 `.gitignore`。

运行方式：

```bash
# 从项目根目录运行
D:\anaconda3\envs\vanna311\python.exe benchmark/duckdb_benchmark.py

# 或指定数据目录
D:\anaconda3\envs\vanna311\python.exe benchmark/duckdb_benchmark.py --data-dir E:/PycharmProjects/OSkhQuant1.3/stock_data
```

---

## 6. 不做的事情

- 不新建 `stock_data_reader.py`（方案 A 实现，后续再做）
- 不改动任何现有 `backtest/` 代码
- 不纳入分钟线（数据量 4.9 GB，导入耗时长；分钟线场景后续单独评估）
- benchmark 生成的 `stock_data.duckdb` 加入 `.gitignore`

---

## 7. 验证方式

1. 运行 `python benchmark/duckdb_benchmark.py`
2. 检查 §2.5 正确性校验是否全部通过
3. 检查各场景 cold/warm 加速比是否满足 §3 阈值
4. 根据 §3 综合判定决定方案 B 去留
5. 若保留方案 B，更新 `parquet_duckdb_dual_mode_reader_plan.md` 第 9 节的对比结论
6. （建议）在非交易时段重复运行 3 次，确认加速比波动 < 20%。若波动大，取 3 次结果的 median 作为最终结论

---

## 8. 评审意见变更记录

### v4 → v5

| # | 评审意见 | 严重级 | 修复 |
|---|---------|--------|------|
| 1 | 版本号与变更记录不一致（v4 无记录） | P0 | 补 v3→v4、v4→v5 条目 |
| 2 | 方案 B 缺少 symbol 索引，Q3 公平性存疑 | P0 | §2.2 建库后增加 `CREATE INDEX idx_symbol ON stock_data(symbol)` |
| 3 | `benchmark/` 与 `stock_data/` 相对路径未定义 | P0 | §5 增加自动探测项目根 + `--data-dir` 参数覆盖 |
| 4 | "最近 N 个交易日" SQL 实现未定义 | P1 | §2.3 增加 A/B 方案完整 SQL 模板（`MAX(time)` 动态推导） |
| 5 | OS Page Cache 对 cold start 影响未量化 | P1 | §2.4 增加首次 cold run 单独标注，差异 > 2× 时以首次为准 |
| 6 | 缺少 DuckDB 版本声明 | P1 | §1.1 增加 DuckDB >= 0.8.0（当前 v1.5.2） |
| 7 | 未预估方案 B 导入时间与存储膨胀 | P1 | §2.2 增加预估（1.0~1.7 GB，2~5 min），超范围标注异常 |
| 8 | 未定义异常处理策略 | P1 | §2.4 增加异常处理：单次失败终止场景，3 次连续失败终止 benchmark |
| 9 | 混合场景决策规则过于笼统 | P2 | §3 补充 3 条辅助规则（5× 加速比、3× 膨胀、Q3 索引检查） |
| 10 | 缺少跨天稳定性验证 | P2 | §7 增加建议：非交易时段重复 3 次，波动 < 20% |
| 11 | regex 对非 A 股兼容性 | P2 | §2.5 增加注释说明当前仅适用于 A 股 6 位代码 |

### v3 → v4

| # | 评审意见 | 严重级 | 修复 |
|---|---------|--------|------|
| 1 | Cold start "新进程+新连接"与实际操作（同进程）不一致 | 中 | 改为"新连接冷启动（同进程）"，注明跨进程不在范围 |
| 2 | 报告模板 `column sums` 与实现 `np.allclose` 不一致 | 低 | 同步为 `row-level allclose` |
| 3 | `volume`(int64) 走浮点容差不够严格 | 低 | 拆分为 float_cols `allclose` + volume 精确 `==` |

### v2 → v3

| # | 评审意见 | 严重级 | 修复 |
|---|---------|--------|------|
| 1 | `str.contains('.')` 中 `.` 是正则通配符，`000001_SZ` 也会误判为含点号 | 高 | 改为 `str.match(r'^\d{6}\.[A-Z]{2}$')`，严格匹配点号格式 |
| 2 | 列求和 `round(2)` 可能掩盖行级错位/正负抵消 | 中 | 改为按 `['symbol','time']` 排序后 `np.allclose(rtol=1e-10)` 逐行对比 + 差异最大行定位 |
| 3 | `benchmark_cold` 参数名 `query_fn_factory` 与内部调用名 `query_fn` 不一致 | 低 | 改为 `make_query_fn`，返回 `(con, query_fn)` 元组，消除歧义 |

### v1 → v2

| # | 评审意见 | 严重级 | 修复 |
|---|---------|--------|------|
| 1 | 判定阈值 3× 与主文档 §8 的 2× 冲突 | 高 | 改为按场景分阈值，与主文档 §8 对齐：全市场 ≥ 2.0×，单股 [0.8×, 1.2×] |
| 2 | Q3 symbol 用点号但实际目录为下划线 | 高 | 增加 symbol 规范化前置步骤：建库后统一 `REPLACE(symbol, '_', '.')`，查询使用点号格式 |
| 3 | 计时未区分冷/热缓存和连接生命周期 | 高 | 新增 cold start / warm run 两套口径 |
| 4 | 仅测 front 日线却用于全局决策 | 中 | 新增 §4 适用范围声明 |
| 5 | 缺少正确性校验 | 中 | 新增 §2.5 |
| 6 | 维护成本模型过于单点 | 中 | 输出新增同步频率、恢复耗时、schema 变更三项 |
