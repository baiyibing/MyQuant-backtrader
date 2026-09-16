# PR #78 NP3 引擎分层 — Grok 核评审

> 日期：2026-09-16
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #78](https://github.com/baiyibing/MyQuant-backtrader/pull/78) `feat/np3-engine-layering`（`origin/feat/np3-engine-layering` vs `origin/master`）
> 权威：[`docs/backtest/plan-np3-engine-layering-2026-09-16.md`](../../../../backtest/plan-np3-engine-layering-2026-09-16.md) v1.2（P1–P4 人裁 GO）· [`docs/backtest/handoff-np3-engine-layering-codex-impl-2026-09-16.md`](../../../../backtest/handoff-np3-engine-layering-codex-impl-2026-09-16.md) · 硬锁 N-R1…N-R10
> HEAD：`b9b101ee364095ddd0ecc602296f308cf54c479d`
> merge-base：`2780603a812004d944887def285670cedaf5036f`（= `origin/master`）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改成交语义）。

对照 plan v1.2 / 交接 / N-R1…N-R10：这是一次合格的纯机械分层。被搬 14 个函数 + 4 个常量的 **AST 与原文函数体均与 master daily 逐字同一**；两条 `simulate()` / 卖环 / `csv_ledger.py` 记账体 / CLI `main()` / `HELP_LOCK` / 落盘三件套文件名 **零改**；minute→daily import **41 → 0** 且 AST 围栏已落；artifacts 6 符号闭包、loader `_read_one_daily` + `_PERIOD_ENV_KEYS`、无环、artifacts 不 import loader；P1–P4 与 N-R9 测试面 pin 均落地；CI `python-tests` 全绿。

唯一计划字面偏差：slice B 在 `csv_common` 多写了未列入落点的 `_limit_prices = resolve_limit_prices` 及一段误导注释（无反向边、无调用方、不改行为）。不构成 BLOCK。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#78 feat(np3): engine layering — dual entry + shared core (A–D)](https://github.com/baiyibing/MyQuant-backtrader/pull/78) |
| 比较 | `origin/master...origin/feat/np3-engine-layering`（16 files, +583 / −376） |
| A | `278bf6f` retarget 29 符号 + P1–P4 GO 文档；minute→daily **41→10** |
| B | `d0adf54` 抽 `csv_artifacts`（6）+ `_progress`→common；**10→6** |
| C | `8ec5bba` 抽 `csv_daily_loader` + 3 常量→common；**6→0** |
| D | `b9b101e` AST 围栏、`_VECTORIZED_RESEARCH_FACE`、pin「仅测试」、README 引擎地图 |

plan §5 A/B 完成定义写的是 41→13 / →8（把 minute 从未 from-import 的伴生算进剩余）。实测剩余是 minute 仍从 daily 拉的符号数：**10 / 6 / 0**。PR 正文计数更准；不是实施漏搬。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **N-R1** 不合并卖环 / `simulate()` | **PASS** | 禁区文件不在 diff：`csv_ledger.py` / `csv_simulate_loop.py` / `csv_pool.py` / `market_layer.py` / `strategy6_rules.py` / v7 / Rust。daily 残留 top-level 中 `simulate` / `main` / `HELP_LOCK` / `help_lock_for` **原文同一**；minute `simulate` 原文同一。两引擎 `run()` 各只改 **1 行**（P3 直呼，见下）。 |
| **N-R2** 函数体零改动 | **PASS**（1 处字面 nit，见违规） | 对 master daily 抽取 vs 新家：`summarize` / `write_run_artifacts` / `maybe_compare_daily` / `find_daily_equity_csv` / `format_equity_compare` / `load_daily_bars` / `_read_one_daily` / `warmup_start` / `warn_stale_period_env` / `_progress` / `DEFAULT_DAILY_QUOTA` / `WARMUP_DAYS` / `STRATEGY4_CALENDAR_SLACK_DAYS` / `_PERIOD_ENV_KEYS` 全部 **IDENTICAL-AST 且 raw-source 同一**（含 docstring、默认参数）。REPO 复算公式与 daily 原式同一：`os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))`。 |
| **N-R3** pytest + golden + 三单测 | **PASS**（本核未复跑全量 pytest） | GitHub Actions [`35058768602`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35058768602) `pytest-and-gates` **SUCCESS**（Contract gates + `pytest -q -m "not production and not benchmark"` → **578 passed, 5 skipped, 24 deselected, 3 warnings / 19.47s**）。PR 正文本地全量宣称 604 passed / 3 skipped，与 CI deselected 口径差可对上，非红。三 data-free 单测见 P4。宿主 trades.csv 逐字节对照：PR 标明未做（plan 写明非合入门）。golden 夹具文件不在本 diff。 |
| **N-R4** 不留兼容 re-export | **PASS** | daily 无 `__all__`、无下沉符号 stub。全树 `from backtest.research.csv_daily_backtest import` **零命中**。daily 因 `run()` 自用仍绑定 `summarize` / `write_run_artifacts` / `load_daily_bars` 等，不是兼容转发层。`load_pool_days` wrapper 已删。 |
| **N-R5** 无环 + artifacts↛loader | **PASS**（csv_common 多 1 个别名，见 nit） | 静态边：`artifacts → ledger`；`loader → common, market_layer`；`common → ledger`；两引擎 → 共享核。环检测 **NONE**。artifacts 不 import loader / 引擎；loader 不 import artifacts / 引擎。 |
| **N-R6** minute→daily 41→0 + 持久围栏 | **PASS** | master 顶部 ImportFrom 41 符号；HEAD `tree.body` 与 `ast.walk` 均为 **0**（含 `import csv_daily_backtest` 形式）。围栏：`tests/test_research_face_imports.py::test_csv_minute_ast_no_csv_daily_import`（与 plan §6 同一：只扫 top-level `ImportFrom`）。 |
| **N-R7** CLI / HELP / 落盘 | **PASS** | `HELP_LOCK` 原文同一；两引擎 `main()` 原文同一。`write_run_artifacts` 仍写 `trades.csv` / `daily_equity.csv` / `summary.txt`（函数体未改）。 |
| **N-R8** 搬移闭包 | **PASS** | artifacts **6**：summarize / write_run_artifacts / maybe_compare_daily / **find_daily_equity_csv** / **format_equity_compare**（`_progress` 进 common，不进 artifacts）。loader：**load_daily_bars / `_read_one_daily` / warmup_start / warn_stale_period_env / `_PERIOD_ENV_KEYS`** + 本地 REPO。 |
| **N-R9** 测试面 pin 保留 | **PASS** | daily `_ = (...)` 保留，注释改为「仅测试…（N-R9）；非引擎转发。」`chase_explained` import 保留；测试仍 `sim.chase_explained`（daily 9 处 + v8 2 处）。`_limit_prices = resolve_limit_prices` 保留；`test_csv_daily_backtest.py:593` 仍 `sim._limit_prices`。`help_lock_for` wrapper 保留（默认 `shared=HELP_LOCK`）。`to_partition_key` 已从 daily 删除，测试改从 `oskh_data.symbol_format` 取。 |
| **N-R10** UTF-8 无 BOM、NUL=0 | **PASS** | 新/改 py：`csv_artifacts.py` / `csv_daily_loader.py` / `csv_common.py` / 两引擎 / `test_np3_layering.py` / `test_research_face_imports.py` 均为 UTF-8、BOM=false、NUL=0。本沙箱无 vanna312；CI 用 Python 3.12（workflow 既定）。 |
| **P1** 常量归属 | **PASS** | 三常量在 `csv_common`。`MINUTE_LAKE_END = "20260909"` **仅** minute 自定义；daily / loader / artifacts / common **均无**该名。`_PERIOD_ENV_KEYS` 在 loader。 |
| **P2** 不留 re-export | **PASS** | 同 N-R4；测试面按 N-R9 保留。 |
| **P3** 直呼 `load_pool_day_map` | **PASS** | 两引擎均为 `load_pool_day_map(actual_pool_dir, start, end, key="ymd", empty_in_map=False)`。master wrapper 默认 `REPO/stock_pool` 本就是死路径（`run()` 已先 `resolve_research_pool_dir`）。csv_pool 未改（repo-无感）。测试 `test_load_pool_days_reads_utf8_without_qmt_logger` 改直呼。v7 自有 `load_pool_days`，本 diff 未碰。 |
| **P4** 三 data-free 单测 + docstring 契约 | **PASS** | `tests/test_np3_layering.py`：`test_summarize_deterministic_full_text_golden`（剔 `耗时:`）/ `test_maybe_compare_daily_peer_caption`（对端目录 + 空 book + 缺对端）/ `test_warn_stale_period_env_monkeypatch`（静默 + 一键告警）。artifacts docstring 含「`csv_daily_{book}_{start}_{end}` … 命名串是数据，不是对引擎代码的依赖。」loader docstring 含「三职责」且声明不 import 引擎。 |
| 消费者闭包 §1.2 | **PASS** | daily 测试：`_read_one_daily`×5→loader；`summarize`×4 / `write_run_artifacts` / `format_equity_compare` / `find_daily_equity_csv`→artifacts；`load_pool_days`→`load_pool_day_map`。minute / minute_v8：`chase_explained`→ledger。v8 summarize 测试、`test_csv_strategy_books.py:352`→artifacts。`test_csv_daily_outdir` / `test_strategy9_book` / `test_strategy10_tr_pool` / `generate_snapshot.py` 仍 `sim.main/run/simulate`，零动作。 |
| D 片围栏 / 白名单 / 地图 | **PASS** | 两新模块入 `_VECTORIZED_RESEARCH_FACE`。README 引擎地图段写明双入口 + 共享核（含 artifacts / loader）。plan 状态 →「A–D 已落地（待 PR 评审）」；交接 →「生效 / A–D 完成；勿自动 merge」。 |

### 机械同一（N-R2）明细

从 `origin/master:backtest/research/csv_daily_backtest.py` 抽出定义，与 HEAD 新模块 `ast.unparse` + `ast.get_source_segment` 双比，全部同一：

```
summarize / write_run_artifacts / maybe_compare_daily / find_daily_equity_csv / format_equity_compare  → csv_artifacts
load_daily_bars / _read_one_daily / warmup_start / warn_stale_period_env / _PERIOD_ENV_KEYS          → csv_daily_loader
_progress / DEFAULT_DAILY_QUOTA / WARMUP_DAYS / STRATEGY4_CALENDAR_SLACK_DAYS                         → csv_common
```

daily 残留 `simulate` / `main` / `HELP_LOCK` / `help_lock_for` / `_` pin / `_limit_prices` / `REPO` / `resolve_csv_daily_out_dir` 原文同一。minute 新增 `MINUTE_LAKE_END`；其余 top-level 除 `run()` 外原文同一。

### 依赖图（HEAD，无环）

```
csv_minute_backtest ─┬→ csv_artifacts → csv_ledger → market_layer
csv_daily_backtest  ─┤→ csv_daily_loader → csv_common → csv_ledger
                     ├→ csv_common / csv_ledger / csv_pool / csv_strategy_books
                     └→ csv_simulate_loop → csv_common / csv_ledger / csv_strategy_books
```

`csv_artifacts ↛ csv_daily_loader`；两新模块 ↛ 引擎文件。

---

## 违规 / 风险

无 🔴。无合入阻断。

### nit-1（N-R2 / N-R5 字面）`csv_common` 多了一条未列入落点的别名

slice B（`d0adf54`）在搬 `_progress` 时额外写入：

```python
# Re-exported from csv_common for existing imports / minute engine.
# (build_calendar, _named_limits, _pool_names_asof)

_limit_prices = resolve_limit_prices
```

- `build_calendar` / `_named_limits` / `_pool_names_asof` **本就在** `csv_common`，注释是错误的「转发」叙事。
- `_limit_prices` 真身仍按 N-R9 留在 daily（`resolve_limit_prices` 别名）；common 这条绑定 **全树零 from-import**。
- `csv_common` 在 master 已 import `resolve_limit_prices`，**未新增反向边**，N-R5 的环/倒挂风险未触发。
- 计划允许 common 只加 **3 常量 + `_progress`**。这 4 行是顺手附加，不是被搬函数体改动。

不改成交、不改 CLI、不引入环。建议合入后删这 4 行（或下一 hygiene 片），**不必为此 BLOCK / 不必重切 PR**。

### nit-2（卫生，非锁违例）daily 装载 import 成为死绑定

`_read_one_daily` / `load_daily_bars` 迁走后，daily 仍留 `ThreadPoolExecutor` / `as_completed` / `numpy` / `pyarrow.compute` / `pyarrow.parquet` / `resolve_period_root`。plan C 只要求删 `to_partition_key`（已删）。**留下死 import 更贴 N-R2「禁止格式化无关行」**；列为后续卫生，不是本 PR 缺陷。

### nit-3（交接措辞严于 plan）`warn_stale_period_env` 单测只覆盖一键

handoff C 片写「monkeypatch OSKH_\* env **各键**」。实现：全键 `delenv` 后静默 + 只 set `OSKH_PERIOD_1D_ROOT` 断言文案。plan P4 / §5 原文是「monkeypatch env」，静默/告警两分支已焊。未扫 `_PERIOD_ENV_KEYS` 其余四键是覆盖宽度 nit，假绿通道已堵。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 围栏半径 | 只扫 minute **top-level ImportFrom**（与 plan §6 脚本同一）。`import csv_daily_backtest` / 函数体内 import 不会被围栏抓住；HEAD `ast.walk` 亦为 0。 |
| plan 计数文案 | §5 仍写 41→13 / →8；实施与 PR 正文为 41→10 / →6。差在伴生函数本就不在 minute import 块。 |
| 交接页眉 | 状态已「A–D 完成」，但仍写「权威对象 plan v1.1」（正文 plan 已 v1.2）。 |
| CI vs 本地计数 | CI 578 passed / 5 skipped / 24 deselected；PR 宣称本地 `pytest -q tests/` 604 / 3 skipped。workflow 显式 `-m "not production and not benchmark"`，不是失败。 |
| pandas 告警 | CI 3 warnings 含 minute `:305` `copy=False` Pandas4Warning，在 **未改** 的 minute 函数体内，非本轮引入。 |
| 宿主对照 | 重构前后一窗 trades.csv 逐字节对照未做（plan §6 可选、非合入门）。 |

---

## 建议动作（是否可合）

**可以合入 master。** 不要为 nit-1 重开切片或阻塞 PR。合入后若顺手：

1. 删 `csv_common.py` 末尾 `_limit_prices` 别名与「Re-exported…」注释（nit-1）。
2. 可选：plan §5 完成定义计数改成 41→10 / →6；handoff 权威对象改 v1.2。
3. 不要在本 PR 顺手清 daily 死 import（会扩大 N-R2 半径）。
4. 宿主若要加保险，合入后另跑一窗 daily+minute `trades.csv` 对照（非门禁）。

本核 **未 merge、未改引擎业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin master feat/np3-engine-layering
git merge-base origin/master origin/feat/np3-engine-layering
# AST/原文同一、import 图、minute→daily 计数、BOM/NUL：本核 python3 脚本（对照 origin/master 与 HEAD）
gh pr view 78 --json … statusCheckRollup
gh run view 35058768602   # 578 passed, 5 skipped, 24 deselected
```

本沙箱无 `vanna312` / 无 pytest 依赖，**未**复跑 `python -m pytest -q tests/`；pytest 证据以 CI `python-tests` SUCCESS 为准。

> **合入前处理（2026-09-16）**：nit-1 已删 `csv_common._limit_prices` 别名与误导注释；本评审文件随 PR 合入。
