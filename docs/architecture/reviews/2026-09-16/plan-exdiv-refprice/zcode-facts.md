# 除权修正片 plan 事实锚点评审（host: zcode-facts）

> 评审对象：plan-exdiv-refprice-2026-09-16.md v1.0 · 结论 **READY-AFTER-FIXES**（4🔴，v1.1 已全采纳）
> 完整版见评审会话；本文件为施工要点版（勘误已回写 plan v1.1）。

## 关键锚点（切片 B 施工图）

**日线 `csv_daily_backtest.py`**：日环 :248；持仓码环 :253；bar 取得 :256-259（无 bar 不进缩放）；**prev_close :260 → _named_limits :261**（映射必须在 :261 前替换 :260 值，保持 round_fen 在 D 域内）；**lot 环 :266**（缩放落点，须在其前）；pending_exit :269-274（reason 非价格，open 成交不引用 cost）；止损 trigger :279；peak 更新 :301；止盈 :314；chase :328-346；pool 买 :348-373（当日买入 lot 在缩放 pass 后 append——PX-3 结构性保证）。

**分钟 `csv_minute_backtest.py`**：日环 :846；码环 :851-854（无 K guard :854）；prev_rows/prev_close :859-862；_named_limits :863-867；**lot 环 :872-874（缩放落点）**；scan_held_day 调用 :875-901（cost/peak 按值传参 :879-880）；**peak 回写 :902-903**（缩放绝不插在 :875 与回写之间）；scan 内 new_peak 初始化 :561 = 传入 peak（缩放后起点同域 ✓）。

**共享 `csv_simulate_loop.py`**：chase prev_close :129-130 → _named_limits → chase_decision :135；**pool 买 prev_close :195-196 → hit_limit_up :201**（v1.0 漏——除权日涨停拦截/挂 chase 失效）。

**数据层**：`resolve_source_parquet` 不检查存在性（`common/infra/data_root.py:270-299`，FileNotFoundError 归调用方）→ 模块内 `is_file()` + try/except（范本 `l2_analytics/ref_data.py:30-34`）；真实 env 旋钮 `OSKH_SOURCE_PARQUET_ROOT`（constants.py:1173）——**不存在 `OSKH_ADJ_FACTOR`**。

**adj_factor 停牌口径**（`oskh_data/adj_factor.py:82-162`）：front∪none outer-merge + ffill → 停牌段因子恒定、跳变落复牌首成交行 = 引擎可见 bar 日 ✓；**k 必须行到行 LAG（禁日历 D-1）**；宿主实测三项保留（占位行/front 连续性/28 起无因子行码）。

**golden/测试**：v1/v6 golden 驱动链 = `test_csv_strategy_books.py:337-352` → `generate_snapshot.py:31-34` 直调 `sim.simulate` 注入合成 bars ✓；**布线锁**：`simulate(..., exdiv=None)` 显式参数（内部自动加载会使宿主 golden 变 273MB 湖依赖）；stats 全字典断言仅三处且 SimpleNamespace 起步（安全）；`test_np3_layering.py:22-67` summarize 全文 golden → 新 stats 行条件打印；合成 parquet fixture 复用 `test_exdiv_hold_hits.py:137-163` 模式（date 列双兼容，`normalize_date`）。

## 勘误表（v1.1 已采纳）

| # | 勘误 | 级别 |
|---|------|------|
| 1 | X-R3 补 pool 买侧第 5 触点（:195-202） | 🔴 |
| 2 | 「与 v2 无文件冲突」→「同文件不同区域，后合者 rebase」；v2 plan :590-598 行号因 NP3 过期 | 🔴 |
| 3 | 检测源层级反转 → 改回 ex_date_index 主 ∪ 跳变>1e-2 兜底（survey C2 / probe DESIGN_LOCKS） | 🔴 |
| 4 | `OSKH_ADJ_FACTOR` env 不存在 → 参数注入 / `OSKH_SOURCE_PARQUET_ROOT` | 🔴 |
| 5 | §6/§7 cost 落点自相矛盾 → 定稿 ledger 纯函数 `rescale_position` | 🟡 |
| 6 | simulate 布线未钉 → `exdiv=None` 参数锁 | 🔴 |
| 7 | 读窗须含 warmup（start−10d）否则首日事件丢 k | 🟡 |
| 8 | v4 SMA gate closes 链不映射 = 未声明残留 → E-R6 声明 ②（PX-5） | 🟡 |
| 9 | pending_exit 无触发价存储（grep 证实）→ 无需处理 | 🟢 结案 |
| 10 | 行号勘误：日线 prev_close :260-261（非 :352-353）；分钟回写 :902-903（非 :895-898） | 🟢 |
