# PR #90 统一卖出规则网格 · 模式 A — Grok 核评审（复核）

> 日期：2026-09-17（复核；上一轮 BLOCK 于 Q33 / `a3a351f`）
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #90](https://github.com/baiyibing/MyQuant-backtrader/pull/90) `feat/unified-exit-modea`（`origin/feat/unified-exit-modea` vs `origin/master`）
> 权威：[handoff-unified-exit-modea-codex-impl-2026-09-17.md](../../../../backtest/handoff-unified-exit-modea-codex-impl-2026-09-17.md) · [stock-backtest-unified-exit-proposal-2026-09-17.md](../../../../backtest/stock-backtest-unified-exit-proposal-2026-09-17.md)（Q1–Q35）· [host-runbook-unified-exit-modea-2026-09-17.md](../../../../backtest/host-runbook-unified-exit-modea-2026-09-17.md)（切片 D 非合入门）· 上一轮本文件（`a3a351f` 对象、结论 **BLOCK**）
> HEAD：`c1c2cafdcdcc49863a52083de4196f6d86fbbe80`
> merge-base：`f738c7d25302513d2dc21df1335dc8a59c72db22`（= `origin/master`）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**
> 工作树：`/workspace/MyQuant-backtrader-unified-exit`

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改成交核 / 策略书 / A/B 语义。本核不 merge）。

上一轮 🔴（Q33 锚线 ④ `total_return` 与 hold-end 逐字节同一）已在 `c1c2caf` 关掉：`build_daily_equity` 对 `reason=="mark_end_zero"` 跳过 MTM（贡献 0），`is_trade=False` 仍不记卖出、不扣卖佣。本核用上一轮同一合成（cash=3e6，断码 11/04 close=10.2，end=11/06）复现：`hold.total_return = 0.006333` → `delist_zero.total_return = −0.333667`（= `−buy_cost/cash`），严格更低。`test_delist_zero_sensitivity` 已断言 `zero.total_return < hold.total_return`。

A/B 在本补丁中 **零改**（`evaluate_exit` / `assemble_instances` / 网格 / v01–v15 未动），上一轮 PASS 仍成立。硬边界未破。Q34 三处口径缩水（半窗全 280 label、创业/科创前缀拆分、plateau `endswith _n{n}`）已改到可接受。剩余是报告解读 nits，不挡合入。

---

## 复核对照（相对 `a3a351f` BLOCK）

| 项 | 上一轮 | 本轮 `c1c2caf` |
|----|--------|----------------|
| 结论 | **BLOCK** | **GO-WITH-NITS** |
| 🔴 bug-1 Q33 锚线 ④ MTM | `total_return`/`max_drawdown` 与 hold-end 同一 | **关闭**。MTM 计 0；`total_return` 分离；单测过聚合 |
| A front 装配 | PASS | **仍 PASS**（本补丁未改 assemble） |
| B 退出求值器 | PASS | **仍 PASS**（本补丁未改 `evaluate_exit` / 网格） |
| 硬边界 | PASS | **仍 PASS** |
| 🟡 Q34① 半窗只切 ranked[:50] | 截断污染 top20 | **关闭（可接受）**：全 matrix 280 标签（剔三锚） |
| 🟡 Q34③ `chinext_star` | 20% 板合成一块 | **关闭（可接受）**：`300/301/302`→chinext，`688/689`→star |
| 🟡 Q34② `_n1` 吃 `_n10/_n15` | 子串误匹配 | **关闭（可接受）**：`endswith("_n{n}")`；x/y 改 `_x{}_` / `_y{}_` |
| 切片 D | 未伪完成 | **仍未勾** |
| CI | `35183059641` SUCCESS | [`35184413203`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35184413203) SUCCESS @ `c1c2caf` |

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#90 feat(unified-exit): Mode A slices A/B/C — assembly, exit matrix, reports](https://github.com/baiyibing/MyQuant-backtrader/pull/90) |
| 比较 | `origin/master...origin/feat/unified-exit-modea`（10 files, +2058 / −4） |
| A | `e5b9c50` front 装配 + instances；合成 fixture |
| B | `331d410` 实例×策略退出求值器 + ≥12 手算向量 |
| C | `a3a351f` 11 亿聚合 / 四锚线 / Q34 四件套 / 报告 + AGENTS/README |
| C′ | `c1c2caf` Q33 `mark_end_zero` MTM→0 + 聚合单测；Q34 半窗/板块/plateau nits |
| D | **未做、未勾**（host-runbook 仍 `host-only — NOT done in PR`） |

新代码落点仍符合交接：`backtest/research/unified_exit_modea.py` + `scripts/research/run_unified_exit_modea.py` + 三份 `tests/test_unified_exit_modea_*.py`。相对 master 多了一份本评审文件。文档只改交接状态行、提案页眉「A/B/C 已落地」、AGENTS 一行、`docs/backtest/README.md` 入口。

`git diff a3a351f..c1c2caf` 只动 `build_daily_equity` / `board_bucket` / `neighborhood_plateau_flags` / `run_modea` 半窗循环 + 聚合单测 + 本文件。禁区文件不在 diff。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **硬边界** 独立模块；禁区一行不碰 | **PASS** | vs master 10 文件，无 `csv_ledger.py` / `csv_simulate_loop.py` / `csv_daily_backtest.py` / `csv_minute_backtest.py` / `csv_minute_backtest_v7.py` / `*_rules.py` / 策略书。库 AST import：`csv_daily_loader` / `csv_pool` / `market_layer` / `data_root`；`csv_minute_backtest_v7.load_index_daily` 仅生产日历惰性引用。无 `backtrader` / `Cerebro` / Rolling / PortAnaRecord。 |
| **路径 / 湖** 无硬编码盘符、cwd `stock_data/`、CI data-free | **PASS** | 生产路径 `resolve_period_root("1d") / "dividend_type=front"`。新 `.py` BOM=false、NUL=0、UTF-8。`verify_no_hardcoded_machine_paths.py` OK；`verify_data_path_ssot.py` OK。`stock_data/` 只出现在 docstring 否定句。CLI `--pool-dir` 默认 `stock_pool`。 |
| **A** front 装载、封板跳过、无 K 跳过、缺名单日不买不报错 | **PASS（仍成立）** | 本补丁未改 `assemble_instances`。名单日无 close → `no_bar`；封板 ±0.2%；缺文件 `continue`；`_prev_close_on` 跨停牌；未知板块 / 整百股 0 fail-closed。assemble 9 测仍绿。 |
| **B** T+1 / N 市场日 / 跌停顺延 / 停牌顺延 / trailing peak / 期末估值；≥12 向量 | **PASS（仍成立）** | 本补丁未改 `evaluate_exit` / `iter_grid`。网格 `8+252+20=280`。exit v01–v15 + `test_matrix_shape` 仍绿。 |
| **C / Q33 锚线 ④** 受冻仓 MTM=0，`total_return` 相对 hold-end 更低 | **PASS** | 见下节。`is_trade=False` 保持。默认现金池与 cash=3e6 两条路径均 `zero.total_return < hold.total_return`。 |
| **C / Q34** 半窗全 label、board 前缀、plateau endswith | **PASS（可接受）** | 见下节。不是 1-step 网格邻接，但是上一轮「至少末锚匹配」的下限。 |
| **切片 D 未伪完成** | **PASS** | PR body Out of scope；host-runbook `host-only — NOT done in PR`；交接「切片 D 仍宿主-only」；提案页眉同。无宿主短记、无 `backtest_output/unified_exit_modea/` 真数据入仓。 |
| **UTF-8 / 门禁 / pytest** | **PASS**（计数口径差，非红） | 本核：Mode A 三文件 **33 passed / 0.53s**（vanna312）。GitHub Actions [`35184413203`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35184413203) @ `c1c2caf`：`674 passed, 5 skipped, 24 deselected, 3 warnings / 17.89s`。STOP：无 Q36。 |

### Q33 关闭（本核复现）

`delisting_zero_exits`：`reason=="mark_end"` 且 `sell_date < end` → `ExitResult(sell_price=0, return_pct=-1, pnl=-buy_cost, is_trade=False, reason="mark_end_zero")`。`build_daily_equity` 对 `is_trade=False` 仍不进 `sells_on`；MTM 环对 `reason=="mark_end_zero"` `continue`（贡献 0）。现金仍扣买成本，不回补卖佣。

同一合成（上一轮表格）：

| 指标 | hold-end | delist_zero（本轮） | 上一轮「若 MTM=0 应是」 |
|------|----------|---------------------|-------------------------|
| total_return | 0.006333 | **−0.333667** | −0.333667 |
| total_pnl | +19000 | −1_000_999.999… | −buy_cost |
| mean_return_pct | +0.01898 | −1.0 | −1.0 |
| is_trade | False | False | False |

`zero.total_return == -buy_cost/cash`（100_000 股 × 10 × 1.001 / 3e6）。默认 `CASH_POOL=1.1e9` 下 `hold=1.727e-5`、`zero=-0.00091`，同样严格更低。单测 `tests/test_unified_exit_modea_aggregate.py:131-135` 断言 `zero.total_return < hold.total_return` 且 `zero.max_drawdown >= hold.max_drawdown`。

Q33 锁定「仅动期末估值，不动任何卖出路径」：卖出路径未动。实现把受冻仓 **全程** MTM 计 0（买入日起），期末 `total_return` 与「只改末日估值」等价；本合成两条路径 `max_drawdown` 均为 0（单测 `>=` 在此 fixture 上不证明回撤移动）。排名键是 Q30 总收益率，已分离，不升格。

### Q34 三处（可接受）

1. **半窗全 label**（`run_modea` `:1044-1048`）：`half_labs = [lab for lab in matrix if lab not in (oracle, delist_zero, anchor_hold_end)]`。`iter_grid(include_anchor_hold_end=True)` = 281；剔三锚后 **280**。不再用 `ranked[:50]`。
2. **board strata**（`:775-789`）：前缀先拆 `300/301/302`→`chinext`、`688/689`→`star`，再 `board_limit_pct` 0.10→`main` / 0.30→`bse`。与 `market_layer._BOARD_20` 的 300 vs 688 划分一致。本核：`600000` main / `300001` chinext / `688001` star / `920001` bse。
3. **plateau endswith**（`:828`）：`o.label.endswith(f"_n{n}")`，`_n1` 不再当 N 键匹配 `_n10/_n15`。x/y 改为 `_x{_fmt_grid(x)}_` / `_y{_fmt_grid(y)}_`。族仍是 **同 N 或同 X 或同 Y 的 OR**（不是 1-step `(ΔX,ΔY,ΔN)` 邻接），同 X/Y 的 n10/n15 仍会进 family——这是启发式宽度，不是子串 bug。上一轮建议的下限「末锚匹配」已满足，孤峰警报可接受。

### 退出语义抽检（对照提案 §二/§四 / Q32；B 未改）

| 场景 | 实现 | 单测 |
|------|------|------|
| T+1 买入日不可卖 | 循环 `range(buy_i+1, end_i+1)` | v01/v02 |
| N=1 ≡ 规则 2 N=1 的成交日/价（reason 可不同） | 同日 close；规则 2 可能标 `take_profit` | v01（return 相等） |
| 到期停牌顺延到复牌首根 K | 无 K `continue`，`market_held` 已 ≥ N | v04 |
| 跌停不卖、次日重评 | `_is_limit_down` 容差 0.2% | v03 / v13 |
| trailing：买入日只计 peak；可卖日先更新后判定 | 种子 `max(buy, buy_close)`；`peak=max(peak,close)` 再比 | v07 / v08 / v15 |
| 断码冻最后收盘、不记成交 | `mark_end` / `is_trade=False` | v10 / v11 |
| 佣金双边 0.1%；估值不扣卖佣 | `_price_return(..., is_trade=)` | v14 |
| Q33 敏感性 MTM=0 | `mark_end_zero` + equity skip | `test_delist_zero_sensitivity` |

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

上一轮 🔴 bug-1 **关闭**。上一轮 🟡 suggestion-1/2/3 **关闭（可接受）**。无新 🔴。

### nit-1（§三 报告口径）排名 CSV 未按 233 有效组去重

网格全跑 280 正确（§三「去重只是解读」）。规则 2 的 42 个 N=1 与 r1_n1 同日同价，外加 5 组「不设 TP/SL」。若 N=1 最优，top 20 会被等价行占满。报告侧应标 `equivalent_to` 或另出 233 解读表。宿主 runbook「规则 2 N=1 与规则 1 N=1 逐字节一致」须比 **日期/价格/收益**，不要比 `reason`（v01 已允许 `n_expire` vs `take_profit`）。

### nit-2（C 输出）实例明细只 dump top + 四锚；稳健性塞在 `summary.json`

交接写「排名 CSV、实例明细 CSV、汇总 JSON」；runbook 还列「稳健性」为第四类产物。`instance_detail_top.csv` 对合入门够用。`half_window_split` 仍忽略传入的 `start/end`，写死锁定窗——本任务窗一致，换窗会 silently 错。

### nit-3（聚合）偶数实例的中位数取 `sorted(rets)[n//2]`

不是两中点平均。4266 实例下偏差可忽略。

### nit-4（Q33 代理）窗口末日停牌也会被扫进 `mark_end_zero`

`delisting_zero_exits` 条件是 `reason=="mark_end" and sell_date < end`。本核：K 停在 11/05、窗末 11/06 → 也被置 0。预检 3 码是窗内早断，量级仍约 9 笔；真数据若有末日 1 日停牌会被误伤。上一轮「顺带」未升格；宿主 D 可用 3 码白名单或「最后有 K 日 ≪ 窗末」收窄。不挡合入。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| Q33 全程 vs 末日 MTM | skip 从买入日起 MTM=0。期末 `total_return` 正确；若断码前大涨，回撤会少记峰值。排名键不受影响。 |
| plateau OR 族 | 同 X/Y 的远 N 仍进 family；`[:8]` 取排名前 8 而非网格 1-step。endswith 已堵住 N 子串误匹配。 |
| 单测未钉差值 | `test_delist_zero_sensitivity` 只断言 `<` / `>=`，未钉 `−buy_cost/cash`。本核手算已对齐；不要求补测才能合。 |
| ST 幅度 | `limit_pct` 对 ST 名仍恒 5%；提案 20260706 起 10%。预检本窗 0 只 ST。 |
| 次日开盘买 | 只重跑 top5 + `r1_n1`（cost control）。交接写「敏感性组」，可接受。 |
| 年化半窗 | h1/h2 仍用 `WINDOW_CALENDAR_DAYS=322`；半窗排名键是总收益率。 |
| CI vs 本地 | 700/3 vs 674/5/24 deselected，同 #78 口径，非失败。 |
| Q35 指纹 | 可选留痕，本 PR 未写 front 指纹进 `summary.meta`。按 Q35=D 可接受。 |

---

## 建议动作（是否可合）

**可以合。** 不要为 nit-1…4 重切 A/B，也不要顺手改成交核 / 策略书。切片 D 仍宿主-only。

合入后 / 宿主 D（非本 PR）：

1. 按 host-runbook 跑真数据；sanity 对 5061 / 封板≈795 / 9 笔受冻；峰值并发触 11 亿须标记。
2. 排名解读用 233 有效组；N=1 等价比价不比 reason。
3. 不要把切片 D 勾成完成。
4. （可选）`delist_zero` 用 3 码白名单或「最后有 K ≪ 窗末」避免末日停牌误伤。

本核 **未 merge、未改业务代码**；仅覆盖本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin master feat/unified-exit-modea
# HEAD c1c2caf == origin/feat/unified-exit-modea
# merge-base origin/master = f738c7d
git diff --name-status origin/master...HEAD
# 10 files; 禁区文件不在列
gh pr view 90 --json mergeable,mergeStateStatus,statusCheckRollup,headRefOid
# MERGEABLE / CLEAN / head = c1c2caf
gh run view 35184413203          # 674 passed, 5 skipped, 24 deselected @ c1c2caf
# worktree: /workspace/MyQuant-backtrader-unified-exit @ c1c2caf
/workspace/vanna312/bin/python -m pytest -q tests/test_unified_exit_modea_*.py
# → 33 passed in 0.53s
/workspace/vanna312/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py
/workspace/vanna312/bin/python scripts/gates/verify_data_path_ssot.py
# 合成复现 delist_zero.total_return = -0.333667 < hold 0.006333（cash=3e6）
# board_bucket: main/chinext/star/bse；half_labs=280；endswith _n1 不吃 _n10
```

真数据网格 / 切片 D **未**跑（非合入门，本环境无 F 湖）。

---

## 附录：上一轮结论（`a3a351f`，已关闭）

**BLOCK**（合入前须修 Q33 锚线：`delist_zero` 的总收益率 / 最大回撤仍按最后收盘 MTM）。C 骨架有落地但锚线 ④ 在 Q30 第一排序指标上假绿；Q34 半窗 top-50 / 创业科创合并 / `_n1` 子串误匹配。合入前最小集即本轮 `c1c2caf` 已做的补丁 + 聚合单测。
