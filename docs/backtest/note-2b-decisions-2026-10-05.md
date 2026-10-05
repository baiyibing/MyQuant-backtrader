# Step 2b 决策与勘误清单（2026-10-05 14:13 CST）

| 字段 | 值 |
|---|---|
| 日期 / 人裁 | 2026-10-05 14:13 CST（Asia/Shanghai） |
| Evidence base | 行号按 master `b57ec047c844eca2b61e4cc5a1110224a5c6b1be` 复核；之后 #372（`a37c5322`）只新增 V6F v7 fixture 与 generator 两行常量，不影响下文行号 |
| 性质 | Docs-only；记录授权与 corrected item list，本 PR 不实施代码 |
| 输入 | `.2b-items-draft.md`；`/tmp/bs2b/summary.md`、`host_facts.md`、R1 / R2 五席讨论 |

本文所有本仓 file:line 均按上述 tree 复核。下文简写 Python 文件名的路径为 `backtest/research/`；`scripts/`、`tests/` 保留完整相对路径。brainstorm 基线 `678b3300` 与草稿旧行号仅为历史，不是当前证据。

## 1. 用户决策 · 14:13 CST

以下保留用户裁定的实质；brainstorm 是建议票，人裁优先。

- **B1–B4：fold into step 3。** 测试迁移后退役 `bar_scan_exit` / `minute_true_core_wire` / host version1 round trip；不单独改。
- **A3：保持现状并文档化。** numba 仅支持默认 fill policy；custom `FillConfig` = Python backend only，non-default 在 numba 分流时 raises。
- **B9 与 C：保持现状并文档化。** engine exclusions 与 per-book strategy semantics 不改。
- **B6：version7 书规则，文档化且不改。** v7 在跌停价不买，与 qlib `TopkDropoutStrategy` 默认 `forbid_all_trade_at_limit=True` 一致。
- **B7 / B8：deferred。** B7 拟加 `on_short_cash` 参数、默认 `raise`；B8 拟统一一个 lot-rounding 函数、zero diff；本轮不做。
- **A1 limit pair 与 B5：ADOPT（2026-10-05 16:08 CST）。** 统一采用共享 open+fill pair：bar OPEN 或成交价达到跌停即顺延，沿用单一 shared eps；不改 `defer_sell_at_limit` 定义。
- **A1 pipe：do now，独立 PR。** 将 6.x side sells（`step_stop` / `scale_out` / `peak_dd_exit`；version6_8、6_10、6_13–6_17）接入 `FillConfig`；defaults byte-identical，不夹带 limit-pair rules。
- **A2：用户覆盖 brainstorm 的五席 drop。Do it。** 将 version9_2（`strategy9_2_engine`）、version12（`strategy12_engine`）及 version11 `minute_open` 收进主引擎 `csv_minute_backtest.simulate` / `HeldMinuteCursor`，只留一个 minute loop。新 baselines / overlays 单独记录，旧 ones 永不覆盖；version9_1 untouched。独立 PR，大则每书一票。

B9 的「保持排除」不撤销 A2 的明确迁移授权：日线、v7 等仍不扩围，9_2 / 12 / 11 的分钟迁移只按 A2 独立 PR 执行。本文锁住决策，不把批准后续实施写成当前已交付。

## 2. Brainstorm 终票（R2）

来源：`/tmp/bs2b/summary.md`，五席 Codex / Grok / Cursor / Kimi / GLM；R1+R2，未开 R3。票面 `drop` 指不立行为变更项，不指删除代码。

| 项 | 终票 |
|---|---|
| A1 管道 | do-now 4 / do-later 1（Cursor） |
| A1 限价对 | do-later 4 / do-now 1（Kimi） |
| A2 / A3 / B9 / C | 各 drop 5 |
| B1–B4 | fold-into-step-3 5 |
| B5 | do-later 4 / do-now 1（Kimi） |
| B6 | do-later（仅开关、默认不变）3（Codex / Grok / Kimi） / drop（书语义）2（Cursor / GLM） |
| B7 / B8 | 各 do-later 5 |

主持人勘误已按当前 tree 复核：v7 probe / add / tail 都挡跌停价买；Kimi R2 对 add 分支的相反说法不成立。A2 的最终授权来自用户，不来自票数。

## 3. Corrected item list

统一讨论口径：bar-scan backtest 在配置的 bar / 配置价成交，或带原因 skip / defer；不能由「行业惯例」推导所有书应改成同一种策略。open+fill 双检是需要单独裁决的保守研究假设。

Golden ownership 以 `scripts/research/generate_off_byte_baseline.py` 为准：历史 19 本及 `version7/minute` 冻结；S8、V61、V91、V92、S12、S9 为独立 overlays。当前 V6F 是 **v7**，文件 `tests/fixtures/off_byte_baseline_v6_family_v7_20261006.json`，revision **`strategy6-family-v7-6_2-to-6_17-20261006`**（generator:99–106；#372 因 v6 把 version6_17 首仓录成 100 万而非规则的 20 万而新增 v7，v6 保留不动）。名称中的 20261006 是 tree 内 revision 名，不改写成人裁日期。迁移目标复现 defaults；如需新 baseline / overlay，新增记录，永不覆盖历史版本。

### A1. Side sells 绕过 FillConfig（管道与限价对分票）

- **现状 / 证据：** `csv_minute_backtest.py:918–938` 在 close 相位传 `c[bar_idx]` 给三个 side-sell 函数。`minute_cash_order.py:134/171/216` 分别为 peak-dd / scale-out / step-stop；成交价检查为 :157/:201/:235，报价审计为 :163/:206/:241 的 `minute_trigger_bar_close`。step lot 另以 :229 保证 T+1。非默认配置在 `csv_minute_backtest.py:745–746` fail-closed。
- **勘误：** open+fill 对照在 `minute_cash_order.py:107–108`，属于外层 `advance_independent_exit` 闸门，**不是 HeldMinuteCursor 内部**；open 检查带 **`not pending`** 条件，fill 检查仍执行。不能把它描述成无条件双检。
- **受影响书：** version6_8 / 6_10（step）、6_13（step + scale）、6_14–6_17（step + scale + peak-dd）。已实际调用 `apply_csv_strategy` 核对；6_17 同样设置这三种 hooks（`csv_strategy_books.py:1361–1364`）。
- **裁定 / baseline：** pipe 独立 PR do-now，default byte-identical，V6F 不动；自定义时机 / 价格通过 FillConfig。限价对已于 **2026-10-05 16:08 CST ADOPT**；同 bar side sells 检查 OPEN 或 fill，next_bar_open 在执行 open 检查（open == fill）。历史只读 count「开盘跌停、成交价脱离」候选：只读计数结果（2026-10-05，master `b57ec04`，脚本 `/tmp/count2b/count_limit_pair.py`，未提交）：V92 与 V6F 共 34 个 case，目标 side-sell / touch-stop 成交 23 笔，限价对拦截 **0**，成交与净值变化 **0**。但 V92 与 7 本受影响 6.x 书的 fixture **没有任何跌停 bar**，故 0 是构造使然，fixture 无法衡量该规则；仅 6_11/6_12 突破 fixture 含跌停 bar（2 根日线 / 10 根分钟），且这两本不开 side-sell hook。本机未配置行情湖，未跑全窗。实施后如 frozen case 有差异，另录 V6F revision，旧文件保留。排队、部分卖出、跨日 carry 与优先级需在实施票验收。

### A2. Separate minute engines / minute_open 收口

- **现状 / 证据：** `csv_minute_backtest.py:747–748` 拒绝 custom config；9_2 的 `strategy9_2_engine.py:203`、v12 的 `strategy12_engine.py:234` 各有 `run_minute_day`。v11 hook 当前为 `csv_strategy_books.py:1752/1762`（旧 `1711/1721` 已漂移），pending EOD 次日开盘卖出为 `csv_minute_backtest.py:942–967`，含 volume 与跌停闸门。
- **裁定：** 三书迁入 `simulate` / `HeldMinuteCursor`，只留一个 minute loop；独立 PR，大则每书一个。version9_1 不动。v11 的昨日 EOD → 次日开盘不能简化成任意分钟信号的 next-bar-open；应保留日决策边界。
- **Baseline / 风险：** 默认目标零差异，分别对账 V92、S12、历史 v11；新记录单独存，旧记录永不覆盖。9_2 的 turtle pending / retry、v12 的逐 lot hold count 与 v11 的 pending / volume 是迁移验收重点。当前尚未实施。

### A3. Numba 仅支持 default policy

- **现状 / 证据：** `_scan_held_day_numba_trail` 在 `csv_minute_backtest.py:250`；`can_offload` :439–452 限 close 域、无 callbacks / version9 plan / range ratio 等，且 numba opt-in。:453–454 在实际可 offload 时拒绝 non-default config；默认 backend 是 Python。
- **裁定 / baseline：** keep，custom FillConfig 只用 Python。numba-ineligible 路径原本留在 Python，不是强制移入 numba；不移植配置状态机。默认 golden 影响 none。

### B1. Wire stop basis / limit 与引擎不同（probe only）

`bar_scan_exit.py:91/123–131` 按 open gap 或 low touch 止损，touch 填 line；该文件及 wire 无跌停检查。共享默认 `minute_stop_trigger="close"`（`csv_minute_backtest.py:640`），生产有跌停 deferral。探针不产 NAV。**并 step 3**，测试迁移后退役；off-byte 影响 none，不单独对齐探针成交。

### B2. Wire 字面 stop / take 表（probe only）

`minute_true_core_wire.py:150/155/195` 仍是 `_DRAWDOWN` / `_PERCENT_STOP` / `_BOOK_TAKE`；:246 定义派生，:561–563 仅缺项才 derive，字面项不随运行时 CLI overrides 变化。#370 已补 auto-derive / classification gate，不能再把旧收集失败当未解决项。**并 step 3**；golden 影响 none，不再单独修表。

### B3. Host round trip 在 T+0 抬 peak（probe only）

`minute_bar_scan_host.py:68` 的 `scan_version1_round_trip` 在不可 T+1 卖时仍更新 peak（:162–163/:172–173/:182–183/:201–202/:211–212）。主引擎约定 T+0 不卖也不抬 peak；host CLI :770 走 `run_simulate`，该旧函数服务直接调用 / 测试。**并 step 3**，迁测试后退役；golden 影响 none。

### B4. Host short budget raises（probe only）

同 host :148 短预算抛 `RuntimeError`，inline budget 无 `cash_deploy_frac` / top-up。**并 step 3**，不为退休路径重做预算；golden 影响 none。

### B5. version9_2 stop 的限价检查缺口仅在 touch

- **现状 / 证据：** `strategy9_2_engine.py:69–73` 的 gap 分支 `px = open`，所以 **gap 已检查真实 open**。只有 touch 分支将 minute close / daily trigger 作为 px，:77 包成 `SimpleNamespace(open=px)`，:92 仅检查该价；缺的是真实 bar open。
- **对照：** `csv_minute_backtest.py:1017–1019`、`strategy12_engine.py:107`、`fullstrat_research_book.py:210–212` 采用 open+fill；独立退出闸门另有 A1 所述 `not pending` 条件。
- **裁定 / baseline：** 与 A1 limit pair 一起于 **2026-10-05 16:08 CST ADOPT**。分钟 touch 检查当根 OPEN 与 cursor fill；日线 touch 检查日 OPEN 与 stop-line fill。受阻保留 turtle pending reason/quantity，两个计数器各加一，retry_day=day_i+1，当日后续 bar 不重试，次日按 open 沿用残余成交路径。只影响 version9_2，version9 / version9_1 不动。若实施命中 frozen touch 候选，V92 可变，需新增 revision；只读 count 见 A1（V92 fixture 无跌停 bar、无 touch-stop 触发，计数 0 不具代表性）。

### B6. Version7 跌停价不买是书规则

- **现状 / 证据：** `csv_minute_backtest_v7.py:549–550` 尾窗买记 `skip_limit_down`；probe :578/:789、add :562/:763 同样在跌停价不买。这是 version7 的书规则，保持。
- **Golden 勘误：** `scripts/research/generate_off_byte_baseline.py:213–216` 调 `v7.simulate_v7` **未传 tail_window_buy**；v7 :401/:624/:913 默认 False。尾窗 :549–550 在历史 `version7/minute` golden 中不可达，因此该分支 baseline impact = **none**。不是「可能命中后要改历史 golden」。
- **已钉测试：** `tests/test_tail_window_peak_audit_regressions.py:91–99` 明确断言 hm=872 → `skip_limit_down`，不是未覆盖的偶然行为。
- **行业对照：** [qlib TopkDropoutStrategy 源码](https://github.com/microsoft/qlib/blob/main/qlib/contrib/strategy/signal_strategy.py) 默认 `forbid_all_trade_at_limit=True`，涨跌停均不交易，包括跌停不买；False 则允许跌停买 / 涨停卖。两种约定都是行业做法，不能据此判本书为标签或方向错误。
- **本仓已有同名开关：** `csv_simulate_loop.py:275/372–375`；分钟 :779、日线 :341 读取 hooks；`csv_strategy_books.py:210` 默认 False，topk 书 :1850/:1932 为 True。此对照不表示给 v7 新接开关。**裁定：文档化、unchanged。**

### B7. Independent-position cash short raises

`csv_ledger.py:567–572` 在 policy 存在时抛 `InsufficientCashError`，否则 `skip_cash`；同类抛错在 `csv_simulate_loop.py:428` / `minute_cash_order.py:532`。v7 :259 记 `skip_cash`。受影响为 per_name 的 version6_1–6_17、version8 / 8_2–8_6，raise 是已写明的书契约。**Deferred：** 拟 `on_short_cash="raise"|"skip"`，默认 raise；默认基线应不动，opt-in skip 会让原本停止的长窗继续，合计可变。

### B8. Lot rounding 多处各有选项

`csv_ledger.py:473` 的 `_buy_size` 含 top-up，STAR integer / 200 下限见 :478/:556–558；override :552 整百。host 含费递减、无 top-up。其他取整：`strategy9_1_rules.py:45`、`strategy9_2_engine.py:54`、`strategy12_rules.py:222`、`ashare_volume_cap.py:84`、`tail_window_buy.py:58/102`。数量分片、容量取整、风险定仓不能混成同一种金额预算。**Deferred：** 一个 lot-rounding 函数，各调用保留当前选项和浮点顺序，zero diff；若以后改选项，另裁并新增所属 historical / V91 / V92 / S12 overlay。

### B9. Residual engine exclusions

共享 cursor 已解释 FillConfig；日线 `--stop-fill`（`csv_daily_backtest.py:302–304`）、v7 阶段语义、9_2 touch / v12 仍各有原路径。**Keep / documented**：不借统一配置合并日线或 v7，不统一书规则；9_2 / 12 / v11 后续只按 A2 迁分钟循环。当前 baseline 影响 none。

### C. Per-book strategy semantics（keep，全部不改）

| 项 | 当前证据与边界 |
|---|---|
| version8 stale timing | `strategy8_rules.py:26/113–114` 的 STALE_DAYS=8 / `force_sell:stale` 在首个可成交分钟 close 触发；不改成 15:00 close_clear |
| Hold-day origin | 共享 `csv_minute_backtest.py:888` 按 entry_idx；9_2 `strategy9_2_engine.py:33/45` 按最后 add 的 anchor_idx；v12 `strategy12_engine.py:61–66` 按 lot；各书保留 |
| 8_3 / 9_2 sizing | 8_3 `strategy8_3_rules.py:38/47–51/63` 为 50% probe、winner-only add；9_2 unit bands 保留，不统一定仓 |
| 8_3 index gate | `strategy8_3_rules.py:43` INDEX_BLOCKS_ADD=True，未定义 INDEX_GATE_ON；不等于无指数门控，不借本票改书 |
| v8 vs 8_6 take_profit | v8 `strategy8_rules.py:108–114` 要 px≥cost 并有 stale；8_6 `strategy8_6_rules.py:75–94` 没有这两项；保留 |
| version9 / version9_1 sell rules | 不改；absolute_exit 固定 bar_low（`fill_config.py:39/49–50`），version9_1 明确 untouched |

## 4. 后续入口与文档锁

[分钟扫描现状](note-minute-scan-status-2026-10-05.md) 的 11:05 人裁与 step 3 测试迁移顺序继续有效；本票补齐 14:13 的逐项裁定。[Step 2a](minute-fill-config-step2a.md) 是已交付范围锁，不能把 A1 / A2 的后续 GO 写成 2a 已支持；A3 / B9 排除保持。

原决策 PR 仅文档；A1 pipe / A2 已由后续独立 PR 交付。16:08 CST 人裁授权本次 A1 limit pair / B5 实施；B7 / B8 deferred。本次执行 frozen off-byte 与合成测试，无湖访问；逐书差异见 worktree 未提交的 `LIMIT_PAIR_DELTA.md`。
