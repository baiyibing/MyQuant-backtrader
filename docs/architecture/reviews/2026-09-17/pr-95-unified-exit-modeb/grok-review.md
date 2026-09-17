# PR #95 统一卖出规则网格 · 模式 B 实施 A–D — Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #95](https://github.com/baiyibing/MyQuant-backtrader/pull/95) `feat/unified-exit-modeb`（tip `580cca5` vs `origin/master`）
> 权威：[plan-unified-exit-modeb-2026-09-17.md](../../../../backtest/plan-unified-exit-modeb-2026-09-17.md) v1.1（P1=A / Q36=A / Q37=A / Q38=A / warmup cache key）· [handoff-unified-exit-modeb-codex-impl-2026-09-17.md](../../../../backtest/handoff-unified-exit-modeb-codex-impl-2026-09-17.md) · 提案 [stock-backtest-unified-exit-proposal-2026-09-17.md](../../../../backtest/stock-backtest-unified-exit-proposal-2026-09-17.md) Mode B 锁（Q2/Q3/Q7/Q8/Q20/Q21/Q29 + Q36–Q38）
> HEAD：`580cca5a3ee352ae4722e0f7f5e02fe48badb0eb`
> merge-base：`55bfe4a3cb3219c11baa95d9c314206fad52ecd2`（= Merge #93 plan；其后 `origin/master` 另合 #94 分钟就绪 docs）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35198836728](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35198836728)）
> 工作树：`/workspace/MyQuant-backtrader-modeb`（分支 `feat/unified-exit-modeb`）
> 本核 **未 merge**。CI 绿 **不是** 合入条件。

---

## 结论

**BLOCK**（**不合入**。合成向量与硬边界其余项合格，但 `session_minutes` 把湖 SSOT 的 `hm`（分钟从 0 点，09:30=570）当成 HHMM（930/1500）过滤，生产 cache / 1m none 湖的全部 session K 被丢光。本核不 merge）。

A–D 骨架对上了人裁：独立模块、none 日收买、high/low 触发、分钟 close 成交、同根先止损、Q36 末根 session 分钟到期、Q37 非等价反例、Q38 只剔除跌停分钟、P1=A 18 格、报告目录隔离、ledger/Mode A 零改、切片 E 未勾。合成 77 测与 CI 739 都绿，**正因为 fixture 写的是 HHMM，而 `load_minute_bars` 写的是 570/895**。本核用湖单位复现：同一根 10:00 TP，HHMM 成交、生产 `hm=600/900` → `mark_end` 且 coverage=0。按 README 去跑宿主 cache，网格会变成「全员冻在买价」。这不是 nit。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#95 feat(modeb): implement minute exit grid, anchors, robustness and CLI (A–D)](https://github.com/baiyibing/MyQuant-backtrader/pull/95) |
| 比较 | `origin/master...HEAD`（11 files, +884 / −13） |
| A | `2482072` none 日线 + warmup cache `minute_none_20251013_20260909` |
| B | `3550c38` 分钟退出；Q36 末分钟；Q37 反例 |
| C | `c3506bc` 局部 E-R6 + `shares/=k`；ledger 行为测 |
| D | `580cca5` 窄网格 / 四锚 / Q34 / CLI / 目录隔离 |
| Q 人裁 | `d65442b` Q36=A Q37=A + cache；`a8f619f` Q38=A |
| E | **未做、未勾**（handoff `[ ] E`；plan「宿主 E 未执行」；PR body 同） |

`git diff --name-status origin/master...HEAD`：

```
M  AGENTS.md
A  backtest/research/unified_exit_modeb.py
M  docs/backtest/README.md
M  docs/backtest/handoff-unified-exit-modeb-codex-impl-2026-09-17.md
M  docs/backtest/plan-unified-exit-modeb-2026-09-17.md
M  docs/backtest/stock-backtest-unified-exit-proposal-2026-09-17.md
A  scripts/research/run_unified_exit_modeb.py
A  tests/test_unified_exit_modeb_aggregate.py
A  tests/test_unified_exit_modeb_exdiv.py
A  tests/test_unified_exit_modeb_exit.py
A  tests/test_unified_exit_modeb_load.py
```

禁区文件不在列：`csv_ledger.py` / `csv_simulate_loop.py` / `csv_daily_backtest.py` / `csv_minute_backtest.py` / `unified_exit_modea.py` / `*_rules.py` 相对 master **diff 空**。GitHub head = `580cca5`。CI SUCCESS 不能覆盖本 🔴。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **1 硬边界** 只动 Mode B 模块/CLI/测/相关 docs；不改 `rescale_position` shares；不改 Mode A 语义 | **PASS** | 11 文件如上。`inspect.getsource(csv_ledger.rescale_position)` 仍只 `cost*=k; peak*=k`；行为测 shares 10000 在 k=0.5 下不变。Mode A 三测文件零改；`test_v01_n1_equals_rule2_n1_regardless_of_tp_sl` 仍在。无 qlib / backtrader / Cerebro。 |
| **2 价域** 买 none 日线 close；触发 1m high/low；成交分钟 close；同根先止损 | **合成 PASS / 生产 FAIL** | 算法：`load_none_bars` → `dividend_type=none`；rule 2 先 `low` 再 `high`；fill=`close`；trailing `peak=max(peak, close)` 不用 high。向量表绿。**生产路径先被 `session_minutes` 丢光，价域链到不了湖。** |
| **3 Q36=A** 到期 = 当日最后一根 session 分钟 close；无 K 顺延；不回退日线 | **合成 PASS / 生产 FAIL** | `j == len(rows)-1` 才 `n_expire`；空日不卖；`test_expiry_no_daily_fallback_and_off_session_ignored` 用 1130。生产 rows 恒空 → 退化为买价 `mark_end`。 |
| **3 Q37=A** Mode B 不测 N=1 等价；盘中先触发反例；Mode A 不动 | **PASS**（合成） | `test_n1_intraday_counterexample`：r2 N=1 @1000 close=103 vs r1_n1 @1459 close=100。Mode A v01 仍在。 |
| **3 Q38=A** oracle 只排除跌停**分钟** close；同日其他分钟可候选；不模拟更早失败卖出 | **合成 PASS / 生产 FAIL** | `oracle_exits` 逐分钟 continue 跌停 close，不设全日 blocked。测：跌停前 110 / 跌停后 110 都能入选。生产 minutes 被滤空 → 全走 hold_end 回退。 |
| **4 P1=A** 默认窄网格 18 r2 + 四锚；报告目录隔离；CI data-free；切片 E 未伪完成 | **PASS** | `iter_grid`：X∈{5,7,10}×Y∈{5,10,None}×N∈{8,10} = 18；ranked=19（+ r1_n1）；锚 hold_end / r1_n1 / oracle / delist_zero。`DEFAULT_OUT_DIR=backtest_output/unified_exit_modeb`；路径含 `unified_exit_modea` 抛错。四门禁 OK。E checkbox 空。 |
| **5 单测覆盖关键向量** | **合成 PASS；缺湖单位回归 → 本 🔴 逃逸** | 见下节。Mode A+B 本核 **77 passed / 1.69s**。CI 739 @ `580cca5`。 |
| **Cache key** warmup `20251013` 超集，不重建 `20251023` | **PASS**（也是 🔴 的放大器） | `load_monitor_bars` → `warmup_start(start, days=10)`；测断言 `("20251013","20260909")`。正确复用 #94 已备 cache，然后把 cache 里的 570/895 **全部丢掉**。 |
| **UTF-8 / 门禁** | **PASS** | 本 diff 11 文件 BOM=false、NUL=0、CR=0、LF 结尾。`git diff --check` 空。`verify_oskh_data_contract` / `verify_data_path_ssot` / `verify_no_hardcoded_machine_paths` / `verify_tr_bridge_import_ssot` OK。 |

### 🔴 bug-1 — `session_minutes` 单位与湖 SSOT 相反（合入阻断）

- File: `backtest/research/unified_exit_modeb.py:52`
- Status: open

`csv_minute_backtest._read_one_minute`（`:197`）与 `_annotate`（`:174`）：

```text
hm = utc.hour * 60 + utc.minute    # 09:30 → 570, 14:55 → 895, 15:00 → 900
AM_OPEN, AM_CLOSE = 570, 690
PM_OPEN, PM_CLOSE = 780, 900
```

既有单测钉死湖单位：`tests/test_csv_minute_backtest.py:52` `list(got["hm"]) == [570, 895]`。`load_minute_bars` **已经** `_in_session` 过。

Mode B 又滤一次，当成 HHMM：

```52:52:backtest/research/unified_exit_modeb.py
    mask = hm.between(930, 1130) | hm.between(1300, 1500)
```

生产 session 的 hm 落在 570–690 / 780–900，与 930–1130、1300–1500 **无交**。`PreparedMinutes` / `minute_coverage` / `evaluate_exit_modeb` / `oracle_exits` / `build_daily_equity` 全部走这条滤。

本核复现（同一实例买 100，T+1 10:00 high=106 close=103，末分钟 close=100；r2 N=1 X=5 Y=5）：

| 输入 `hm` | 含义 | `session_minutes` 行数 | 退出 |
|-----------|------|------------------------|------|
| 1000 / 1459 | 测试用 HHMM | 2 | `take_profit` @103，`sell_hm=1000` |
| 600 / 900 | 湖 10:00 / 15:00 | **0** | `mark_end` @100，`sell_hm=None`，`is_trade=False` |
| 570 / 900 | 湖 09:30 / 15:00 | **0** | 同上 |
| coverage 湖单位 | | | `covered_codes=0`，码记入 missing |

合成测全用 1000/1130/1459/1500（HHMM），所以 77 绿、CI 绿。宿主若按 README 跑 `run_unified_exit_modeb.py` 并命中 warmup cache，覆盖率会报全缺，矩阵会报全员 `mark_end`。R2 / Q36 / Q38 在真数据上同时失效。

**Suggestion：** `session_minutes` 改用 `csv_minute_backtest` 的 `AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE`（或湖帧已 session-filter 则不要二次用另一套钟）。合成 fixture 改成 570/600/690/780/899/900。加一条 **湖单位** 回归：`hm=600` 必须 TP 成交；`minute_coverage` 必须 counted。现有 HHMM 向量在改钟后应红——这是预期，不要为保绿而继续写 1500。

---

### 价域 / Q 锁（算法层，假定 `hm` 已是 session 行）

这些在 HHMM fixture 上成立；修 bug-1 后应仍成立。

| 场景 | 实现 | 单测 |
|------|------|------|
| 买 = none 日线 close | `load_none_bars` 把 `front_root` 指到 `dividend_type=none`；assemble 复用 Mode A 身份/封板 | `test_none_root_and_pool` buy=10.5 |
| 同根 TP&SL → 先止损，成交=该分钟 close | rule2 先 `low<=cost*(1−Y%)` 再 `high>=cost*(1+X%)` | 参数化 `(106,94,102)→stop_loss` |
| 仅 TP / 仅 SL / 精确 5% | 同上 | `(106,99,102)` / `(102,94,97)` / `(105,99,101)` / `(101,95,98)` |
| trailing 用 close 不是 high；halt 冻 peak | 买日跳过；`peak=max(peak,close)`；缺分钟日不更新 | high=200/close=104 不在当日 trailing；第三日 98 才触（若 peak 用 high=200，当日就会卖） |
| T+1 买日整日不触发、不入 peak | 循环从 `buy_i+1` | `test_buy_day_unavailable_to_trigger_or_peak` |
| Q36 到期末日分钟；盘外 925/1200/1501 忽略；无 K 顺延 | 最后一根 session 行；空日 continue | `test_expiry_no_daily_fallback_and_off_session_ignored`（**单位须随 bug-1 改写**） |
| Q36 不回退日线 close | 成交只用 minute close | 无日线 fill 分支 |
| Q7 触发分钟 close 跌停 → 当日 blocked，次日重评 | `_is_limit_down(close, prev)` 后 `blocked=True` | 10:00 跌停、14:00 收回仍不卖，次日 TP |
| 到期日末分钟跌停顺延 | n_expire 后跌停检查 | `test_limit_down_expiry_postpones` |
| Q37 反例 | r2 盘中 103 vs r1 末分钟 100 | `test_n1_intraday_counterexample` |
| Q38 同日跌停分钟剔除、前后非跌停可候选 | oracle 不套全日 blocked | 105 在跌停前或后都能赢 |
| Q38 不模拟更早失败卖出 | 只比扣佣 pnl | 与 Q7 实际规则隔离；meta 写「分钟可成交 close 事后上界」 |
| Q29=B 局部 shares/=k，不再整百 | 日初 `cost/peak/shares/mark` 缩放 | k=0.5/0.98/0.73；0.73 后 `shares%100 != 0` |
| 除权映射昨收（涨停不买） | assemble 覆写 `prev_maps` | 50→55 在 k=0.5 下 skip `limit_up` |
| 停牌日除权市值冻结 | 无分钟仍 ×k | shares=25000, mark=40, pnl≈−1000 |
| Q33 只改期末 MTM | `mark_end_zero` 跳过末日 mtm | 历史 equity 逐日相等；`is_trade=False` |
| 引擎 ledger 只读 | 不调用改 shares | dummy pos shares 仍 10000 |

Mode A close-only 先 TP 后 SL（一根 close 不会双触）。Mode B 先 SL 是 R3，没有回写 A。

### P1 / 报告 / E

- 窄网格：18 r2 + r1_n1 进排名，hold_end 不进 ranked，oracle/delist 锚线另挂。与 plan P1=A 点名族一致。
- `_validate_out_dir` 拒绝任何 path part `unified_exit_modea`（含 nested）。pipeline 测断言未创建 Mode A 目录。
- CLI HELP 含「模式 B」「窄网格」；默认目录 `backtest_output/unified_exit_modeb`。
- 切片 E：handoff `[ ] E · 宿主网格`；plan 头部「宿主 E 未执行」；PR body「不列为实现合入门」。未伪完成。

### 依赖（HEAD，无环，禁区未改）

```
run_unified_exit_modeb.py → unified_exit_modeb
  ├→ unified_exit_modea          # 装配/网格/报告形状/涨跌停；不改其文件
  ├→ csv_daily_loader.warmup_start
  ├→ csv_minute_backtest.load_minute_bars / MINUTE_LAKE_END
  ├→ exdiv_map.load_exdiv_ratios
  └→ data_root.resolve_period_root
csv_ledger.rescale_position      # 仅测试 import；生产路径不调用
```

---

## 违规 / 风险

### 🔴 bug-1（合入阻断）湖 `hm` 单位

见上。不修则 A 覆盖、B 求值、C 除权阈值、D 净值/oracle/CLI **在真 cache 上同时空转**。CI data-free 按设计看不见。

### nit-1（文档）plan 页眉仍写「v1.1 docs-only；本 PR 不写 Mode B Python」

实现票已写 Python。实施进度行已补，页眉第一句未改。不挡（本票反正 BLOCK）。

### nit-2（文档）提案 Q36/Q37 标题仍「实施 STOP，待人裁」

正文回答已是 **A**。标题与状态句不一致，后人会以为还要 STOP。

### nit-3（卫生）plan §3.1 Q38 写了两行；handoff 硬边界编号 9→12→13→10→11

重复与乱序。不挡。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 跌停用**触发分钟 close** 相对昨收，不是 low 触板 | 与 Q38「排除跌停分钟 close」同构；盘中 wick 收回仍可按 close 成交。plan 注「按交易日重评、不自创新语义」。修 bug-1 后若要改用 low，须新开 Q。 |
| `ExitResult` 子类把 `shares: int` 覆成 `float` | 字段序仍对（本核 `fields()` 确认）；除权后允许非整百。 |
| 半窗仍用 Mode A 写死的 20251023–20260404 / 20260407–20260909 | 与 Mode A 同；换窗会 silently 错。#90 nit，不重复升格。 |
| plateau 复用 Mode A 邻域，作用在 18 格而非 280 | P1=A 预期；全 280 是 E 后置。 |
| `load_none_bars` 调用 `load_front_bars(..., front_root=none)` | 价域对；函数名易误导，不升格。 |
| 合成测 0 真实 symbol | 符合 R6；缺的是湖 **单位** 契约测，不是真码。 |

---

## 建议动作（是否可合）

**不可以合入 master。** 不要用 CI SUCCESS / 77 passed 当生产就绪。

修完再审（仍不要让本核 merge）：

1. `session_minutes` 对齐 `AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE`（570–690 ∪ 780–900）。不要 `divmod(hm, 100)` 去「兼容」两套钟。
2. 重写 Mode B fixture 的 `hm` 为湖单位；现 HHMM 断言必须改到红→绿。
3. 新增回归：生产单位 10:00=`600` 必须成交；`minute_coverage` 对 570/900 计 covered；oracle/净值走同一滤。
4. 文档 nit 可顺手：plan 页眉去掉 docs-only；Q36/Q37 标题去掉「待人裁」。
5. 切片 E 继续空着，直到 1 之后用真 cache 跑通覆盖率 ≠ 0。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git rev-parse HEAD
# = 580cca5a3ee352ae4722e0f7f5e02fe48badb0eb
git merge-base origin/master HEAD
# = 55bfe4a3cb3219c11baa95d9c314206fad52ecd2
git diff --name-status origin/master...HEAD
# 11 files；无 csv_ledger / unified_exit_modea / csv_minute_backtest
gh pr view 95 --json mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / head = 580cca5 / pytest-and-gates SUCCESS
# 本核 vanna312：
#   Mode A + Mode B 合成 77 passed / 1.69s
#   四门禁 OK
#   session_minutes(hm=570) → 0 行
#   session_minutes(hm=930) → 1 行
#   evaluate_exit_modeb hm=600/900 → mark_end 100
#   evaluate_exit_modeb hm=1000/1459 → take_profit 103
# UTF-8：11 文件 BOM=false NUL=0 CR=0
# rescale_position：shares untouched (X-R1)
```

真湖分钟网格 / 切片 E **未**跑（非合入门；且 bug-1 下跑了也无意义）。
