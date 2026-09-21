# PR #151 strategy12 金榕元均线减仓书 — Grok 核评审

> 日期：2026-09-21
> 角色：MyQuant-backtrader Grok 核（只审不合入）
> 对象：[PR #151](https://github.com/baiyibing/MyQuant-backtrader/pull/151) `feat/strategy12-jinrongyuan` → `master`
> 权威：[handoff-strategy12-codex-impl-2026-09-21.md](../../../../backtest/handoff-strategy12-codex-impl-2026-09-21.md) §0 + 切片 A–C · [plan-strategy12-jinrongyuan-2026-09-21.md](../../../../backtest/plan-strategy12-jinrongyuan-2026-09-21.md) v1.0 · 人裁 latch=A / residual=2 · [merge-consensus S1–S19](../plan-strategy12-jinrongyuan/merge-consensus.md)
> HEAD：`ce29d46367781a805f49d94bf414b3e8754d1a31`
> merge-base：`32b78b174d75fcdf6bccbb3a92ba3fb37fe1d50f`（= 本工作区 `master`，含 ma_infra #150/#154）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35571960153](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35571960153) @ `ce29d46`）
> 本核 **未 merge**。CI 绿不是合入条件；切片 D 非 A–C 合入门。

---

## 结论

**PASS_WITH_NITS**（A–C 齐、人裁已编码、S1 已修；nits 不改成交语义。本核不 merge）。

对照 handoff §0、plan v1.0、以及 PR 上锁定的 latch=A / residual=2 / S1 三刀：这是一次合格的策略 12 落地。切片 A 把昨收 MA5/MA10 纯函数、周期锁、残余记忆和 lot 顺序钉死；切片 B 把 `pos.shares -= shares` 提到 volume_cap/exdiv 条件外，默认路径部分卖不再静默丢股；切片 C 把双通道状态挂在 `st.book_state`，并按 P12 四键注册 `version12`。默认书走 `run_*_day is None` 的 else 分支，12 本既有书 trades/equity 字节指纹与宣称的切片 B 前基线一致。

切片 D（实湖五点对比）未跑。按交接：A–C 完整且诚实则 **不得仅因缺 D 判 FAIL**。记 N/A，不挡本核。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#151 strategy12 jinrongyuan MA de-risk book](https://github.com/baiyibing/MyQuant-backtrader/pull/151) |
| 比较 | `master...feat/strategy12-jinrongyuan`（16 files, +1933 / −429） |
| docs-first | `9ddc169` 交接 · `e83feaf` latch=A · `fa20f04` residual=2 |
| **A** | `9fa8b27` `strategy12_rules` + data-free pins |
| **B** | `86a2880` `_sell` 守恒 / `shares_override` / `run_buybacks_day` / entitle 回调 |
| **C** | `ce29d46` `strategy12_engine` + 注册 + 双引擎接线 |
| **D** | **未跑**（handoff 实施回填已标明；非 A–C 门） |

`git log --oneline master..HEAD`：

```text
ce29d46 feat(research): wire and register strategy12 dual-channel buybacks
86a2880 fix(research): conserve partial sells and support bounded buyback fills
9fa8b27 feat(research): strategy12 MA rules with cycle latch and retained residuals
fa20f04 docs(handoff): human cut residual=2 keep <100 buyback memory
e83feaf docs(handoff): human cut latch=A cycle-only for strategy12
9ddc169 docs(handoff): strategy12 codex implementation handoff (plan v1.0 GO at d75f9c9)
```

---

## 范围

| 锁 | 结果 | 证据 |
|----|------|------|
| 禁改 1–10 / 8.x 书与 Mode A/B | **PASS** | `git diff --name-only master...HEAD` 无 `strategy{1-10,_8_*}_rules.py`、无 `unified_exit_mode{a,b}`、无 LEBS / live。`csv_strategy_books.py` 只加 `version12` 注册 + hooks `setdefault`；既有 `_apply_version*` 零改。 |
| 不占 `version11` | **PASS** | `csv_strategy_names()` 仍从 version10 跳到 version12；`test_csv_strategy_books.py` 清单 pin。 |
| γ 三触点以外零行为 diff | **PASS** | 日线/分钟 `simulate` 默认路径只被包进 `else`（`run_*_day` 未登记时）；`append_equity_and_eod_marks` 仍是日环唯一无条件语句（`tests/test_p4_touch_mark_separation.py` AST pin 仍绿）。`entitle(..., on_event=None)` 在空仓+无回调时与旧 `if not quantities: return None` 等价。 |
| `scan_held_day` 5-tuple | **PASS** | 仅增 `exit_plan` / `exit_state` 可选参数；numba 卸载条件含 `exit_plan is None`。`test_scanner_keeps_five_tuple_and_reports_partial_size_out_param`。 |
| 记忆挂 `st` | **PASS** | `st.book_state["strategy12"]`；无模块级 dict。`test_memory_is_per_run_and_wiring_does_not_inherit_v8_exits`。 |
| UTF-8 无 BOM / NUL=0 | **PASS** | 本核抽查 15 个触及文本：BOM=false、NUL=0；`git diff --check` 干净。 |

日线 +417/−190、分钟 +498/−211 的行数来自默认环缩进 + v12 `run()` 价域门，不是把 1–10 卖环改写进 hook。`-w` diff 确认 else 内原循环仍在。

---

## 人裁（必须已编码）

### 1. Latch = A（周期锁 only）

| 要求 | 结果 | 证据 |
|------|------|------|
| 同一下方周期只减一次 | **PASS** | `exit_plan`：`if memory.reduced.latched: return None`。`Memory` 无日期字段。`test_uninterrupted_below_cycle_does_not_reduce_again_on_later_days`：三根 9.9 只减一次。 |
| 成功收复并买回后立即再武装 | **PASS** | `Memory.reclaimed`：扣实际成交后若 `shares < 100` 则 `latched=False`（整百买完或只剩尘埃）。 |
| 同日再跌破允许再减 | **PASS** | 人裁示例（1000→减 500→买回 500 T+1 锁→再破卖 200）由 `test_minute_cycle_rearms_same_day_and_new_buys_remain_t1_locked` 钉死：`REDUCE 500, RECLAIM5 500, REDUCE 200, RECLAIM5 200`。规则层 `test_cycle_only_same_day_rederisk_and_partial_fill_stays_pending`。 |
| 不叠每日一次 / once-per-day | **PASS** | 全仓无 `derisk_day` / daily latch。HELP_LOCK 含 `latch=A`、`无每日锁`。P11「每通道每日一次」已被本裁覆盖，实现未偷加日锁。 |
| MA10 不因止损记忆跳过 | **PASS** | `exit_plan` 先评 `px < MA10×0.90`，不读 `stopped.latched`。本核加跑：reduced/stopped 已 latch 时 8.99 仍返回 `STOP`。 |

日线引擎是「收盘评估、次日开盘卖 / 收盘买回」，同一根收盘不可能同时 ≥MA5 又 <MA5，故同日再减是分钟语义。这是时钟粒度，不是日锁。

### 2. Residual = 2（保留 <100 买回记忆）

| 要求 | 结果 | 证据 |
|------|------|------|
| 成功收复后再武装，但保留 <100 | **PASS** | 150 卖 → 100 买 → `(shares, latched)==(50, False)`；下一轮 250 卖合并为 300 买回。规则 + 分钟引擎双通道 parametrize。 |
| `memory<100` 且无买入：保留残余并再武装 | **PASS** | `run_buybacks_day` 对 0 股合格 reclaim 仍调 `on_reclaim(..., 0)`。`test_sub100_no_buy_*`（规则/分钟/日线）。 |
| 禁止等记忆归零才再武装 | **PASS** | 再武装条件是 `shares < 100`，不是 `== 0`。500 卖 / 200 买（仍欠整百）保持 latch，与「周期未完成买回」一致，不是归零门槛。 |
| MA5 reduced 与 MA10 stopped 都适用 | **PASS** | 两通道同一 `Memory` 类型；测试对 `reduced`/`stopped` parametrize。日线奇数股止损：1050 卖 / 1000 买 / 余 50 再武装，下一轮合并。 |
| 新池/chase 清双记忆 | **PASS** | `on_buy` 仅 `pool` / `chase*` 调 `fresh_buy()`；台阶只 `steps += 1`。`test_pool_fill_clears_both_memories_before_same_clock_buyback`。 |

送转 `scale_memory` 的 floor100+stats 是 P9③ **另一把**取整，HELP_LOCK 已与 residual=2 拆开。现金红利 `factor==1` 不缩放。

### 3. S1 部分卖静默丢股

旧路径：`pos.shares -= shares` 只在 `volume_cap or exdiv_economics` 分支可达；默认路径入账部分现金后 **整 lot 删除**。

现路径（`csv_ledger.py:426-433`）：

1. 先按 wanted / locked bonus / cap 得到实际 `shares`
2. 入账、写 trades
3. **无条件** `pos.shares -= shares`
4. 余股 >0 保留 lot；==0 才删

| 路径 | 结果 | 证据 |
|------|------|------|
| 默认（无 cap）部分卖 | **PASS** | `test_s1_partial_sell_conserves_cash_and_nonzero_lot(None)`：卖 500 / lot 留 500 / Σ+filled=1000 / cash+佣金守恒。 |
| cap=150 | **PASS** | 同测：成交 150，lot 留 850。 |
| 卖空才删 | **PASS** | `test_s1_deletes_only_empty_and_t1_blocks_override`。 |
| locked bonus 先扣再 wanted | **PASS** | 1200 中锁 200：先卖 500 留 700；再 wanted 700 只卖 500，lot 留 200。 |
| 既有书全卖等价 | **PASS** | `test_default_trades_and_equity_byte_identical_to_pre_s1_head`：12 本书 × 日线/分钟 trades+equity CSV sha256 与夹具一致。本核复跑该测，绿。 |
| 默认调用方忽略返回值 | **PASS** | `_sell` 现返回 `int`；1–10 调用仍丢弃返回值。v12 `fill_exit` 用返回值累加实际成交并更新记忆。 |

`wanted_shares is None` 且无 cap/exdiv 时 `shares==pos.shares`，减完即删，与旧「不减直接删」对既有整 lot 卖等价。S1 修的是 **部分卖** 这条新能力。

---

## Handoff §0 其余硬边界

| # | 边界 | 结果 | 证据 |
|---|------|------|------|
| 1 | `execute_buy(..., shares_override=None)`，`per=notional` | **PASS** | override 整百；cap 后 `per=notional`；`supplementary_used==0`；不足一手不 force_min。 |
| 3 | is_step 先、中间 lot_id 升序、lot0 最后且 ≥100 | **PASS** | `allocate_exit` 键 `(2 if lot0 else 0 if is_step else 1, lot_id)`；`keep_anchor` 只对 REDUCE。 |
| 4 | 基数 = t1_sellable ×50% floor100；周期锁 | **PASS** | `available // 200 * 100`，再按保锚容量二次 floor。锁见上。 |
| 5 | 双记忆挂 st；按实际成交；送转 k；池/chase 清零 | **PASS** | `sold(filled)` / `reclaimed(trades[-1].shares)`；exdiv 显式开启才缩放。 |
| 6 | 买回第四买因；上限=记忆；过 T+1/涨跌停/费用/容量；skip_cash 预检 | **PASS** | `run_buybacks_day` 照 step 模板；现金预检在 cap 前；涨停不买不 re-arm（`test_buyback_limit_up_preserves_whole_lot_memory`）。 |
| 7 | wiring 四键 + `peak_gap_min=0` + 书侧自管止损 | **PASS** | `_apply_version12`：`reserve/defer=False`、`daily_same_bar_prefixes=()`、`stop_pct=None`、`peak_gap_min=0`。`--stop-pct` SystemExit。 |
| 8 | reason 前缀 `ma_signal:` | **PASS** | `MA5-derisk` / `MA10-stop` / `MA5-reclaim` / `MA10-reclaim`。 |
| 9 | 价域 front；缺分区失败；分钟不混 none 缓存 / qlib | **PASS** | 两入口 `run()` 拒非 front；front 关 E-R6；分钟 `lake_root=.../1m/dividend_type=front`。`test_front_*`。 |
| 10 | 台阶单调记忆；单码单日买向不加闸 | **PASS** | `CodeMemory.steps`；卖掉 is_step 后同段不重加。HELP_LOCK 声明 5+。 |
| 11 | 5-tuple 不扩 | **PASS** | 见上。 |
| 12 | 禁改 1–10 / Mode A/B；UTF-8；新文件 ruff | **PASS** | 范围见上。本核 ruff 0.16 默认集比仓内 0.12 宽，不据此 FAIL；`--isolated --select F,E4,E7,E9` 新文件零告警，与 0.12 默认口径一致。 |

P5 止损优先、双记忆并存、同日先卖后买：`exit_plan` 先 STOP；`fill_exit` 只写入对应通道；分钟环每根先卖再买回。`test_dual_channels_reclaim_independently_after_same_day_stop`。

P7 无上证闸：`index_blocks_add=False`，`run()` 不装 SSE gate。P8 默认 `stock_pool/`：`FORBIDDEN_DEFAULT_STOCK_POOL` 仍只有 9/10。AGENTS.md 增行写明与 v7 入口/必填池分工。

---

## 切片完成度

### A — 纯函数

消费 `ma_infra.sma_asof`（PIT 昨收序列）；无 ledger/engine import。不足 5/10 根、`px≤0`/`nan` → None。`take_profit_reason` 恒 None。HELP_LOCK 钉 latch=A / residual=2 / front / 费用偏差 / chase `px==open` / 容量不整百 / 5+ 买向。

本核不依赖 pytest 复跑了 rules 全向量 + 两条对抗加测（latch 不挡 MA10 止损；reason 前缀），全过。

### B — 引擎面

`shares_override`、S1 卖出重构、`run_buybacks_day`、entitle `on_event` opt-in、hooks `setdefault` 七键。默认书指纹 pin 在仓。

### C — 状态机 + 注册

`strategy12_engine` 持有日线独立部分卖队列与分钟逐根编排。别名 `12/v12/version12`，`per_name` 100 万，`apply()` 返回 `take_profit` + `record_params`。`--strategy 12 --help` 两入口冒烟含人裁字面（本核复跑）。

handoff 切片 C 旧句「当日买回当日不可再减」在 latch=A 后应读成 **新买回股 T+1**，不是日锁。实现按 T+1：同日再减只碰到原 lot，买回 lot 的 `entry_idx` 全是当日。

### D — 实湖五点对比

**未执行**。handoff 实施回填与 PR 正文均标明。命令已写死 `--dividend-type front`，不猜盘符。本核不因缺 D 判 FAIL。

---

## Nits（不挡）

1. **切片 D 未跑。** 不是 A–C 门；合入后需已配置 front 日线/分钟分区的湖再开。
2. **分钟缺 K 的池代码被静默丢掉。** `run_minute_day` 先按 `pool_at` 过滤再调用 `run_pool_buys_day`，缺帧代码不进名单、不计 `skip_no_bar`。默认分钟环会记 skip。只影响 v12 可观测性。
3. **送转把 <100 记忆 floor 到 0 时不改 `latched`。** 若仍 latch（尚未合格 reclaim），会以 0 股挡住 MA5 再减，直到下一次 reclaim 调 `reclaimed(0)`。P9③ 与 residual=2 的交叉边；HELP 未写。建议合入后补一句或在 `scale_memory` 对 `shares<100` 同步 `latched=False`——**本核不自裁**。
4. **`test_csv_strategy_books` 只把 `version12` 推进名单**，人裁字面只在 `test_strategy12_rules.test_help_pins_human_cuts`。里程碑书的 HELP pin 惯例（S16）未在 books 测试复用。
5. **指纹夹具标注 `9fa8b27`，文件却加在 C。** 当前 HEAD 复算与夹具一致（测绿）。本核未把 9fa8b27 树单独再跑一遍生成哈希；「B 前逐字节」的出处是实施者声明 + 现测等价。
6. **`_normal_buys` 写死 `allow_add=True` / `buy_gate=None`**，不读 hooks。对 v12 为真，但以后改书字段不会自动生效。
7. **plan 时代 collect-only=1401** 已被本 PR 新测 Dilute；含义是「既有断言不放宽」，不是钉死 1401。CI 现 1495 passed / 4 skipped / 24 deselected。

无 🔴。没有发现未编码的人裁、隐藏日锁、或默认路径丢股回潮。

---

## 本核跑了什么

解释器：`/tmp/s12-review-venv`（Python 3.12.3；本机无 vanna312 / `/tmp/ma-infra-venv`）。`PYTHONPATH=/workspace`。

| 命令 | 结果 |
|------|------|
| rules 纯函数对抗脚本（stdlib，不经 pytest） | PASS |
| `pytest -q tests/test_strategy12_rules.py tests/test_partial_sell.py tests/test_strategy12_engine.py tests/test_csv_strategy_books.py` | **100 passed**（与 PR 评论一致） |
| `pytest -q tests/test_p4_touch_mark_separation.py tests/test_ashare_simulate_import_fence.py tests/test_ashare_exdiv_economics.py` | **110 passed** |
| 两入口 `--strategy 12 --help` | 含 latch=A / residual=2 / 无每日锁 / 禁止等归零 |
| ruff `--isolated --select F,E4,E7,E9` 新文件 | All checks passed |
| UTF-8 / `git diff --check` | 干净 |
| 全量 1495 | **未在本核重跑**（依赖不全）。采信 CI `pytest-and-gates` SUCCESS @ `ce29d46` |

未跑实湖 D，未读行情盘。

---

## 明确未做 / 不挡

- 切片 D 五点对比与 reviews 数字（数字不入库）。
- 本核不 merge、不改生产 Python、不在 #151 上留合入指令。
