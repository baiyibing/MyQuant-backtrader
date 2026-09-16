# Plan：资金配给显式化 NP1（先测量探针，后可选 `--ration`）

> **落盘**：2026-09-16。**v1.0**。
> **状态**：🚧 **v1.0 · A 实施中（本 PR）**。切片 **A（只读探针）** 为 **L1 / data-free**，与战略分析 NP1(a) 一致，**本 PR 实施 A**（不改引擎、不改默认配给）。切片 **B（`--ration`）须人裁 GO 后方可编码**；A 合入不构成 B 的 GO。
> **风险档**：**L1**（A：事后归因脚本 + pytest 合成 fixture；零业务路径变更）。B 升为中风险（触及 `run_pool_buys_day`），另开或本 plan 修订后 GO。
> **业务源**：[strategic-analysis-opus5-next-2026-09-16.md](strategic-analysis-opus5-next-2026-09-16.md) §6 NP1 / §5 D1；宿主证据 [money-modes-v8-pername-smoke-2026-09-16.md](money-modes-v8-pername-smoke-2026-09-16.md)（5,064 名次 → 271 成交；宽度>21 天 104/215 = 48%）。
> **工作流**：走 [Codex 交接工作流](workflow-codex-handoff.md)。**本 plan 对 B 保留「GO 前禁编码」**；对 A 按战略分析「(a) 零风险、建议先单独成片」与人指令「A 明确 L1 可读即可同 PR」执行。
> **成交核现锁**：[engine-ashare-correctness.md](engine-ashare-correctness.md)（E-R1–E-R4，本轮不动）。名单契约 [pool-csv-contract.md](pool-csv-contract.md) 不动（B 合入时各补一行，不在 A）。
> **基线 tip**：`5d34603`（`origin/master`，含战略分析 #68）。

---

## 0. 一句话

把「名单行序 = 先到先得」从**隐式策略**变成**可测量事实**（A），再在人裁后才加可选 `--ration`（B，默认 `file_order` 字节不变）。A 只读 `trades.csv` + `--pool-dir`，**不改 6/8 卖点、不改默认配给、不做优化器**。

```text
Slice A（本 PR）：report_capital_ration — 按日「宽度 / 获配 / 未获配位次」
Slice B（人裁 GO 后）：--ration {file_order,seeded_shuffle,...}；默认 file_order = 现行行为
```

---

## 1. 问题锚点（禁止重做已落地项）

| 事实 | 锚点 |
|------|------|
| 池买按 `planned` **文件序**遍历，现金不足 `skip_cash` | [csv_simulate_loop.py:155-197](../../backtest/research/csv_simulate_loop.py)（`for code in planned` :159；per_name 现金拒 :185-191） |
| 现实 `stock_pool/` 多为代码升序 → 行序 ≈ 代码序 | [pool-csv-contract.md](pool-csv-contract.md)；money-modes M-R2 / P4 |
| D 烟测：名次 5,064 → 成交 271；宽日 48% | [money-modes-v8-pername-smoke-2026-09-16.md:85,105](money-modes-v8-pername-smoke-2026-09-16.md) |
| 行业对照：Qlib `TopkDropoutStrategy` = 显式排名+淘汰 | 战略分析 §2.2；**本仓仅作分层镜子，不引入 Qlib 策略、不接 PortAna** |
| sizing 双模式已落地（`daily_quota` / `per_name`） | money-modes plan / PR #61；本 plan **不重做 sizing** |

---

## 2. 现锁（R-\* / 硬边界）

| # | 规则 |
|---|------|
| **R-1** | **不改 6/8/9/10 卖点语义**（含 trail / stop / defer / band）。A/B 均禁止动卖环。 |
| **R-2** | **A 不改默认配给行为**：零引擎 diff；不碰 `csv_simulate_loop.py` / `csv_ledger.py` / 策略书。 |
| **R-3** | **B 默认必须 `file_order` 且与现行行为 byte-identical**（`tests/test_csv_strategy_books.py` golden 仍绿）。非默认策略仅供 A/B 量化，**不用结果给策略定胜负**。 |
| **R-4** | **不做优化器 / 不做选股**：配给 ≠ TopK 选股；禁止把探针做成调参器。 |
| **R-5** | **Qlib TopkDropout 仅文档层对照**，不 import Qlib、不复刻 dropout 逻辑进引擎。 |
| **R-6** | **不实施 NP2（除权）/ NP3（分层倒置）/ NP4 / NP5**；不碰复权链、`dividend_type`、CloudAgent。 |
| **R-7** | A 探针 **data-free**：合成 fixture + 可选宿主工件路径；**不进 CI 湖门禁**；数字产物不入库。 |
| **R-8** | 探针口径声明：事后「名单有、当日无 `reason=pool` 的 BUY」= **未获配（广义）**，含 `skip_cash` / `skip_held` / `skip_no_bar` / gate / 涨停追买排队等；**不声称等于引擎 `skip_cash` 计数**。位次分布用于观测文件序偏好；与 summary 的 `skip_cash` 对照属宿主解读，非 CI 断言。 |

**人裁点**

| # | 问题 | 默认 / 状态 |
|---|------|-------------|
| **P1** | 是否在 A 结果出来前批准 B（`--ration`）？ | **默认否**。A 合入后据宿主归因短记再裁；**B 编码前须显式 GO**。 |
| **P2** | B 若 GO，首版枚举是否仅 `file_order` + `seeded_shuffle`？ | **建议是**（战略分析原文）；GO 时确认，禁止顺手加 score/optimizer。 |
| **P3** | 追买（`reason` 以 `chase` 开头）是否计入「获配」？ | **A 默认：主表只计 `reason=pool`；追买单独列 `chase_buys` 观测，不并入挤出分母**（追买日 ≠ 名单日）。 |

---

## 3. 非目标

| 不做 | 原因 |
|------|------|
| 实现 `--ration` / 改 `run_pool_buys_day` 序 | B，待 P1 GO |
| 改默认 sizing、加 `--sizing` 全局开关 | money-modes M-R1 已锁 |
| 改 6/8 卖点、成交核、佣金、整百股 | R-1 / E-R\* |
| 复权 / 除权探针（NP2） | R-6；另开 |
| 用 A/B NAV 给策略排名 | R-3 / R-4 |
| 接 run-manifest / 湖写 | 本仓只读 |
| 合并日线↔分钟卖环 | 战略分析禁区 |

---

## 4. 切片

从 **当时 master**（`5d34603+`）开 `feat/capital-ration-np1a`。

| 切片 | 做什么 | 完成定义 | GO |
|------|--------|----------|-----|
| **A · 只读归因探针** | 库 + CLI：吃 `trades.csv` + `--pool-dir`；按日输出宽度 / 获配名数 / 未获配名次（文件序 0-based）/ 未获配位次直方图；全窗汇总（名次合计、获配合计、宽日阈值可选）；data-free pytest + 合成 pool+trades fixture；plan/README 短用法 | pytest 绿；NUL=0；引擎与策略书 **零 diff**；CLI `--help` 可跑 | **本 PR 直接做**（L1） |
| **B · 可选 `--ration`**（后置） | CLI `--ration {file_order,seeded_shuffle}`（或 GO 裁定枚举）；`file_order` 默认；seeded 仅研究；HELP_LOCK / pool-csv-contract / engine-ashare 各一行；golden byte-identical | `file_order` 下 strategy_books golden 绿；宿主 A/B 短记**不进 CI** | **须人裁 GO（P1）** |

---

## 5. 验收（对照战略分析 NP1）

| 项 | 标准 |
|----|------|
| A | data-free pytest + 一份合成 fixture；输出含「名单宽度 / 获配名数 / 被挤出名次 / 位次分布」 |
| B（GO 后） | `--ration file_order` 下 byte-identical golden；宿主 A/B 另附短记不进 CI；契约文档补一行 |
| 硬锁 | 不改 6/8 卖；A 不改默认配给；无优化器；Qlib 仅镜子 |

---

## 6. 验证命令

```bash
# A（本机 / CI data-free）
/workspace/vanna312/bin/python -m pytest -q tests/test_capital_ration_probe.py
/workspace/vanna312/bin/python scripts/research/report_capital_ration.py \
  --trades path/to/trades.csv --pool-dir path/to/pool [--format text|json|markdown]

# 回归（确认引擎未碰）：
/workspace/vanna312/bin/python -m pytest -q tests/test_csv_strategy_books.py tests/test_report_pool_list_quality.py

# B（仅 GO 后；示意）
# ... --ration file_order  → golden 绿
# 宿主 A/B 短记不入库 CI
```

---

## 7. 代码落点（A）

| 文件 | 动作 |
|------|------|
| `backtest/research/capital_ration_probe.py` | 库：加载 trades / pool；按日归因；格式化 text/json/markdown；`main()` |
| `scripts/research/report_capital_ration.py` | 薄 CLI（同 `report_pool_list_quality.py` 模式） |
| `tests/test_capital_ration_probe.py` | tmp_path 合成 fixture（多日宽名单 + 部分 pool BUY + 一笔 chase） |
| `docs/backtest/plan-capital-ration-2026-09-16.md` | 本文件 |
| `docs/backtest/README.md` | SSOT 表或工具段加一行指针（可选短节） |
| `docs/backtest/pool-csv-contract.md` | **A 不改**；B GO 后补「配给序」一行 |

禁止改（A）：`csv_simulate_loop.py`、`csv_ledger.py`、`csv_*_backtest.py`、策略书、卖点规则、fixtures golden。

---

## 8. 风险

- A 广义「未获配」≠ `skip_cash`（R-8）——文档与 CLI 文案必须写清，避免宿主误读成现金拒单精确数。
- 代码列口径：pool 经 `parse_pool_csv` → canonical；trades `code` 已是点分；比较前统一。
- 日期列：trades `date` 可能为 `YYYYMMDD` 或带分隔；探针归一为 `YYYYMMDD`。
- B 若抢跑：违反本 plan GO 门与战略分析「默认 byte-identical」——实施者遇分叉停问人。

---

## 9. 修订程序

改 R-\* 须改本文并升版本。P1 GO 后把状态改为「✅ B 已人裁 GO（hash）」再开 B 实施或同 plan 续片。A 合入后头部改为「✅ A 已实施（PR #N）」；B 仍为待 GO。

## 10. Changelog

- **v1.0**（2026-09-16）：初稿。切片 A=只读探针（本 PR）；B=`--ration` 后人裁。硬锁 R-1…R-8；Qlib TopkDropout 仅分层镜子。

---

## 11. 实施记录（随 PR 回写）

| 切片 | 状态 | commit | 备注 |
|------|------|--------|------|
| A · 只读归因探针 | ✅ 本 PR | `592d40c` | data-free 探针 + 测试；引擎零 diff；B 仍待 GO |
| B · `--ration` | ⏸ 待人裁 GO（P1） | — | 默认 file_order；勿抢跑 |
