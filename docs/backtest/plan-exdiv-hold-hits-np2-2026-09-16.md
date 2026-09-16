# Plan：除权持仓命中只读计数 NP2（主源 ex_date_index → 人裁 E-R5 / 复权片）

> **落盘**：2026-09-16（Asia/Shanghai）。**v1.0**。
> **状态**：🚧 **implementing read-only count（切片 A）** → 宿主跑数（切片 B）→ **人裁** E-R5 vs 新复权 plan（**非自动**）。
> **风险档**：**L1**（A：事后归因脚本 + data-free pytest；零成交核 / 零 `dividend_type` / 零 golden 变更）。
> **业务源**：survey [survey-exdiv-adj-data-prep-2026-09-16.md](survey-exdiv-adj-data-prep-2026-09-16.md) §0–§3 **GO + 三条设计锁**；引子 [handoff-exdiv-adj-data-prep-intro-2026-09-16.md](handoff-exdiv-adj-data-prep-intro-2026-09-16.md) §7；战略 [strategic-analysis-opus5-next-2026-09-16.md](strategic-analysis-opus5-next-2026-09-16.md) §6 NP2；D 烟测工件提示 [money-modes-v8-pername-smoke-2026-09-16.md](money-modes-v8-pername-smoke-2026-09-16.md)。
> **工作流**：Codex / 本机 agent；**No CloudAgent**。与 NP1（配给）/ 费率严格分离。
> **成交核现锁**：[engine-ashare-correctness.md](engine-ashare-correctness.md)（E-R1–E-R4，本轮不动；E-R5 仅人裁后另写）。
> **基线 tip**：`578cb80`（`origin/master`，survey PR #71 合入后）。

---

## 0. 一句话

用 **`ex_date_index.parquet` 作主源**，在 D 烟测同窗对已落盘 `trades.csv` 做**只读**「持仓区间 ∩ 除权日」计数（含可疑卖因分桶与样例行）；**因子跳变仅副证**。数字出来后由**人**裁：影响可忽略 → E-R5；显著 → **另开**复权实施 plan。**本片不实现复权、不改引擎。**

```text
Slice A（本 PR）：exdiv_hold_hits 库 + CLI + data-free pytest + 宿主 runbook
Slice B（宿主）：对着 F 湖 + D 烟测 trades 跑数 → 结果短记（VM 无湖则 stub）
Adjudication：HUMAN cut after numbers（E-R5 vs 复权 plan）— never auto
```

---

## 1. 设计锁（Hard locks · 必须写进代码注释）

源自 survey §3：

| # | 锁 | 含义 |
|---|----|------|
| **L1** | **主源 = `ex_date_index.parquet`**（QMT detect 产物） | `cumulative_adj_factor` 日际跳变（ε=**5e-3**）= **parity 副证 only**，禁止当主枚举器（现金分红 ≤0.5% 淹没在舍入噪声） |
| **L2** | 窗 = **20251023–20260909**；命中 = **持仓区间 ∩ ex_date** | 仅 **D+1 起仍持仓** 的 lot（买入日当日不评卖 — 对齐 T+1）：`entry < ex_date ≤ exit`（未平仓 lot 的 exit 取 `--end`） |
| **L3** | 输出三件套 | ① 持仓期除权命中计数；② 其中卖因 ∈ `stop_loss:gap_open` / `defer_sell_limit_down` / band-trail（`trail:band:*`）的笔数；③ 对应 `trades.csv` 行样例。工件提示：`backtest_output/csv_daily_v8_20251023_20260909/` |

**附加约束（survey / 引子）**

| # | 规则 |
|---|------|
| **R-1** | **不改** `csv_daily_backtest.py` / `csv_minute_backtest.py` 的 `dividend_type`、limit/stop/peak、golden fixtures、GPU。 |
| **R-2** | NP2 **不与** NP1（配给）/ COMMISSION 打包。 |
| **R-3** | 幅度先验（survey §3）：>5% 送转段为假止损主嫌疑；≤0.5% 大概率可归 E-R5——**仅供人裁写稿**，脚本不自动裁决。 |
| **R-4** | G2：无 front / 因子 NaN 码在 **parity 路径**跳过并记数。G4：ex index vs adj 码集差记 note。 |
| **R-5** | **裁决是人裁**：数字落地后才写 E-R5 或新复权 plan；禁止脚本/CI 自动落锁。 |
| **R-6** | `defer_sell_limit_down` 主要是引擎 **summary 计数器**，极少作为 `trades.csv` 的 `reason`；探针仍按 reason 字面分桶，并在报告 note 中声明可能为 0。 |

---

## 2. 非目标

| 不做 | 原因 |
|------|------|
| 改 `dividend_type` / cost / peak / 涨跌停锚 | 复权实施片；会改写全部 NAV + golden |
| 重算 `tests/fixtures/csv_engine_pre_er1/` | R-1 |
| 探针进 CI 湖门禁 | 需稳定 F 湖 |
| 自动写 E-R5 或自动开复权 | R-5 人裁 |
| 资本配给 B（`--ration`） | 另枝；本片禁碰 |

---

## 3. 切片

从 **`578cb80`** 开 `feat/exdiv-hold-hits-np2`。

| 切片 | 做什么 | 完成定义 | GO |
|------|--------|----------|-----|
| **A · 工具 + data-free 测** | `backtest/research/exdiv_hold_hits.py` + `scripts/research/report_exdiv_hold_hits.py`；合成 trades + tiny ex_date_index（parquet/csv）；plan + README 指针 | pytest 绿；引擎/fixture **零 diff**；CLI `--help` | **本 PR 直接做** |
| **B · 宿主测量短记** | 宿主对 `F:\stock_data\ex_date_index.parquet` + D 烟测 `trades.csv` 跑 CLI；写 dated 结果（含样例行） | 真实命中数字；**不发明** | VM 无湖 → **runbook-only**，结果节 **awaiting host run** |
| **裁决（后置）** | 人读 B 数字 + survey 幅度先验 → E-R5 **或** 新复权 plan | 正确性文档 / 新 plan | **须人裁**；A/B 合入≠裁决 |

---

## 4. 验收（对照引子 §7 / 战略 NP2）

| 项 | 标准 |
|----|------|
| A | data-free pytest：T+1 排除买入日命中；FIFO lot 重入；卖因分桶；可选 adj parity |
| B | 宿主结果文档含窗、口径、①②③；或 runbook stub 明确 awaiting |
| 硬锁 | 主源 ex_date_index；副证 ε=5e-3；不改引擎；裁决非自动 |

---

## 5. 验证命令

```bash
# A（本机 / CI data-free）
/workspace/vanna312/bin/python -m pytest -q tests/test_exdiv_hold_hits.py
/workspace/vanna312/bin/python scripts/research/report_exdiv_hold_hits.py --help

# B（宿主 Windows；路径见 runbook）
D:\anaconda3\envs\vanna312\python.exe scripts\research\report_exdiv_hold_hits.py ^
  --trades backtest_output\csv_daily_v8_20251023_20260909\trades.csv ^
  --ex-date-index F:\stock_data\ex_date_index.parquet ^
  --adj-factor F:\stock_data\adj_factor.parquet ^
  --start 20251023 --end 20260909 --format markdown
```

---

## 6. 指针

| 文档 | 用途 |
|------|------|
| [exdiv-hold-hits-np2-host-runbook-2026-09-16.md](exdiv-hold-hits-np2-host-runbook-2026-09-16.md) | 宿主 CLI + 结果 stub |
| [survey-exdiv-adj-data-prep-2026-09-16.md](survey-exdiv-adj-data-prep-2026-09-16.md) | GO + 三锁 + 幅度先验 |
| [engine-ashare-correctness.md](engine-ashare-correctness.md) | 未来 E-R5 落点 |
