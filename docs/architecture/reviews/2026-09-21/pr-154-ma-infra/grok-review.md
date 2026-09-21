# PR #154 共享均线基础设施 ma_infra（#150 后续实现）— Grok 核评审

> 日期：2026-09-21
> 角色：MyQuant-backtrader Grok 核（只审不合入）
> 对象：[PR #154](https://github.com/baiyibing/MyQuant-backtrader/pull/154) `feat/ma-infra` → `master`（draft）
> 权威：[handoff-ma-infra-codex-impl-2026-09-21.md](../../../../backtest/handoff-ma-infra-codex-impl-2026-09-21.md) §0 · [plan-ma-infra-shared-2026-09-21.md](../../../../backtest/plan-ma-infra-shared-2026-09-21.md) v1.0 GO · [merge-consensus C1–C12](../plan-ma-infra-shared/merge-consensus.md)
> HEAD：`213ee123b49bb5b720cde97d9575ba0f40b07e1d`
> merge-base vs `origin/master`：`9f0c4b921254d8bcf4160f59f0f36b78631f2baa`（#150 交接文档）
> GitHub：`MERGEABLE` / `CLEAN` / draft / `pytest-and-gates` **SUCCESS**（[run 35568232438](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35568232438) @ `213ee12`）
> 本核 **未 merge**。保持 draft。

---

## 结论

**PASS_WITH_NITS**（无合入阻断；nits 是文档编号与下游用法提醒，不要求本票改算子或扩 scope）。

切片 A/B 落在人裁八件上：`sma_asof` 与 master 种子**逐字相同**（NaN 传播、`n<=0`→None、`int(n)` 截断，无“清理”）；σ 钉死 `ddof=1` / `std([1..5]) == 1.5811388300841898`，未抄 `oskh_factors.price_bb` 的 `ddof=0`；周线返回 `_last_day`、末端未完成周保留、停牌空周无行，并与 `_daily_to_weekly` 差分对齐。`strategy4_rules.py` 的 diff 只有 import + 删本地 def；`buy_gate` / `sell_gate` / `take_profit_reason` / `record_strategy4_params` 函数体与 `origin/master` **字节相同**。零引擎、零 BOOKS、零 `oskh_factors`。模块标准库-only。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#154 feat(research): shared MA infrastructure (follow-up to #150)](https://github.com/baiyibing/MyQuant-backtrader/pull/154) |
| 比较 | `9f0c4b9..213ee12`（GitHub vs `origin/master`：5 files, +405 / −8） |
| A | `af6b812` — `ma_infra.py` 八件 + `tests/test_ma_infra.py` 46 pins |
| B | `3b3b7e4` — strategy4 删 def + `from backtest.research.ma_infra import sma_asof` |
| Docs | `213ee12` — handoff 完成记录 + plan 状态回写 |
| 代码面 | **三处**：新 `backtest/research/ma_infra.py`、新 `tests/test_ma_infra.py`、改 `strategy4_rules.py`（import + 删 def） |
| 禁区 | 无 `csv_strategy_books.py` / 引擎 / `oskh_factors` / BOOKS `register()` |

`git diff --name-status origin/master...HEAD`：

```
A  backtest/research/ma_infra.py
M  backtest/research/strategy4_rules.py
M  docs/backtest/handoff-ma-infra-codex-impl-2026-09-21.md
M  docs/backtest/plan-ma-infra-shared-2026-09-21.md
A  tests/test_ma_infra.py
```

多出来的两份 md 是 handoff「回写要求」规定的完成记录，不是第四个代码面。`origin/master` 在 merge-base 之后另有 #149 / s12+v11 文档（`dbefea8`）；本 PR `MERGEABLE`/`CLEAN`，那些提交不在本 diff 内。

---

## 硬边界证据表

| 锁 | 结果 | 证据 |
|----|------|------|
| **1 三代码面 / 零引擎 / 零 BOOKS** | **PASS** | name-status 如上。`git diff --stat origin/master...HEAD -- csv_strategy_books.py oskh_factors csv_daily_backtest.py csv_simulate_loop.py csv_ledger.py` 空。`csv_strategy_books.py:483-484` 仍按模块属性挂 `strategy4_rules.buy_gate/sell_gate`；`register(version4)` 块未动。 |
| **2 `sma_asof` 原样搬家** | **PASS** | AST 抽出的函数源码与 master 种子逐字相等。`sma_asof([1,nan,3],3)` 是 nan 且 `is not None`；`[nan,2,3],2 → 2.5`（NaN 出窗后不“清理”成 None）；`n in {0,-1}` → None；`n=2.9` → 窗口 2、均值 3.5。 |
| **3 σ = ddof=1** | **PASS** | `sqrt(2.5) == stdev([1,2,3,4,5]) == 1.5811388300841898`；`bb_asof([1..5], n=5, k=1)` 上轨 = `3+σ`，不是 `ddof=0` 的 `3+√2`。`bb_series` 增量式 `(s2−s1²/n)/(n−1)`。测试对照 `pandas.rolling.std(ddof=1)`。`oskh_factors` 零 diff；未采用 `price_bb.py` / `full_market_chip_resist.py` 的 ddof=0，也未套 `chip/bands.py` 的 round4。 |
| **4 周线三条** | **PASS** | 返回键是 `_last_day` 不是 W-FRI 标签。合成样本含节假短周、停牌空周、跨年/周六开桶、末端周、NaN 周、乱序/重复日，与 `_daily_to_weekly` 逐值相等，且存在 `label != _last_day`。本核另跑 cursor-auto 日历：`2024-09-16/17/18` → `[(2024-09-18, 12)]`，周五标签是 `2024-09-20`；`weekly_sma_asof(..., n_weeks=1) == 12`（不是 None）。周五休市样本 `2024-09-09..12` → last_day=`09-12`、label=`09-13`。`2024-01-12` 空周不在行集。 |
| **5 `ma_infra.py` 标准库** | **PASS** | AST import 仅 `__future__` / `datetime` / `math` / `typing`。无 `pandas`/`numpy`。测试文件内联 pandas 做差分，符合 R2。 |
| **6 不动 `oskh_factors`** | **PASS** | 该树零 diff。`_daily_to_weekly` 仍私有；`:183` MA200 仍在。测试只 **读** 参照。 |
| **7 无 EMA/WMA/自适应 / 无 `*_frame`** | **PASS** | 八个 `def`：`sma_asof` / `sma_series` / `sma_live` / `bb_series` / `bb_asof` / `daily_to_weekly` / `weekly_sma_series` / `weekly_sma_asof`。无 AST pin（plan：留给将来 `*_frame`）。 |
| **8 `sma_live` 尾部 n−1 + px** | **PASS** | `prev=[1,2,3,4], px=10, n=3 → (3+4+10)/3`；**不是**前缀 `(1+2+10)/3`。`list()` 拷贝，输入不突变。`len<n−1` 或 `px<=0` → None。`n=1` 允许空 prev。 |
| **9 模块零复权 / 零证券代码** | **PASS** | 无 `adjust` / `qfq` / `hfq` / `dividend` / `symbol`。截止权与价格域留在调用方（R4/C5）。 |
| **切片 B import-only** | **PASS** | `strategy4_rules.py` diff = 顶部一行 import + 删除本地 `sma_asof`。`buy_gate`/`sell_gate`/`take_profit_reason`/`record_strategy4_params` 与 `origin/master` 源码 IDENTICAL。`rules.sma_asof is ma_infra.sma_asof`。既有 `tests/test_strategy4_rules.py` 4 passed（未改 pin）。 |
| **UTF-8 无 BOM** | **PASS** | 五个触及文件 NUL=0、BOM=false、CR=0。`git diff --check` 空。 |
| **Ruff 0.12.0** | **PASS** | 本核：`ruff check ma_infra.py strategy4_rules.py test_ma_infra.py` → All checks passed（与实施记录同一 ruff 版本）。 |

---

## 行为 / 测试是否够用

handoff 清单（差分 / 数值 / 边界 / 等长 / 尾部拼接 / 周线三条）各至少 1 条，且 parametrize 后官方文件是 **46 items**。本核复跑：

| 命令 | 结果 |
|------|------|
| `pytest -q tests/test_ma_infra.py`（`_daily_to_weekly` 经 importlib 直载，避开 `oskh_factors/__init__` 的 chip 链） | **46 passed** |
| `pytest -q tests/test_strategy4_rules.py` | **4 passed** |
| `pytest -q tests/test_csv_strategy_books.py` | 本核薄环境缺 `pyarrow`，`test_daily_quota_trades_byte_identical[version1]` 在 `csv_daily_backtest` import 处收集失败；其余 **26 passed**（含 `test_apply_version4_has_sma_gates_and_no_stop`）。**不是 PR 回归**。 |
| CI `pytest-and-gates` | **SUCCESS** @ `213ee12`（实施记录：1420 passed / 4 skipped / 24 deselected） |
| 独立对抗脚本（cursor-auto 日历、周五休市、ddof=0 反例、live 非前缀、gate 身份） | **全过** |

`*_asof = 序列件[-1]`：`bb_asof` / `weekly_sma_asof` 确是薄封装。`sma_series[i] == sma_asof(prefix i)` 有 pin（含 NaN/±inf）。`bb_series(n<2)` 整列 None，无 ZeroDivision。

`weekly_sma_series[i]` **不等于** `weekly_sma_asof(dates[:i+1], …)`。这不是漏测，是归档口径：

> 中间未完成周不参与；序列末端未完成周若 `_last_day<=D` 可参与。

全序列上，一周只在该周 `_last_day` 进入；调用方先截到 D 再 `weekly_sma_asof`，末端未完成周才入窗。测试钉了 `asof(dates[:3])==16` 而全序列 Jan 2 位仍是 `None`。v11 R8「调用方先截 ≤D」依赖这个契约——**不要改成前缀向量化**。见 nit-3。

---

## 违规 / 风险

无 🔴。硬边界未破。无引擎 / BOOKS / `oskh_factors` / 成交核 diff。

### nit-1（文档）plan 页眉「已实施（本 PR #150）」编号错位

#150 已于 2026-09-21 06:06:14 UTC 合并，内容只有交接文档 `9f0c4b9`。实现在本票 #154。handoff 完成记录与 plan「交付说明」已经写明「不表示代码已入 master」，所以**不阻断**。合入前或合入后把页眉改成「已实施（PR #154）」即可，避免后人把 #150 当成实现票。

### nit-2（测试覆盖，可选）cursor-auto 日历未写进 `tests/test_ma_infra.py`

共识 R1 点名的数值 pin：`2024-09-16/17/18`、`n_weeks=1`、D=`2024-09-18` → `12`，且 W-FRI 标签 `2024-09-20 ≠ _last_day`。仓库测试用 2023-12 / 2024-01 合成样本覆盖了同一条（标签≠last_day、末端周保留）。本核已用该日历独立复验通过。**不要求本票补测**；v11 落地前补一条更直观。

### nit-3（下游用法，不改本模块）`weekly_sma_series` 不是逐日前缀 asof

批量件按「一次换算 + 周窗滚动 + 按 `_last_day` 回填」。v11/s12 若把 `weekly_sma_series(full)[i]` 当成 `weekly_sma_asof(full[:i+1])`，中间交易日会看到**上一完整周**，不是「截到当日的周-to-date」。正确用法：asof 先截 `≤D`；序列件用于图表/导出的 backward ffill。本模块注释已写 “Callers must truncate inputs to D”。**不要为本句改算法。**

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 5 文件 vs「仅三处」 | 代码三处成立；两份 md 是规定回写。 |
| Ruff 0.16 vs 0.12 | 实施记录：0.16 会咬既有 strategy4 风格。本核不改 lint、不改种子。本核 0.12.0 绿。 |
| `origin/master` 已走到 `dbefea8` | 与本实现无文件冲突。 |
| 热路径 fence | `ma_infra` / `strategy4_rules` 不在 15 模块清单；`csv_strategy_books` 源码未新增 import。`ma_infra` 无 qlib/lebs/fee/fill_clock。 |
| `sma_live(px=nan)` | `nan <= 0` 为 False，走 NaN 传播而非 None。与种子 `sma_asof` 一致，plan 未另裁。 |

---

## 建议动作（是否可合）

**可以合（仍保持 draft，本核不点 merge / 不改 ready）。** 不要为 nit-1/2/3 重写八件或动 BOOKS/引擎。

合入时（文档卫生，可另点或跟本票）：

1. plan 页眉 PR 号改为 **#154**。
2. v11/s12 实施时按 nit-3 截断再 asof。

本核 **未 merge、未改业务代码**；只落本评审文件。

---

## 核验命令（本核已跑）

```text
git rev-parse HEAD
# = 213ee123b49bb5b720cde97d9575ba0f40b07e1d
git merge-base origin/master HEAD
# = 9f0c4b921254d8bcf4160f59f0f36b78631f2baa
git diff --name-status origin/master...HEAD
# A ma_infra.py / M strategy4_rules.py / M two docs / A test_ma_infra.py
gh pr view 154 --json isDraft,mergeable,mergeStateStatus,headRefOid
# draft true / MERGEABLE / CLEAN / 213ee12
gh run view 35568232438
# SUCCESS @ 213ee12
# ruff 0.12.0: All checks passed
# pytest test_ma_infra.py: 46 passed
# pytest test_strategy4_rules.py: 4 passed
# sma_asof source == master seed
# buy_gate/sell_gate/take_profit/record IDENTICAL vs origin/master
# stdev([1,2,3,4,5]) == 1.5811388300841898
# sma_live([1,2,3,4],10,3) == (3+4+10)/3 != (1+2+10)/3
# 2024-09-16/17/18 weekly_sma_asof n=1 == 12; label=2024-09-20
# 2024-09-09..12 last_day=09-12, label=09-13
# UTF-8: five files BOM=false NUL=0 CR=0
```

全量 CI 口径本核未在薄环境重跑（缺 pyarrow / 完整 vanna312）；以 GitHub `pytest-and-gates` SUCCESS 为准。
