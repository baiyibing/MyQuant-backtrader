# PR #81 v8 规则 v2 — Grok 核评审

> 日期：2026-09-16  
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）  
> 对象：[PR #81](https://github.com/baiyibing/MyQuant-backtrader/pull/81) `feat/v8-rules-v2`（`origin/feat/v8-rules-v2` vs `origin/master`）  
> 权威：[plan-v8-rules-v2-2026-09-16.md](../../../../backtest/plan-v8-rules-v2-2026-09-16.md) **v1.1** · [handoff-v8-rules-v2-codex-impl-2026-09-16.md](../../../../backtest/handoff-v8-rules-v2-codex-impl-2026-09-16.md) · [zcode-facts](../plan-v8-rules-v2/zcode-facts.md) / [zcode-arch](../plan-v8-rules-v2/zcode-arch.md) / [merge-consensus](../plan-v8-rules-v2/merge-consensus.md)  
> HEAD：`61c6c6656e44bd788774b672f874bcb851729413`  
> merge-base：`bd32d5f184d146fcc3ab3bee2c3c1dad03405754`（= `origin/master`，含 #85+#84）  
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35078556395](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35078556395)）  
> 覆盖：同路径旧文是脚手架 BLOCK（当时 PR 相对 master 仅 plan §11 +11 行、无 A/B/C 实码）。本文件取代之。

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改成交语义。本核不 merge）。

对照 plan v1.1 / 交接 / V-R1…V-R5：这是一次合格的 v8 规则 v2 落地。切片 A 把止盈改成价格比较分档 + `n_days<2` 门 + `px≥cost` 守卫 + `trail:band:{1..5}`；切片 B **只删** `csv_strategy_books.py` per_name→`allow_add=False` 两行，成交核 / `csv_ledger.py` / `csv_simulate_loop.py` 不在 diff；切片 C 换齐 HELP/README/归档取代注记/pre_er1 禁再生成，并顺带翻转 rebase 后 facts 未列的 np3 summarize 与 exdiv T5 golden。v6 对照、v1/v6 golden、v9/v10/`topk_dropout` 的 `allow_add=False` 均未误伤。切片 D 非合入门，本 PR 未勾。

Codex STOP（facts §4b `:88-93` 期望日与引擎差一天）：**核可接受**。plan §1 是唯一数学权威；该期望是预实施手推，把 T+2 close 11.85 误判为触 档3 线 11.80。引擎按收盘评估、次日开盘离场，实际 T+3 close 11.7 触线、`20251107@11.7 trail:band:3`。单测按代码并注释 STOP，plan §11 / 交接 §6 已记。不构成 BLOCK。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#81 v8 规则 v2（plan v1.1 A–C，Codex 实施；D 挂 E-R5 后）](https://github.com/baiyibing/MyQuant-backtrader/pull/81) |
| 比较 | `origin/master...origin/feat/v8-rules-v2`（18 files, +341 / −174） |
| scaffold | `3665aab` 实施记录表 |
| **A** | `241b607` `strategy8_rules` 价式 band + `n_days<2` + record/summarize 键 + 向量单测 |
| **B** | `5176cab` 删 books 覆写两行；facts §4 翻转；引擎向量 #21 |
| **C** | `61c6c66` HELP/README/归档/pre_er1 冻结；np3 summarize + exdiv T5 reason |
| **D** | **非合入门**；挂 E-R5 复核后宿主 5 亿重跑 |

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **V-R1** 只改 v8 规则与 per_name 加仓锁；1–6/9/10 逐字节；成交核不动 | **PASS** | 禁区不在 diff：`csv_ledger.py` / `csv_simulate_loop.py` / `csv_minute_backtest_v7.py` / `strategy{1–7,9,10}_rules.py` / golden CSV。v6 对照仍 `skip_held==1`（`test_csv_daily_backtest_v8.py:248-251`、minute 同构）。v1/v6 `test_daily_quota_trades_byte_identical` 原文还在，夹具未改。registry 仍仅 v8 为 `sizing="per_name"`；v9/v10/`topk_dropout` `ALLOW_ADD=False`。 |
| **V-R2** band 数据化 + 价格比较 + `n_days: int = 1` 契约 | **PASS** | `strategy8_rules.py:20-25` `BAND_ARMS=(0.06,0.15,0.50,1.00)` / `BAND_KEEPS=(0.30,0.60,0.70,0.80)` / `BAND2_ABS_MULT=1.02` / `BAND3_GLOBAL_MULT=1.15`。`band_of` 用 `peak` vs `cost×(1+arm)`（`:43-51`：6%/15% 用 `<`，50%/100% 用 `≤`）对齐 plan 开闭 `(0,6%)/[6%,15%)/[15%,50%]/(50%,100%]/(100%,∞)`。`take_profit_reason(..., n_days: int = 1)` 签名未改；日线 `:346` / 分钟 `:612` 仍 4 参位置传 `n_days`。 |
| **V-R3** 加仓恢复 = 删 books 两行覆写 | **PASS** | 切片 B 对 `csv_strategy_books.py` **仅** `-2`：删 `if book.sizing == "per_name": hooks["allow_add"]=False`。HEAD `:106` 只留 `hooks["allow_add"] = book.allow_add`。本核直调：v8 `allow_add is True`；v1/v6/v9/v10 `False`。`ALLOW_ADD=True` 现状未改。 |
| **V-R4** golden 不红；facts §4 翻转；summarize 键同步 | **PASS**（§4b 首例按引擎，见 STOP 裁决） | facts 4a 整文件重写；4b 止损两例未动、其余日期/reason/加仓已翻；4c T+1 scan `idx==-1` + 加仓；4d per_name 加仓/chase held；4e `:324 allow_add is True`（易漏，已收）；4f `test_csv_minute_backtest.py` **不在 diff**。`record_strategy8_params` 写 `band_arms/keeps/band2_abs_mult/band3_global_mult`；消费点随 NP3 迁到 `csv_artifacts.py:48-59`（`.get` 带默认，无 KeyError）。 |
| **V-R5** `n_days≥2` 单点覆盖两引擎 | **PASS** | 规则头 `:79-80` `if int(n_days) < 2: return None`。T+1 峰值仍更新（日线 `:308-333` 在 `n_days>=1` 块内；分钟 scan `:571-577`）。numba 路径本 PR 未碰（v8 仍注入 callable，不可达）。 |
| **plan §1** 触发线 / reason / px≥cost | **PASS** | 档1 `cost+0.30×(peak−cost)`；档2 `cost×1.02`；档3 `max(cost×1.15, cost+0.60×(peak−cost))`；档4/5 keep 0.70/0.80。`px ≤ line` → `trail:band:{band}`。`px < cost` 守卫保留（`px==cost` 可止盈，向量 #4）。`csv_ledger.py:260` `reason.startswith("trail")` 仍吃新 reason。旧 `trail:band:15` / `trail:peak_dd` 退役。 |
| arch 必收 **#6/#10/#14/#16/#20/#21/#22** | **PASS**（冲突行以 plan §1 为准） | 见下表。#21 日线 simulate + 分钟 `scan_held_day(n_days=2)` 各一。 |
| 切片 C 文档 + pre_er1 禁再生成 | **PASS** | `strategy8_rules` docstring/HELP_LOCK；两引擎 HELP（per_name 加仓 + v8 T+1 只评止损）；README v8 段；归档 money-modes 头取代注记；`tests/fixtures/csv_engine_pre_er1/README.md` + `generate_snapshot.py` 顶部禁再生成。存在性断言 `test_pre_er1_trades_snapshot_exists` 未改。 |
| 与 **#85 / #84 / #78** 共存 | **PASS** | merge-base 已含三者。#85：只把 T5 reason `trail:band:15`→`trail:band:3`（缩放后 cost=5/peak=6/px=5.70，档3 线 5.75；本核复算成立）；ledger/simulate 未再动。#84：`topk_dropout` 非 per_name、`ALLOW_ADD=False`，删覆写不影响。#78：summarize 在 `csv_artifacts.py`，A 片正确改消费点而非已搬走的 daily `:590`。 |
| UTF-8 无 BOM、NUL=0 | **PASS** | 本核抽查 12 个改动 py：BOM=false、NUL=0。 |
| 切片 D | **N/A（非门）** | plan §11 / 交接 §6 标明挂 E-R5；本 PR 未跑 5 亿、未报 days==1 trail 占比。 |

### plan §1 档位 vs 实现（cost=10，本核复算）

| 档 | plan 区间 | 实现 | 线 | 本核抽检 |
|----|-----------|------|----|----------|
| 1 | (0, 6%) | `p < cost×1.06` | `cost+0.30×(p−c)` | peak=10.60 因 `10.6 < 10.600000000000001` 落一档（Y1 价式锁）；线 10.18；10.18 触 / 10.19 不触 |
| 2 | [6%, 15%) | `p < cost×1.15` | `cost×1.02` | peak=10.601 → 档2；10.20 等号触 |
| 3 | [15%, 50%] | `p ≤ cost×1.50` | `max(cost×1.15, cost+0.60×(p−c))` | `11.50 < 11.5` 为 False → 档3（plan 含 15%；arch #10「价式二档」不采用）；peak=13 线 **11.80** |
| 4 | (50%, 100%] | `p ≤ cost×2.00` | `cost+0.70×(p−c)` | #14 15.00 留三档；#16 20.00 留四档，线 17.0 |
| 5 | (100%, ∞) | else | `cost+0.80×(p−c)` | peak=30 线 26；25.99 触 |

### 向量覆盖

| # | 必收？ | 测试 | 核验 |
|---|--------|------|------|
| 1 g≤0 / 低于成本 | 否 | `test_vector_1_*` / `test_take_profit_below_cost_*` | None / None |
| 3–4 档1 线与保本 | 否 | `test_vector_3_4_*` | 10.015 触；px=cost 触 |
| 5 近 6% | 否 | `test_vector_5_*` | 10.18 不触 / 10.17 触 |
| **6** 浮点 6% | **是** | `test_vector_6_*` | 价式一档；**不**采用 arch「px=10.19 触发」（线 10.18） |
| 7 跨 6% | 否 | `test_vector_7_*` | 10.599 档1 / 10.601 档2 |
| 9 档2 +2% | 否 | `test_vector_9_*` | 10.19 触 / 10.21 不触 |
| **10–11** 15% | **是** | `test_vector_10_11_*` | 11.50→档3 线 11.5；px=11.49 触（arch「二档 None」与 plan 冲突，以 plan 为准） |
| 12 kink 25% | 否 | `test_vector_12_*` | 线 11.5 |
| **14** 50% | **是** | `test_vector_14_*` | 留三档，线 13.0 |
| 15 刚过 50% | 否 | `test_vector_15_*` | 档4，线 ≈13.507 |
| **16** 100% | **是** | `test_vector_16_*` | 留四档，线 17.0 |
| 17–18 档5 | 否 | `test_vector_17_18_*` | 含 #18 peak=30 |
| 19 跨档低于成本 | 否 | `test_vector_19_*` | None |
| **20** T+1 门 | **是** | `test_vector_20_*` | 默认 n_days=1 与三参全 None；n_days=2 深档可触 |
| **21** 反弹抬 peak | **是** | 单测 + daily `test_peak_cross_15pct_*` + minute `test_scan_peak_cross_15pct_*` | 11.49 档2 不触 11.40；11.51 档3 触；日线卖日 20251106@11.30 |
| **22** 等号 | **是** | `test_vector_22_*` | 档1 等号 10.18（非旧 +2%）；档2 等号 10.20 |

---

## Codex STOP：facts §4b 期望日（核裁决）

facts §4b 原文：`:88-93 → T+1 不评、T+2 触发、卖日 20251106@11.80`。  
引擎 + 单测：`20251107@11.7` / `trail:band:3`。

独立推演（`test_band_tp_exits_next_open`，买入日=0，日线收盘评估、次日开盘离场）：

| 日 | n_days | OHLC 要点 | peak | 线（档3） | TP |
|----|--------|-----------|------|-----------|----|
| 20251103 | 0 | 买 close=10 | 10（T+0 不计 high） | — | 不评 |
| 20251104 T+1 | 1 | high=13.0, close=11.489 | **13.0** | 11.80 | **门挡**（若评则会触） |
| 20251105 T+2 | 2 | close=**11.85** | 13.0 | 11.80 | 11.85 ≰ 11.80 → **不触** |
| 20251106 T+3 | 3 | close=11.7 | 13.0 | 11.80 | 触 → pending |
| 20251107 | 4 | open=11.7 | | | 成交 `trail:band:3` @11.7 |

facts 手推把「T+2 触发」写成了卖日 20251106@11.80（等于 T+2 **开盘**，不是收盘）。plan §1 未改日线评估时点。其余 4b 三条（`:106-111` 20251106@10.10、`:124-129` 20251107@10.02、`:143-145` 20251106@11.30）与引擎一致。

**裁决**：接受单测按代码；不要求改引擎去贴合 facts 手推。建议合入后在 facts §4b 加勘误一句（非合入门）。

arch #6/#10/#22 同理：表内部分 px/档位与 plan 价式开闭打架；单测以 plan §1 为准并注释。Y1 已锁价格比较，6% 精确点落入档1 是 IEEE 后果，不是实现偏了表。

---

## 违规 / nits

无 🔴。nits 不挡合入：

1. **plan §7 落点仍写** `csv_daily_backtest.py:590-598` summarize。NP3 后消费点是 `csv_artifacts.py`；A 片改对了文件，plan 字面未回写。  
   - File: `docs/backtest/plan-v8-rules-v2-2026-09-16.md:96`  
   - Suggestion: 合入后勘误一行「summarize 随 #78 在 `csv_artifacts`」。

2. **分钟 T+1 旧触价四例只断言 `idx==-1`**，未给同一 K 线 `n_days=2` 正例。跨 15% 已有 #21；小档 / 深档 T+2 触价靠 rules 单测间接覆盖。  
   - File: `tests/test_csv_minute_backtest_v8.py:79`  
   - Suggestion: 非必须；若补，复制四组 bars 把 `n_days=2` 即可。

3. **T5 仍只钉 reason**（现 `trail:band:3`），未钉成交价 5.70 / 线 5.75。#85 核已记同一 nit，本 PR 只翻字符串。  
   - File: `tests/test_exdiv_refprice_engines.py:236`

4. **`generate_snapshot.py` 仍可执行**；冻结靠注释 + README（切片 C 要求是注记，不是 chmod）。可接受。

---

## 明确未做 / 不挡

- 切片 D：双引擎 5 亿重跑、days==1 trail 占比对照、峰值并发——plan 已锁宿主、挂 E-R5。  
- 本核未在沙箱跑全量 pytest（无 vanna312 / 无 pytest 模块）。CI `pytest-and-gates` SUCCESS；Codex 本机宣称 665 passed / 3 skipped。本核独立跑通 `strategy8_rules` 向量与 books `allow_add` 钩子。  
- 未 merge、未改源码。
