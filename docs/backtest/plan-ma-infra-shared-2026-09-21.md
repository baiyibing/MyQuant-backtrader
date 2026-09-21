# Plan: 共享均线基础设施 ma_infra（2026-09-21）

> **Status**: **v0.1 · draft（未评审、未人裁，GO 前禁编码）**。风险档：**低**——纯函数模块 + 一处行为零变更重构；无引擎/数据路径改动。
> **业务源**：用户 2026-09-21 指示「几个策略都需要 MA，作为基础设施，不要分别实现」。消费方：策略 4（SMA5/10 闸，现存）、[strategy12](plan-strategy12-jinrongyuan-2026-09-21.md)（MA5/10 减仓买回，起草中）、[version11 ma_chip](plan-version11-machip-csv-2026-09-21.md)（MA20/60 + 20 周线 + 布林中轨，起草中）。
> **Main ship / 单行范围**：新建 `backtest/research/ma_infra.py` 作为全仓均线 SSOT（asof 标量 / 序列 / 盘中实时 / 布林 / 周线换算），策略 4 迁移为 re-export（行为零变更），后续书一律消费本模块。
> **前序**：[workflow-codex-handoff.md](workflow-codex-handoff.md)。

---

## 0) One-line scope

一个纯函数模块收敛全部均线口径；strategy4 的 `sma_asof` 成为种子 API；strategy12 / version11 plan 的切片改为引用本模块，不再各自实现。

## 1) 现状盘点（HEAD `40f660d`）

| 能力 | 现存实现 | 位置 |
|---|---|---|
| 日线 SMA（asof 标量） | `sma_asof(closes, n)`——全仓唯一 MA 实现 | `backtest/research/strategy4_rules.py:23-27` |
| 周线换算 | `_daily_to_weekly`（W-FRI + `_last_day=max`，私有） | `oskh_factors/weekly_macd_divergence.py` |
| 布林带（SMA20+2σ，ddof=1） | **无存活实现**（随 Cerebro 退场删除；口径锁在归档 ma_chip plan §2） | 归档 plan 转录 |
| 盘中实时 MA（n−1 昨收 + 现价） | **无**（strategy12 P2-B 需要） | — |
| 批量序列 MA（导出器用） | **无**（version11 池导出需要全市场 MA20/60） | — |

## 2) API 面（草案，P1 人裁）

```python
# backtest/research/ma_infra.py —— 纯函数，无引擎/数据 import；pandas 仅限 *_frame 批量件
sma_asof(closes: Sequence[float], n: int) -> Optional[float]        # 种子：原样采纳 strategy4 版
sma_series(closes: Sequence[float], n: int) -> list[Optional[float]] # 前缀逐点 SMA（导出器/回放）
sma_live(prev_closes_ending_yesterday, px: float, n: int) -> Optional[float]  # 盘中实时 = 截 n-1 + px
bb_asof(closes, n=20, k=2.0) -> Optional[tuple[float, float, float]]  # (mid, upper, lower)，σ ddof=1
daily_to_weekly(dates, closes) -> list[tuple[date, float]]          # W-FRI + last_day=max（移植副本）
weekly_sma_asof(dates, closes, n) -> Optional[float]                 # 周线 asof，只 backward
```

## 3) R\* hard locks

| ID | 硬锁 |
|---|---|
| **R1** | 策略 4 行为零变更：`strategy4_rules.sma_asof` 改为从 `ma_infra` re-export（冗余别名消 F401），既有全量 pytest 不放宽全绿。 |
| **R2** | 模块纯函数：不 import 引擎/湖/resolver；标量件零第三方依赖；`*_frame` 批量件可 import pandas 且不得被 simulate 热路径 import（import fence 现状不动）。 |
| **R3** | 不改 `oskh_factors` 公共 API：周线换算以**移植副本**进本模块（出处注释指向 `weekly_macd_divergence._daily_to_weekly`），两处并存；合并回 oskh_factors 另开非目标。 |
| **R4** | PIT 纪律：本模块只做数学，序列截止权在调用方——书侧拿到的 `daily_closes_ending_yesterday` 喂 asof/live 件；不自行读湖。 |
| **R5** | 语义 pin：不足 n 根返回 None（非 0 非 NaN）；`sma_live` 输入序列长 ≥ n−1；布林 σ=ddof=1；UTF-8 无 BOM；新文件 ruff 零告警。 |

## 4) P\* 人裁点

| ID | 问题 | 建议 |
|---|---|---|
| **P1 API 面** | §2 六件是否齐套？EMA/WMA 现在要不要？ | 只做消费方要得到的六件；EMA/WMA 等真有消费方再加（YAGNI）。 |
| **P2 批量实现** | `sma_series` 纯 Python 前缀和 vs pandas rolling | 纯 Python 前缀和 O(n)；全市场导出器若慢再补 `*_frame` pandas 件（本刀不做）。 |
| **P3 strategy4 迁移深度** | 只 re-export，还是连 `buy_gate`/`sell_gate` 内调用一并改写？ | 只 re-export + import 改向；gate 逻辑不动（最小 diff，pins 全在）。 |
| **P4 位置** | `backtest/research/ma_infra.py` vs `oskh_factors/` | research——三个消费方两个在 `backtest/research` 书侧；oskh_factors 是因子库，职责不同。 |

## 5) 非目标

- 不改 oskh_factors / turnover_resist；不合并周线副本回源。
- 不做 EMA/WMA/自适应均线；不做分钟级 MA 序列件（`sma_live` 已覆盖盘中语义）。
- 不动 Mode A/B、不动引擎钩子签名。

## 6) 切片（各一 commit）

| 刀 | 内容 | DoD |
|---|---|---|
| **A** | `ma_infra.py` 六件 + `tests/test_ma_infra.py` data-free pin（None 边界 / live 拼接 / ddof=1 数值 / 周线 asof 无未来） | 纯函数；ruff 零告警；单测全绿 |
| **B** | strategy4 迁移：`from ...ma_infra import sma_asof as sma_asof` + 调用点改向；复跑既有 v4 测试 | 全量 pytest 零变更全绿；`git diff` 仅 import 行 |

## 7) 验证命令

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_ma_infra.py tests/test_csv_strategy_books.py
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
D:\anaconda3\envs\vanna312\python.exe -m ruff check backtest/research/ma_infra.py backtest/research/strategy4_rules.py tests/test_ma_infra.py
```

## 8) 代码落点

- 新：`backtest/research/ma_infra.py`、`tests/test_ma_infra.py`
- 改：`backtest/research/strategy4_rules.py`（re-export）
- 下游引用（各自 plan 实施）：strategy12 切片 A、version11 切片 A/B 改为 `from backtest.research.ma_infra import ...`

## 9) 修订程序

v0.x → 评审（`reviews/2026-09-21/plan-ma-infra-shared/`）→ P1–P4 人裁 → vN GO → Codex 交接工作流。**顺序建议：本 plan 最先 GO/实施**（最小、零风险），12/11 实施时直接消费。
