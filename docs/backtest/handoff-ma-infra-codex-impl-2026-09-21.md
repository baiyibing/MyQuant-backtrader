# Handoff：ma_infra 共享均线基础设施 → Codex 无头实施（2026-09-21）

- **日期**：2026-09-21（Asia/Shanghai）
- **Plan**：[plan-ma-infra-shared-2026-09-21.md](plan-ma-infra-shared-2026-09-21.md) **v1.0 已人裁 GO**（merge commit `029b24c`；P1–P4 全按共识裁定）
- **评审链**：四稿 fan-out（codex/kimi/cursor/claude，全 rc=0）→ [merge-consensus C1–C12](../architecture/reviews/2026-09-21/plan-ma-infra-shared/merge-consensus.md) → 人裁 GO（对抗层按 runbook §A「可不启用」跳过——低风险纯函数）
- **实施基线**：`feat/ma-infra` 分支自 master `029b24c` 切出

## §0 硬边界（人裁已定，勿越）

1. **改动面仅三处**：新增 `backtest/research/ma_infra.py`、新增 `tests/test_ma_infra.py`、修改 `backtest/research/strategy4_rules.py`（删 def + import）。**零引擎 diff、零 BOOKS 注册表 diff。**
2. **`sma_asof` 原样搬家**（`strategy4_rules.py:23-27`）：NaN 传播（非 None）、`n<=0`→None、`int(n)` 截断——**禁止任何"清理"**（C4）。
3. **σ = ddof=1**：测试数值 pin `std([1,2,3,4,5]) == 1.5811388300841898`。**禁止**采用 `oskh_factors/price_bb.py:16`（ddof=0）、`scripts/data/full_market_chip_resist.py:49`（ddof=0）、`oskh_factors/chip/bands.py`（ddof=1 但 round4 舍入——禁止套用到收盘价布林）。
4. **周线三条**（`daily_to_weekly` 纯 py 重写 W-FRI 分桶）：返回 `date = _last_day`（该周**最后交易日**，非 pandas W-FRI Friday 标签）；末端未完成周**保留**（`_last_day ≤ D` 可参与）；停牌空周无行。
5. **标准库零依赖**：`ma_infra.py` 不得 `import pandas` / `numpy`（测试文件内联 pandas 做差分 pin 不受限）。
6. **不动 `oskh_factors`**：`_daily_to_weekly` 保持私有、`weekly_macd_divergence.py:183` 的 MA200 不迁不删。
7. **不做**：EMA/WMA/自适应均线；`*_frame` pandas 批量子模块；AST pin 测试（留给将来 `*_frame` 落地时）。
8. `sma_live` 取**尾部** n−1 根 + px（非前缀）；`len(prev) < n−1` 或 `px <= 0` → None。
9. 复权域 100% 在调用方（R4/consensus C5）：模块零复权、零证券代码。

## 切片 A：ma_infra 八件 + data-free 测试

**代码事实锚点（HEAD `029b24c`）**
- 种子：`backtest/research/strategy4_rules.py:23-27`（`sma_asof`，行为见 §0.2）
- 周线参照（只读、差分对照）：`oskh_factors/weekly_macd_divergence.py:86-104`（`W-FRI` resample、`close:"last"`、`_last_day:"max"`、末尾 `dropna()`；`WEEK_RULE` 见 `:47`）

**实施步骤**
1. 新建 `backtest/research/ma_infra.py`，按 plan §2 v0.2 的八件签名逐字实现：
   - `sma_asof` / `sma_series`（前缀和 O(n)，等长输出，前 n−1 位 None）
   - `sma_live`（§0.8）
   - `bb_series` / `bb_asof`（增量 `s1=Σc, s2=Σc² → var=(s2−s1²/n)/(n−1)`，`n<2` 整列 None，`*_asof` = 序列件 `[-1]`）
   - `daily_to_weekly`（纯 py W-FRI 分桶：周六开新桶、跨年周归 W-FRI 年、`_last_day=max`、NaN 周按参照 `dropna()` 语义丢弃）
   - `weekly_sma_series`（一次换算 + 周窗滚动 + 逐日对齐回填）/ `weekly_sma_asof`
2. 新建 `tests/test_ma_infra.py`。

**语义要点（评审实证，勿推翻）**
- 标量/批量同口径靠 `*_asof = 序列件[-1]` 薄封装保证，不写两份算法。
- 差分 pin：合成样本含**节假短周**（周五休市）、**停牌空周**（整周无 bar）、**跨年周**，断言 `daily_to_weekly` 与 pandas `_daily_to_weekly` 参照逐值相等（测试内 `import pandas`）；断言 W-FRI 标签 ≠ `_last_day` 的样本存在（防实现者抄成标签）。
- 数值 pin：σ 数值（§0.3）、`sma_series` vs `sma_asof` 逐点 `pytest.approx`（FP 漂移 ~1e-12）、`sma_live` 例 `prev=[1,2,3,4], px=10, n=3 → (3+4+10)/3`。
- 边界 pin：`sma_asof([1,nan,3],3)` → nan（**不是 None**）；`n<=0`→None；`bb_series(n=1)` → 整列 None（不 ZeroDivision）。

**测试清单（新增）**：上述差分/数值/边界/等长/尾部拼接/周线三条 各至少 1 条。

## 切片 B：strategy4 迁移（零行为变更）

**代码事实锚点（HEAD `029b24c`）**
- 被迁函数：`backtest/research/strategy4_rules.py:23-27`
- 唯一外部消费形态：`backtest/research/csv_strategy_books.py:483-484` 按**模块属性**访问 `strategy4_rules.buy_gate/sell_gate`（不直接 import `sma_asof`）
- 直接 pin：`tests/test_strategy4_rules.py:4-6`（`rules.sma_asof`）；三层下游 pin：`tests/test_csv_daily_backtest.py:180/:190`、`tests/test_csv_strategy_books.py:107`

**实施步骤**
1. `strategy4_rules.py`：删除本地 `def sma_asof`（4 行），顶部加 `from backtest.research.ma_infra import sma_asof`（gate 函数体内继续调本地名 `sma_asof`——有调用即不触发 F401，**无需冗余别名**）。
2. `buy_gate`/`sell_gate` 函数体**零 diff**。

**DoD**：`git diff master...feat/ma-infra -- backtest/research/strategy4_rules.py` 仅 import 行 + 删 4 行 def；既有三层 pin 零变更全绿。

## 门禁清单（实施完成前全过）

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_ma_infra.py tests/test_strategy4_rules.py tests/test_csv_strategy_books.py
D:\anaconda3\envs\vanna312\python.exe -m pytest -q -m "not production and not benchmark" tests/
D:\anaconda3\envs\vanna312\python.exe -m ruff check backtest/research/ma_infra.py backtest/research/strategy4_rules.py tests/test_ma_infra.py
# 文本门：UTF-8 无 BOM，NUL 计数 0
```

## 回写要求

- 完成后：plan 头部改「✅ 已实施（PR #N）」；本文件标完成；宿主复核 diff（缺陷优先）后开 PR。
- 遇 plan 未覆盖的语义分叉（尤其周线分桶边界、NaN 周）：**停下来问人，不自裁**。
