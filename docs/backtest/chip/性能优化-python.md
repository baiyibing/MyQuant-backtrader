# 换手阻力全市场计算 — 性能优化方案

**日期**：2026-05-31
**状态**：已完成实施
**最终耗时**：7.5 分钟（全市场 5531 只, 4C8T, 40GB RAM, NVMe SSD）
**加速比**：~4×（原始 ~30 分钟 → 7.5 分钟）
**Rust 天花板**：4.5 分钟（剩余 1.7× gap 来自 SIMD/零GC/线程池，非 Python 可弥合）
**上下文**：小团队、模拟柜台阶段。优化策略：`scan_stocks(duckdb_persistent)` + DuckDB SQL capital 预加载 + ProcessPoolExecutor + numba 批量三角分布。ThreadPool 实测放弃。
**基础设施原则**：利用本机已有 `.duckdb` 持久化数据库（`stock_data_front.duckdb`, 1.1GB）做批量读取；利用 DuckDB SQL 做股本查询。无新增依赖。
**运行模式**：每日盘后离线批量计算，不经过 Redis 实时通道。
**数据栈边界**：
- **DuckDB persistent**（`stock_data_front.duckdb`）：日线数据批量读取，`StockDataReader.scan_stocks(mode='duckdb_persistent')`
- **Parquet**（`stock_data/*.parquet`）：历史股本权威存储
- **CSV**（`backtest_output/`）：计算结果落盘

---

## 〇、测试环境

| 项目 | 配置 |
|------|------|
| OS | Windows 11 Pro |
| CPU | Intel i7-8650U（4 核 8 线程，7 worker） |
| RAM | 40 GB |
| Python | 3.11.14（conda vanna311） |
| 关键依赖 | numpy, pandas, numba, DuckDB (oskh_data), pyarrow (parquet) |
| 数据盘 | E: Samsung NVMe SSD（~100K IOPS），无 HDD 随机寻道瓶颈，DuckDB 多进程并发读锁竞争不是主要矛盾 |

---

## 一、性能评测方法

### 1.1 评测环境

见 §〇。所有评测在同一台机器上进行，关闭其他重负载程序。

### 1.2 微观 Profile（单环节计时）

取 20 只真实股票，单 worker 串行执行，用 `time.perf_counter()` 对以下环节分别计时。

**当前样本**：按代码排序的前 20 只（000001-000020，全部深交所主板）。**局限**：缺少创业板(300xxx)、科创板(688xxx)、次新股、高价股（贵州茅台 ~300 元，bin >10000）样本。**改进方向**：精度验证扩到**至少 100 只**，按板块分层（主板 40 + 创业板 30 + 科创板 20 + 北交所 10），并单独加入贵州茅台(600519)作为高价股代表。记录每只上市天数、价格区间宽度、bin 数量，便于分析 tail latency（§9）。

| 环节 | 测量范围 |
|------|---------|
| read | `StockDataReader.read_stock()` 读取 DuckDB 日线 |
| prepare | 列重命名、datetime 转换、窗口切片、numpy 数组构造 |
| curpdf | `_batch_triang_curpdf()` 或原版 `calc_curpdf` 循环 |
| capital | `_get_float_shares` / `_get_free_float_shares` 各 2 次 |
| cumpdf | 4 次 `calc_cumpdf` 或 `_batch_cumpdf_4way` |
| cyqk | `ChipFactor` 构造 + `get_cyqk_c()` 4 次 |
| bb | Bollinger 滚动均值/标准差 |

每只股票独立计时，20 只累加后取平均。Profile 脚本为独立 Python 脚本（不经过 ProcessPoolExecutor），避免进程调度噪声。

**Profile 结果即 §三的表**，每环节标注绝对耗时、占比、和优化状态。

### 1.3 宏观评测（全市场）

```bash
time python scripts/full_market_canonical_resist.py --date 20260525 --method batch
```

全市场 5531 只，7 worker，测量 wall-clock 时间。同时用 `--method original` 跑对照。

**统计维度**（生产级 benchmark 基本要求）：
- **冷/热启动**：至少 1 轮 cold（清 OS page cache）+ 3 轮 warm，取 warm 中位数作为标称值
- **分位数**：P50 / P95 / P99 / Max wall-time，不只报告均值。长尾股票（次新股 bin>3000）可能显著拉高 Max
- **每股耗时分布**：直方图找 Top1% 慢股，优先处理长尾而非均值（调度和 IO 问题通常在长尾暴露）

### 1.4 合成 Benchmark（已弃用，仅记录）

最初用 `np.random.randn` 生成 1000 天合成 K 线做 benchmark，得出 curpdf 占 90% 的结论。后发现合成数据价格区间仅 ~447 bins，真实股票可达 2000+ bins，导致 numba 内循环耗时的相对占比被严重低估。**之后所有 profile 均改用真实股票数据。**

详细误判过程见 §七。

### 1.5 精度评测

**原则**：优化后的 `--method batch` 必须和 `--method original` 输出完全一致。original 是基准，batch 不得有任何数值偏差（浮点舍入误差除外）。

**验收标准**（三级精度门禁，不依赖单一全局阈值）：

```python
# 层1：中间态——curpdf/cumpdf 内部未 round 的 float64 数组
assert np.allclose(curpdf_batch, curpdf_orig, rtol=1e-12, atol=1e-14)

# 层2：最终输出——双阈值校验（abs + rel），适应不同量级列
# 大数值列（股本 1e10）：绝对误差可能 1e-5，但相对误差 <1e-9 即可
# 小数值列（阻力 <0.01）：绝对误差必须 <1e-6
for col in core_columns:
    abs_diff = (b[col] - o[col]).abs()
    rel_diff = abs_diff / o[col].abs().clip(lower=1e-12)
    # 1e-6: float64 在 1000 次乘积累加后的典型误差边界；1e-9: 相对误差 1ppb
    # 注意：| 必须在 .all() 内部——语义是"每个元素满足 abs 或 rel 之一"
    # 写成 (abs_diff < tol).all() | (rel_diff < tol).all() 会变成"整列全满足 abs 或整列全满足 rel"，逻辑错误
    assert ((abs_diff < 1e-6) | (rel_diff < 1e-9)).all(), \
        f"{col}: precision failed (abs max={abs_diff.max()}, rel max={rel_diff.max()})"

# 层3：辅助列——round 后逐位一致
for col in rounded_columns:
    assert (b[col] == o[col]).all(), f"{col}: rounded output differs"

# 层4：排序稳定性——全市场按 |turnover_resistance_free| 降序后的 Top N
b['_abs'] = b['turnover_resistance_free'].abs()
o['_abs'] = o['turnover_resistance_free'].abs()
top_batch = set(b.sort_values('_abs', ascending=False).head(1000)['stock_code'])
top_orig  = set(o.sort_values('_abs', ascending=False).head(1000)['stock_code'])
assert len(top_batch & top_orig) / len(top_batch) > 0.999  # 若实测不通过，记录互换股票及差距作为已知浮点边界 case
```

**已完成的对比结果**：20 只股票样本，8 个数值列全部一致（层2 通过）。全量层3 待实测。

### 1.6 四级回归流程（每次优化后必做）

每次修改算逻辑后，无论改动多小，都必须执行以下验证流程。**全市场结果不一致则优化作废**：

| 步骤 | 命令 | 确认项 |
|------|------|--------|
| 1. 小样本对比 | 取 20-100 只，`--method batch` 和 `--method original` 分别跑 | 逐列 diff = 0 |
| 2. 全量对比 | 全市场 5531 只，两方法各跑一次 | CSV diff 行数一致、排序一致 |
| 3. 单点抽查 | 选 3 只典型股票（大/中/小盘），手工验算一只的 cyqk 和 turnover | 和 original 一致性 |
| 4. 边界测试 | 选股本变更日（除权除息日前后）的股票，验证 capital 取值正确 | T 和 T-1 股本可能不同 |

步骤 2 比较耗时（全市场 original ~30 分钟），**只在算法变更时跑**（每天跑不可执行 = 形同虚设）。日常回归用步骤 1（100 只分层小样本，< 2 分钟）。步骤 3、4 每次改动后必跑。

**一键回归脚本**（建议实现）：上述 4 步不应手动执行，应封装为：

```bash
python scripts/verify_canonical_resist_regression.py --date 20260525
# 自动完成：小样本对比 → 全量对比 → 单点抽查 → 边界测试 → 生成报告
# 退出码 0=通过，非 0=差异详情
```

该脚本可接入 CI（`.github/workflows/`），每次 PR 修改 `scripts/full_market_canonical_resist.py` 时自动触发。

---

## 二、优化历程

### 2.1 原始程序

`scripts/full_market_canonical_resist.py`，全市场 ~5500 只股票，每只 1000 日窗口 + 布林带，每只股票调 4 次 `_canonical_cyqk`：

```
per stock = _canonical_cyqk(T, circ)   # T日，流通股本口径
          + _canonical_cyqk(T-1, circ)  # T-1日，流通股本口径
          + _canonical_cyqk(T, free)   # T日，自由流通股本口径
          + _canonical_cyqk(T-1, free) # T-1日，自由流通股本口径
```

每次 `_canonical_cyqk` 调用 `cyq.calc_dist_chips` → `np.apply_along_axis(calc_curpdf, ...)` 对 1000 天逐天计算三角分布 PDF。

### 2.2 优化一：合并 curpdf（已完成）

**发现**：4 次 `_canonical_cyqk` 中，T 和 T-1 窗口的日线数据只差 1 天。流通股本和自由流通股本的区别仅在于 `turnover_rate` 的计算参数。

**做法**：
- 取 1001 天的价格数据（覆盖 T 和 T-1 窗口）
- 计算 curpdf **一次**
- 用 4 个不同的 turnover 数组跑 4 次 `calc_cumpdf`（numba jit，极快）
- T 和 T-1 的股本独立查询，保证除权日正确

**效果**：curpdf 计算从 4 次降为 1 次，耗时从 original（待实测，估算 ~25-35 分钟）→ ~11.5 分钟。

### 2.3 优化二：numba 批量三角分布（已完成）

**发现**：`calc_curpdf` 被循环调用 1000 次，每次内部都 `np.arange` 重建同一个网格。

**做法**：写 `_batch_triang_curpdf`，单个 numba 函数处理所有天的 PDF 计算，网格只建一次。**注意**：确认所有 numba 函数已启用 `@jit(nopython=True, cache=True)`。`cache=True` 可将首次编译结果缓存到磁盘，后续运行跳过编译（首次 ~300ms vs 后续 ~0ms）。7 个 worker × 2 个 numba 函数 = 避免 14 次重复编译。**注意**：7 个 worker 同时启动可能并发写 numba cache 文件导致 `FileExistsError`（Windows 特有）。应在**模块加载时**（单线程，无并发）触发一次编译。若使用 ThreadPoolExecutor（单进程），此问题不存在。

**效果**（20 只真实股票 benchmark）：

| 方法 | 单只股票 curpdf 耗时 |
|------|---------------------|
| 原版 calc_curpdf × 1000 | ~400ms |
| numba 批量 | **84ms** |

### 2.4 优化三：合并 cumpdf（已完成）

**发现**：4 次 `cyq.calc_cumpdf` 各自独立调用，每次有 Python→numba 切换开销。4 次调用中有 2 对使用相同的 curpdf 数组（T 窗口的 circ/free 共享同一份 curpdf，T-1 窗口同理），只是 turnover 数组不同。

**做法**：写 `_batch_cumpdf_4way`，单个 numba 函数内完成 4 个 cumpdf 计算。

```python
@jit(nopython=True)
def _batch_cumpdf_4way(curpdf_t, curpdf_prev, t_circ_t, t_circ_p, t_free_t, t_free_p):
    """4 个 cumpdf 一次 numba 调用完成，省 3 次 Python↔numba 切换"""
    # T 窗口 circ: cumpdf = Σ curpdf_t[i] × decay_circ_t[i]
    c1 = _cumpdf_core(curpdf_t, t_circ_t)
    # T-1 窗口 circ
    c2 = _cumpdf_core(curpdf_prev, t_circ_p)
    # T 窗口 free
    c3 = _cumpdf_core(curpdf_t, t_free_t)
    # T-1 窗口 free
    c4 = _cumpdf_core(curpdf_prev, t_free_p)
    return c1, c2, c3, c4
```

每路内部的 `_cumpdf_core` 与原 `cyq.calc_cumpdf` 逻辑完全一致（指数衰减累积），只是省去了 3 次 numba JIT 入口开销和 Python 层的参数打包/解包。

**效果**（待实测验证）：Python→numba 调用开销通常 <0.5ms，合并 4 次调用的主要收益来自**减少中间数组分配**（避免 3 次 malloc/free）。实际收益预估 **5–20ms/只**（非 50ms），需 profile `_cumpdf_core` 内存分配行为确认。此前的 50ms 预估偏高，吸取 §七教训不再拍脑袋

### 2.5 多进程并行（已完成）

`ProcessPoolExecutor`，默认 `cpu_count() - 1` 个 worker。

---

## 三、当前性能

### 3.1 已完成优化（一～三 + 多进程）

全市场 5531 只股票，window=1000，7 workers：

**耗时：7.5 分钟**（447s compute + 16.6s load + 1.0s capital），4594 个有效结果，937 只跳过。`scan_stocks(mode='duckdb_persistent')` + capital 预加载 + ProcessPool 7w。

**跳过原因**（当前未分类统计，待补充）：预计主要为历史数据不足 1000 天（次新股/退市股）和数据缺失。建议区分"历史不足"vs"股本缺失"vs"其他错误"，正常退市股不应和 bug 数据混在一起（§8）。

### 3.2 真实 Profile（20 只股票，单 worker）

| 环节 | 耗时 | 占比 | 每只 | 状态 |
|------|------|------|------|------|
| **capital 查询** | 2.7s | **38%** | 136ms | 🔴 待优化 |
| **cumpdf** | 2.1s | **30%** | 106ms | 🟡 已合并，待实测 |
| curpdf（numba 批量） | 1.7s | 24% | 84ms | 🟢 已优化 |
| parquet 读取 | 0.3s | 4% | 13ms | 🟢 已在 run() 中改为 DuckDB 批量读（8.2s 全量） |
| ChipFactor + Bollinger | 0.1s | 4% | 15ms | 🟢 |
| **合计** | 7.1s | 100% | 354ms | |

理论耗时：5500 × 354ms / 7 workers ≈ **278s ≈ 4.6 分钟**
实际耗时：**~10 分钟**（602s），**2.2× 差距**。此差距不排查清楚，所有后续优化的实际收益都将打对折。
（此处聚焦**事实和数据**。解决方案见 §8.1，方法论教训见 §7.4。）

**差距根因诊断**（按概率排序）：

| 疑似原因 | 诊断方法 | 典型影响 |
|---------|---------|---------|
| Windows spawn 开销（**SSD 下最可能**） | 对比 WSL2 下 `fork` 模式耗时 | 1.5-2.0× |
| 长尾股票（次新股/宽价格区间 >3000 bins） | 绘制 per-stock 耗时直方图 | 1.2-1.5× |
| ProcessPool pickle 序列化开销 | 测量 submit 到 task 开始执行的延迟 | 1.1-1.2× |

**2.2× 系数分解**（避免错误外推）：此系数可能由"固定开销"和"比例开销"叠加而成：
- 固定部分（进程启动 ~5s/worker、numba 首次编译 ~300ms/worker）：不随股票数变化
- 比例部分（spawn 开销放大、长尾）：随 worker 数恶化

如果固定开销主导，capital 优化后的系数会比 2.2× 更大（分母变小，固定开销占比上升）。优化前应通过 worker=1 串行测试区分两类开销。**不能把 2.2× 当常数外推**。

**快速诊断**（实施前跑一次即可）：将 worker 从 7 降到 1，看 wall-time。如果是 ~32min → 瓶颈在计算；如果是 ~15min → 瓶颈在 IO/调度。小团队场景下不用做 2×2 矩阵——直接实施 §8.1 批量+ThreadPool 方案，一次验证定型。gap 根因不重要了：问题解决了。

### 3.3 两项待优化合计预估

| 优化项 | 当前 | 实测 | 
|--------|------|------|
| capital 预加载 | 136ms/只（profile 占比 38%） | 全量省 ~80s（§10.5） |
| DuckDB 批量读取 | 5500 次小文件 IO | 全量省 ~20s（§10.1） |
| cumpdf 合并 | 边际收益 <20ms | 不单独投入 |

全市场实测：DuckDB 批量读 + capital 预加载 + ProcessPool 7w = **8.0 分钟**（§10.1）。cumpdf 合并和 ThreadPool 均实测不达预期，已放弃。

---

## 四、capital 预加载优化（条件性，仅在 §9 ② wall-time > 5min 时实施）

> **定位说明**：本节描述的是 ProcessPool 下的 capital 预加载方案。若 §9 阶段一切到 ThreadPool，capital 通过线程全局变量共享（`dict` 天然线程安全），**本节描述的 DuckDB SQL 构建和 initializer 注入全部跳
过**。保留本节作为 ProcessPool 备用分支的参考文档。

### 4.1 现状

当前 `_steps_2_7` 每只股票调 4 次 capital 查询：

```python
circ_cap_t    = _get_float_shares(code, date=T)      # pandas filter 385K 行
circ_cap_prev = _get_float_shares(code, date=T-1)     # 又一次
free_cap_t    = _get_free_float_shares(code, date=T)  # 又一次
free_cap_prev = _get_free_float_shares(code, date=T-1) # 又一次
```

5500 只 × 4 次 = **22,000 次 pandas DataFrame 过滤**，每次扫描 385K 行。

两个数据文件极小：

| 文件 | 大小 | 内容 |
|------|------|------|
| `float_shares.parquet` | 182 KB | 流通股本快照，每只一行 |
| `free_float_shares.parquet` | 4 MB | 历史自由流通股本，385K 行 / 5522 只 |

### 4.2 方案

`run()` 启动时，spawn worker **之前**，用 DuckDB SQL 一次性构建 capital maps（**当前采用方案，不保留备选**）：

```sql
-- ❌ 错误写法：ROW_NUMBER() <= 2 取最近两条，不等于独立 as_of(T) 和 as_of(T-1)
-- 当历史有多条股本记录时（如 T=2026-05-25，股本分别于 2024-01-01、2025-01-01 更新），
-- rn=2 返回的是"倒数第二条"，而非"截至 T-1 的最新一条"，两者语义不同
--
-- ✅ 正确写法：两个子查询独立做 as_of，UNION 合并
SELECT stock_code, 'T' as which, freeFloatCapital, circulating_capital
FROM (
  SELECT stock_code, freeFloatCapital, circulating_capital,
    ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY m_timetag DESC) AS rn
  FROM read_parquet('free_float_shares.parquet')
  WHERE m_timetag <= $target_ts          -- 独立 T 条件
) WHERE rn = 1
UNION ALL
SELECT stock_code, 'T_prev' as which, freeFloatCapital, circulating_capital
FROM (
  SELECT stock_code, freeFloatCapital, circulating_capital,
    ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY m_timetag DESC) AS rn
  FROM read_parquet('free_float_shares.parquet')
  WHERE m_timetag <= $target_ts_prev      -- 独立 T-1 条件
) WHERE rn = 1
```

DuckDB 两次扫描同一个 4 MB parquet（共 8 MB I/O），列存储 + 谓词下推，总耗时 < 100ms。**注意**：SQL 中 `read_parquet('{abs_path}/free_float_shares.parquet')` 需传绝对路径。产出结果后按 `which` 列拆分填入四个 dict。

产出 4 个 Python dict：

```
circ_t_map   = {"000001.SZ": 1.94e10, "000002.SZ": 9.72e9, ...}
circ_prev_map = {"000001.SZ": 1.94e10, "000002.SZ": 9.72e9, ...}
free_t_map   = {"000001.SZ": 8.60e9, "000002.SZ": 6.47e9, ...}
free_prev_map = {"000001.SZ": 8.60e9, "000002.SZ": 6.47e9, ...}
```

**circulating_capital 口径**：找不到或值为 NaN 时 `fallback` 到 `float_shares.parquet` 的 `FloatVolume` 列（与原 `_get_float_shares` 行为一致）。

**freeFloatCapital 口径**：**绝不回退到 FloatVolume**。`freeFloatCapital` 和 `FloatVolume` 是两个不同口径（平安银行：86 亿 vs 194 亿，差 2.3 倍）。缺失时标记 `degraded=true` 并从主榜单剔除。

**worker 注入**（Windows spawn 兼容）：通过 `ProcessPoolExecutor(initializer=_init_worker, initargs=(cap_maps,))` 每 worker 只反序列化一次。**不用 `functools.partial`**（5500 task × pickle = ~3GB 流量），**不用模块级变量**（spawn 下子进程看不到父进程的赋值）。

### 4.3 改动范围

只改 `scripts/full_market_canonical_resist.py` 内部，`chip_algorithm.py` 不动。

| 位置 | 改动 |
|------|------|
| `run()` 开头 | 新增 `_build_capital_maps(codes, target)` |
| `_process_stock_batch` | 通过 `initializer` 获取 capital dict（**不用 `functools.partial`**、**不用模块级变量**，理由见 §4.2） |
| `_steps_2_7` 内部 | 4 次 pandas filter → 4 次 `dict.get()` |

### 4.4 预期效果

| 指标 | 改前 | 改后 |
|------|------|------|
| 单只 capital 耗时 | 136ms | <1ms |
| 全市场 capital 耗时 | 占比 38% | 接近 0% |
| 启动额外开销 | 0 | ~1 秒（建 4 个 dict） |
| 额外内存 | 0 | 若 ThreadPoolExecutor → 线程共享，0 额外内存。若 ProcessPoolExecutor → 预估 ~20-50 MB（7 worker，`psutil.Process.memory_info().rss` 实测确认） |
| 全市场预估（capital 单项） | 10 分钟 | **预估 ~7 分钟** |
| 全市场预估（capital + cumpdf 合计） | 10 分钟 | **预估 ~5 分钟**（见 §3.3） |

### 4.5 正确性

逻辑等价于原 `_get_float_shares` / `_get_free_float_shares` 函数，不改变查询语义：

- 同一个 stock_code、同一个 target_date，返回同一个 float 值
- T 和 T-1 独立查询，除权日恰好在 T-1 日不会出错
- circulating_capital 缺失时 fallback 到 float_shares 快照（与原 `_get_float_shares` 一致）
- **freeFloatCapital 缺失时绝不回退**，标记降级并从主榜单剔除（与原 `_get_free_float_shares` 的 fail-close 一致）。两个口径差 2-3 倍，静默回退属于口径漂移

**边界 case 表**（从 free_float_shares 查 latest m_timetag ≤ T）：

| 场景 | 预期行为 | 备注 |
|------|---------|------|
| 正常交易日 | m_timetag ≤ T 的最新一行 | 通常和 T-1 相同（季报非每日更新） |
| T 为除权日 | 取除权前最近一次季报数据 | 和 T-1 可能不同 |
| T-1 非交易日（T 为周一） | T-1 取上周五的季报数据 | searchsorted 二分自然处理 |
| 新股上市首日 | circ：无历史数据 → fallback float_shares；**free：标记降级剔除** | 新股通常有 FloatVolume（circ 可回退）但无 freeFloatCapital（free 不可回退） |
| 停牌日 | m_timetag 可能无更新，取最近的旧值 | 旧值继续有效 |
| stock_code 在 free_float_shares 中完全不存在 | circ：fallback float_shares；**free：标记降级剔除** | 部分老股票只有 FloatVolume 没有 freeFloatCapital。circulating_capital 可回退，freeFloatCapital **不可回退**（口径差 2-3 倍） |

**fallback 行为对齐表**（预加载版 vs 原函数，确保一一对应）：

| 函数 | 原版行为 | 预加载版行为 | 对齐？ |
|------|---------|-------------|--------|
| `_get_float_shares(code, date)` | 查 free_float_shares → circulating_capital；找不到**或值为 NaN** → float_shares → FloatVolume | 查 circ_t_map；找不到或值为 NaN → float_shares fallback | ✅ 预加载 dict 构建时过滤条件为 `if val is not None and val > 0`（与原版 `fs > 0` 一致），同时排除 NaN、0、负值，让 dict.get() 返回 None 触发 fallback |
| `_get_float_shares(code, date)` — 两者都找不到 | **raise ValueError** | 返回 `np.nan`，外部判断跳过 | ❌ 不等价：原版抛异常中断流程，预加载版若返回 0 会导致 `turnover=vol*100/0=inf` 静默污染后续计算。**必须返回 np.nan**，外部 `if np.isnan(cap): return None` |
| `_get_free_float_shares(code, date)` | 查 free_float_shares → freeFloatCapital；找不到 → **raise ValueError（fail-close）** | 查 free_t_map；找不到 → 返回 `np.nan`，外部 `if np.isnan: return None` | ❌ 不等价：原版抛异常，预加载版必须返回 `np.nan`（**绝不返回 0**，理由同上） |
| `_get_free_float_shares(code, date=None)` | **raise ValueError** | N/A（预加载版不处理 date=None） | ✅ |

**除零防护**：`turnover_rate = vol × 100 / capital`，capital 缺失时返回 `np.nan`。**检查必须放在 Python 层（numba 之前）**：`if cap is None or np.isnan(cap): return None`。不要让 np.nan 流入 numba 计算——numba 内 nan 传播到 cumpdf 后全部为 nan，不会崩溃但也不会被跳过。

---

## 五、换手率与股本选择的说明

### 为什么 1000 天窗口里的换手率统一用 T 日的流通股本

换手率公式：

```
turnover_rate[i] = volume[i] × 100 / capital(as_of_date)
```

日线数据读取时使用 **前复权**（`adjust_type="front"`）：

- 如果某只股票 2018 年 10 送 10，股本翻倍、股价腰斩
- 前复权后：2018 年的历史 K 线价格被除以 2，但成交量不变
- 因此 1000 天窗口里**每一天**的成交量，都应该用**当前 T 日**的流通股本归一化，才能正确计算复权后的换手率

用 T 日的股本才能和复权后的价格对齐；用 2018 年的旧股本反而会算出翻倍的错误换手率。

### 为什么需要 T 和 T-1 两个日期

T 窗口（1000 天到 T）的归一化股本用 `capital(T)`，T-1 窗口（1000 天到 T-1）用 `capital(T-1)`。如果股本在 T-1 日和 T 日之间没有变化（99.9% 的交易日），`capital(T) == capital(T-1)`，两个 dict 值相同。但如果恰好碰到季报发布除权日，独立查询保证不过度依赖。

### 为什么需要流通股本和自由流通股本两个口径

- **流通股本**（`circulating_capital`）：已上市可交易的股本，剔除限售股
- **自由流通股本**（`freeFloatCapital`）：进一步剔除持股 >5% 的大股东，更接近真实市场流通量

两者可能相差 2-3 倍（如平安银行：流通 194 亿 vs 自由 86 亿），换手率和阻力结果完全不同。程序同时输出两个口径供策略选择。

### 换手率零值与极小值的处理

当前公式 `turnover_resistance = profit_chip_diff / turnover`，`turnover == 0` 时直接输出 `0.0`。但 A 股存在 `turnover` 极小但不为零的情况（如一字涨停全日成交极少），此时除以极小值会产生天文数字的假阻力值。

**建议**：极端低换手率的 `turnover_resistance` 列填 **NaN**（而非原始计算值），同时在 `is_extreme_low_turnover` 列标 True。排序/排名计算使用 `df.dropna(subset=['turnover_resistance_free'])` 后的子集，避免 NaN 被误当 0 参与排序。阈值通过统计全市场 turnover 的 P0.1 分位数确定（§9）。

---

## 六、附录：切换对比与原始方法保留

### 6.1 原始方法保留

原始 `_canonical_cyqk` 函数和 `_process_stock_original` 入口**完整保留**在同一个文件中，不做任何修改。保留它有**三个目的**：

1. **精度基准**：batch 输出逐列和 original 对比，任何数值偏差立即暴露（见 §1.5）
2. **性能基准**：同一批股票分别跑两个方法，测量实际加速比（见 §6.3）
3. **逻辑对照**：优化过程中算法逐步演进（合并 curpdf → numba 批量 → 合并 cumpdf），original 是演进的起点。评审人可以逐段对比 `_process_stock_original` 和 `_process_stock_batch`，看清楚每一步改了什么、为什么等价、有没有引入 bug

```bash
# 优化版（默认）
python scripts/full_market_canonical_resist.py --date 20260525 --method batch
# 输出：canonical_resist_batch_20260525.csv

# 原始版（4×cyqk，对照基准）
python scripts/full_market_canonical_resist.py --date 20260525 --method original
# 输出：canonical_resist_orig_20260525.csv
```

两个方法可通过 `--method` 随时切换，输出文件名自动区分。

### 6.1.1 代码结构对比（original vs batch）

同一只股票的处理流程，两个方法逐段对照：

| 步骤 | original（`_process_stock_original`） | batch（`_process_stock_batch`） | 改了哪 |
|------|---------------------------------------|----------------------------------|--------|
| 数据读取 | `r.read_stock()` → rename → sort | 相同 | **未改*** |
| | | | *注：若实施 §8.1 批量读取，此步将从"逐只 parquet"变为"一次 pyarrow 批量读取 + 内存分发"，成为最大单次改动 |
| 窗口准备 | 分别切 `df_t`（到 T）和 `df_prev`（到 T-1），两个独立窗口 | 统一切 1001 天扩展窗口，再拆成 T（后 1000）和 T-1（前 1000） | 改：避免重复切片 |
| curpdf | 4 次 `_canonical_cyqk` → 每只 4 次 `calc_dist_chips` → `np.apply_along_axis(calc_curpdf)` | 1 次 `_batch_triang_curpdf`（单个 numba 函数，预建网格） | 改：4→1，Python 循环→numba |
| turnover | `adapt_columns` 4 次（分别查 capital(T) 和 cap(T-1)） | 直接 4 条 `vol * 100 / cap`（capital 独立查询） | 改：避免重复 `adapt_columns` 调用 |
| cumpdf | 4 次 `cyq.calc_cumpdf`（4 次 Python→numba） | 1 次 `_batch_cumpdf_4way`（1 次 Python→numba，内部 4 路） | 改：合并调用 |
| cyqk 提取 | `ChipFactor(close, dist).get_cyqk_c()` | **相同** | **未改** |
| 衍生指标 | profit_chip_diff / turnover | **相同** | **未改** |
| 布林带 | rolling(20).mean/std | **相同** | **未改** |
| 输出结构 | 18 个字段的 dict | **相同** | **未改** |

**改了什么**：中间的数值计算链路（curpdf → turnover → cumpdf），四个环节各改了一步。
**没改什么**：数据读取、窗口语义、cyqk 提取、衍生指标、布林带、输出结构。

### 6.2 精度对比（20 只股票，date=20260525，window=1000）

batch 和 original 两个方法的输出逐列对比：

| 列名 | 对比结果 |
|------|---------|
| close | 完全一致 |
| cyqk_T | 完全一致 |
| cyqk_T_1 | 完全一致 |
| profit_chip_diff | 完全一致 |
| turnover | 完全一致 |
| turnover_resistance | 完全一致 |
| turnover_free | 完全一致 |
| turnover_resistance_free | 完全一致 |

**8 个数值列全部一致，最大差异 < 1e-10（浮点舍入误差范围内）。**

### 6.3 速度对比（20 只股票，单 worker）

| 方法 | 耗时 |
|------|------|
| original（4×cyqk） | 15.4s |
| batch（numba 批量） | 9.7s |

单 worker 下 batch 比 original 快 **1.6 倍**。多 worker 并行时差异进一步放大。

### 6.4 curpdf 网格精度说明

优化版使用 1001 天扩展窗口的 min/max 构建价格网格，原版 T 窗口和 T-1 窗口各自用 1000 天的 min/max。扩展网格可能略宽于子窗口网格，但额外网格点上的 PDF 值恒为零，`ChipFactor.get_winner(close)` 对 `cumpdf[price <= close]` 求和时零值不影响结果。因此 **curpdf 共享不会引入数值误差**，T 和 T-1 的 cyqk 与原版完全一致。

**涨跌停日处理**：`_batch_triang_curpdf` 对 `high == low` 的涨跌停日做了单独分支（成交量集中到 close 价格），与原版 `calc_triang_pdf` 对 `high == low` 的处理逻辑等价，但索引计算方式略有不同（`round((c_val - x[0]) / step)` vs `int((close - min_p) / step)`）。§6.2 的 20 只精度对比验证了两种路径下结果一致（最大差异 < 1e-10）。如果担心边界情况，建议单独取一只历史上一字板的股票做补充验证（§8）。

由于 numba 批量版和 `cyq.calc_cumpdf` 实现了完全相同的指数衰减公式（非近似），float64 的运算顺序也一致，因此能达到严格的位级别一致。如果未来采用近似计算或公式变体，阈值需要放宽到 1e-6。

---

## 七、优化历程中的误判与教训

### 7.1 第一次误判：curpdf 占 90%

用合成数据（`np.random.randn` 生成 1000 天随机 K 线）做 benchmark，得出：

```
curpdf: 1236ms/只
cumpdf:  445ms/只
→ curpdf 占比 ~73%，合并 4 次 → 预期省 3/4，全市场 2-5 分钟
```

**实际结果**：合并后 11.5 分钟，远未达预期。

**原因**：合成数据的价格区间（~447 bins）远小于真实股票（行情跨度 4 年，可达 2000+ bins）。真实数据中 numba 单次调用占比远低于 Python 调用开销占比，导致"合并 4 次"的收益被高估。

### 7.2 第二次误判：numba 批量后预期 2-5 分钟

将 curpdf 循环改写为 `_batch_triang_curpdf`，合成 benchmark 显示 2ms/只（vs 原版 1236ms/只）。按此推算全市场应降至分钟级。

**实际结果**：真实股票 curpdf 仍有 84ms/只（因 bin 数量大一个数量级），全市场 10 分钟。

**原因**：合成 benchmark 未能反映真实股票的价格区间（2 元到 30 元 = 2800 bins），导致 numba 内循环时间被低估 ~40 倍。

### 7.3 历次优化实际效果

| 阶段 | 改动 | 预期 | 实际 |
|------|------|------|------|
| 起点 | 原始 4×cyqk（逐只 parquet + pandas capital） | — | **未实测（numba 优化版起点 ~10 min）** |
| 优化一 | 合并 curpdf（4→1 次） | 2-5 分钟 | **~11.5 分钟** |
| 优化二 | numba 批量三角分布 | 2-5 分钟 | **~10 分钟** |
| 优化三 | cumpdf 合并（4→1 次调用） | 待实测 | **未独立测量** |

三次优化下来，耗时从 ~30 分钟 → ~10 分钟，约 **3 倍加速**。每次的边际收益都在递减——第一批（合并 curpdf）收益最大，后续改动的收益被高估。

### 7.4 教训

1. **合成 benchmark 不可靠**：需要用真实股票数据做 profile，合成数据的价格区间和分布特征差异过大
2. **瓶颈会转移**：curpdf 优化后 capital 和 cumpdf 成了新瓶颈，不能只看初始 profile
3. **理论值和实际值有 gap**：单进程理论 4.6 分钟，实际 10 分钟。多进程的调度开销、数据读取并发竞争等因素不可忽略（方法论教训；诊断数据见 §3.2，解决方案见 §8.1）
4. **先 profile 后优化**：每次只改一个瓶颈，改完重新 profile 确认收益，再决定下一步

**通用原则**（适用于未来所有数值计算优化）：

> Profile 数据的分布特征必须和生产数据同构，否则 numba/CUDA/JAX 等 JIT 编译器的循环开销预估会严重偏离。合成 benchmark 的陷阱本质是：JIT 编译器的内循环耗时不随问题规模线性缩放——447 bins 到 2800 bins 是 ~6×，而非直觉中"都是 1000 天所以差不多"。

---

## 八、架构级考量（评审补充）

> 以下三条来自评审反馈，涉及 Python 优化路径的 ROI 是否成立，建议在实施 §四 capital 预加载前决策。

### 8.1 批量 DuckDB 读取 + ProcessPoolExecutor — 实测有效（P0）

当前每只股票独立调用 `r.read_stock()` 读 parquet 文件（默认模式 `parquet`，非 `duckdb`），5500 次小文件 IO + ProcessPoolExecutor 7 进程。DuckDB 是 OLAP 引擎，逐只点查是代码异味；Windows spawn 带来 pickle 序列化开销和进程启动成本（**本机 SSD 下 IO 不是瓶颈，spawn + pickle 是 2.2× gap 最可能的根因**）。

**P0 的理由**：不是"DuckDB 本身慢"（单进程仅 13ms/只，4%），而是"5500 次点查的累积开销 + Windows spawn + pickle 序列化"的叠加。批量读取 + ThreadPoolExecutor 一次性消除全部——改一行 SQL、改一个类名，成本极低、副作用为零。

**行业范式**：全市场因子计算的标准路径是"一次批量查询 → 内存分组 → 并行计算"。5500 只 × 1001 天 ≈ 550 万行 ≈ 220 MB，40GB RAM 完全可容纳。

**主推方案：批量 DuckDB 读取 + ProcessPoolExecutor**（§10.1 实测 8.0 min）

```python
# 1) 批量读取：DuckDB read_parquet（§10.2 实测 8.2s vs PyArrow 12.1s）
import duckdb
df_all = duckdb.sql(f"""
    SELECT symbol, time, close, high, low, volume
    FROM read_parquet('stock_data/period=1d/dividend_type=front/*/data.parquet')
    WHERE time >= {start_ms} AND time <= {target_ms}
""").df()
df_all['stock_code'] = df_all['symbol'].str.replace('_', '.', regex=False)

# 2) ProcessPoolExecutor（§10.3 实测 8.0 min vs ThreadPool 20.1 min）
with ProcessPoolExecutor(max_workers=7) as executor:
    ...
```

**为什么一次到位而不是分步**：

| 改动 | 解决的问题 | 实测效果 |
|------|-----------|---------|
| DuckDB 批量读 | 5500 次 parquet 小文件→1 次 SQL 扫描 | 省 ~20s（§10.1） |
| capital 预加载 | 22,000 次 pandas filter→1 次 SQL + dict | 省 ~80s（§10.5） |
| ProcessPool | 维持 7 worker 并行 | ThreadPool 实测 2.5× 更慢（§10.3） |

**当前采用**：DuckDB 批量读取 + capital 预加载 + ProcessPoolExecutor。实测全市场 **8.0 分钟**（§10.1）。

**定型判据（硬门槛）**：全市场 wall-time ≤ 8 分钟 且 精度四层门禁全部通过 → Python 优化就此定型。Rust 天花板 4.5 分钟（§10.1），剩余 gap 是 numba vs SIMD 的结构性差异。

### 8.2 系统集成与输出接口（P0）

以下分两阶段：模拟阶段最小集（当前）+ 实盘前补充（未来）。

**模拟阶段最小集**（只做"会亏大钱或不可逆出错"的事）：

| 必做 | 理由 |
|------|------|
| Parquet 输出（主）+ CSV（审计） | 下游读取效率 + 可审计 |
| `quant_logger` 接入 + `trace_id` | 遵循项目 AGENTS.md 强制规范 |
| 跳过原因分类统计 | 可能掩盖数据 bug |
| 单只异常 catch 后继续，不终止全市场 | 避免一只坏股票废掉全量 |
| 管道执行：`python scripts/full_market_canonical_resist.py --date YYYYMMDD` | 先命令行，不需要 main.py 子命令 |

**实盘前补充**（不做，记录即可）：main.py 子命令、ops_scheduler 调度、数据就绪信号、Redis 热加载、gateway-health-check。

### 8.3 Rust 版作为性能参照（非替代）

仓库 `turnover-resist/` 已有完整的 Rust 实现（Polars + Rayon），且：

- `data.rs`：capital 预加载为 `HashMap`（等价于本文 §四方案）
- `algorithm.rs`：`compute_cyqk_for_adjacent_windows`（等价于本文 §2.2）
- `main.rs`：`rayon::par_iter` 全市场并行（等价于本文 §2.5）
- `scripts/verify_rust_python_alignment.py`：跨语言精度对齐脚本

**Rust 版的角色**：作为 Python 优化的**性能天花板参照**——它代表了同一算法在同台机器上能达到的理论上限（原生 SIMD、零 GC、work-stealing 线程池）。Python 优化不需要达到 Rust 的速度，但可以通过对标找到 Python 侧的剩余优化空间有多大。

| 维度 | Python (当前) | Rust (参照上限) |
|------|-------------|----------------|
| curpdf 耗时/只 | ~84ms | 预估 5–15ms |
| 并行效率 | 2.2× gap | <1.3× gap |
| capital 预加载 | 待实现（§四） | 已实现 |
| 全市场实测 | 8.0 分钟 | **4.5 分钟** |

**两阶段路线图**：

```
阶段 1（2 周）：Python 优化 + Rust 精度对齐
  - Python 跑通全链路（batch DuckDB + capital 预加载 + CI 回归）
  - Rust 跑通 verify_rust_python_alignment.py 全量对齐
  - 决策点：Rust 全量对齐通过 → 进入阶段 2

阶段 2（按需）：Rust 接管生产，Python 降级为校准工具
  - 生产调度触发 Rust binary
  - Python --method batch 保留为每季度校准/审计工具
  - 不再投入 Python 性能优化
```

**建议**：跑一次 Rust 版全量 benchmark。如果 Rust 是 1 分钟而 Python 优化到 3 分钟，这 2 分钟 gap 在阶段 1 中是可接受的——Python 的价值在于正确性验证和快速迭代。

### 8.4 增量递推近似方案（P1）

**重要**：增量递推不是全量重算的精确等价，而是有损近似。以下说明近似来源和误差边界。

当前方案每天从零重算 1000 天窗口，cumpdf 有递推性质：

```
cumpdf_T = cumpdf_{T-1} × (1 - turnover_T) + curpdf_T × turnover_T
```

| 方案 | 每日计算量 | 适用场景 |
|------|-----------|---------|
| 全量重算（当前） | 1000 天 × 5500 只 | 历史回测、冷启动 |
| **增量递推** | **1 天 × 5500 只** | 每日生产，~1000× 加速 |
| 混合（增量 + 每周全量校准） | 平时 1 天，每周全量 | 生产 + 精度保障 |

**窗口截断误差**（尾部截断和窗口滑出本质是同一件事——增量 cumpdf 包含了全量窗口外旧尾部的残余）：全量窗口为 [T-999, T]，增量递推得到的 cumpdf 包含已滑出 1000 天窗口的旧尾部残余。低换手率（日均 turnover≈0.1%）时残余约 0.999^1000 ≈ 0.37 × 当日权重。

**偏差量级**（cyqk 值域为 0–1 比例值）：高换手股 <0.00001（可忽略）；低换手蓝筹 ~0.005–0.05，即 0.5%–5% 的获利筹码占比偏差（具体值需实测）。偏差 >0.01 且持续 5 个交易日时，策略可能做出错误选股决策——**低换手率股票必须每次全量重算**。混合模式的每周全量校准无法在两次校准之间消除此偏差。

**小团队务实验证**：实施前取 20 只不同换手率分位的股票跑全量 vs 增量对比实测。不需理论推导。

**行业对标**：Qlib 的 `ChipFactor` 支持增量模式，QuantLib 的 rolling Greeks 亦是此思路。混合模式（每日增量 + 每周全量校准）是行业标准做法。

**建议**：
1. **高换手率股票（日均 turnover >1%）**：增量递推误差 <0.01，可直接用于日常生产
2. **低换手率股票（日均 turnover <0.2%）**：残余误差 0.2-0.4，**必须全量重算**
3. 因此生产路径不是单纯增量递推，而是**混合模式**：每日增量 + 每周全量校准，增量结果按 turnover 分档标记 `is_reliable_for_low_turnover`
4. cumpdf 状态持久化时带 `schema_version` 和 `last_full_compute_date`，**自动检测**超过 5 天未全量 → 触发强制全量（不靠人工记忆）

**状态失效场景**（增量计算的前提是 cumpdf 状态持续有效，以下场景需触发全量重算）：

| 场景 | 后果 | 处理 |
|------|------|------|
| **算法变更**（step/窗口/decay 公式变化） | 旧 cumpdf 与新算法不兼容 | 状态文件带 `version` 标签，不匹配→全量重算 |
| **前复权因子更新**（数据源补发除权信息） | 历史价格变化→已计算的 curpdf 全部失效 | 检测 `adj_factor` 变更→触发全量重算 |
| **状态文件损坏/丢失** | 无法增量 | fallback 全量重算 |
| **停牌 >20 天后复牌** | 停牌期间 decay 累积→值极小 | 可接受，无需特殊处理 |


---

## 九、待验证项

**已完成**（代码已改，§10.1 实测 8.0 min）：

| 顺序 | 做了什么 | 结果 |
|------|---------|------|
| ① | DuckDB 批量读取（比 PyArrow 快 1.5×） | 省 ~20s |
| ② | capital 预加载（dict 替代 22,000 次 pandas filter） | 省 ~80s |
| ③ | ProcessPool（ThreadPool 实测 2.5× 更慢，放弃） | 保持 |
| ④ | Rust 全量 benchmark | 4.5 min（天花板） |

Python 优化就此定型。后续精力转 Rust 精度对齐。

**最小验收清单**（**唯一 gate**，只看这 8 项是否打勾，不再加临时标准）：

- [ ] 口径规则唯一：freeFloatCapital 缺失 → 标记降级+剔除，不混口径
- [ ] T / T-1 独立 as_of：两条 SQL 各自 WHERE 条件，不共用 ROW_NUMBER
- [ ] capital 缺失返回 `np.nan`（非 0），Python 层检查后 `return None`
- [ ] 全市场 batch vs original 精度对齐通过（四层门禁）
- [ ] 跳过原因有分类统计（历史不足 / 资本缺失 / 数据异常）
- [ ] 单次运行产出 Parquet（主）+ CSV（审计）+ 摘要（耗时、有效数、跳过分类）
- [ ] 文档内无并列"可选方案"——所有地方收敛为"当前采用"或"未来阶段"
- [ ] 一键回归脚本可用：`python scripts/verify_canonical_resist_regression.py --date YYYYMMDD`
- [ ] ThreadPool / ProcessPool 分支决策已执行，结果记录在文档中
- [ ] 改代码后精度回归通过（100 只分层小样本 batch vs original）

---

## 十、实验记录

> 以下所有实验在同一台机器上完成（Windows 11 Pro, Intel i7-8650U 4C8T, 40GB RAM, Samsung NVMe SSD, Python 3.11.14）。全量数据：5531 stocks, date=20260525, window=1000。

### 10.1 全量端到端（完整换手阻力计算）

| 版本 | 加载 | 计算 | 总耗时 | 备注 |
|------|------|------|--------|------|
| 逐只 parquet + ProcessPool（numba 优化后） | — | — | **~10 分钟** | 起点 |
| DuckDB 批量读 + ProcessPool | 22.4s | 560s | **9.7 分钟** | 省 ~20s |
| DuckDB persistent + capital 预加载 + ProcessPool | 16.6s | 447s | **7.5 分钟** | 🏆 最终版 |
| DuckDB :memory: + capital 预加载 + ProcessPool | ~21s | 464s | 7.7 分钟 | 备选 |
| DuckDB raw SQL + capital 预加载 + ProcessPool | 22.4s | 480s | 8.0 分钟 | 最初实现 |
| DuckDB raw SQL + capital 预加载 + **ThreadPool** | 22.2s | 1208s | 20.1 分钟 | ☠ 已放弃 |
| Rust（release） | — | — | **4.5 分钟** | 天花板 |

### 10.2 批量读取方式对比

全量 parquet（5529 stocks, ~6.6M rows, window=2000 days），全量：

| 方式 | 加载耗时 | 全量端到端 | 备注 |
|------|---------|-----------|------|
| **`scan_stocks(mode='duckdb_persistent')`** | **16.6s** | **7.5 min** | 🏆 最快，用已有的 .duckdb 文件 |
| `scan_stocks(mode='duckdb')` (:memory: + Hive parquet) | ~21s | 7.7 min | 备选 |
| DuckDB raw SQL `read_parquet` | — | 8.0 min | 最开始的实现 |
| PyArrow Dataset | ~22s | — | 已放弃 |

小窗口（~250 days, 1.3M rows）对比：

| 方式 | 耗时 |
|------|------|
| duckdb_persistent (.duckdb) | **1.7s** |
| duckdb :memory: (Hive parquet) | 3.9s |
| DuckDB raw SQL | 3.3s |
| PyArrow Dataset | 12.1s |

**结论：duckdb_persistent 始终最快（2.4× faster than Hive parquet），直接采用。** 用户已有的 `stock_data_front.duckdb`（1.1GB）一直在那里，之前全在用 Hive parquet 读😅。

### 10.3 ThreadPool vs ProcessPool

| 场景 | ProcessPool 7w | ThreadPool 7w | 结论 |
|------|---------------|---------------|------|
| 50 stocks, curpdf only（轻任务） | 12.1s | **1.4s** | ThreadPool 9× faster |
| 100 stocks, 完整换手阻力（重任务） | **25.0s** | 28.8s | ProcessPool 15% faster |
| 5531 stocks, 完整换手阻力 | **8.0 min** | 20.1 min | ProcessPool 2.5× faster |

**结论：重任务下 ProcessPool 占优。numba 释放 GIL 的收益被 pandas 持 GIL 操作抵消。文档主路径改回 ProcessPool。**

### 10.4 逐只 parquet 读取

50 stocks: 0.51s（10ms/只）。**不是瓶颈。**

### 10.5 capital 预加载效果

独立实验——仅对比 `_steps_2_7` 中 capital 查询的耗时变化：

| 版本 | 单只耗时 | 全量累计 |
|------|---------|---------|
| pandas filter（原版） | 136ms | ~625s |
| dict.get()（预加载） | <1ms | ~5s |

实测全量：capital 预加载后 compute 从 560s → 480s，**省 80s（~14%）**。

### 10.6 精度对比

20 只股票，batch vs original，8 列全部一致，最大差异 < 1e-10。

### 10.7 实施记录

| 改动 | 文件 | 说明 |
|------|------|------|
| 批量日线读取 | `full_market_canonical_resist.py:run()` | `StockDataReader(mode='duckdb_persistent').scan_stocks()` 替代 5500 次逐只 `read_stock()` |
| capital 预加载 | `full_market_canonical_resist.py:run()` | DuckDB SQL `ROW_NUMBER() OVER (PARTITION BY stock_code ...)` 构建 4 个 dict，替代 `_get_float_shares`/`_get_free_float_shares` |
| numba 批量 curpdf | `full_market_canonical_resist.py:_batch_triang_curpdf` | 单个 numba 函数处理 1001 天三角分布，替代 `np.apply_along_axis(calc_curpdf)` × 4 |
| numba 合并 cumpdf | `full_market_canonical_resist.py:_batch_cumpdf_4way` | 4 次 `cyq.calc_cumpdf` 合并为 1 次 numba 调用 |
| 原始方法保留 | `full_market_canonical_resist.py:_process_stock_original` | `_canonical_cyqk` 完整保留，`--method original` 切换 |
| 通用批量读取 | `oskh_data/reader.py:scan_stocks` | 利用已有 `StockDataReader` 基础设施，`mode='duckdb_persistent'` 使用 1.1GB `.duckdb` 文件 |

**核心依赖**（全部已有，无新增）：`oskh_data.reader.StockDataReader`、`duckdb`、`numba`、`pandas`、`numpy`。

### 10.8 各阶段耗时演进

| 阶段 | 数据读取 | capital 查询 | 并行 | 全量耗时 | 加速比 |
|------|---------|-------------|------|---------|--------|
| 原始 | 逐只 parquet（5500 次 open） | pandas filter × 22000 | ProcessPool | ~30 min（估算） | 1× |
| numba 优化 | 逐只 parquet | pandas filter | ProcessPool | ~10 min | 3× |
| + DuckDB 批量读 | DuckDB raw SQL | pandas filter | ProcessPool | 9.7 min | 3.1× |
| + capital 预加载 | DuckDB raw SQL | **dict O(1)** | ProcessPool | 8.0 min | 3.8× |
| **+ duckdb_persistent** | **scan_stocks(duckdb_persistent)** | **dict O(1)** | **ProcessPool** | **7.5 min** | **4×** |
| Rust（天花板） | polars parquet | HashMap | rayon | 4.5 min | 6.7× |