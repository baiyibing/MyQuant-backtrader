# PR #87 topk arm0 qlib-align — Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #87](https://github.com/baiyibing/MyQuant-backtrader/pull/87) `feat/topk-arm0-qlib-align`（`origin/feat/topk-arm0-qlib-align` vs merge-base `origin/master`）
> 权威：[plan-topk-dropout-overlay-2026-09-16.md](../../../../backtest/plan-topk-dropout-overlay-2026-09-16.md) · [handoff-topk-dropout-overlay-codex-impl-2026-09-16.md](../../../../backtest/handoff-topk-dropout-overlay-codex-impl-2026-09-16.md) · PR #87 body（qlib `features/*.day.bin` 后复权 `$close`；买侧 ST/上市年龄/5d>15% 仍 BT 侧；`--stop-pct 0`；`--qlib-cost` 买 5bp/卖 15bp/min5；湖 `none`+10bp 两边仍默认）
> HEAD：`9cd5bb9156c20817f3e5b3fe175ace49a2c8d770`
> 含：`06eaa45` qlib bin / 买卖门槛 / 5·15bp + `9cd5bb9` 分数补零、年龄溢出 fail-closed
> merge-base：`f818b40eb5f3c5d0b5ddf47f517c7d533dff9779`
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35107133104](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35107133104)）
> 本核 **未 merge**。

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改 v6/v8 默认成交语义。本核不 merge）。

对照 overlay plan / 交接硬边界 / PR #87 正文：这是一次 scoped 的 **topk 日线对齐片**，不是把 PortAna 做成第四台引擎。`qlib_bin_daily.py` 按 `qlib.utils.read_bin` 布局纯 numpy 读 `$close` 后复权，全树研究路径无 `import qlib`。默认佣金仍是双边 10bp 无最低（`SimState.buy/sell_cost_rate=COMMISSION`，`min_cost=0`）；`--qlib-cost` 才切 5bp/15bp/min 5。v6/v8 钩子仍 `qlib_limit_pct=None` / `limit_up_chase=True` / `limit_down_pending=True` / `forbid_all_trade_at_limit=False` / `cash_deploy_frac=None`；v6 `--stop-pct 0` 仍拒，topk `--stop-pct 0` 才关止损。买侧 ST / 年龄 / 5d>15% 走 `eligible_buy` + walk-down，不进 sell_gate。`9cd5bb9` 分数 `dtype=str`+zfill 与日历内 `idx+60` 溢出写 `99991231` 正确。

成交核 / 日线卖环有挂钩扩展（账本费率、`book_limit_prices`、跌停 pending 开关、forbid-all），但 **默认分支与 master 主语义等价**（本核对照旧卖环四分支 + 默认 `execute_buy` 佣金探针）。禁区无无关漂移。nits 是新路径脆性（warmup 自然日落非交易日会 SystemExit）、CLI 年龄日历未接线、以及分钟 topk 只吃到部分钩子。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#87 feat(research): align topk daily with qlib bins, buy gates, and 5/15bp costs](https://github.com/baiyibing/MyQuant-backtrader/pull/87) |
| 比较 | `origin/master...HEAD` 三-dot = merge-base `f818b40`..`9cd5bb9`（17 files, +951 / −65） |
| **06eaa45** | qlib `features/*.day.bin`、买门槛、`--qlib-cost` 5/15、topk 9.5% 统一板、same-bar `topk_drop`、risk_degree 0.95 |
| **9cd5bb9** | scores `dtype=str` + 裸码 zfill；上市日起点 +60 越出日历 → `99991231` |
| 相对现 `origin/master` | master 已合 #90 unified-exit；与本 PR **文件交集为空**，GitHub `MERGEABLE` 与语义正交一致 |

overlay BT-A/B/C 已在 merge-base 上。本 PR 是 arm0 对齐，不是重做淘汰算法。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **R-3 / 硬边界** 不 `import qlib` | **PASS** | 新增 `qlib_bin_daily.py` docstring 与实现只有 `numpy`/`pandas`/`Path`。`git grep` 本 diff 无 `import qlib` / `from qlib`（`qlib_cost` 包是既有筹码，不在本 diff）。 |
| **R-4 / 硬边界** 不改 v6/v8 默认语义 | **PASS** | `strategy6_rules.py` / `strategy8_rules.py` **不在 diff**。`apply_csv_strategy` 对新钩子 `setdefault`：v6/v8 `qlib_limit_pct is None`、`limit_up_chase is True`、`limit_down_pending is True`、`forbid_all_trade_at_limit is False`、`cash_deploy_frac is None`、`daily_same_bar_prefixes==("open_board",)`。`strategy6_kwargs_from_args` 仍要求 `--stop-pct in (0,1)`，**拒绝 0**。本核直调 v6/v8 hooks + v6 `stop_pct=0` → SystemExit。`test_version6_keeps_limit_up_chase_hook` / `test_version6_golden_stop_pct_unchanged` / `test_topk_stop_pct_is_ten_percent_not_v6`。 |
| **硬边界** 默认成本不变；`--qlib-cost` 才 5/15 | **PASS** | `csv_ledger.py`：`COMMISSION=0.001` 仍默认；`QLIB_OPEN_COST=0.0005` / `CLOSE=0.0015` / `MIN=5` 只作常量。`SimState` 默认 `buy/sell_cost_rate=COMMISSION`、`min_cost=0`。`trade_commission` 在 `min_cost==0` 时就是 `notional*rate`。日线 `main()`：`buy_cost_rate=QLIB_OPEN_COST if args.qlib_cost else None`（None 不改账本默认）。本核：默认 `execute_buy` 100 万名义佣金 **1000**（10bp）；`test_trade_commission_qlib_floor_and_default` / `test_execute_buy_uses_qlib_open_cost`。湖 `--dividend-type` 默认 `none`。 |
| **R-3′** n_drop 不进成交核 | **PASS** | `n_drop` 仍在 `strategy_topk_dropout_rules` / `decide_topk_dropout`。引擎只多 default-None 钩子：`cash_deploy_frac` / `qlib_limit_pct` / `limit_up_chase` / `forbid_all_trade_at_limit` / `limit_down_pending`。旧书不设则走原式 `min(quota,cash)/n` 与板块档。 |
| **R-6** 不读 `live_pool/*sell.csv` | **PASS** | 本 diff 仅 HELP 禁止句；无 live_pool 读径。 |
| **R-7** 不对 PortAna NAV | **PASS** | PR 宿主报 782/733 笔与 5.00/15.00bp，无 NAV/IR。买门槛声明为 **BT 侧**，不把 PortAna 当闸。 |
| **qlib bin 读径** | **PASS**（nit：warmup 日期必须在 `day.txt`） | `read_qlib_bin`：LE float32 header=ref index，`seek(4*(si-ref)+4)`，与 qlib `read_bin` 同构。`qlib_inst_dir`：`600519.SH`/`SH600519`→`sh600519`。缺日历日 **SystemExit**；缺 features 目录 **FileNotFoundError**。OHLC 缺 open/high/low 用 close 填。`$close` 后复权由 dump 契约声明（`$adjclose` 为 none）。`test_read_qlib_bin_respects_ref_start` / `test_load_qlib_bin_daily_bars_reads_close`。湖路径仍丢 volume=0（E-R4）；qlib 路径无 volume 列（见 nit）。 |
| **9cd5bb9 分数补零** | **PASS** | `load_scores_dir` / `load_pred_csv` 改 `dtype=str`。`_bare_or_canon` 对 `\d{1,6}` `zfill(6)` 再走 `canonical_from_bare_code`。`_bare_or_canon(48)==000048.SZ`、`(608)==000608.SZ`；`load_scores_dir` 保留 `000048`/`000608`。无 zfill 时 `(\d{6})` 吃不到 3 位整数，票会被静默丢掉——这正是补丁所修。 |
| **9cd5bb9 年龄溢出 fail-closed** | **PASS**（函数层；CLI 日历接线见 nit） | `load_age_min_buy_ymd`：命中日历且 `idx+age_days>=len(cal)` → `99991231`（06eaa45 已有）；`idx is None` 且 `start_ymd > cal[-1]` → **不再写回上市日**，改 `99991231`。`ds < min_d` 则不可买。`test_age_map_overflow_is_not_yet_eligible` 钉 920072/920083。未知年龄仍 fail-closed（`min_d is None → False`）。 |
| **买门槛 vs PortAna/BT 声明** | **PASS**（自洽） | PR body：ST / 年龄 / 5d>15% **留在 BT**。实现：`make_eligible_buy` 只过滤 `planned_for_day` walk-down；`test_held_becoming_st_does_not_force_sell_gate`。`with_return_threshold`：T-1 vs T-6（`cal[i-1]` / `cal[i-(5+1)]`），`>` 15% 挡新开，缺 close **放行**（docstring：qlib 缺值当 −inf ≤15%）。`--return-threshold-filter` 默认关；开时 `run()` 用已加载日线（qlib bin 则用后复权 close）。不 import qlib 过滤器。与「对齐成交价/费率/bins，不对齐 PortAna 闸」一致。 |
| **`--stop-pct 0`** | **PASS** | `_apply_topk_dropout`：`float(stop_pct)==0 → resolved_stop=None`。`simulate` `stop_enabled = isinstance(stop_pct,float) and 0<stop_pct<1`。`test_stop_pct_zero_disables_stop`。CLI `_run_kwargs_topk_dropout` 允许 0；v6 路径不允许。 |
| **禁区：成交核默认路径** | **PASS** | `_sell` / `execute_buy` 只把 `notional*COMMISSION` 换成 `trade_commission(rate, min)`；默认 rate=0.001、min=0 → 原文同一。`run_pool_buys_day`：`cash_deploy_frac is None → frac=1.0`；`forbid_all_trade_at_limit False` 只拦涨停；`limit_up_chase True` 仍 `queue_limit_up_chase`。per_name 现金预检同步用账本费率。 |
| **禁区：日线卖环默认路径** | **PASS** | 默认 `blocked=at_down`，`limit_down_pending=True`。四分支与 master 等价：① same-bar 非跌停 → 当日卖；② same-bar 跌停 → defer+pending；③ 非 same-bar 跌停 → defer+pending；④ 非 same-bar 非跌停 → pending 且不 defer。新 `skip_limit_sell` 只是计数。`limit_down_pending` / `forbid_all` / 9.5% 板 **仅 topk 书打开**。 |
| **topk 对齐钩子（仅新书）** | **PASS** | `SAME_BAR_PREFIXES=("open_board","topk_drop")` 当日收盘卖 dropout；`QLIB_LIMIT_PCT=0.095`；`QLIB_CASH_DEPLOY=0.95`；`limit_up_chase=False`；`limit_down_pending=False`；`forbid_all_trade_at_limit=True`。`test_planned_for_day_matches_decide_buy` / `test_topk_limit_skip_has_no_chase`（创业板 +12%：板块会放、9.5% 跳过且不追买）/ `test_daily_simulate_holds_topk_after_fill`。 |
| **UTF-8 无 BOM、NUL=0** | **PASS** | 本核抽查本 diff 全部 py：BOM=false、NUL=0。 |
| **CI / 单测** | **PASS** | GitHub Actions `python-tests` **SUCCESS**：`656 passed, 5 skipped, 24 deselected, 3 warnings / 18.96s`。本核 `/workspace/vanna312/bin/python -m pytest` 相关面 **214 passed / 10.87s**。pandas 告警在未改 minute `:310`，非本轮引入。 |

### 默认卖环等价（日线，`forbid_all=False` / `limit_down_pending=True`）

| 情形 | master | HEAD 默认 |
|------|--------|-----------|
| same-bar 且非跌停 | 当日 `_sell` | 同 |
| same-bar 且跌停 | defer++，pending | `skip_limit_sell++`，defer++，pending |
| 非 same-bar 且跌停 | defer++，pending | 同（多 skip 计数） |
| 非 same-bar 非跌停 | pending，不 defer | 同 |

### 买门槛覆盖

| 闸 | 测试 | 核验 |
|----|------|------|
| ST 新开 walk-down | `test_walk_down_skips_st_first_candidate` | 第一名 ST → 下一只 |
| 年龄挡次新 | `test_age_gate_blocks_young_name` | min_buy 未来日被跳过 |
| 持仓变 ST 不强制卖 | `test_held_becoming_st_does_not_force_sell_gate` | sell_gate 仍 None |
| 5d>15% walk-down | `test_return_threshold_walks_down_hot_name` | T-6=10 → T-1=12（+20%）挡，补 600011 |
| 年龄溢出 | `test_age_map_overflow_is_not_yet_eligible` | 99991231，20260708 不可买 |
| 分数补零 | `test_load_scores_dir_keeps_leading_zeros` | 000048.SZ / 000608.SZ |

### 依赖（HEAD，无环）

```
csv_daily_backtest ──┬→ qlib_bin_daily          （仅 --qlib-data-root）
                     ├→ csv_daily_loader         （默认湖 none/front/back）
                     ├→ csv_simulate_loop → csv_common.book_limit_prices
                     ├→ csv_ledger.trade_commission / execute_buy / _sell
                     └→ strategy_topk_dropout_rules → topk_dropout_eligibility
                                                    → topk_dropout_scores
csv_minute_backtest ──→ 同上钩子透传（无 --qlib-data-root / --qlib-cost）
qlib_bin_daily ↛ import qlib
csv_ledger ↛ 引擎
```

---

## 违规 / 风险

无 🔴。无合入阻断。硬边界未破。

### nit-1（新路径脆性）qlib bin 要求 start/end **恰好**在 `day.txt`

`load_qlib_bin_daily_bars`：`start_iso not in pos → SystemExit`。`run()` 把 `warmup_start`（**自然日** Timedelta）传进去。`WARMUP_DAYS=10` 时 `--start 20260106`（周二）→ load_start=`20251227` **周六**，默认 `--qlib-data-root` 会直接退出。`--return-threshold-filter` 改 warmup=20 → `20251217` 周三，可能碰巧能跑。湖装载用时间闭区间，不要求 start 是交易日。

这是 fail-closed（不会读错 bar），不是默认湖回归。PR 正文宿主窗若未开 5d 闸，需确认实际 load_start。建议合入后：对 qlib 日历 bisect 到 `≥start` / `≤end` 的最近交易日（或把 warmup 改交易日）。**不必为此 BLOCK。**

### nit-2（接线）CLI `--age-days` 在未给 `calendar_ymd` 时是空操作

`_run_kwargs_topk_dropout` 调 `make_eligible_buy(age_map_file=..., age_days=...)` **不传** `calendar_ymd`。按 docstring，此时文件值当作 **已经算好的最早可买日**，不做 +60。`9cd5bb9` 溢出修只在「带日历的 `load_age_min_buy_ymd`」生效（单测是这种）。若宿主文件是上市日、指望 CLI `--age-days 60` 移位，CLI 现在不会做。建议 `run()` 在 `build_calendar` 之后重建 eligible_buy。overlay 接线缺口，本片函数层已修对。

### nit-3（年龄）窗内非交易日上市日仍可能跳过 +60

`idx is None` 且 `start_ymd <= cal[-1]` → 保持上市日（「日历之前老股」分支）。周六上市、周一在日历内时，不会从下一交易日再 +60。北交/次新若上市日落在休市日，闸会偏松。溢出（`> cal[-1]`）已 fail-closed。

### nit-4（旗标半径）`--qlib-cost` / `--qlib-data-root` 挂在日线引擎，不限 topk

`main()` 无 `strategy==topk_dropout` 守卫。显式传给 v6 会改费率或跳过 E-R6（front/back/qlib 连续价）。默认不传则不变。HELP 已写 opt-in。可选：非 topk 拒绝这两旗。

### nit-5（数据）qlib 路径无 volume，不能做 E-R4 零量丢 K

湖 `_read_one_daily` 仍丢 volume==0。qlib 只读 OHLC，停牌若 dump 填了 close 会进日历。对齐 PortAna 用 qlib 域是预期；不要把 `--qlib-data-root` 当 v6 湖替代。可在 HELP 加一句。

### nit-6（覆盖宽度）缺 CLI 级 `--qlib-cost` 往返；0.95 资金只钉钩子值

费率函数与 `execute_buy` 有单测；没有 `main(["--qlib-cost"])` 解析断言。`cash_deploy_frac==0.95` 已钉，未钉实际 `per` 名义。分钟 topk 吃到 9.5%/不追买，但 **没有** qlib bin、`--qlib-cost`、same-bar 收盘卖、`limit_down_pending`（日线专用）。PR 标题是 daily align，可接受；分钟 topk 不要当已对齐。

### nit-7（卫生）日线 / 分钟仍 import 未用的 `_named_limits`

卖环已改 `book_limit_prices`。死 import。日线 `simulate()` 凡走日循环都会把 `buy_cost_rate` 写入 stats，summary 对 **所有** 日线书多一行 cost（默认 0.001/0.001/0）。不改编 trades.csv。`defer_sell_limit_down` 在 topk `limit_down_pending=False` 时仍可能 +1（stat 名「顺延」与「当日跳过」不完全同义）。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 宿主 782/733 | 本核无 qlib dump / 无 F 湖，未复跑。CI 与合成单测为合入证据。 |
| master #90 | unified-exit 新模块，与本 PR 文件不相交。 |
| `_bare_or_canon` 已带后缀 | `000001.SH` 原样返回，不按前缀纠正；qlib 文件夹会走 `sh000001`。裸码路径会纠到 SZ。MyQuant 导出通常裸码或正确后缀。 |
| qlib `except Exception: continue` | 与湖 loader 同一吞异常形态；坏 bin 静默缺票。 |
| LIMIT_EPS | 9.5% 板仍用价格绝对 ε=0.001，与板块档同一套，略紧于纯收益率 `>=0.095`。 |
| 共享 HELP_LOCK | 日线总锁仍写板块 10/20/30；topk 书 HELP 写 9.5% 统一板。拼接 help 两段并存，以书为准。 |

---

## 建议动作（是否可合）

**可以合入 master。** 不要为 nit-1…7 重开切片或阻塞 PR。合入后若顺手（非本 PR）：

1. qlib 日历对 warmup/start/end **snap 到最近交易日**（nit-1）。
2. `run()` 在日历就绪后把 `calendar_ymd` 注入 `make_eligible_buy`，让 `--age-days 60` 真正移位（nit-2）。
3. 可选：非 topk 拒绝 `--qlib-cost` / `--qlib-data-root`（nit-4）；HELP 声明 qlib 路径无 E-R4（nit-5）。
4. 不要在本 PR 顺手改 v6 卖环或清死 import 以外的引擎格式化。

本核 **未 merge、未改引擎业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git merge-base origin/master HEAD
# = f818b40eb5f3c5d0b5ddf47f517c7d533dff9779
git rev-parse HEAD
# = 9cd5bb9156c20817f3e5b3fe175ace49a2c8d770
gh pr view 87 --json number,title,mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / pytest-and-gates SUCCESS
gh run view 35107133104   # 656 passed, 5 skipped, 24 deselected
/workspace/vanna312/bin/python -m pytest -q \
  tests/test_qlib_bin_daily.py tests/test_topk_dropout_book_a.py \
  tests/test_topk_dropout_book_b.py tests/test_topk_dropout_book_c.py \
  tests/test_topk_dropout_rules.py tests/test_csv_strategy_books.py \
  tests/test_csv_daily_backtest.py tests/test_csv_daily_backtest_v8.py \
  tests/test_np3_layering.py tests/test_research_face_imports.py
# 214 passed in 10.87s
```

默认佣金 / v6·v8 钩子 / v6 拒绝 `--stop-pct 0` / `_bare_or_canon(608)`：本核 vanna312 探针。
`import qlib`、live_pool、BOM/NUL、#90 文件交集、卖环默认四分支：对照 `origin/master...HEAD`。

全量 `pytest -q tests/` 以 CI `python-tests` SUCCESS 为准（656 passed）。
