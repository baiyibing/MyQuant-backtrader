# 分钟线数据补录性能优化方案

**文档编号**: PLAN-2026-0528-001  
**日期**: 2026-05-28  
**状态**: ✅ 已实施（§3.4 Gate 决策通过，切 :memory: + read_parquet(glob)，§4-§6 方案作废）  
**实施日期**: 2026-05-28


## 目录

- [1. 执行摘要](#1-执行摘要)

  - [1.5 小团队裁剪原则](#15-小团队裁剪原则)

  - [1.6 实施后目标状态（P0 + P1 落地后 3 个月内）](#16-实施后目标状态p0-p1-落地后-3-个月内)

  - [1.7 黄金准则级防护（高于所有优化）](#17-黄金准则级防护高于所有优化)

- [2. 现状与耗时分析](#2-现状与耗时分析)

  - [2.1 数据规模](#21-数据规模)

  - [2.2 当前流程与耗时（2026-05-28 实测）](#22-当前流程与耗时2026-05-28-实测)

  - [2.3 当前增量策略](#23-当前增量策略)

  - [2.4 "处理股票数据" 逐只耗时拆解](#24-处理股票数据-逐只耗时拆解)

  - [2.5 A 股特有风险与防护](#25-a-股特有风险与防护)

  - [3.1 第一层：Parquet 不可追加 → 逐只全量重写](#31-第一层parquet-不可追加-逐只全量重写)

  - [3.2 第二层：DuckDB 全量重建](#32-第二层duckdb-全量重建)

  - [3.3 第三层：已有增量过滤未充分利用](#33-第三层已有增量过滤未充分利用)

  - [3.4 架构决策 Gate：是否必须维护持久化 .duckdb 文件？（实施前必须通过）](#34-架构决策-gate是否必须维护持久化-duckdb-文件实施前必须通过)

- [4. 优化方案](#4-优化方案)

  - [方案 A'：全量 read_parquet(glob) + 只加索引（最简折中，20 行代码）](#方案-a全量-read_parquetglob-只加索引最简折中20-行代码)

  - [方案 A：DuckDB 增量 INSERT（高级选项，仅当方案 A' 的 ~100s rebuild 不可接受时）](#方案-aduckdb-增量-insert高级选项仅当方案-a-的-100s-rebuild-不可接受)

  - [方案 B：Parquet 按月分区 + DuckDB 合并（P1，根治下载阶段 IO）](#方案-bparquet-按月分区-duckdb-合并p1根治下载阶段-io)

  - [方案 C：追加路径跳过 CPU 冗余操作（不独立排期，已并入方案 B）](#方案-c追加路径跳过-cpu-冗余操作不独立排期已并入方案-b)

  - [不做的事：为什么我们不把权威源迁到 DuckDB（原方案 D）](#不做的事为什么我们不把权威源迁到-duckdb原方案-d)

- [5. 实施建议](#5-实施建议)

  - [5.1 优先级与排期（工时估算；执行步骤详见 §6.8）](#51-优先级与排期工时估算执行步骤详见-68)

  - [5.2 验收标准](#52-验收标准)

  - [5.3 回滚策略](#53-回滚策略)

  - [5.4 监控与告警（方案 A/B 上线后必装）](#54-监控与告警方案-ab-上线后必装)

- [6. 关键工程考量补充](#6-关键工程考量补充)

  - [6.1 Parquet 不可追加——理解 IO 瓶颈的本质](#61-parquet-不可追加理解-io-瓶颈的本质)

  - [6.2 当前下载流程中不被方案 A 影响的关键步骤](#62-当前下载流程中不被方案-a-影响的关键步骤)

  - [6.3 方案 A 中 staging → atomic switch 保持崩溃安全](#63-方案-a-中-staging-atomic-switch-保持崩溃安全)

  - [6.4 方案 B 文件数爆炸与文件系统限制](#64-方案-b-文件数爆炸与文件系统限制)


> **实施后注记**：经 §3.4 Gate 决策——NVMe 实测 parquet I/O 仅 118ms/只（§2.4 高估 25-30×），`:memory:` 启动 1.0s。**切 :memory: + read_parquet(glob)，删 `stock_data_minute.duckdb`（释放 17 GB），本文档 §4-§6 方案全部作废。** 代码改动 ~20 行，半天完成。

**关联文档**:
- `docs/prompts/prompt-stock-data-minute-backfill-sync-workflow.md`（分钟线补录工作流）
- `docs/backtest/data/parquet_duckdb_dual_mode_reader_plan.md`（Parquet + DuckDB 双模式方案）
- `docs/backtest/data/daily_data_backfill_summary.md`（日线补录与增量更新）

---

## 1. 执行摘要

当前分钟线全市场（~5,500 只）增量更新到最新交易日，总耗时约 **6–10 小时**（下载 4–6h + rebuild 9min），导致日常运维效率极低。

**核心结论**：瓶颈不在 QMT 下载，也不在 DuckDB rebuild 本身，而在**逐只 parquet 的重复全量读写**——Parquet 是**不可追加的列存格式**，每天只新增 ~240 根 bar/只，却要读全文件再写全文件。

**推荐方案**：

| 优先级 | 方案 | 改动量 | 预期收益 | 风险 |
|--------|------|--------|----------|------|
| **P0** | DuckDB 增量 INSERT（替代全量 rebuild） | ~150 行 + 前置修复 | Rebuild 从 546s → ~10–30s | 中（需处理 schema 一致性、原子性、崩溃恢复、read_only 审计） |
| **P1** | Parquet **按月** Hive 分区 + DuckDB 合并 | ~200 行 + 消费者迁移 + 审计脚本 | 根治下载 IO：月内追加 3s/只 → 0.5s/只（IO 缩小 16×），全市场 ~6-10h → ~1.5-2.5h | 中（消费者盘点、双写过渡期、row group benchmark） |
| **P2** | 追加路径跳过 CPU 冗余 | ~10 行 | 微优化：~100ms CPU / 只（端到端 ~3%） | 极低（仅当 P1 不实施时保留） |

**关键设计决策**（详见 §4 方案 B）：
- **分区粒度**：**按月**（非按天）。按天 = 138 万文件；按月 = 6.6 万文件，月内重写 ~5000 行代价 ~0.5s
- **分区方式**：**Hive 目录**（非文件名）。DuckDB `hive_partitioning` 原生支持，与项目现有 `period=*/symbol=*` 约定一致
- **合并引擎**：月内追加用 **DuckDB SQL**（非 pandas）。`UNION ALL + QUALIFY ROW_NUMBER() + src` 显式优先级去重，全部向量化 C++ 执行
- **Parquet 保留**：作为 source of truth + 冷备份；DuckDB 作为日常查询加速层。两格式各司其职，不互相替代

**注意**：原始分析将跳过 sort/去重的收益高估为 3–5×（混淆了 IO 和 CPU 瓶颈）。逐只耗时拆解（§2.4）表明 IO 占 ~85%，CPU 仅 ~3%，跳过 sort 节省 ~100ms/只，端到端几无变化。真正的高收益来自：① DuckDB 增量（省 546s 全量扫描）；② 按月分区（根治逐只全量 IO 重写）。

**不实施的代价（线性外推锚点）**：每交易日新增 ~132 万行 / ~60 MB parquet + ~70 MB DuckDB；一年约 **+240 个交易日**，分钟线总规模将从当前 1.65 亿行 / 6 GB 增长到约 **4.8 亿行 / ~20 GB**。在当前全量 rebuild 架构下：
- DuckDB rebuild 耗时与数据量近线性，预计 546s → **~1600s（约 27 分钟/次）**
- 逐只 parquet 读写：单只历史行数从 8 万增长到 ~16 万，单文件处理 ~3s → ~6s，下载阶段进一步恶化
- 磁盘：年度 ~20 GB，当前 33 GB 余量在不做冷备轮转的前提下 **约可维持 1.5 年**

该外推用于优先级判断，不作为性能承诺。

### 1.5 小团队裁剪原则

本文档完整版（4 方案、7 监控指标、4–6 周双写、季度灾备演练等）面向工程完备性。2–4 人团队须按以下黄金准则裁剪——**有限精力必须压在"会亏大钱"和"不可逆出错"的事上**：

| 维度 | 黄金准则 | 本文档完整版 | 小团队裁剪 |
|------|---------|-------------|-----------|
| 数据正确性（OHLCV parity） | 不可妥协 | ✅ 三种崩溃注入 + OHLCV 逐行比对 | 保持（会亏大钱） |
| 回滚能力 | 一行命令可回滚 | ⚠️ §5.3 有表但步骤多 | **补"一键 emergency exit"脚本**（§5.3） |
| 监控 | 1–2 个核心指标 | ❌ 7 个指标 | **收敛到 2 核心 + 2 可选**（§5.4） |
| 双写审计 | 跑回测比对就够 | ❌ 2–4 周 + 每日差异告警 | **1 周 + 3 次回测 baseline 比对**（§4.13.2） |
| 灾备演练 | 半年一次足够 | ❌ 季度 + 首次演练前置 | **半年一次，首次保留**（§4.19.2） |
| 方案 D（权威源迁移） | 小团队不做 | ⚠️ 仍保留为 P3 | **砍掉**（明确为"§4.17 不做的事"） |
| 方案 C（CPU 微优化） | ROI 接近零 | P2 | **删除**（方案 B 落地后无意义） |
| backfill 运行时间窗 | 实盘不能被拖死 | ❌ 未定义 | **交易日 15:30 之后 / 9:00 之前**（§2.5） |

### 1.6 实施后目标状态（P0 + P1 落地后 3 个月内）

| 指标 | 目标值 |
|------|--------|
| 日常分钟线全市场更新到最新交易日 | ≤ 3 小时（下载 + DuckDB 同步） |
| DuckDB 同步耗时 | ≤ 30s（增量，替代 546s 全量） |
| 数据正确性 gate 失败率 | < 0.1%（1000 次 backfill < 1 次） |
| 年度全量 rebuild 次数 | ≤ 12 次（月度 compaction） |
| 运维人力 | < 30 分钟/周（不含异常处理） |

### 1.7 黄金准则级防护（高于所有优化）

**backfill 运行时间窗 gate**：A 股交易日 9:15–15:15 期间跑 backfill 会与实盘路径抢 QMT 资源（实测可造成实盘心跳超时）。**完整规格见 §2.5.2**（含启动期 gate + 运行期 graceful exit，必须成对交付）。

**QMT 客户端升级回归**：miniQMT 由券商控制升级节奏，每次升级后字段语义/复权算法/bar 切分规则可能静默改变。维护 checklist（1 页纸，归档到 `docs/run-records/_qmt_upgrade_YYYY-MM-DD.md`）：
1. 5 只基准股 OHLCV 与升级前快照逐行比对
2. `close × volume / amount` 检查（应接近 1，偏离 > 10% 告警——防止单位静默变更）
3. 分钟线 bar 时间戳分布比对（9:30 包含否 / 14:57 独立否 / 半日市）
4. 下游因子（RSRS / 筹码分布）输出比对



---

## 2. 现状与耗时分析

### 2.1 数据规模

| 指标 | 数值 |
|------|------|
| 股票总数 | ~5,548 只（沪深京A股） |
| 历史起点 | 2025-01-01 |
| 分钟线总数据量 | ~1.65 亿行 |
| Parquet 总大小 | ~6 GB |
| DuckDB 大小 | ~6.3 GB（膨胀 1.29×） |
| 单只历史长度 | 3–8 万行（取决于上市日期） |
| 每日新增/只 | ~240 根 bar（4 小时交易 × 60 分钟；实际中位数 ~230，含停牌 0、半日市 ~120、9:30/14:57 切分差异） |
| 每日新增总量 | ~132 万行（以活跃股数 × 实际交易分钟数计；停牌/退市股排除后活跃股数 ≈ 5,200–5,400） |

### 2.2 当前流程与耗时（2026-05-28 实测）

```
Step 1: 生成代码列表          → ~1 分钟
Step 2: download --period 1m  → ~6–10 小时（瓶颈）
  ├─ QMT 下载 100 只/批       → ~3 分钟/批
  └─ 处理股票数据（写parquet） → ~5–7 分钟/批  ← 🔴 最大瓶颈
Step 3: rebuild --period 1m   → ~546s（~9 分钟）
```

**实测批次时间线**（2026-05-28 05:45 启动）：

| 批次 | 下载完成 | 处理完成 | 批次耗时 |
|------|---------|---------|---------|
| 第 1 批 | 05:47 | 06:01 | ~14 分钟 |
| 第 2 批 | 06:04 | 06:15 | ~13 分钟 |
| 第 3 批 | 06:15 | 06:34 | ~19 分钟 |
| 第 4 批 | 06:34 | ... | 进行中 |

**累计完成**：800 只 / 5,548 只（~14%），预计总耗时 **10–11 小时**。

### 2.3 当前增量策略

源码：`oskh_data/downloader.py:358-377`（`_filter_incremental`）

- 已有数据最新日期 `<` 目标截止日期 → 加入下载列表
- 已有数据 `>=` 目标日期 → 跳过

写入策略：`oskh_data/downloader.py:474-477`

```python
df_merged = pd.concat([df_existing, df_new])
df_merged = df_merged[~df_merged.index.duplicated(keep='last')]
df_merged = df_merged.sort_index()
df_merged.to_parquet(file_path)
```

- **追加合并**：新旧数据 `concat` 后按时间索引去重，`keep='last'` 保留新数据。**注意**：miniQMT 的 `download_history_data` 返回的是**全量时间窗数据**（非增量 delta）——若某只股票在 QMT 侧已有完整历史，返回的是完整 DataFrame。`pd.concat([existing, new])` 本质是"用新全量覆盖旧全量"，不是"追加新行"。`append-only` 假设在 QMT 数据修正场景（停牌复牌、除权回补、节假日修正）下不成立
- **Schema 门闸**：列名/dtype/index 类型不一致时全量覆盖

**硬件对 IO 瓶颈的影响**（实施前必测）：将 `stock_data/` 复制到 NVMe SSD 分区后跑 benchmark：

```bash
# 100 只测试集
python -m oskh_data.backfill download --period 1m \
  --codes tests/fixtures/bench_100_codes.txt --start 20250101 --end 20260527
```

如果 NVMe 下单批写入 < 2 分钟（当前 SATA SSD 下 ~5-7 min）→ 方案 B（按月分区）的全部工程投入不值得。硬件升级（1TB NVMe ¥400-600）是 ROI 最高的"优化"。

#### 2.3.1 已知缺陷：progress 文件非原子写入

源码：`oskh_data/backfill.py`（`_save_progress("1m", done)` / `_load_progress("1m")`）

```python
# 当前实现（示意）：
def _save_progress(period: str, done: Set[str]) -> None:
    with open(_progress_path(period), "w", encoding="utf-8") as f:
        json.dump(sorted(done), f)  # ← 直接覆盖，非原子
```

**风险**：崩溃发生在 `json.dump` 写入过程中时，progress 文件可能只剩半截（不是合法 JSON），导致下次启动 `_load_progress` 抛 `JSONDecodeError`、整个断点续传失效、或更糟：读到部分集合 → 部分股票被重复下载、部分被漏掉。

**当前影响面**：仅分钟线批次（每批完成后 `_save_progress` 一次）；若某批中途崩溃，整批重跑即可，影响有限。

**方案 A / B 下的放大效应**：
- 方案 A 引入 DuckDB staging 写入，progress 推进时机须与 staging INSERT **严格顺序化**（先 DB 后 progress，或反过来），否则 progress 显示 done 但 DB 缺行、或反之
- 方案 B 下 progress 还要协调 parquet 月分区文件与 DuckDB 两路写入，不一致窗口更大

**建议修复（与 P0 同批次合入）**：

```python
def _save_progress(period: str, done: Set[str]) -> None:
    path = _progress_path(period)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(done), f)
        f.flush()
        os.fsync(f.fileno())  # 确保落盘
    os.replace(tmp, path)      # 原子切换
```

> **更简方案**：项目已有 SQLite 依赖（`ops_scheduler_state.db`），用 SQLite 事务替代 JSON 原子写入更简洁——`BEGIN; DELETE+INSERT; COMMIT` 天然原子，支持增量更新，无需 `tmp + os.replace`。若团队偏好 SQLite，此修复可简化为 3 行。

### 2.4 "处理股票数据" 逐只耗时拆解

以单只已有 8 万行历史数据的股票为例（每批 100 只）：

```
① pd.read_parquet(file_path)          ~1.0–1.5s   ← IO（读全文件）
② pd.concat([df_existing, df_new])    ~0.05s      ← 内存拷贝
③ normalize_schema(df_existing)       ~0.1s       ← 列名/dtype 归一化
④ schema gate checks (dtype compare)  ~0.02s      ← 校验
⑤ index.duplicated(keep='last')       ~0.05s      ← CPU（8 万行去重）
⑥ sort_index()                        ~0.05s      ← CPU（8 万行排序）
⑦ to_parquet(file_path, snappy)       ~1.0–1.5s   ← IO + snappy 压缩写全文件
────────────────────────────────────────────────
单只合计                              ~2.5–3.5s
× 100 只                              ~4–6 分钟
```

> **关键发现**：IO（① + ⑦）占总耗时的 **~85%**，CPU（⑤ + ⑥）仅占 **~3%**。任何跳过 CPU 操作的优化对总耗时影响极小。

### 2.5 A 股特有风险与防护

#### 2.5.1 停牌 / 退市 / 北交所新股

- **停牌股**：QMT 返回空或最后交易日数据，当前 `_filter_incremental` 会反复把它加入下载列表（最新日期 < 目标日期），每天浪费 1 次请求。100 只/批 × 长期停牌 ~50 只 ≈ 50% 无效流量
- **退市股**：5,500 只里每年约 50–80 只退市，历史数据永远停更，但 rebuild 仍要扫描其 parquet
- **北交所新股**：上市首日只有半天，240 bar/天的假设不成立

**缓解**：
- 维护 `stock_data/.retired_codes.json`（每月更新）：退市 + 长期停牌（> 60 交易日无新数据）的代码，增量下载与 rebuild 均跳过。**复活机制**：每月更新时对标记为"长期停牌"的 code 发一次 QMT 查询——若有新数据则自动移出 retired 集合；若仍无数据则保持 retired。退市 code 永久 retired，不复活
- §5.4 监控阈值使用"活跃股数 × 实际交易分钟数"而非固定 132 万

#### 2.5.2 Backfill 运行时间窗 Gate（黄金准则级）

A 股交易日 9:15–15:15 期间 miniQMT 的分钟线 push 是高频的，同期跑 backfill 会与实盘路径抢 QMT 资源（**实测可造成实盘心跳超时 → 亏大钱**）。文档内所有优化都不及此防护重要。

**强制约束**（启动期 gate + 运行期 graceful exit，必须成对交付）：

1. **启动期 gate**（`backfill.py` 启动时检查，违反即拒绝启动）：
   - 交易日 15:30 之后 / 9:00 之前 允许
   - 非交易日任意时间 允许
   - 判断逻辑复用 `oskh_core/trading_calendar_resolve.py`

2. **运行期 graceful exit**（批次循环内检查，防止跨夜撞开盘）：
   - 6–10h 全量 backfill 在 15:30 启动，次日 9:15 仍在跑 → 撞上开盘 miniQMT 高频 push
   - 启动期 gate 无法阻止已在跑的进程——必须加运行期检查
   ```python
   for idx, batch in enumerate(batches):
       if _approaching_market_open(threshold_min=30):
           logger.warning("Approaching market open, graceful exit after this batch")
           _save_progress(...)
           return  # 保留 progress，下次从断点继续
       ...
   ```
   - `_approaching_market_open(threshold_min=30)`：判断当前时间距离下一个交易日 9:15 < 30 min 则返回 True，非交易日永远返回 False

#### 2.5.3 QMT 静默字段变更 / 数据漂移

miniQMT 版本升级（券商不定期推送）会静默改变：
- `xtdata.download_history_data` 返回的列序
- 复权算法（前复权基准切换）
- 分钟线 bar 切分规则（9:30 是否包含 / 14:57 是否独立）

版本级漂移比日内修正更危险：某次 QMT 升级后 `amount` 单位从"元"变"万元"，COUNT 和行数全部正确，但下游因子计算全部错误 100×。

**缓解**（§1.6 QMT 升级回归 checklist 已定义）：
- 每次 backfill 结束后，对 5 只基准股算 `close × volume / amount`（应接近 1，单位一致），偏离 > 10% 告警
- 每次 QMT 客户端/xtquant 升级后，强制跑一次全量 parity（与升级前快照比对）

---

### 3.1 第一层：Parquet 不可追加 → 逐只全量重写

**这是根本原因**。Parquet 是**不可变列存格式**——不存在 "append to existing parquet file" 操作。要往已有 parquet 文件加数据，唯一方法是：读全文件 → 在内存中合并 → 写全文件。

**以 000001.SZ 为例**：
- 历史数据：2025-01-01 ~ 2026-05-26，约 **8 万行**（~800 KB）
- 每日新增：2026-05-27，约 **240 行**（~3 KB）
- 当前做法：读取 800 KB → 合并 → 去重 → 排序 → 压缩写回 ~803 KB
- **I/O 放大比**：3 KB 新增有效数据 / 803 KB 读写总量 ≈ **0.4%**
- **CPU 放大比**：sort_index/duplicated 在 8 万行上 ~100ms，非瓶颈

**乘以 5,500 只**：这就是"处理股票数据"阶段需要 5–7 分钟/批的根本原因。**但瓶颈是 IO，不是 CPU**。

### 3.2 第二层：DuckDB 全量重建

**问题**：`rebuild --period 1m` 执行 `StockDataReader.build_persistent_db()`（`oskh_data/reader.py:440-489`），逻辑为：

1. `_validate_parquet_schema_consistency` — 全量 schema 校验
2. `read_parquet(glob, hive_partitioning=1)` — 扫描全部 5,551 只 parquet 读入 DuckDB staging
3. symbol 下划线→点修正
4. 创建索引 `idx_symbol`
5. `os.replace` 原子切换 + 旧版本备份

**耗时**：~546s（文档 `parquet_duckdb_dual_mode_reader_plan.md` §10 实测）

**浪费**：每天只新增 **132 万行**（~0.8%），却扫描并重写全部 **1.65 亿行**。

**但当前架构的优点不可忽视**：
- Staging → atomic switch 提供崩溃安全
- 全量重建天然消除任何数据漂移/重复
- `_validate_parquet_schema_consistency` 是重要的数据质量门闸

#### 3.2.1 DuckDB 并发读写模型（方案 A/B 的前置约束）

DuckDB 是**单写者、多读者**模型（与 SQLite 类似但更严格）：

- **写者持 exclusive lock**：写入期间所有读者会立即得到 `IOException: Could not set lock on file` 或 `CatalogException: Database is locked`（默认不 block、不 retry）
- **WAL 模式**（`PRAGMA enable_checkpoint_on_shutdown=false` + 显式 `CHECKPOINT`）可让读者在写者活跃时继续读旧版本，但文件体积膨胀更快
- **`read_only=True` 连接**：读者端用 `read_only=True` 打开可避免锁冲突，但仍受写者 exclusive lock 影响（取决于版本与 locking mode）
- **`os.replace` 切换**：在 Windows/NTFS 上，`os.replace(src, dst)` 原子替换 dst 文件。已打开旧文件的读者继续读旧 inode（Windows：旧文件句柄持有原数据），新打开者读到新文件。DuckDB 不像 SQLite 那样有 `.db-wal` 副作用，切换本身对读端透明

**当前项目内的相关进程**：
- `live_trading` / `executor_stream` / `stream_monitor` 在实盘中可能同时持有 `StockDataReader` 的 DuckDB 连接
- `backtest/` 下大量脚本通过 `StockDataReader` 读 parquet 或 duckdb
- `backfill.py` 作为 CLI 工具，与上述进程可能并发运行

**方案 A 的关键约束**：增量 INSERT 期间**不能有任何读者打开 staging 文件**（staging 是独立文件，不影响 main DB，故满足）；`os.replace` 切换瞬间读者仍读旧 DB（满足）。但 main DB 切换后若有读者立即打开，必须使用 `read_only=True` 避免与后续 `backfill.py` 再次增量 INSERT 时的锁冲突。该约束当前**未在 StockDataReader 中显式声明**——需在方案 A 落地时盘点所有 `duckdb.connect(...)` 调用点，确认 `read_only` 参数已正确设置。

### 3.3 第三层：已有增量过滤未充分利用

`_filter_incremental`（`downloader.py:358-378`）已经实现了按股票粒度的增量判断——数据已到截止日期的股票会被跳过。但这只在"部分股票落后"的场景有效。对于首次全量回补或全市场落后 N 天的情况，所有股票都需要更新，过滤无效。

### 3.4 架构决策 Gate：是否必须维护持久化 .duckdb 文件？（实施前必须通过）

**本文档所有方案（P0/P1/B'）都假设 `stock_data_minute.duckdb` 持久化文件必须存在。这个假设本身需要先被验证。**

#### 替代架构 A：放弃 .duckdb 持久化，全面切 `:memory:` + `read_parquet(glob)`

DuckDB 官方推荐的小团队用法：

```python
con = duckdb.connect(":memory:")
con.execute("""
    CREATE VIEW stock_data AS
    SELECT * FROM read_parquet(
        'stock_data/period=1m/dividend_type=none/symbol=*/data.parquet',
        hive_partitioning=1, union_by_name=True)
""")
# 查询时自动解析 parquet footer，按需读取；进程结束自动释放
con.execute("SELECT * FROM stock_data WHERE symbol = '000001.SZ' AND time BETWEEN ...")
```

| 维度 | 持久化 .duckdb（当前） | :memory: + read_parquet(glob)（替代） |
|------|----------------------|--------------------------------------|
| Rebuild 耗时 | 546s（全量）/ 需增量 INSERT 工程 | **0**（parquet 更新后立即可见） |
| 数据一致性风险 | parquet vs DuckDB 双源，需 OHLCV parity 检查 | **零**（永远只有一个数据源：parquet） |
| 锁冲突 | 需 read_only 审计、staging 隔离 | **零**（每个进程独立 :memory: 连接） |
| 磁盘 | 6.3 GB .duckdb | **0**（省 6.3 GB） |
| 启动开销 | 0（文件已存在） | ~1-2s（扫描 5,551 个 parquet footer） |
| 单股点查 | < 10ms（索引命中） | ~50-100ms（首次需读 parquet row group） |
| 全市场扫描 | < 1s（列存索引） | ~2-5s（每次需扫描全部 parquet） |
| 工程复杂度 | P0 150 行 + 4 阻塞项 + P1 200 行 | **0 行**（删除 rebuild 逻辑即可） |

**决策标准**：
- 如果查询延迟要求 < 10ms（如实盘策略每 tick 查分钟线）→ 保留 .duckdb，继续读 §4
- 如果查询延迟容忍 50-100ms（回测、盘后分析）→ **直接切 :memory:，本文档余下内容全部不需要**
- 如果全市场扫描频率高（每天 > 10 次）→ 保留 .duckdb（列存索引优势明显）
- 如果全市场扫描频率低（每天 1-2 次）→ :memory: 的 2-5s 完全可接受

#### 替代架构 B：硬件升级优先于软件复杂度

当前 §2.4 拆解的 "1.0-1.5s/只 parquet 读写" 瓶颈，在 NVMe SSD 上实测通常 < 200ms。投入 ¥400-600（1TB NVMe）可换来的收益：

| 指标 | SATA SSD（当前假设） | NVMe SSD | 无需改代码 |
|------|---------------------|----------|-----------|
| 单只 parquet 读写 | ~3s | **~0.5s** | ✅ |
| 单批 100 只写入 | ~5-7 min | **~1-2 min** | ✅ |
| 全市场下载 | ~6-10h | **~2-3h** | ✅ |
| DuckDB rebuild（如保留） | ~546s | **~100s** | ✅ |

**判断方法**：把 `stock_data/` 复制到 NVMe 分区，跑 `backfill download --period 1m --codes 100只测试.txt`，看单批耗时。如果 < 2 分钟 → 方案 B（按月分区）的全部工程投入都不值得。

#### 强制决策流程

```
实施前团队必须回答以下 3 个问题，答案写入 PR 描述：

Q1: 分钟线查询的延迟要求是多少？
    < 10ms → 保留 .duckdb，继续 §4
    50-100ms 可接受 → 切 :memory:，本文档 §4-§6 全部跳过

Q2: stock_data/ 当前在什么存储介质上？
    SATA HDD / SATA SSD → 先迁移到 NVMe SSD，重新 benchmark 耗时
    NVMe SSD → 当前瓶颈不是 IO，继续 §4

Q3: 全市场扫描频率？
    每天 > 10 次 → 保留 .duckdb（:memory: 每次 2-5s 不可接受）
    每天 1-2 次 → :memory: 完全可接受
```

**如果 Q1+Q3 指向 :memory: 且 Q2 确认 NVMe**：删除 `stock_data_minute.duckdb`，删除所有 rebuild 逻辑，删除本文档 §4-§6。改动量：修改 `StockDataReader` 分钟线模式为 `:memory: + read_parquet(glob)`，约 20 行代码。总投入：半天。

---

## 4. 优化方案

> **前置说明**：以下方案均假设 §3.4 的决策结果为"保留持久化 .duckdb"。如果决策结果为"切 :memory:"，则 §4-§6 全部跳过——删除 rebuild 逻辑、删除 .duckdb 文件、StockDataReader 改为 :memory: 模式，半天完成。

### 方案 A'：全量 read_parquet(glob) + 只加索引（最简折中，20 行代码）

如果团队决定保留 .duckdb 但不想承担增量 INSERT 的工程复杂度（150 行 + 4 阻塞项 + 崩溃恢复模型），此方案是更安全的选择：

```python
# backfill.py 末尾（下载完成后），替代 _incremental_insert_to_duckdb
con = duckdb.connect(staging_path)
con.execute("""
    CREATE TABLE stock_data AS
    SELECT * FROM read_parquet(
        'stock_data/period=1m/dividend_type=none/symbol=*/data.parquet',
        hive_partitioning=1, union_by_name=True)
""")
con.execute("UPDATE stock_data SET symbol = REPLACE(symbol, '_', '.')")
con.execute("CREATE INDEX idx_symbol ON stock_data(symbol)")
con.execute("CREATE INDEX idx_symbol_time ON stock_data(symbol, time)")
con.close()
os.replace(staging_path, main_path)
```

| 对比 | 方案 A（增量 INSERT） | 方案 A'（全量 + 索引） |
|------|---------------------|----------------------|
| 代码量 | ~150 行 + 4 阻塞项 | **~20 行，无阻塞项** |
| 崩溃恢复 | 需验证 3 种崩溃场景 | staging 不完整→直接删了重建 |
| 数据一致性 | INSERT 可能列错位/行数双计 | **无**（数据直接从 parquet 读，100% 对齐） |
| 耗时 | ~10-30s（增量） | ~546s（全量，NVMe 下 ~100s） |
| 维护负担 | 高 | **极低**（一行 SQL 建索引） |

> K 的评审意见：对小团队，代码简单到不会出错 > 省 9 分钟。如果 NVMe SSD 把 rebuild 从 546s 降到 ~100s，方案 A' 的"9 分钟 rebuild"代价完全可以接受。此方案不排斥后续升级到方案 A（增量 INSERT），但不再作为 P0 硬性交付。

### 方案 A：DuckDB 增量 INSERT（高级选项，仅当方案 A' 的 ~100s rebuild 不可接受时）

#### 4.1 核心思路

保留 parquet 写入流程不变（保持 source of truth 定位），但在下载完成后**不执行全量 rebuild**，改为将本批新增数据 **INSERT 到 DuckDB staging，最后原子切换**。

#### 4.2 为什么这是最高 ROI 的改动

- 收益确定：省掉 546s 的全量 parquet 扫描
- 风险可控：下载流程不动，parquet 仍是权威源，出问题可随时全量重建
- 改动集中：只改 `_rebuild_duckdb` 和/或 backfill 批次循环，不动 downloader

#### 4.3 实现方式

**方式 1：批次级增量 INSERT（推荐）**

修改 `oskh_data/backfill.py` 的 `_download_impl` 批次循环，每批 parquet 写入完成后，将 `processed_data` 中的 DataFrame 写入 DuckDB staging：

```python
# backfill.py 批次循环中新增（伪代码）
if args.period == "1m" and processed:
    _incremental_insert_to_duckdb(processed, staging_db_path)
```

核心逻辑（新增函数 `_incremental_insert_to_duckdb`）：

```python
# staging 路径与 reader.py 约定对齐：
#   stock_data_minute.duckdb           ← main DB
#   stock_data_minute_staging.duckdb   ← staging（reader.py 使用 db.stem + '_staging' + db.suffix）


def _incremental_insert_to_duckdb(
    processed: Dict[str, pd.DataFrame],
    staging_db_path: str,
    expected_columns: List[str],
    # ↑ 从已有 parquet 推断 schema：next(Path("stock_data/period=1m/...").rglob("*.parquet"))
) -> None:
    """将本批 processed data 增量写入 DuckDB staging（DELETE+INSERT 幂等）。

    冷启动（无任何 parquet）→ 走全量 rebuild（build_persistent_db），不在此函数处理。
    """
    con = duckdb.connect(staging_db_path)
    try:
        # 首次建 staging 表：取任一已有 parquet 推断 schema（空表）
        con.execute("""
            CREATE TABLE IF NOT EXISTS stock_data AS
            SELECT * FROM read_parquet(?, hive_partitioning=1) WHERE 1=0
        """, [str(_SCHEMA_REF_PARQUET)])

        # expected_columns = 业务列（不含 symbol），table_columns = 业务列 + symbol（与 DB schema 一致）
        table_columns = expected_columns + ("symbol",)
        for code, df in processed.items():
            if 'time' not in df.columns:
                continue
            # ⚠️ 符号契约（不可变）：
            #   - DB 中 symbol 为点格式（000001.SZ），由 build_persistent_db 的
            #     UPDATE REPLACE(symbol, '_', '.') 保证（reader.py:455）
            #   - 增量路径的 df 不含 symbol 列（QMT 原始数据），需手动添加
            #   - DELETE/INSERT 必须使用点格式，否则静默命中零行 → 重复行 → 数据错误
            df['symbol'] = code  # 点格式，与 DB 一致
            df = df[list(table_columns)]  # 显式投影到表 schema，附 symbol 列
            min_t, max_t = int(df['time'].min()), int(df['time'].max())
            con.execute(
                "DELETE FROM stock_data WHERE symbol = ? AND time BETWEEN ? AND ?",
                (code, min_t, max_t),
            )
            # con.append()：PyArrow 零拷贝路径，要求 DataFrame 列严格按表 schema 顺序完整覆盖
            con.append('stock_data', df)
        con.commit()  # ① 先 commit DB
    finally:
        con.close()
    # ② DB commit 成功后，调用方执行 _save_progress（原子切换，见 §2.3.1）

# ── 调用方必须包含 try/except fallback（§5.3 回滚策略的行级实现）──
try:
    _incremental_insert_to_duckdb(processed, staging_path, expected_columns)
    os.replace(staging_path, main_db_path)  # 原子切换
except Exception:
    logger.exception("增量 INSERT 失败，回退到全量 rebuild")
    if staging_path.exists():
        staging_path.unlink()
    StockDataReader.build_persistent_db(base_dir=BASE_DIR, period='1m', adjust_type='none')
```

> `_SCHEMA_REF_PARQUET`：取任一已有 parquet 文件路径（`next(Path("stock_data/period=1m/...").rglob("*.parquet"))`）。Schema 有问题时 INSERT 会报错，报错再修——小团队不为 < 1% 概率的损坏文件写防御性选择逻辑。

**冷启动**：无任何 parquet 时直接走全量 rebuild（`build_persistent_db`），**不做**硬编码 DDL 冷启动路径——硬编码 schema 与 parquet 实际 schema 漂移后数据会静默错位，是不可逆风险。

**Staging 残留**：启动时 `if staging_path.exists(): staging_path.unlink()`（常识性操作，一行代码）。

**⚠️ Symbol 编码契约（不可变，违反复核）**：本项目中存在两种 symbol 格式，必须严格区分：
- **Parquet 目录名 / hive 分区值**：下划线格式 `000001_SZ`（文件系统限制，点号在部分工具中为分隔符）
- **DuckDB 表中 `symbol` 列**：点格式 `000001.SZ`（`build_persistent_db` 的 `UPDATE REPLACE(symbol, '_', '.')` 保证，reader.py:455）
- **增量路径的 DataFrame**：来自 QMT 原始数据，**不含 `symbol` 列**，需手动添加为点格式（`df['symbol'] = code`）
- **DELETE 语句**：必须使用点格式匹配 DB 中的列值，否则静默命中零行 → 重复数据 → 下游回测/实盘用错数据

`StockDataReader` 读取侧也通过 `_style == 'underscore'` 时 `REPLACE(symbol, '_', '.')`（reader.py:672-674）保证读出的总是点格式。此契约写入本段而非仅靠代码注释，因为符号格式不一致是**静默错数据**类型的 bug——不会 crash、不会报错，只会让下游在数周后才发现回测结果异常。

**方式 2：rebuild 命令改为增量模式**

修改 `_rebuild_duckdb`（`backfill.py:226-248`），分钟线走增量逻辑而非 `build_persistent_db` 的全量重建：

```python
def _rebuild_duckdb(rebuild_period: str) -> None:
    if rebuild_period == '1m':
        _incremental_sync_minute_duckdb()  # 新增
        return
    # 日线保持原逻辑
    ...
```

> 方式 1 更精细（批次粒度），但方式 2 改动更集中。建议先用方式 2 快速验证，再视情况改为方式 1。

> **commit 顺序一致性**：§4.3 伪代码中 `con.commit()` 在函数内、`_save_progress` 在调用方（函数外注释 `②`）。§4.4 表格"commit 顺序（DB ↔ progress）"行与此一致——实施时注意保持调用方在 `_incremental_insert_to_duckdb` 返回后才执行 `_save_progress`。

#### 4.4 必须处理的工程问题

| 问题 | 说明 | 处理方式 |
|------|------|----------|
| **time 列转换** | downloader.py:438-439 将 time 从 DatetimeIndex 转为 UTC 午夜毫秒 int64。parquet 文件中的 time 列和内存中 df_new 的 time 列格式必须一致 | 方案 A 的 df_new 来自 `_process_downloaded_data`，已经过 time 转换（line 438-439），直接 INSERT 即可 |
| **schema drift** | downloader.py:444-445 的 `normalize_schema` 修复旧 parquet 的大小写/dtype 问题。增量路径无此保护 | 首次建 staging 时从 parquet 读取 schema（`CREATE TABLE ... AS SELECT ... LIMIT 0`），后续 INSERT 前检查列一致 |
| **崩溃恢复** | 直接 INSERT 到主 DB 无原子性保证 | 保持 staging → atomic switch 模式：所有批次 INSERT 到 staging，最后 `os.replace` 原子发布（与当前 rebuild 一致） |
| **并发读取** | backtest / trading 可能在 backfill 期间读取 DuckDB | 写入 staging（独立文件），不影响 main DB 的读取；切换时 `os.replace` 对读端透明。**main DB 切换后读者必须用 `read_only=True` 打开**，详见 §3.2.1 的 read_only 审计项 |
| **parquet 与 DuckDB 行数验证** | 需要确认增量写入无误 | 切换前 `SELECT COUNT(*)` 对比 parquet 总文件数和 staging 行数；**同时抽样 3–5 只股票做 OHLCV 逐行比对**（仅 COUNT 无法发现列错位/值损坏） |
| **_validate_parquet_schema_consistency** | reader.py:442 在 rebuild 前做全量 schema 校验，增量路径跳过此检查 | 保留为可选：每周全量 rebuild 一次（如周末），日常增量跳过 |
| **commit 顺序（DB ↔ progress）** | DB 写入与 `_save_progress` 之间崩溃会导致两边状态不一致 | **强制顺序：① DuckDB commit → ② progress 原子切换**（见 §4.3 伪代码注释 + §2.3.1 progress 原子修复）。三种崩溃场景均被 DELETE+INSERT 幂等性覆盖，但顺序反了会留下"progress=done 但 DB 缺行"的不可恢复洞 |
| **read_only 审计** | 方案 A 上线后，main DB 会被多进程持续读；增量 INSERT 到 staging 虽不影响 main，但切换后的下次增量 INSERT 会与未关闭的 main DB 读连接冲突 | 在 P0 落地前盘点所有 `duckdb.connect(...)` 调用点（含 `StockDataReader`、`live_trading`、`executor_stream`、`stream_monitor`、`backtest/` 脚本），确认分钟线 DuckDB 路径一律传 `read_only=True`；未设置的调用点必须修复 |
| **数据质量 parity 断言** | COUNT(*) 一致无法检出列错位、值损坏、时间列单位漂移 | 在切换前除 COUNT 外，抽样 **N 只股票 × 固定时间窗**，逐行比对 `time / open / high / low / close / volume`，任一行不一致即拒绝切换并回退到全量 rebuild |
| **Hive 路径列名契约** | `hive_partitioning=1` 时，路径中的 `symbol=` / `month=` 会被自动注入为列。如果 staging 表 schema 中已有这些列，注入时会冲突 | 首次建 staging 时显式排除 hive 注入列，或在 `read_parquet` 时传 `hive_partitioning=0`（单文件）+ 手动加 `symbol` 列，二选一并在文档中固化 |

#### 4.5 收益评估

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| DuckDB 同步方式 | 全量扫描 5551 parquet → 建 staging（546s） | 批次 DataFrame 直接 INSERT 到 staging（~10–30s 累计） |
| 磁盘 I/O | 读 6GB parquet + 写 6.3GB staging | 每批只写 ~132 万行的增量数据 |
| 日常总耗时 | 下载 6h + rebuild 9min | 下载 6h + 增量 ~30s |
| Schema 校验 | 全量扫描 | 可选周度全量 rebuild |

> **务实预期管理**：方案 A 省掉的是 546s 的 rebuild，不是 6–10h 的下载。体感改善有限（6h 9min → 6h）。它的核心价值是**架构正确化**（不再全量 rebuild，为增量铺路），而非立竿见影的省时。真正有体感的是方案 B（6–10h → 1.5–2.5h）。

#### 4.6 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 增量 INSERT 导致数据重复 | 中 | 每批 INSERT 前 DELETE 该 symbol 该时间范围的行（DELETE+INSERT 幂等，见 §4.3） |
| DuckDB 文件膨胀（频繁 INSERT/DELETE） | 低→中 | 每周全量 rebuild 一次（compaction）；**建立监控**：每日记录 `stock_data_minute.duckdb` + `.wal` 大小，超过基线 1.5× 即触发全量 rebuild。132 万行/天 × 30 天 ≈ 4000 万行 DELETE 残影（未 checkpoint 前）会显著膨胀 |
| 某批 INSERT 失败后 staging 不一致 | 低 | 批次失败时标记该批不推进 progress，下次重跑覆盖；或异常时回退到全量 rebuild |
| 周度全量 rebuild 与日常增量的切换窗口 | 低 | 全量 rebuild 在周末执行，不影响交易日 |
| **QMT 数据修正场景** | 中 | QMT 除"除权回补"外，还会在**停牌复牌首日、盘后修正、节假日后首交易日**推"历史时间戳 + 新值"的 bar。这类数据满足 `time BETWEEN min_t AND max_t`，会被 DELETE+INSERT 覆盖到，**但前提是 `df_new` 中确实含该历史 bar**。建议在首批上线前回放 2026-04 至 2026-05 含五一假期的实际数据，验证修正场景覆盖率 |
| **DELETE 在大表上的性能退化** | 中 | `DELETE FROM stock_data WHERE symbol = ? AND time BETWEEN ? AND ?` 在 symbol 只有 5500 个 distinct 值时，单列 `idx_symbol` 每个分区仅几千行，性能差异可能不显著。**改为 benchmark 驱动**：上线前随机选 10 只跑 DELETE，若 > 100ms/只 则追加 `CREATE INDEX IF NOT EXISTS idx_symbol_time ON stock_data(symbol, time)`；否则保持单列索引。不要预设结论 |
| **progress 原子修复未与 P0 同批次合入** | 中 | §2.3.1 的 `_save_progress` 原子切换修复**必须**作为 P0 合入的前置 commit；否则方案 A 的"DB commit → progress 原子切换"顺序无法落地，崩溃恢复模型不成立 |
| **read_only 审计未完成就上线** | 中 | §4.4 表格中 read_only 审计项必须在 P0 上线前完成，否则 trading/executor 持有非 read_only 连接时，下次 backfill 增量 INSERT 会触发 `Database is locked` 错误，影响实盘读路径 |
| **周度全量 rebuild 与日常增量时间窗冲突** | 中 | 方案 A 假设日常增量 ~30s、周度全量 rebuild ~546s。若两者在同一凌晨窗口触发，全量 rebuild 持 staging 文件写锁 ~9 分钟，期间日常增量 backfill 会因 staging 被占而失败 | 排他锁 / PID 文件：`backfill.py` 启动时 `flock` staging 文件，避免并行；cron 中"周度全量 rebuild"与"日常增量"互斥（`flock -n` 失败即退出）。详见 §5.4 监控表"backfill 进程互斥锁健康" |

---

### 方案 B：Parquet 按月分区 + DuckDB 合并（P1，根治下载阶段 IO）

#### 4.7 核心思路

当前每只股票的所有历史数据存在**一个 parquet 文件**中：

```
symbol=000001_SZ/data.parquet     ← 全部历史（8 万行）
```

改为按**月分区**——每月一个文件（Hive 目录风格）：

```
symbol=000001_SZ/month=2026-05/data.parquet   ← 当月数据（~5000 行）
symbol=000001_SZ/month=2026-06/data.parquet   ← 下月数据（~5000 行）
```

**核心变化**：日常增量分两种情况：
- **跨月第一天**：新文件，直接 `to_parquet`（~0.05s/只）
- **月内追加**：读当月文件 → 合并新数据 → 回写（~0.5s/只，5000 行 vs 当前 8 万行）

读写量从全天历史的 8 万行降到单月的 5000 行，**IO 缩小 16×**。

#### 4.8 为什么按月而非按天

| 粒度 | 单只年文件数 | 全市场年文件数 | 月中追加成本 | 评价 |
|------|------------|--------------|-------------|------|
| 按天 | 240–250 | **138 万** | 0（纯新文件） | 🔴 文件数灾难，NTFS glob 扫描极慢 |
| **按月** | **12** | **6.6 万** | 重写 ~5000 行（~0.5s） | ✅ 最佳平衡点 |
| 按年 | 1 | 5,500 | 重写 ~8 万行（~3s） | 🟡 年尾退化到接近当前瓶颈 |

6.6 万文件/年 NTFS 轻松处理；月内重写 5000 行的成本（~0.5s）远低于当前 8 万行（~3s）。

#### 4.9 为什么必须用 Hive 目录分区（而非文件名区分）

```
✅ 目录分区（推荐）                ❌ 文件名区分
symbol=000001_SZ/                  symbol=000001_SZ/
  month=2026-05/                     2026-05.parquet
    data.parquet                     2026-06.parquet
  month=2026-06/
    data.parquet
```

Hive 目录分区的优势：
1. **DuckDB 原生支持**：`read_parquet(..., hive_partitioning=1)` 自动把 `symbol`、`month` 提取为列，无需手动解析
2. **项目约定一致**：当前 `period=1m/dividend_type=none/symbol=XXX/` 已经是 Hive 风格
3. **glob 精确定位**：`symbol=*/month=2026-05/data.parquet` 直接锁定目标月，文件名方案需要 LIKE 或 glob 扫全部文件再过滤
4. **扩展性好**：未来加 `dividend_type` 等维度不需要改文件名解析逻辑

#### 4.10 为什么 Parquet 不支持文件级 append

Parquet 文件结构：Row groups（数据）→ Footer（schema + 偏移量元数据）。追加数据需要重写 Footer + 追加 Row groups。`pyarrow.parquet.ParquetWriter` 理论上支持同一文件句柄多次 `write_table`，但跨进程/跨会话时 Footer 不完整会导致文件损坏，且与 Hive 分区模式不兼容。行业标准做法是用**目录分区模拟追加**，而非文件级追加。

#### 4.11 下载阶段：按月分区 + DuckDB 合并

新增数据的处理逻辑（替代 `_process_downloaded_data` 中的逐只合并）：

```python
# 业务列常量（不含 Hive 注入列 symbol/month）
MINUTE_PARQUET_SCHEMA_COLUMNS: Tuple[str, ...] = (
    "time", "open", "high", "low", "close", "volume", "amount",
)

def _write_monthly_partitioned(
    base_dir: Path, period: str, adjust_type: str,
    stock_code: str, df_new: pd.DataFrame,
    expected_columns: Tuple[str, ...] = MINUTE_PARQUET_SCHEMA_COLUMNS,
) -> None:
    """按月分区写入 parquet。日常增量仅需处理当月文件（~5000 行）。"""
    safe_code = stock_code.replace('.', '_')
    for month_str, month_df in df_new.groupby(df_new.index.to_period('M')):
        month_dir = (base_dir / f"period={period}" / f"dividend_type={adjust_type}"
                     / f"symbol={safe_code}" / f"month={month_str}")
        month_dir.mkdir(parents=True, exist_ok=True)
        file_path = month_dir / "data.parquet"

        if not file_path.exists():
            # 新月：直接写
            month_df.to_parquet(file_path, engine='pyarrow', compression='snappy')
            continue

        # 月内追加：pandas 合并（月文件 ~5000 行，pandas 比 DuckDB SQL 更快更简单。
        # 月内追加：pandas 合并（3 行代码，团队人人会 debug）
        # 5000 行的月文件 pandas 比 DuckDB SQL 更快（0.1s vs 0.3s），无需引入
        # QUALIFY/UNION ALL/Hive 列注入等额外故障点
        df_existing = pd.read_parquet(file_path, engine='pyarrow')
        df_merged = pd.concat([df_existing, month_df])
        df_merged = df_merged[~df_merged.index.duplicated(keep='last')]
        df_merged = df_merged.sort_index()
        tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        df_merged.to_parquet(tmp_path, engine='pyarrow', compression='snappy')
        os.replace(tmp_path, file_path)
```

> **年合并**：6.6 万文件/年 NTFS 完全可控，当前无需实施。等数据积累满 2 年（2027 年初）文件数成为实际瓶颈时再单独设计。本节不占用 P1 工期。

#### 4.13 收益评估

| 场景 | 优化前（单文件全历史） | 优化后（按月分区） |
|------|----------------------|-------------------|
| 新月第一天：单只处理 | read 8万行 + write 8万行（~3s） | write 240 行新文件（~0.05s） |
| 月内追加：单只处理 | read 8万行 + write 8万行（~3s） | read 5000行 + write 5000行（~0.5s） |
| 月内追加：单批 100 只 | ~5–7 分钟 | **~1 分钟** |
| 全市场下载总耗时 | ~6–10 小时 | **~1.5–2.5 小时** |
| DuckDB rebuild | 全量扫描 5551 文件（546s） | 增量读当月文件（~10-30s） |
| 文件总数（年化） | 5,551 | **~6.6 万**（12/只 × 5500） |
| DuckDB 进程启动 + SQL 解析开销 | — | **~50–150 ms/只（固定）**；100 只/批 × ~100 ms ≈ 额外 10s/批 |

#### 4.13.1 消费者盘点（P1 上线前必填）

方案 B 改动了 parquet 目录结构（`symbol=XXX/data.parquet` → `symbol=XXX/month=YYYY-MM/data.parquet`），所有**直接打开 parquet 文件**的代码都需要迁移。落地前需运行盘点脚本（建议新建 `~~scripts/audit_minute_parquet_consumers.py~~（已删除）`），输出至少包含：

| 类别 | 已知入口（需核实，不可视为完整） | 迁移策略 |
|------|-------------------------------|----------|
| 域层权威读取 | `oskh_data/reader.py`（`StockDataReader`） | 修改为 DuckDB 优先；parquet 模式自动 `read_parquet('symbol=*/month=*/data.parquet', hive_partitioning=1)` |
| 回测入口 | `backtest/**/*.py`、`verify_chip_factor_consistency.py`、`preflight_chip_diagnosis.py` | 统一收敛到 `StockDataReader`；禁止直接 `pd.read_parquet(symbol_path)` |
| 特征工程 | `features/` 下分钟线因子脚本（若有） | 同上 |
| 运维脚本 | `scripts/data/rebuild_minute_duckdb_standalone.py`、`backfill.py` | 按新路径重写 |
| 测试 fixture | `tests/` 下依赖固定 parquet 的用例 | fixture 改为月分区目录结构 |

**盘点方法**：在仓库根跑 `rg -n "read_parquet|period=1m|dividend_type=none"` + `rg -n "symbol=.*\.parquet"`，人工分类到上表；结果纳入 PR 描述，作为方案 B 合入的硬性前置。

**⚠️ 方案 B 硬前置：`_validate_parquet_schema_consistency` 迁移**：当前该函数（reader.py:825）glob 为 `symbol=*/data.parquet`。方案 B 改为 `symbol=*/month=*/data.parquet` 后 glob 命中为空，schema 校验**静默失效**（不抛异常，因为 `files` 为空时直接 return）。必须在方案 B 合入前将 glob 改为 `symbol=*/month=*/data.parquet`，否则数据质量门闸失灵——这是会"不可逆出错"的缺口。

#### 4.13.2 一次性迁移策略（替代双写过渡期）

小团队无多余磁盘（33 GB 余量）存双份数据，且双写过渡期日常维护成本翻倍。改为**一次性迁移 + 旧数据冷备份**：

```
周末全天停服（~6–8h，实际拆解）：
  1. 备份 6 GB parquet：5–10 min
  2. 重写 5551 只 parquet 为月分区：5551 × 3s ≈ 4–5 h（瓶颈，可用多进程加速到 ~1h）
  3. 全量 rebuild DuckDB：546s ≈ 9 min
  4. 改 StockDataReader 读新路径：5 min
  5. 跑全量回测 diff = 0：30 min – 2 h（取决于回测套件）
  6. 验证 + 删除旧文件：30 min
```

**分阶段执行支持**（推荐替代一次性迁移）：迁移 5551 只中途崩溃时，已迁移和未迁移的 parquet 路径格式不同，StockDataReader 无法统一读取。迁移脚本必须支持 progress 文件持久化——复用 `_save_progress` 原子修复机制（§2.3.1），记录已完成 code 集合，重启时自动跳过。

回滚：`cp -r stock_data/period=1m.bak.$(date +%Y%m%d)/* stock_data/period=1m/` + StockDataReader 切回旧路径。

消费者盘点（§4.13.1）通过 `rg` + 人工分类完成，不需要独立脚本。

#### 4.13.3 Parquet row group 大小

pyarrow 默认 `row_group_size=1024*1024`（约 100 万行）。月文件只有 ~5000 行，**每文件只会有 1 个 row group**，DuckDB `read_parquet` 单线程读单文件、无法在文件内并行。

**影响**：
- 单文件读取延迟受单线程带宽限制，对小文件无所谓（5000 行本就极快）
- 但 `read_parquet('symbol=*/month=*/data.parquet', hive_partitioning=1)` 跨多文件时，DuckDB 按文件分配线程；文件数 6.6 万 >> CPU 核数，**调度开销可能成为新瓶颈**

**建议**：
- 方案 B 落地后跑一次 `read_parquet` benchmark，对比扫描耗时：

  ```bash
  # 旧路径（单文件全历史，5551 个 parquet）
  duckdb -c "SELECT COUNT(*) FROM read_parquet('stock_data/period=1m/dividend_type=none/symbol=*/data.parquet', hive_partitioning=1)"

  # 新路径（月分区，~6.6 万个 parquet）
  duckdb -c "SELECT COUNT(*) FROM read_parquet('stock_data/period=1m/dividend_type=none/symbol=*/month=*/data.parquet', hive_partitioning=1)"
  ```

  预期：月分区扫描耗时不应超过旧路径的 **1.5×**（文件数增大但单文件更小，部分抵消）。
- 若退化超过 1.5×，可在 DuckDB 读取端改用 `union_by_name=True` 或显式按 `symbol` 分批扫描

---

### 方案 C：追加路径跳过 CPU 冗余操作（不独立排期，已并入方案 B）

收益 ~3%（仅省 CPU，IO 不变），端到端可忽略。方案 B（按月分区）落地后完全不需要此优化。代码改动（10 行 if 分支 + 存量单调性扫描）若顺手做掉也无害，但不作为独立排期项。详见 §2.4 IO vs CPU 拆解。

---

### 不做的事：为什么我们不把权威源迁到 DuckDB（原方案 D）

**决策：确定不做。** A 股小型私募/自营行业惯例是 parquet 为 source of truth、DuckDB 为查询加速——这与项目现有架构（`parquet_duckdb_dual_mode_reader_plan.md` §2.1）一致。

- **风险**：DuckDB 单文件灾备脆弱；周度 EXPORT 出问题需要 6–10h 全量 QMT 重下载（miniQMT 频繁断连环境下真实可能触发）
- **收益趋零**：方案 B 落地后 parquet 维护成本已被消除，日常读写走 DuckDB 增量，parquet 仅作冷备份
- **触发条件（再评估）**：仅当 channel ≥ 3（实盘/backtest/第三方）且 DuckDB 多读单写经 ≥ 6 个月稳定验证，再单独 RFC。当前不计入本文档任何排期

**灾备降级**（原 §4.19.2）：parquet 作为 source of truth 已有天然灾备——parquet 损坏 → 从 QMT 重新下载单只；DuckDB 损坏 → 从 parquet 全量 rebuild（546s）。无需额外演练。文件系统快照由运维层面覆盖，不在此文档定义。

---

## 5. 实施建议

### 5.1 优先级与排期（工时估算；执行步骤详见 §6.8）

| 优先级 | 方案 | 预估工作量 | 目标日期 | 阻塞项 |
|--------|------|-----------|---------|--------|
| **Gate** | §3.4 架构决策（:memory: vs .duckdb / NVMe benchmark） | **半天**（跑 §3.4 Q1-Q3 + NVMe benchmark） | 实施前 | **必须通过才能进入 §4-§6**。如果决策为 :memory: → 删 .duckdb + 改 StockDataReader 20 行，半天完成，本文档完结 |
| **P0+** | Backfill 时间窗 gate（§2.5.2）含运行期 graceful exit | **0.5 天** | 2026-05-30 | 无（独立交付，阶段 0） |
| **P0（简）** | 方案 A'（全量 read_parquet + 加索引，§4 新增） | **半天**（20 行代码，无阻塞项） | — | 方案 A 的降级选项。如果 NVMe 下 rebuild ~100s 可接受，选此方案 |
| **P0（全）** | 方案 A（DuckDB 增量 INSERT）+ 方案 C（append-only fast path） | **2–3 天** | 2026-06-03 | 仅当 rebuild ~100s 不可接受时选。阻塞项仅 2 个：① `read_only=True` 审计；② try/except fallback 到全量 rebuild。P0 的核心价值是架构铺路（增量 INSERT 路径是 P1 rebuild 从 546s → 30s 的前置依赖） |
| **P1** | 方案 B（按月分区 parquet）或 B'（单文件+季度 rebuild，视 §6.8 决策） | **B: 3–5 天**（消费者盘点 0.5–1d + downloader 改造 1d + 迁移脚本+执行 1d + 回测回归+diff 验证 0.5–1d + 文档 0.5d）**B': 0.5 天** | 2026-06-20（B）/ 随时（B'） | B: ① _validate_parquet_schema_consistency glob 迁移（§4.13.1 硬前置）；② 迁移脚本支持分阶段执行（复用 progress 原子修复）；③ row group benchmark。B': 无阻塞项 |
| **不做** | 方案 C（CPU 微优化）、方案 D（权威源迁移） | — | — | §4 "不做的事" 已说明理由 |

### 5.2 验收标准

> **与 §5.1 阻塞项对照**：以下标注 Ⓐ–Ⓔ 的验收项与 §5.1 P0 阻塞项一一对应。ⒶⒷⒸ 为前置交付，ⒹⒺ 为实施交付。

#### 方案 A 验收

- [ ] Ⓐ **`_save_progress` 原子切换修复**已作为前置 commit 合入（§2.3.1）
- [ ] Ⓑ **`read_only=True` 审计**已完成（§4.4 表格），所有分钟线 DuckDB 读路径传 `read_only=True`；审计结果作为 PR 附件
- [ ] Ⓒ **`(symbol, time)` 复合索引**：上线前随机 10 只跑 DELETE benchmark，> 100ms/只则追加索引；否则保持单列 `idx_symbol`（§4.6→benchmark 驱动，不预设结论）
- [ ] `update --period 1m` 执行后 DuckDB 同步耗时 **< 60s**（不含下载）
- [ ] DuckDB staging 行数 = parquet 总行数（`SELECT COUNT(DISTINCT symbol, time)` 比对）
- [ ] **OHLCV 抽样 parity**：从 5500 只中分层抽样 ≥ 5 只（覆盖大盘/中小盘/北交所/停牌复牌/除权），对每只固定时间窗的 `time/open/high/low/close/volume` 与 parquet 源逐行比对，差异 = 0
- [ ] `StockDataReader` 三模式（parquet/duckdb/duckdb_persistent）读取同一只股票的分钟线，返回 DataFrame 行数/索引/列值逐项等价
- [ ] Ⓓ **staging 残留清理**：每次 backfill 启动时自动删除残留 staging 文件（§4.3 新增段落）
- [ ] Ⓔ **崩溃恢复幂等验证**（小团队减负：CI 自动化 + 首周一次性手动验证，非长期验收项）：① 单测层面 mock `con.commit()` 抛异常，验证 staging 残留被清理 + 重启重跑结果正确；② 集成 CI 用固定 fixture（10 只 × 3 天）跑"崩溃→重启→比对基线"；③ 上线首周手动做一次生产崩溃注入验证 DELETE+INSERT 幂等
- [ ] 原子切换（staging → main）后旧 DB 正确备份（保留最近 3 个版本，命名含时间戳）

#### 方案 B 验收

- [ ] 日常增量单批写入 **< 1 分钟**（100 只 × 新文件写入）
- [ ] 全市场分钟线下载总耗时 **< 3 小时**
- [ ] DuckDB rebuild 完成后行数与 `month=*` 文件总行数一致
- [ ] 月度合并脚本执行后旧 `month=` 文件正确删除，合并 parquet 与原始文件逐行等价
- [ ] **消费者盘点清单**（§4.13.1）已完成并经评审，所有直接读 parquet 的入口要么已迁移、要么列入豁免清单
- [ ] **差异审计脚本**已交付并跑通 ≥ 1 周（§4.13.2），无差异告警
- [ ] 所有消费者（回测脚本、preflight 等）在新路径上的输出与旧路径历史输出 **逐字等价**（diff = 0，或差异已归因并记录）
- [ ] **row group benchmark**（§4.13.3）完成，新路径下 `read_parquet` 跨月扫描耗时不超过旧路径 1.5×；超过则需给出优化方案
- [ ] 年合并脚本（§4.12）经 dry-run 验证：合并后行数 = 原始月文件行数之和，OHLCV 逐行等价

### 5.3 回滚策略

#### 一键 Emergency Exit（小团队凌晨首选）

小团队凌晨被叫起来修问题时，不应对照多列表格：

| 方案 | 操作 |
|------|------|
| **A** | 删 `stock_data_minute_staging.duckdb` + 跑 `python -m oskh_data.backfill rebuild --period 1m`（全量 rebuild 546s）。一行命令：`rm -f stock_data_minute_staging.duckdb && D:/anaconda3/envs/vanna311/python.exe -m oskh_data.backfill rebuild --period 1m` |
| **B** | 删 `month=*` 目录 + 从备份恢复旧 `symbol=*/data.parquet` + 全量 rebuild |

#### 详细回滚步骤

| 方案 | 触发条件 | 操作步骤 | 预期耗时 | 验证方式 |
|------|---------|---------|---------|---------|
| **A** | 增量 INSERT 期间抛异常 / 切换后 OHLCV parity 差异 > 0 | ① `backfill.py` 内部 try/except 自动 fallback 到 `build_persistent_db` 全量 rebuild；② 若 staging 已污染，删除 staging，下次运行重建 | 全量 rebuild ~546s | DuckDB 行数 = parquet 总行数；OHLCV parity = 0 |
| **A** | `Database is locked` 错误（read_only 审计遗漏） | ① 立即停止 backfill；② 排查持有非 read_only 连接的进程；③ 修复后重启 | 10min–1h | 所有 `duckdb.connect` 调用点审计通过 |
| **A** | 崩溃后 progress 文件损坏 | ① 删 progress + 删 staging + 全量重跑；② 或从 git 恢复 + 删 staging 重建 | 6–10h（全量）/ ~1h（git 恢复） | `json.load` 成功 |
| **B** | 月分区写入异常 / 消费者结果与基线不等价 | ① 保留旧路径 `symbol=XXX/data.parquet`（过渡期双写）；② `StockDataReader` 切回旧路径；③ 删 `month=` 目录 | 重新下载 6–10h；若旧路径保留则 0 | 旧路径 OHLCV 与基线逐行等价 |
| **B** | 文件数超过 NTFS 性能阈值（>10 万/目录） | 触发月度/年度合并脚本；若仍超，回退到单文件全历史 | 合并 ~30min | 目录文件数 < 阈值 |

### 5.4 监控与告警（方案 A/B 上线后必装）

| 指标 | 级别 | 采集频率 | 告警阈值 | 响应 |
|------|------|---------|---------|------|
| parquet vs DuckDB 抽样 OHLCV parity | **核心** | 日（凌晨） | 差异 > 0 | 启动根因排查（直接保护数据正确性） |
| `stock_data_minute.duckdb` 文件异常膨胀 | **核心** | 日 | 较基线增长 > **2×** | 触发全量 rebuild（compaction）；防止 DELETE 残影吃磁盘 |
| 日增量行数 | 可选（月度巡检） | 月 | 偏离 `活跃股数 × 交易时段数 × 60 ± 30%` | 检查 QMT 数据源 / 停牌股过滤 |
| 全市场 backfill 总耗时 | 可选（月度巡检） | 月 | > 基线 1.5× | 排查 IO 退化 |

> **小团队裁剪**：`_save_progress` 原子修复后 progress 文件不会损坏 → 删除该项。`read_only` 审计一次性做完 → 删除该项。backfill 进程互斥锁由时间窗 gate（§2.5.2）保证不并发 → 删除该项。WAL 大小被文件膨胀指标覆盖 → 删除该项。

**采集落点**：核心指标写入 `ops_order_metrics` 表（复用 `stream_monitor` 已有的指标管道）。

---

## 6. 关键工程考量补充

以下是在之前分析中遗漏或低估的重要工程问题。

### 6.1 Parquet 不可追加——理解 IO 瓶颈的本质

Parquet 是列存格式，文件末尾有 footer（包含 row group 元数据）。追加数据需要重写 footer + 追加 column chunks。`pyarrow.parquet.ParquetWriter` 支持同一文件句柄多次 `write_table`，但：
- 不支持跨进程/跨会话追加
- 崩溃时 footer 不完整导致文件损坏
- 与 Hive 分区模式不兼容

**行业中标准做法**：用目录分区（如 `date=20260528/data.parquet`）模拟追加，而非文件级追加。这正是方案 B 的依据。

### 6.2 当前下载流程中不被方案 A 影响的关键步骤

方案 A（DuckDB 增量）**不动**下载流程，以下步骤保持原样：

- **`normalize_schema`**（downloader.py:444-445）：修复旧 parquet 的列名大小写、dtype 问题
- **schema gate**（downloader.py:447-466）：列/dtype/index 不一致时全量覆盖
- **`time` 列转换**（downloader.py:438-439）：DatetimeIndex → UTC 午夜毫秒 int64
- **`process_minute_data`**（downloader.py:158-184）：过滤非交易时间

这些步骤保护的是 parquet（source of truth）的数据质量。方案 A 的 INSERT 源是已通过这些步骤的 `processed_data`，因此继承了同样的数据质量保证。

### 6.3 方案 A 中 staging → atomic switch 保持崩溃安全

方案 A 不改当前 `build_persistent_db` 的 staging → atomic switch 模式，只改变 staging 的构建方式：

```
当前：read_parquet(全部文件) → staging → validate → os.replace
方案A：批次 DataFrame INSERT → staging → validate → os.replace
```

`os.replace` 在同一文件系统上是原子操作——读端要么看到旧 DB，要么看到新 DB，不会看到半成品。

### 6.4 方案 B 文件数爆炸与文件系统限制

> **注**：以下 "187 万" 是按天分区的场景（已在 §4.8 被否决，仅作对照）。按月分区为 6.6 万文件/年，NTFS 完全可控。

若**误用按天分区**：5,500 只 × 340 天 = 187 万独立文件。NTFS 单目录 > 10 万文件性能急剧下降，即使分散到 5,500 个子目录，每个目录 340 个文件（可接受），但 glob `**/*.parquet` 扫描 187 万路径仍有显著调度开销。这正是 §4.8 选择按月而非按天的核心依据。

按月分区的实际文件数（6.6 万/年）无需额外缓解，但年合并（§4.12）仍建议作为定期维护步骤：
- DuckDB 读取时 `hive_partitioning=1`，由 DuckDB 并行引擎处理 glob 扫描
- 合并非活跃年份为 `year=YYYY/data.parquet`

### 6.5 为什么不用 Redis 做分钟线缓冲（决策留痕）

项目已用 Redis Stream 做交易信号传递（`redis_stream_bridge`），但分钟线 backfill 完全绕过 Redis，直接 QMT → parquet → DuckDB。行业小团队常见模式：

```
QMT 推分钟线 → Redis Stream（TTL 24h）
  ├─ 实盘交易路径：实时消费
  ├─ backfill 路径：批量 XADD → 夜间 batch 落 parquet
  └─ 回测路径：从 Redis 读近 24h（无需等 parquet）
```

优势：backfill 与实盘读路径解耦，无需 `read_only` 审计；24h 内数据在 Redis，回测不必等 rebuild；崩溃恢复靠 Redis AOF。

**当前不做**：多一跳延迟 + 多一份运维（Redis 内存容量规划、分钟线 TTL 策略、XADD 与 parquet 的一致性问题）。对小团队不划算。

**触发条件（再评估）**：当 backfill 与实盘冲突频率 > 1 次/月，或回测对"最新数据"的时效要求从 T+1 收紧到 T+0，再单独 RFC。

### 6.6 数据存储职责矩阵（SQLite / DuckDB 边界固化）

小团队最容易掉的坑：两套引擎并存，职责漂移，最后每个数据源都有一份半新不旧的副本。以下矩阵固化边界：

| 数据 | 当前存储 | 为什么 | 何时考虑迁移 |
|------|---------|--------|-------------|
| 分钟线行情 | DuckDB (`stock_data_minute.duckdb`) | 列存 + 大行数（> 1 亿） | 永不迁 SQLite |
| 日线行情 | Parquet + DuckDB | 同上 | — |
| 持仓/资金账本 | SQLite (`portfolio.db`) | ACID、行数少（< 10 万） | 永不迁 DuckDB |
| 订单执行日志 | SQLite (`execution_log`) | ACID + 审计 + 行级事务 | 行数 > 5000 万时考虑 DuckDB |
| 治理指标 | SQLite (`ops_order_metrics`) | 行数少、跨进程共享 | — |
| 调度器状态 | SQLite (`ops_scheduler_state`) | 单进程独占、轻量 | — |

**黄金准则**：
- SQLite：事务性强、单表单库、行数少（< 1000 万）、需要 ACID
- DuckDB：列存、分析查询、行数大（> 1 亿）、批量读写
- 不交叉写入同一逻辑数据到两套引擎

---

### 6.7 实用随手修（实施时顺手做，不独立排期）

**`_filter_incremental` 的全量读取优化**：当前 `_filter_incremental`（downloader.py:358-378）对每只股票 `pd.read_parquet` 全量读仅为了取 `index.max()`。优化方向：
- 用 `pyarrow.parquet.read_metadata(fp)` 只读 footer（~0.01s vs 1.5s），从 row group statistics 取 max timestamp
- 或在 `_save_progress` 里额外维护 `max_date_per_symbol` 字典，下次启动查字典
- **~20 行代码，省 ~5 分钟/次 backfill**

**QMT 断连重试**：6–10 小时下载期间 QMT 偶尔断连。`downloader.py` 有 `_DOWNLOAD_STALL_TIMEOUT_SEC` 但 `backfill.py` 批次级无自动重试。建议在 `_download_impl` 批次异常处理中加一次自动重试（单批次失败 → 等待 30s → 重试一次 → 仍失败则记入 `failed_codes`）。

**磁盘空间**：当前 33 GB 余量约可维持 1.5 年。在 `build_persistent_db` 的 `_check_disk_watermark` 中已有机房水位检查（reader.py:437），当前覆盖 staging 写入阶段。分钟线下载阶段（parquet 日增 ~60 MB）无独立水位检查——可在 backfill 启动时加一条 `shutil.disk_usage` 检查，< 5 GB 即拒绝启动。

### 6.8 实施路线图（执行步骤；工时估算见 §5.1）

```
Gate 0（实施前，半天）：架构决策——必须先通过
  ├─ 跑 §3.4 Q1-Q3 决策问题，答案写入 PR 描述
  ├─ NVMe benchmark：cp stock_data/ → NVMe，跑 100 只测试看单批耗时
  ├─ 如果切 :memory: → 删 .duckdb + 改 StockDataReader 20 行，半天完结
  └─ 如果保留 .duckdb → 继续阶段 0-2

阶段 0（本周，1 天）：防护性前置——独立 commit，与方案 A/B 解耦
  ├─ 0.1 backfill 时间窗 gate（§2.5.2，~2h）
  │    防止：交易日盘中跑 backfill → miniQMT 资源竞争 → 实盘心跳超时 → 订单悬挂
  └─ 0.2 QMT 升级回归 checklist（§1.7，~4h）
       防止：QMT 静默升级 → 数据语义漂移 → 下游因子全错。产出：5 只基准股快照 + 1 页纸 checklist

阶段 1（本周，半天–1.5 天）：P0
  ├─ **默认选方案 A'**（全量 read_parquet + 索引，20 行，半天）
  │   如果 NVMe 下 ~100s rebuild 可接受 → 直接选 A'，阶段 1 半天完成
  └─ **仅当 ~100s 不可接受时才选方案 A**（增量 INSERT + try/except fallback，1-1.5 天）
       ├─ _save_progress 原子写入 + 单测（1h）
       ├─ _incremental_insert_to_duckdb + fallback + 单测（4h）
       ├─ read_only=True（只检查 StockDataReader 一处，~10min）
       └─ 验收：生产环境跑 backfill，抽查 3 只基准股 parity，rebuild < 60s
  ⚠️ 方案 C append-only fast path 随 P0 合入（10 行改动，收益永远为正）

阶段 2（方案 B 决策点，半天）：
  ┌──────────┬──────────────────────────┬─────────────────────────────────────┐
  │ 选项     │ 代价                     │ 适合场景                            │
  ├──────────┼──────────────────────────┼─────────────────────────────────────┤
  │ B'       │ 0 改动，日常仍是 6-10h   │ 脚本凌晨跑、早上看结果就行            │
  │ B        │ 2-3 天实施，一次性迁移   │ 每天需多次 backfill（策略迭代密集期） │
  │ B''      │ 1-2 周实施，不做审计     │ 风险承受度高，用回测 baseline 代审计  │
  └──────────┴──────────────────────────┴─────────────────────────────────────┘
  黄金准则：方案 B 优化的是运维效率，不是 PnL。如果运维能接受 overnight 6-10h，选 B'。

阶段 3（不做）：方案 D / 年合并 / 双写过渡期 / 灾备演练 / 复杂监控
  └─ 痛点已消除，回去写策略
```

### 6.10 长期轻量运维清单（方案 A 上线后，替代重型流程）

小团队每月 ~3 小时运维（`5 min × 20 交易日 = 100 min` + 周 rebuild `9 min × 4 = 36 min` + 月巡检 `20 min` + 半年演练均摊 `5 min` + QMT 升级 `10 min`），替代文档中的重型监控管道和定期灾备演练：

| 频率 | 动作 | 用时 | 防止的风险 |
|------|------|------|-----------|
| 每交易日 | 自动采集 2 个核心指标（OHLCV parity / DuckDB 大小），人工每周看一眼 | 0（自动化）/ 周 5 min | 数据漂移、磁盘爆满 |
| 每周一 | 手动跑一次全量 rebuild（compaction） | 9 min | DELETE 残影累积 |
| 每月 | 巡检 backfill 总耗时 + `.retired_codes.json` 更新 + 停牌股复活检查（§2.5.1） | 20 min | IO 退化、停牌/退市股无效流量、复牌漏更新 |
| 每次 QMT 升级 | 跑 QMT 升级回归 checklist（§1.7） | 30 min | 数据语义漂移 |
| 每半年 | 灾备演练（删 DuckDB → 全量 rebuild） | 30 min | 灾难恢复能力验证 |

> **全量 rebuild 节奏调整信号**：实施 1 个月后检查 `.wal` 文件大小：< 500 MB → 可降级为"每两周一次"或"每月一次"；> 1 GB → 保持每周一。给团队实测数据驱动的调整依据，不固化节奏。

---

## 7. 关联文档与代码索引

| 文件 | 说明 |
|------|------|
| `oskh_data/downloader.py:358-377` | `_filter_incremental` 增量过滤逻辑 |
| `oskh_data/downloader.py:380-482` | `_process_downloaded_data` 逐只 parquet 写入（瓶颈点） |
| `oskh_data/downloader.py:438-439` | `time` 列转换（DatetimeIndex → int64 ms） |
| `oskh_data/downloader.py:443-472` | Schema 归一化 + 门闸校验（含 `to_parquet` 覆盖写分支） |
| `oskh_data/downloader.py:128-155` | `PeriodDataManager.get_file_path`（Hive 风格路径） |
| `oskh_data/downloader.py:158-184` | `process_minute_data`（非交易时间过滤） |
| `oskh_data/backfill.py:226-248` | `_rebuild_duckdb` 全量重建逻辑（方案 A 改动点） |
| `oskh_data/backfill.py:251-362` | `_download_impl` 批次循环 |
| `oskh_data/reader.py:411-489` | `build_persistent_db` DuckDB 建库实现（staging → switch） |
| `oskh_data/reader.py:440-442` | `_validate_parquet_schema_consistency` |
| `scripts/data/rebuild_minute_duckdb_standalone.py` | 独立 rebuild 脚本 |
| `~~scripts/audit_minute_parquet_consumers.py~~（已删除）`（待新建） | §4.13.1 消费者盘点 |
| `~~scripts/gates/verify_minute_parquet_duckdb_parity.py~~（已删除）`（待新建） | §4.13.2 / §5.4 差异审计 |
| `~~scripts/compact_minute_yearly.py~~（已删除）`（待新建） | §4.12 年合并 |
| （方案 A 回滚无需独立脚本：`rm staging + rebuild --period 1m` 一行命令，见 §5.3） |
| `docs/backtest/data/parquet_duckdb_dual_mode_reader_plan.md` | 双模式读取方案（背景与 benchmark） |
| `docs/prompts/prompt-stock-data-minute-backfill-sync-workflow.md` | 分钟线补录工作流 |

---

*最后更新：2026-05-28（修正方案 A/B 收益评估、补充 IO vs CPU 分析、新增方案 B 按月分区 parquet、补充工程考量）*

*评审修订：2026-05-28（根据评审意见落实：§1 不实施代价外推；§2.3.1 progress 原子写入缺陷与修复；§3.2.1 DuckDB 并发读写模型；§4.3 DELETE+INSERT 幂等路径与显式列映射；§4.4 工程问题表扩充 commit 顺序 / read_only 审计 / OHLCV parity / Hive 列契约；§4.6 风险表扩充 QMT 修正 / 复合索引 / 前置依赖；§4.11 SQL 合并 src 优先级 + 异常处理；§4.13.1–4.13.3 消费者盘点 / 双写审计过渡期 / row group；§4.19.1–4.19.3 P2 双写审计 / 灾备演练 / 读者收敛；§5.1 阻塞项更新；§5.2 验收标准强化；§5.3 回滚策略表格化；§5.4 监控与告警）*

*第二轮评审修订：2026-05-28（必改 4 项：§4.11 SQL 列映射修复 / §5.3 方案 D 回滚循环依赖 / §4.6+§5.4 rebuild 互斥锁 / §5.1+§6.4 命名一致性；建议改 5 项：§4.3 占位函数约束 / §5.4 节假日鲁棒阈值 / §4.12 rmtree 错误处理 / §4.11 DuckDB 启动开销 / §4.10 ParquetWriter 论断修正；细节 3 项：§1 P2 歧义消除 / §7 新增脚本索引 / §4.14 单调性前置条件）*

*第三轮评审修订：2026-05-28（小团队黄金准则裁剪。必改：§1.5 裁剪原则 / §1.6 目标状态 / §1.7 时间窗 gate + QMT 升级回归 / §2.5 A 股特有风险 / §4 砍方案 C 为脚注 + 方案 D 改为"不做的事" + 方案 B' 对照 / §5.1 P0+ gate / §5.3 一键 emergency exit / §5.4 监控收敛到 2+2 / §6.5 Redis 决策留痕 / §6.6 存储职责矩阵。建议改：§2.1 240 bar 修正 / §4.13.2 双写 1 周 / §5.2 崩溃测试降级）*

*第三轮评审修订（P）：2026-05-28（小团队实战视角。必改：§4.5 方案 A 收益预期管理 / §5.1 P0 工时 2–3 天 + 方案 C 随 P0 合入 / §5.3 一键回滚简化为一行命令 / §6.7 随手修 _filter_incremental + QMT 断连 + 磁盘水位 / §6.8 实施路线图。建议改：§4.12 年合并推迟到 2 年 / §7 删 rollback 脚本索引）*

*第三轮评审修订（K）：2026-05-28（成本约束视角。必改：§4.3 con.register→con.append 消除帧生命周期 bug / §4.3 删冷启动 DDL 分支 + 加 try/except fallback / §4.11 DuckDB SQL→pandas 合并 / §5.1 阻塞项 4→2 / §4.13.2 双写→一次性迁移 / §6.8 路线图 2 阶段。建议改：§4.6 复合索引 benchmark→决定 / §4.12 年合并整节删除 / §5.2 复合索引验收对齐）*

*第三轮评审修订（C）：2026-05-28（实施硬门槛视角。必改 4 项硬门槛：① §4.3 symbol 编码契约下划线→点格式 + DELETE/INSERT 对齐 + df 需手动添加 symbol 列；② staging 命名统一为 _staging 后缀（与 reader.py:434 一致），覆盖伪代码/回滚命令/运维 grep；③ §4.13.1 方案 B 硬前置：_validate_parquet_schema_consistency glob 从 symbol=* 迁移到 symbol=*/month=*；④ §4.11 DuckDB register 约束已在 K 轮通过 pandas 合并消除。总评：文档已可进入实施评审）*
