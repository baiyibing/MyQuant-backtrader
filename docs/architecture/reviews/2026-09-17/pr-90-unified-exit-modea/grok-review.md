# PR #90 统一卖出规则网格 · 模式 A — Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #90](https://github.com/baiyibing/MyQuant-backtrader/pull/90) `feat/unified-exit-modea`（`origin/feat/unified-exit-modea` vs `origin/master`）
> 权威：[handoff-unified-exit-modea-codex-impl-2026-09-17.md](../../../../backtest/handoff-unified-exit-modea-codex-impl-2026-09-17.md) · [stock-backtest-unified-exit-proposal-2026-09-17.md](../../../../backtest/stock-backtest-unified-exit-proposal-2026-09-17.md)（Q1–Q35）· [host-runbook-unified-exit-modea-2026-09-17.md](../../../../backtest/host-runbook-unified-exit-modea-2026-09-17.md)（切片 D 非合入门）
> HEAD：`a3a351fa781bbcd9e30fc274b3c1a58289fdd23b`
> merge-base：`f738c7d25302513d2dc21df1335dc8a59c72db22`（= `origin/master`）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**
> 工作树：`/workspace/MyQuant-backtrader-unified-exit`

---

## 结论

**BLOCK**（合入前须修 Q33 锚线：`delist_zero` 的 **总收益率 / 最大回撤仍按最后收盘 MTM**，与「9 笔受冻实例按 0 计」锁定量不一致。主网格 280 组排序键因此对这条敏感性是空操作）。

A/B 装配与退出求值器对照提案 §一/§二/§四 与交接硬边界是合格的独立模块：front 直读、封板/无 K/缺名单日、T+1、N 市场交易日、跌停/停牌顺延、trailing peak 先更新后判定、期末 `mark_end` 不记成交，均有合成向量覆盖。硬边界未破（未碰 `csv_ledger` / `simulate_loop` / 成交核 / 日线引擎 / v7 正文 / 1–6/8/9/10 书；无 backtrader；CI data-free 绿）。切片 D 未伪完成。

C 的主排序、11 亿现金池、四锚线骨架、稳健性四件套**有落地**，但锚线 ④ 在 Q30 第一排序指标上是假绿；Q34 有几处口径缩水（半窗只切 top-50、创业/科创合并、邻域 `_n1` 子串误匹配）。这些不掩盖 A/B，但 C 是合入门的一部分，Q33 须先修。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#90 feat(unified-exit): Mode A slices A/B/C — assembly, exit matrix, reports](https://github.com/baiyibing/MyQuant-backtrader/pull/90) |
| 比较 | `origin/master...origin/feat/unified-exit-modea`（9 files, +1861 / −4） |
| A | `e5b9c50` front 装配 + instances；合成 fixture |
| B | `331d410` 实例×策略退出求值器 + ≥12 手算向量 |
| C | `a3a351f` 11 亿聚合 / 四锚线 / Q34 四件套 / 报告 + AGENTS/README |
| D | **未做、未勾**（host-runbook 仍 `host-only — NOT done in PR`） |

新代码落点符合交接：`backtest/research/unified_exit_modea.py` + `scripts/research/run_unified_exit_modea.py` + 三份 `tests/test_unified_exit_modea_*.py`。文档只改交接状态行、提案页眉「A/B/C 已落地」、AGENTS 一行、`docs/backtest/README.md` 入口。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **硬边界** 独立模块；禁区一行不碰 | **PASS** | diff 9 文件，无 `csv_ledger.py` / `csv_simulate_loop.py` / `csv_daily_backtest.py` / `csv_minute_backtest.py` / `csv_minute_backtest_v7.py` / `*_rules.py` / 策略书。库 AST import：`csv_daily_loader` / `csv_pool` / `market_layer` / `data_root`；`csv_minute_backtest_v7.load_index_daily` 仅生产日历惰性引用（测试注入 `sessions` 不触发）。无 `backtrader` / `Cerebro` / Rolling / PortAnaRecord。 |
| **路径 / 湖** 无硬编码盘符、cwd `stock_data/`、CI data-free | **PASS** | 生产路径 `resolve_period_root("1d") / "dividend_type=front"`，禁止默认 `load_daily_bars`（none）。新 `.py` BOM=false、NUL=0、UTF-8。`verify_no_hardcoded_machine_paths.py` OK；`verify_data_path_ssot.py` OK。单测 `tmp_path` parquet + 内存 bars，不调 resolvers（除显式 `front_root=`）。`stock_data/` 只出现在 docstring 否定句。CLI `--pool-dir` 默认 `stock_pool` 与提案名单树一致，不是 `stock_data/`。 |
| **A** front 装载、封板跳过、无 K 跳过、缺名单日不买不报错 | **PASS** | `assemble_instances`：名单日无 close → `no_bar`；`close/prev−1 ≥ limit_pct−0.002` → `limit_up`（主板 +9.9%、创业 +19.9% 单测）；`iterate_pool_entries` 缺文件 `continue`。`_prev_close_on` = 序列上一根 K（跨停牌）。买入价 = 名单日 front close。未知板块 / 整百股为 0 额外 fail-closed（提案 §一「未知板块不交易」+ Q16）。 |
| **B** T+1 / N 市场日 / 跌停顺延 / 停牌顺延 / trailing peak / 期末估值；≥12 向量 | **PASS** | `evaluate_exit` 从 `buy_i+1` 起；`market_held = i−buy_i`（停牌日无 K 则 `continue`，N 仍推进，到期后首根有 K 执行）。跌停 `_try_finish` 返回 None 次日重评。规则 3：`peak = max(买入价, 含买入日 close)`，可卖日 **先更新 peak 再** `close < peak×(1−Y%)`（§四原文）。窗口末 / 断码 → `mark_end`、`is_trade=False`、卖佣金不扣（Q12/Q33 主口径）。网格 `8+252+20=280`（+ hold-end 锚 = 281）。exit 单测 v01–v15（N=1 等价价/日、跌停顺延、停牌顺延、trailing 买入日 peak、新高当日不触发、断码冻结、到期与 TP 同日、佣金手算、halt 冻 peak）。 |
| **C** 11 亿、总收益率主排序、锚线四条、稳健性四件套、输出路径 | **FAIL（锚线 ④）** / 其余骨架 PASS | `CASH_POOL=1.1e9`，`rank_strategies` 按 `total_return` 降序。年化 `(1+r)^(365/322)−1`（322 = 20251023–20260909 含首尾）。回撤走 11 亿初始净值曲线；峰值并发 = 在持笔数 × 100 万。先卖后买。输出 `backtest_output/unified_exit_modea/{ranking.csv,instance_detail_top.csv,summary.json}`。四锚：hold-end / r1_n1 / oracle（T+1 起剔跌停最优）/ `delist_zero`。Q34：半窗日期锁定、plateau 函数、board/month 分层、次日开盘买换价重跑。**锚线 ④ 的 `total_return`/`max_drawdown` 未把受冻仓 MTM 置 0**（见 🔴）。 |
| **切片 D 未伪完成** | **PASS** | PR body 明确 Out of scope；host-runbook 状态仍 `host-only — NOT done in PR`；交接「切片 D 仍宿主-only」；提案页眉「切片 D 仍宿主-only」。无宿主短记、无 `backtest_output/unified_exit_modea/` 真数据产物入仓。 |
| **UTF-8 / 门禁 / pytest** | **PASS**（计数口径差，非红） | 本核：Mode A 三文件 **33 passed / 0.50s**（vanna312）。GitHub Actions [`35183059641`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35183059641) `pytest-and-gates` SUCCESS：`674 passed, 5 skipped, 24 deselected, 3 warnings / 21.46s`。PR 宣称本地 `700 passed / 3 skipped` = 703 collected；CI `674+5+24=703`，与 #78 同一 marker 口径差。STOP：无 Q36。 |

### 退出语义抽检（对照提案 §二/§四 / Q32）

| 场景 | 实现 | 单测 |
|------|------|------|
| T+1 买入日不可卖 | 循环 `range(buy_i+1, end_i+1)` | v01/v02 |
| N=1 ≡ 规则 2 N=1 的成交日/价（reason 可不同） | 同日 close；规则 2 可能标 `take_profit` | v01（return 相等） |
| 到期停牌顺延到复牌首根 K | 无 K `continue`，`market_held` 已 ≥ N | v04 |
| 跌停不卖、次日重评 | `_is_limit_down` 容差 0.2% | v03 / v13 |
| trailing：买入日只计 peak；可卖日先更新后判定 | 种子 `max(buy, buy_close)`；`peak=max(peak,close)` 再比 | v07 / v08 / v15 |
| 断码冻最后收盘、不记成交 | `mark_end` / `is_trade=False` | v10 / v11 |
| 佣金双边 0.1%；估值不扣卖佣 | `_price_return(..., is_trade=)` | v14 |

### 依赖（HEAD，无环，禁区未改）

```
run_unified_exit_modea.py → unified_exit_modea
  ├→ csv_daily_loader._read_one_daily / warmup_start
  ├→ csv_pool.parse_pool_csv_entries
  ├→ market_layer.limit_pct / board_limit_pct
  ├→ common.infra.data_root.resolve_period_root
  └→ csv_minute_backtest_v7.load_index_daily   # 惰性，仅生产日历
```

---

## 违规 / 风险

### 🔴 bug-1（Q33 / 锚线 ④ / Q30 第一排序）`delist_zero` 只改了实例 PnL，净值曲线仍按最后收盘估值

- File: `backtest/research/unified_exit_modea.py:701`（`delisting_zero_exits`）+ `:531`（`build_daily_equity`）+ `:610`（`aggregate_strategy`）
- 锁定原文（Q33=B）：主口径冻到最后收盘；敏感性「9 笔受冻实例若按 0 估值」对 **总收益率与排名** 的影响；**只动期末估值，不动卖出路径**。
- 实现：`ExitResult(sell_price=0, return_pct=-1, pnl=-buy_cost, is_trade=False, reason="mark_end_zero")`。`build_daily_equity` **跳过** `is_trade=False`，持仓一直留在 `held`，MTM 仍走 `_last_close_on_or_before`（最后收盘）。因此 `aggregate_strategy.total_return` / `max_drawdown` 与 `anchor_hold_end` **逐字节同一**，只有 `total_pnl` / `mean_return_pct` 被改掉。
- 本核合成复现（cash=3e6，断码 11/04 close=10.2，end=11/06）：

  | 指标 | hold-end | delist_zero | 若 MTM=0 应是 |
  |------|----------|-------------|----------------|
  | total_return | 0.006333 | **0.006333（相同）** | −0.333667 |
  | total_pnl | +19000 | −1_000_999.999… | −buy_cost |
  | mean_return_pct | +0.01898 | −1.0 | −1.0 |

- 预检量级 9×100 万 ≈ 基数 0.8%。宿主若只读 `summary.json` 锚线的 `total_return`（Q30 排序键），会得到「退市敏感性无影响」的假阴性。`test_delist_zero_sensitivity` 只断言 `reason` / `sell_price` / `return_pct`，**未**过聚合。
- Suggestion：在 `build_daily_equity` 对 `reason=="mark_end_zero"` 的键 MTM 记 0（仍 `is_trade=False`，不记卖出、不扣卖佣），或该锚的 `total_return` 改由 `sum(pnl)/cash_pool` 推导并加一条聚合单测：`delist_zero.total_return < hold.total_return` 且差 = 受冻仓买成本 / 现金池。顺带：窗口末日停牌（`sell_date < end` 但并非断码）也会被这条规则扫进「按 0」——修复 MTM 后应用「最后有 K 日 ≪ 窗口末」或预检 3 码白名单收窄，避免末日停牌误伤。

### 🟡 suggestion-1（Q34 ①）半窗「各排一次」只重切全窗排名的 top-50

- File: `backtest/research/unified_exit_modea.py:1030`
- 提案 / 交接：前后半窗（20251023–20260404 / 20260407–20260909）**各自排名** + top 20 名次一致性；①–③「在收益矩阵上重切即可，零额外回测成本」。
- 实现：按 `list_date` 切实例（Spillover 卖出保留，符合「重切实例、不重跑」），但策略集是 **全窗 ranked[:50]**。半窗第一、全窗第 51 的组不会进入 h1/h2 top20，`top20_overlap` 被截断集污染。
- Suggestion：对 `matrix` 全部 280 标签做同样的 subset `aggregate_strategy`（成本仍是聚合，不是再求值）。

### 🟡 suggestion-2（Q34 ③）创业 / 科创被 `board_limit_pct==0.20` 合成 `chinext_star`

- File: `backtest/research/unified_exit_modea.py:768`
- 锁定分层是 **主板 / 创业 / 科创**。`300*` 与 `688*`/`689*` 都是 20% 板，`board_bucket` 无法拆。应按代码前缀分（与 `market_layer._BOARD_20` 已有 300 vs 688 划分一致），不要用涨跌停幅度当板块键。

### 🟡 suggestion-3（Q34 ②）邻域扫描 `_n1` 子串误匹配 `_n10` / `_n15`

- File: `backtest/research/unified_exit_modea.py:816`
- `f"_n{n}" in o.label` 使 `n=1` 吃掉 `n10`/`n15`。本核：`r2_x2_y2_n1` 被标 `island=True`，邻居却是 `n10`/`n15` 而非真正的 1-step `(X,Y,N)`。孤峰警报不可信。应解析 label 后对 `(x,y,n)` 做网格邻接，或至少用 `_n{n}_` / 末锚匹配。

### nit-1（§三 报告口径）排名 CSV 未按 233 有效组去重

网格全跑 280 正确（§三「去重只是解读」）。规则 2 的 42 个 N=1 与 r1_n1 同日同价，外加 5 组「不设 TP/SL」。若 N=1 最优，top 20 会被等价行占满。报告侧应标 `equivalent_to` 或另出 233 解读表。宿主 runbook「规则 2 N=1 与规则 1 N=1 逐字节一致」须比 **日期/价格/收益**，不要比 `reason`（v01 已允许 `n_expire` vs `take_profit`）。

### nit-2（C 输出）实例明细只 dump top + 四锚；稳健性塞在 `summary.json`

交接写「排名 CSV、实例明细 CSV、汇总 JSON」；runbook 还列「稳健性」为第四类产物。`instance_detail_top.csv` 对合入门够用（全矩阵 4266×280 过大），但宿主短记若要对全部组做单股分布，需再跑或加开关。`half_window_split` 忽略传入的 `start/end`，写死锁定窗——本任务窗一致，换窗会 silently 错。

### nit-3（聚合）偶数实例的中位数取 `sorted(rets)[n//2]`

不是两中点平均。4266 实例下偏差可忽略；合成双实例单测未钉 peak_lots==1（只 `>=1`）。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| ST 幅度 | `limit_pct` 对 ST 名仍恒 5%；提案 20260706 起 10%。预检本窗 0 只 ST，网格结果零影响。 |
| 次日开盘买 | 只重跑 top5 + `r1_n1`（代码注释 cost control）。交接写「敏感性组」，可接受；不是 280 全矩阵。换价同时把 `list_date` 挪到次日，N 时钟后移一天——比「只换买入价」更接近真实次日开盘。 |
| 同序校验 | ranking 并列 `total_return` 与 `mean_return_pct`，无 rank-correlation 断言。因整百股残余，两列理论上可微乱序。 |
| 年化半窗 | h1/h2 仍用 `WINDOW_CALENDAR_DAYS=322` 年化；半窗排名键是总收益率，年化列会偏。 |
| warmup | `load_front_bars` 用 `days=20`，`csv_common.WARMUP_DAYS=10`。多取 20 日历日只为名单日 `prev_close`，不改成交。 |
| 首根无昨收 | `prev is None` 时仍开仓、不做封板判定。warmup 后窗口内 IPO/新码边缘。 |
| CI vs 本地 | 700/3 vs 674/5/24 deselected，同 #78 口径，非失败。3 warnings 来自未改的 minute / tr_filter。 |
| 单股分析 | 提案输出表有「每只股票在各参数下的表现分布」；交接 C 未列入，不挡合入。 |
| Q35 指纹 | 可选留痕，本 PR 未写 front 指纹进 `summary.meta`。按 Q35=D 可接受。 |

---

## 建议动作（是否可合）

**现在不能合。** 先修 🔴 bug-1（小补丁 + 一条聚合单测），再把本核结论改为 GO-WITH-NITS。不要为 suggestion-1/2/3 重切 A/B，也不要顺手改成交核 / 策略书。

合入前最小集：

1. `delist_zero` 净值路径把受冻仓 MTM 置 0（保持 `is_trade=False`），并断言 `total_return` 与 hold-end 分离。
2. （建议同补丁）半窗聚合改全 280 标签；`board_bucket` 拆 创业/科创；邻域匹配改解析字段。

合入后 / 宿主 D（非本 PR）：

3. 按 host-runbook 跑真数据；sanity 对 5061 / 封板≈795 / 9 笔受冻；峰值并发触 11 亿须标记。
4. 排名解读用 233 有效组；N=1 等价比价不比 reason。
5. 不要把切片 D 勾成完成。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin master feat/unified-exit-modea
git merge-base origin/master origin/feat/unified-exit-modea
git diff --name-status origin/master...origin/feat/unified-exit-modea
gh pr view 90 --json … statusCheckRollup
gh run view 35183059641          # 674 passed, 5 skipped, 24 deselected
# worktree: /workspace/MyQuant-backtrader-unified-exit @ a3a351f
/workspace/vanna312/bin/python -m pytest -q tests/test_unified_exit_modea_*.py
# → 33 passed in 0.50s
/workspace/vanna312/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py
# 合成脚本复现 delist_zero.total_return == hold.total_return
```

真数据网格 / 切片 D **未**跑（非合入门，本环境无 F 湖）。

> **合入前处理（2026-09-17）**：Codex 已修 Q33 — `build_daily_equity` 对 `mark_end_zero` MTM 计 0；单测 `test_delist_zero_sensitivity` 断言 total_return < hold。待 Grok 复核。
