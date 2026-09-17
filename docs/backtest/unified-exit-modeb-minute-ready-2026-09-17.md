# 模式 B · 分钟数据就绪短记（smoke，非网格结果）

> **日期**：2026-09-17
> **状态**：✅ 宿主 smoke 完成（数据就绪）。runbook：[host-runbook-unified-exit-modeb-smoke-2026-09-17.md](host-runbook-unified-exit-modeb-smoke-2026-09-17.md)。
> **基线代码**：master `55bfe4a`（PR #93 后）。
> **性质**：cache + 覆盖率 + 墙钟。**Mode B 网格排名不在本短记**（等 `feat/unified-exit-modeb` A–D 合入后另开 runbook）。

## 1. 完成定义对照

| 项 | 结果 |
|----|------|
| `period=1m/dividend_type=none` 可达 | ✅ `F:\stock_data\stock\period=1m\dividend_type=none`，`exists True`；`MINUTE_LAKE_END=20260909` 与窗口末日对齐 |
| bar_cache 存在且 meta 合理 | ✅（**偏差见 §2**）现成 `minute_none_20251013_20260909.parquet`：**2322 码 = 名单全并集**、1.259 亿行、1.75GB、2026-09-11 建；meta json 完整 |
| 覆盖率（相对 Mode A 实开） | ✅ 实开 **2080** distinct 码（4167 实例去重，装配层 13s 复现 opened=4167）∩ cache = **2080/2080 = 100%，缺 0** |
| 热加载墙钟 | ✅ 见 §3 |
| Mode B 网格排名 | ❌ 不在本 smoke 范围 |

## 2. 与 runbook 的偏差：cache key = `20251013`（warmup 起点），非字面 `20251023`

- runbook §1.2 字面产物 `minute_none_20251023_20260909.parquet` **未重建**：现有 cache（`csv_minute_backtest` 默认 warmup 起点口径）窗口 `20251013–20260909` **⊇** 业务窗 `20251023–20260909`，码集 2322 全并集 ⊇ 实开 2080，内容是严格超集；重建 = 重扫全湖 + 再写 1.75GB，无信息增益。
- `load_minute_bars` 按 `(start, end)` 精确 key 找 cache：**Mode B 实现侧若沿用 `csv_minute_backtest` 的 warmup 起点建 cache（推荐，与现引擎一致），现成 1.75GB 直接复用**；若坚持业务起点 key，需确认人拍板后重建（成本 ≈ 全湖扫 + 1.75GB 磁盘）。
- 覆盖率与墙钟结论不受 key 选择影响。

## 3. 墙钟与内存（2080 码 / 1.128 亿行）

| 口径 | 墙钟 | 峰值内存 |
|------|------|---------|
| 冷读（`read_minute_cache` 直调，只读不写） | **27.4s** | 6.7GB |
| 官方热路径（`load_minute_bars(use_cache=True)`，第二遍读） | **28.9s**，`status={'cache': 'hit'}` | 6.6GB |

第二遍未见 OS page cache 加速 → 解析为主导（1.75GB parquet → 2080 row-group 反序列化）。本机 39.9GB 内存，余量充足。

## 4. 对 Mode B 的成本推论

- **装配一次 28s / 6.6GB** 是每组网格的固定底座；触判若向量化（`high/low ≥ 阈值` 矩阵化），窄网格（冠军族 ~24 组 + 4 锚线）应在**分钟级**完成。
- 6.6GB 数据驻留在 4090 机器（显存/内存）均轻松——迁移成本主要是 bar_cache 拷贝（1.75GB）与环境（vanna312 + F 湖 resolvable 路径）。
- 前置提醒（沿用 Mode A 短记）：先落 `date_to_ymd` 向量化性能票，否则分钟级 ×240 的矩阵规模会把 Python 热循环放大到不可用。

## 5. 硬边界遵守

未跑 Mode B 业务网格；未写 `unified_exit_modeb.py`；未改湖数据/策略书/成交核；bar_cache 产物未入库（`backtest_output/` gitignored）。
