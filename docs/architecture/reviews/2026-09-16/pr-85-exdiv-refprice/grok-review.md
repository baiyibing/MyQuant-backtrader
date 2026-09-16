# PR #85 除权日参考价修正 — Grok 核评审

> 日期：2026-09-16
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #85](https://github.com/baiyibing/MyQuant-backtrader/pull/85) `feat/exdiv-refprice`（`origin/feat/exdiv-refprice` vs `origin/master`）
> 权威：[`docs/backtest/plan-exdiv-refprice-2026-09-16.md`](../../../../backtest/plan-exdiv-refprice-2026-09-16.md) **v1.1** · [`docs/backtest/handoff-exdiv-refprice-codex-impl-2026-09-16.md`](../../../../backtest/handoff-exdiv-refprice-codex-impl-2026-09-16.md) · [zcode-facts](../plan-exdiv-refprice/zcode-facts.md) / [zcode-arch](../plan-exdiv-refprice/zcode-arch.md) / [merge-consensus](../plan-exdiv-refprice/merge-consensus.md)
> 人裁：PX-1…PX-7 **全部 GO / 是**
> HEAD：`38a1c2e8ad84ce1fc7f709c683f64aa6f10454de`
> merge-base：`546e2a73674dbbb5d0baadde9cd1ef895b6f8441`（= `origin/master`）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改成交语义）。

对照 plan v1.1 / 交接 / PX-1…PX-7：这是一次合格的 scoped 参考量修正。`rescale_position` 只改 `cost`/`peak`；5 处 prev_close 均经 `mapped_prev_close` 替换传入值，`chase_decision` / `hit_limit_up` / `_sell` / `execute_buy` / 估值 / shares / 佣金 / T+1 判定体零改。事件门 = `ex_date_index` 主 ∪ 跳变 >1e-2 兜底，k 恒 LAG 行比，噪声 ≤0.5% 不修，禁用 `dr`。`simulate(..., exdiv=None)` 仅 `run()` 加载；空 map 与旧路径一致。v7 / `*_rules.py` 不在 diff。切片 C 的 E-R6 + E-R5 收窄措辞对齐 arch §4。T1/T3/T4/T5/T8/T9/T11/T14/T15 必收向量均落地；T7/T10 未写（不在 plan 必收子集）。切片 D 宿主-only，本 PR 未勾完成。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#85 feat(research): E-R6 除权日参考价修正（exdiv refprice A/B/C）](https://github.com/baiyibing/MyQuant-backtrader/pull/85) |
| 比较 | `origin/master...origin/feat/exdiv-refprice`（16 files, +1108 / −14） |
| PX GO | `8718384` 人裁 PX-1…PX-7 全部「是」回写 |
| A | `f2c3827` `exdiv_map.py` + `tests/test_exdiv_map.py` |
| B | `c58c6d6` 5 触点 + `rescale_position` + `simulate(exdiv=)` + T 向量 |
| C | `38a1c2e` E-R6 / E-R5 收窄 + 三份「修正前口径」脚注 + D runbook（未做） |
| D | **非合入门**；runbook 已预写回收上界 +35~125 万 |

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **X-R1** 只修 cost/peak + 5 处 prev_close | **PASS** | `csv_ledger.py:140-149`：`rescale_position` 仅 `pos.cost *= k; pos.peak *= k`；`peak_hm` / `shares` / `pending_exit` / `reserved` 不动。ledger 其余 diff = 这 12 行纯函数，`_sell` / `execute_buy` / `chase_decision` / `hit_limit_*` / `COMMISSION` 原文同一。5 触点全部是 helper 替换传入的 `prev_close`，随后仍走 `_named_limits`。成交价来自行情或缩放后 trigger（既有「成交价=触发价」近似，T4 钉 D 域 4.9）。净值 `append_equity_and_eod_marks` 仍 `market_close_mark` raw close（T16）。 |
| **X-R2** 事件门 ∪ 兜底；k=LAG；禁 dr；噪声 ≤0.5% | **PASS** | `exdiv_map.py`：`is_ex` 走 ex_date_index；非 ex 且 `jump > 1e-2` 才兜底；`k = prev_cum / cum`（行到行，禁日历 D-1）。`NOISE_EPS=5e-3`：ex 事件但 jump≤ε → 不写入 map。全文件无 `dr` 列读取（ex 只读 `stock_code, ex_date`）。读窗 `start−10` 日历日，与 `warmup_start`/`WARMUP_DAYS` 同口径。缺失 adj → `{}` + 一次性 stderr。 |
| **X-R3** 5 触点顺序 + `simulate(exdiv=None)` 仅 run() 加载 | **PASS** | 日线：缩放+映射在 lot 环 `:286` 前（`:269-276`）。分钟：缩放在 `scan_held_day` `:894` 前（`:868-877`），**不**插在 scan 与 peak 回写 `:921-922` 之间。chase `:133`、pool `:204` 只换 `closes[-1]`。两引擎 `simulate` 关键字参数默认 `None`；`load_exdiv_ratios` **仅**出现在 `run()`（daily `:458` / minute `:1079`）。`test_csv_strategy_books` 直调 chase/pool 不传 exdiv → 空 map。 |
| **X-R4** v1–v6、v8–v10；v7 不接；golden 空 map | **PASS** | `*_rules.py` / `csv_minute_backtest_v7.py` **不在 diff**。E-R6 正文写明 v7 不接。T15：`exdiv=None` 与 `exdiv={}` trades 相等。CI 含既有 v1/v6 golden（`-m "not production and not benchmark"`）。 |
| **X-R5** stats 三键条件打印 | **PASS** | `csv_artifacts.py`：`exdiv_adjusted_lots` / `exdiv_prev_close_mapped` / `exdiv_skipped_no_factor` 仅 `if val` 才追加。`test_summarize_omits_zero_exdiv_stats` 断言零值无「除权」。本核复跑 `test_np3_layering.py` 绿。 |
| **X-R6** E-R6 + E-R5 收窄 + HELP×2 + README + 三脚注 | **PASS** | `engine-ashare-correctness.md` E-R5 收窄三句与 arch §4 同构（噪声带 / (1−k) pnl / v4 SMA 域 +「修正前口径」）；E-R6 含残留①②③与回收上界。两引擎 HELP_LOCK 复权段改为 E-R6。README 一句点名 E-R6。er5-recheck / np2-host-note / v8-pername 短记均加脚注。 |
| **X-R7** 不做清单 | **PASS** | 无全链复权、无 shares/红利、无 v4 SMA 换域、无湖数据、无 `*_rules.py`、无 v7。 |
| **PX-1** 作用于 v1–v6、v8–v10 | **PASS** | 两引擎共用 ledger + simulate_loop；书规则未改，0/1 次齐次谓词吃缩放后的 cost/peak。 |
| **PX-2** 噪声 ≤0.5% 不修 | **PASS** | `test_noise_band_ex_event_not_adjusted`（0.3% + ex 行 → 无 k）。 |
| **PX-3** 买入日新 lot 不调整 | **PASS** | 日环顺序：持仓缩放 → chase → pool append。`test_t6_buy_day_exdiv_no_double_scale`：D 日买入 cost=5.06。 |
| **PX-4** 检测门改回 survey C2 | **PASS** | 主源 ex ∪ 跳变>1e-2 兜底；T14 + fallback 单测。 |
| **PX-5** v4 SMA 残留另开 | **PASS** | 分钟 `daily_closes_ending_yesterday=prev_rows["close"]` 未映射；chase/pool `buy_gate(..., closes)` 仍旧域。E-R6 声明 ②。 |
| **PX-6** 残留三句 + D 上界 + 历史脚注 | **PASS** | 见 X-R6；D runbook 预写 149→~120–144 与 +35~125 万。 |
| **PX-7** v7 不接 + 假成交消失断言 | **PASS** | v7 不在 diff；T3 断言映射后 D open=4.50 → `defer_sell_limit_down`、无当日 SELL。 |
| **T1–T16 必收** T1/T3/T4/T5/T8/T9/T11/T14/T15 | **PASS**（T7/T10 未写，见 nit） | 见下表。 |
| UTF-8 无 BOM、NUL=0 | **PASS** | 新/改 py 8 文件 BOM=false、NUL=0。 |
| 切片 D | **N/A（非门）** | runbook 标明 host-only；PR 未勾完成。 |

### 5 触点（HEAD 行号）

| 触点 | 落点 | 形态 |
|------|------|------|
| 日线持仓 | `csv_daily_backtest.py:269-276` | `k_for` → `rescale_position` → `mapped_prev_close` → `_named_limits`；lot 环在 `:286` |
| 分钟持仓 | `csv_minute_backtest.py:868-877` | 同上，在 `scan_held_day` `:894` 之前；peak 回写 `:921-922` 之后无缩放 |
| 共享 chase | `csv_simulate_loop.py:133` + 两引擎传入 `exdiv=`/`ds=` | 只换 prev_close；`chase_decision(open_px, buy_px, limit_up)` 未改 |
| 共享 pool 买 | `csv_simulate_loop.py:204` | 只换 prev_close；`hit_limit_up(px, limit_up)` / `execute_buy` 未改 |
| helper | `exdiv_map.mapped_prev_close` / `k_for` | 空 map → raw / None |

### T 向量覆盖

| # | 必收？ | 测试 | 核验 |
|---|--------|------|------|
| T1 假止损消失 | 是 | `test_t1_*_v1` / `_v8` / `test_t1_minute_*` | v1 mild k=0.90 open 9.50：未映射 gap_open，映射后持有；分钟同构 |
| T2 档位 | 否 | `test_t2_limit_mapping_d_domain` | 只测 `limit_prices(5.0)→(5.50,4.50)`，未走引擎日 |
| T3 假成交消失 | 是 | `test_t3_*` | 映射后 4.50 → defer、无 fill。未映射 k=0.5 的 4.50 在 E-R1 下**也会** defer（unmapped LD=9.0）；假 fill 改用 mild open 9.50 对照——适配正确，不是漏断言 |
| T4 touch D 域价 | 是 | `test_t4_*` | SELL `stop_loss:touch` @ **4.9** |
| T5 band 一致性 | 是 | `test_t5_*` | `trail:band:15`；**未钉**成交价 5.70 / 地板 5.75（nit） |
| T6 买入日无双重缩放 | 否 | `test_t6_*` | cost=5.06 |
| T7 pending_exit 跨除权 | 否 | **缺** | 实现顺序覆盖（缩放后走 pending 开盘成交/跌停 defer），无向量单测 |
| T8 chase 到期=除权日 | 是 | `test_t8_*` | chase:T+1 @5.20、`exdiv_prev_close_mapped≥1`；缺反向 px=5.50 拦截（nit） |
| T9 pool 涨停挂 chase | 是 | `test_t9_*` | 未映射 buys=1；映射 skip_limit_up=1 且当日无 pool BUY |
| T10 多 lot / 多事件 | 否 | **缺** | 实现按 (code,ymd) 逐日 ×k，逻辑自洽，无 fixture |
| T11 停牌跨界 | 是 | `test_t11_*` | 注入 k 在复牌日 R；引擎在首个有 K 日缩放。map 层依赖湖「跳变落复牌首行」（facts 口径；切片 D 宿主三项） |
| T12 噪声带 | 否 | `test_noise_band_*` | 0.3% + ex → 无 k |
| T13 NaN/缺行 | 否 | `test_nan_factor_*` | 空 map + skipped≥1 |
| T14 检测门 | 是 | `test_t14_*` + `test_fallback_jump_*` | 0.8% 无 ex 不修；2% 无 ex 兜底 k=1/1.02 |
| T15 空 map | 是 | `test_t15_*` | `None` vs `{}` trades 相等 |
| T16 净值 raw close | 否 | `test_t16_*` | D 日 equity 仍按下折（防误修估值） |

### 依赖（HEAD，无环）

```
csv_daily_backtest  ─┬→ csv_ledger.rescale_position
csv_minute_backtest ─┤→ exdiv_map.{k_for, mapped_prev_close, load_exdiv_ratios}  （仅 run() 调 load）
csv_simulate_loop   ─┘→ exdiv_map.mapped_prev_close
exdiv_map → oskh_core.normalize_a_share_code
          → common.infra.data_root.resolve_source_parquet
          → exdiv_hold_hits.normalize_date   ← 探针模块（nit）
csv_ledger ↛ 引擎；↛ exdiv_map
```

`csv_minute_backtest_v7` 不在此图。

---

## 违规 / 风险

无 🔴。无合入阻断。

### nit-1（覆盖宽度，非锁违例）T7 / T10 未写向量

plan §4 B 写「评审向量 T1–T16，**必收** T1/T3/T4/T5/T8/T9/T11/T14/T15」。必收 9 条均有测试。T7（pending_exit 跨除权执行）与 T10（多 lot / 多事件复合）在 arch 全表中，实现按日环顺序与 `(code,ymd)` 查表可推自洽，但没有 fixture 锁死。不构成 BLOCK；合入后可补，不必重切。

### nit-2（断言紧度）T5 只锁 reason、T8 缺反向拦截

T5 向量原文：px 5.70 → `trail:band:15` **@5.70**（地板 5.75）。现测只 `assert sells[0]["reason"] == "trail:band:15"`。T8 原文反向「px=5.50 时 mapped limit 拦截、unmapped 误放行」未写。正向路径已绿。

### nit-3（卫生）引擎导入 NP2 探针模块

`exdiv_map.py:26`：`from backtest.research.exdiv_hold_hits import normalize_date`。hold_hits 声明「No engine imports」，当前无环；但向量化主路径因此依赖 NP2 探针文件。`normalize_date` 宜下沉到 `exdiv_map`（或 common）以免探针日后加引擎 import 成环。不改行为。

### nit-4（围栏）`exdiv_map` 未入 `_VECTORIZED_RESEARCH_FACE`

`tests/test_research_face_imports.py` 白名单仍是 NP3 的 7 模块。`exdiv_map.py` 已被 rglob AST 零 `backtrader` 扫到；daily/minute 子进程 import 会顺带加载它。与 `csv_ledger` 本就不在白名单的既有口径一致，不是新红。可选补一行。

### nit-5（注释）`_read_parquet_cols` 声称双形态过滤

`exdiv_map.py:152-154` 注释写「Include both raw and normalized forms」，实现只把 **已 normalize** 的 `code_set` 推进 pyarrow `in` 过滤。湖契约 `stock_code` = `^\d{6}\.(SH|SZ|BJ)$` 违例 0（survey §1①），与 `normalize_a_share_code` 同构，**现网不会漏行**。注释过时；若将来湖码无后缀，pushdown 成功但 0 行且不 fallback（fallback 只在 filters 抛异常时）。建议改注释，或 filters 失败/空表时再读全列。非本窗 BLOCK。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| T3 与 E-R1 | k=0.5、open=4.50 在未映射时 LD=9.0，E-R1 同样 defer。原 arch 向量「修正前会以 4.5 成交」与现行跌停拦截不合；测试改为 mild 对照，这是正确适配。 |
| 分钟必收向量 | 除 T1 外必收条只跑日线。共享 chase/pool 两引擎走同一 helper，分钟持仓缩放与日线同构。 |
| 停牌 × ex 主源 | 若 adj_factor 跳变落在复牌首行（facts 口径），ex 日 D 无跳变 → 噪声抑制，R 走 >1e-2 兜底，引擎在 R 缩放（T11）。若某码占位零量 K 被 E-R4 丢弃但因子行记在该日，map 键在 D、引擎看不到 D——切片 D 宿主三项覆盖，非合入门。 |
| CI vs 本地计数 | CI [`35074444121`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35074444121)： **603 passed, 5 skipped, 24 deselected, 3 warnings / 18.94s**。PR 正文本地 `pytest -q tests/` 宣称 629 / 3 skipped。与 workflow `-m "not production and not benchmark"` 口径差可对上（PR #78 同模式）。 |
| pandas 告警 | CI 3 warnings 含 minute `:309` `copy=False` Pandas4Warning，在**未改**的 annotate 路径，非本轮引入。 |
| 切片 D | 未做；runbook 禁止本 PR/CI 勾完成。v8 规则 v2 切片 D 仍挂本片合入 + 宿主重跑。 |
| `#81` 冲突面 | `origin/feat/v8-rules-v2` vs master **仅** `docs/backtest/plan-v8-rules-v2-2026-09-16.md`（+11）。引擎文件当前无交集（A–C 已在 master 侧）。后合者无 rebase 负担；v2-D 仍等本片 + 宿主 D。 |
| `#84` 冲突面 | 同文件三处：`csv_daily_backtest.py` / `csv_minute_backtest.py` / `csv_simulate_loop.py`。#85 在 `simulate`/`run`/`run_pool_buys_day`/`run_chase_due_day` **尾部加 `exdiv=`**；#84 在 `prepare_strategy_hooks` 加 `**extra`、`run_pool_buys_day` 加 `planned_for_day`（替换名单后再 ration）。**同函数不同关键字，后合者必 rebase**；语义正交（参考价 vs 名单 overlay），无逻辑抢写。持仓环 / HELP_LOCK / `mapped_prev_close` 仅 #85。 |

---

## 建议动作（是否可合）

**可以合入 master。** 不要为 nit-1…5 重开切片或阻塞 PR。合入后若顺手（非本 PR）：

1. 补 T7 pending_exit 跨除权 + T10 双 lot/双事件 fixture（nit-1）。
2. T5 钉 fill 价；T8 加 px=5.50 反向拦截（nit-2）。
3. `normalize_date` 搬出 `exdiv_hold_hits`（nit-3）。
4. `_VECTORIZED_RESEARCH_FACE` 可加 `exdiv_map`（nit-4）；不要顺手扩到无关模块。
5. 后合 #84 时：`run_pool_buys_day` 同时保留 `exdiv=` 与 `planned_for_day=`；不要把 mapped prev_close 绑进 overlay。
6. 切片 D 仍由宿主按 runbook 跑；本核不宣称 D 完成，不放行 v2-D。

本核 **未 merge、未改引擎业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git merge-base origin/master origin/feat/exdiv-refprice
# = 546e2a73674dbbb5d0baadde9cd1ef895b6f8441
gh pr view 85 --json number,title,mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / pytest-and-gates SUCCESS
gh run view 35074444121   # 603 passed, 5 skipped, 24 deselected
/workspace/vanna312/bin/python -m pytest -q \
  tests/test_exdiv_map.py tests/test_exdiv_refprice_engines.py \
  tests/test_np3_layering.py tests/test_research_face_imports.py
# 102 passed in 9.85s
```

BOM/NUL、事件门/k/dr、5 触点 diff、v7/`*_rules.py` 空 diff、#81/#84 文件交集：本核脚本对照 `origin/master` 与 HEAD。

全量 `pytest -q tests/` 以 CI `python-tests` SUCCESS 为准（本核只复跑上列 102）。
