# Plan: 共享均线基础设施 ma_infra（2026-09-21）

> **Status**: **v0.2 · draft（已吸收四稿外部评审 merge-consensus；P1–P4 待人裁，GO 前禁编码）**。风险档：**刀 A 中**（周线 asof 键与布林 σ 直接构成 version11 买卖条件）；**刀 B 低**（零行为重构）。共识裁决：[merge-consensus](../architecture/reviews/2026-09-21/plan-ma-infra-shared/merge-consensus.md)（codex/kimi/cursor/claude 四稿收敛 C1–C12）。
> **业务源**：用户 2026-09-21 指示「几个策略都需要 MA，作为基础设施，不要分别实现」。消费方：策略 4（SMA5/10 闸，现存）、[strategy12](plan-strategy12-jinrongyuan-2026-09-21.md)（MA5/10 减仓买回，起草中）、[version11 ma_chip](plan-version11-machip-csv-2026-09-21.md)（MA20/60 + 20 周线 + 布林中轨，起草中）。
> **Main ship / 单行范围**：新建 `backtest/research/ma_infra.py` 作为全仓均线 SSOT（asof 标量 / 序列 / 盘中实时 / 布林 / 周线换算），策略 4 迁移为 re-export（行为零变更），后续书一律消费本模块。
> **前序**：[workflow-codex-handoff.md](workflow-codex-handoff.md)。

---

## 0) One-line scope

一个纯函数模块收敛全部均线口径；strategy4 的 `sma_asof` 成为种子 API；strategy12 / version11 plan 的切片改为引用本模块，不再各自实现。

## 1) 现状盘点（回填时点 HEAD `0d28ef2`；共识 C1 修正）

| 能力 | 现存实现 | 位置与口径 |
|---|---|---|
| 日线 SMA（asof 标量） | `sma_asof(closes, n)`——**书侧消费路径上唯一通用 asof 纯函数** | `backtest/research/strategy4_rules.py:23-27`；现状 **NaN 传播非 None**、`n<=0`→None、`int(n)` 截断——原样搬家不改语义（C4） |
| 周线换算 | `_daily_to_weekly`（W-FRI + `_last_day=max`，私有） | `oskh_factors/weekly_macd_divergence.py:86-104`；另有存活周线 MA200（`:183`）与上证 MA10 手写（`strategy7_rules.py:171-173`）——**不迁不删** |
| 布林带 | **已知存活件（故意不采用）**：`oskh_factors/price_bb.py:11`（`np.std` **ddof=0**，只回 position）；`scripts/data/full_market_canonical_resist.py:246-255`（rolling **ddof=1** 但 `<20` 根回退全序列）；`scripts/data/full_market_chip_resist.py:49`（**ddof=0**）；`oskh_factors/chip/bands.py:27-49`（ddof=1 但 **round4 舍入**会改边缘） | σ 口径仓内**实际分裂**；本 plan 锁 **ddof=1**（归档 + pandas + Rust TR 同源），数值 pin `std([1..5])=1.5811388300841898`（C12） |
| 盘中实时 MA（尾部 n−1 + 现价） | **无**（strategy12 P2-B 需要；P2-B 未裁前为预留件） | — |
| 批量序列件 | **无**（version11 全市场导出必需；逐日 asof 标量实测 682s–505min 不可行，C3） | — |

**SSOT 边界声明**：本模块收敛范围 = 书侧/研究侧 asof 口径；chip/TR 面的 ddof=0 件不在本刀收敛范围，两套并存、用途隔离、测试 pin 差异防"改齐"。

## 2) API 面（v0.2 按共识 C2/C3 扩件）

```python
# backtest/research/ma_infra.py —— 纯函数，标准库零依赖（含周线；纯 py 实测比 pandas 快 2.3x）
sma_asof(closes, n) -> Optional[float]          # 种子原样：NaN 传播、n<=0->None、int(n) 截断（C4 保持现状）
sma_series(closes, n) -> list[Optional[float]]  # 与输入等长，前 n-1 位 None；数值比较 pin 用 approx（C4）
sma_live(prev_closes, px, n) -> Optional[float] # 取尾部 n-1 根 + px（非前缀）；len<n-1 或 px<=0 -> None；P2-B 预留
bb_series(closes, n=20, k=2.0) -> list[tuple]   # 逐点 (mid,upper,lower)，σ=ddof=1，n<2 整列 None（不 ZeroDivision）
bb_asof(closes, n=20, k=2.0) -> Optional[tuple] # = bb_series[-1] 薄封装（标量/批量永同口径）
daily_to_weekly(dates, closes) -> list[tuple[date, float]]  # 纯 py 重写 W-FRI 分桶；date=_last_day（周最后交易日，
                                                                #  非 Friday 标签）；末端未完成周保留；停牌空周无行（C2）
weekly_sma_series(dates, closes, n_weeks) -> list[Optional[float]]  # 一次换算+周窗滚动+逐日对齐回填（C3）
weekly_sma_asof(dates, closes, n_weeks) -> Optional[float]          # 只 backward 到 D（调用方先截 ≤D）
```

`*_asof` 一律是序列件 `[-1]` 薄封装。差分 pin：`daily_to_weekly` vs `_daily_to_weekly` 在含节假短周/空周/跨年样本逐值相等（测试内联 pandas 不违反 R2）；冲突时以差分测试裁判（C10）。

## 3) R\* hard locks

| ID | 硬锁 |
|---|---|
| **R1** | 策略 4 行为零变更：`strategy4_rules.sma_asof` 改为从 `ma_infra` re-export（冗余别名消 F401），既有全量 pytest 不放宽全绿。 |
| **R2** | 模块纯函数、标准库零依赖（fence 实际不禁 pandas——固定 15 模块清单只禁 qlib/lebs/trade_fee_policy/fill_clock，`test_ashare_simulate_import_fence.py:39-57`；C7）。将来若做 `*_frame` pandas 批量件：独立子模块 + 函数内 import + AST pin，不扩 fence。 |
| **R3** | 不改 `oskh_factors` 公共 API：周线换算以**纯 py 重写副本**进本模块（出处注释指向 `weekly_macd_divergence._daily_to_weekly` + 差分 pin 防漂移，C10），两处并存；`_daily_to_weekly` 保持私有、MA200 不迁不删；合并回 oskh_factors 另开非目标。 |
| **R4** | PIT + 复权域：只做数学，序列截止权与**价格域 100% 在调用方**——书侧喂 ending-yesterday 原始 closes（E-R5 锁 v4 除权日不换域，**禁止为统一口径把 v4 改前复权**）；version11 导出器自行传 front 序列（C5）。 |
| **R5** | 语义 pin（C4/C12）：`sma_asof` 原样搬家（NaN 传播、n<=0→None、int 截断）；`sma_series` 等长 + 前 n−1 位 None + approx；`sma_live` 尾部 n−1 + px、len<n−1 或 px≤0 → None；`bb_series` n<2 整列 None（不 ZeroDivision）；σ=ddof=1 数值 pin `std([1..5])=1.5811388300841898`；UTF-8 无 BOM；新文件 ruff 零告警。 |

## 4) P\* 人裁点

| ID | 问题 | 建议 |
|---|---|---|
| **P1 API 面** | §2 八件是否齐套？EMA/WMA 现在要不要？ | 八件（含 C3 序列件）；`sma_live` 为 strategy12 P2-B **预留**（P2-B 未裁前无消费方，人裁顺序先裁 strategy12 P2，C11）；EMA/WMA 有消费方再加（YAGNI）。 |
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
| **A** | `ma_infra.py` 八件（+`bb_series`/`weekly_sma_series`，C3）+ `tests/test_ma_infra.py` data-free pin（None/NaN 边界 / live 尾部拼接 / 等长序列 / ddof=1 数值 / 周线 `date=_last_day` 三条 / **vs `_daily_to_weekly` 差分 pin**） | 纯函数标准库；ruff 零告警；单测全绿 |
| **B** | strategy4 迁移：**删本地 def + `from backtest.research.ma_infra import sma_asof`**（gate 内继续调本地名，无需冗余别名）；gate 函数体零 diff（C6——全仓按模块属性消费，零调用点需改） | 既有 v4 三层 pin 零变更全绿；`git diff` = import 行 + 删 4 行 def |

## 7) 验证命令

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_ma_infra.py tests/test_strategy4_rules.py tests/test_csv_strategy_books.py
D:\anaconda3\envs\vanna312\python.exe -m pytest -q -m "not production and not benchmark" tests/   # CI 口径（C8）
D:\anaconda3\envs\vanna312\python.exe -m ruff check backtest/research/ma_infra.py backtest/research/strategy4_rules.py tests/test_ma_infra.py
```

## 8) 代码落点

- 新：`backtest/research/ma_infra.py`、`tests/test_ma_infra.py`
- 改：`backtest/research/strategy4_rules.py`（re-export）
- 下游引用（各自 plan 实施）：strategy12 切片 A、version11 切片 A/B 改为 `from backtest.research.ma_infra import ...`

## 9) 修订程序

v0.x → 评审（`reviews/2026-09-21/plan-ma-infra-shared/`）→ P1–P4 人裁 → vN GO → Codex 交接工作流。**顺序建议：本 plan 最先 GO/实施**（最小、零风险），12/11 实施时直接消费。
