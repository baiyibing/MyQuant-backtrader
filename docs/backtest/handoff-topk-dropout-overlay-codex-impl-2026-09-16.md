# 交接 · TopkDropout 叠层 实施（Codex 接手）

> 日期：2026-09-16  
> 状态：**待 Codex 实施**。plan v1.0 **已人裁 GO**（P-1～P-6 全 GO；任务书钉 `cd62124`）。  
> 权威 plan：[plan-topk-dropout-overlay-2026-09-16.md](plan-topk-dropout-overlay-2026-09-16.md)  
> 同源（信号厂任务书）：`D:\PycharmProjects\MyQuant\docs\plan-topk-dropout-overlay-2026-09-16.md`  
> 评审：宿主会话裁断，无多路 review 目录。  
> 本仓 tip（写交接时）：`e7fb71f`（`origin/master`）  
> 分支：从当时 master 开 `feat/topk-dropout-overlay`；**BT-A / BT-B / BT-C 各一个 commit**。MQ-A 在 MyQuant 另开同名分支，禁止一个 PR 改两仓。

---

## 0. 硬边界（勿越）

1. **不 import qlib**。算法按 plan §2 用纯函数重写；对照原文只读 `qlib-dev/.../signal_strategy.py:138-231`。
2. **不把 n_drop 写进成交核**（`csv_simulate_loop.py` 的成交/整手/涨跌停逻辑）。允许、且仅允许下面写明的 **default-None 钩子**。
3. **不改** `version6` / `version8` 默认卖点、golden、`--stop-pct` 默认语义。10% 止损只挂在新书上。
4. **禁止**读 `MyQuant/exports/live_pool/*sell.csv` 当多日卖出。禁止「今日池 CSV 没有就清仓」。
5. 池 CSV 契约不变（[pool-csv-contract.md](pool-csv-contract.md)）：文件名=买入日，首列裸六位。
6. 对账禁止 PortAna NAV。`reason` 新前缀：`topk_drop:bottom`；止损沿用 `stop_loss:touch` / `stop_loss:gap_open`。
7. 遇 plan 未覆盖的语义分叉：**停下问人**，不自裁。
8. 每片 commit 后：`D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/` 全绿才进下一片。

---

## 1. 切片 BT-A · 纯淘汰 + 新书 `topk_dropout`

### 代码事实锚点（`e7fb71f`）

| 点 | 位置 | 事实 |
|---|---|---|
| 买环吃全日池文件序 | `backtest/research/csv_simulate_loop.py:158-183` `run_pool_buys_day`：`planned = apply_capital_ration(list(pool_days.get(ds, [])), ...)` | 现行 = 文件里有的都想买；已持 `skip_held` |
| 日线卖环顺序 | `csv_daily_backtest.py:253-326` | 先 pending / **先止损**（276-299）再 `sell_gate` / `take_profit`（311-326） |
| 策略书注册 | `csv_strategy_books.py:41-61` `CsvStrategyBook` + `register`；现书到 `version10`（:654） | 新书必须 `register(...)`，`required=True` 无缺省 |
| `sell_gate` 签名 | `strategy4_rules.py:36`；日线调用 `csv_daily_backtest.py:312` | `sell_gate(code, close, day, closes) -> Optional[str]` |
| `buy_gate` | `csv_simulate_loop.py:204` | 只挡新开，不改 planned 长度 |
| 算法原文 | `D:\PycharmProjects\qlib-dev\qlib\contrib\strategy\signal_strategy.py:199-231` | `today` / `comb` / `sell` / `buy` |

### 实施步骤

1. 新建 `backtest/research/topk_dropout_rules.py`（名字可议，不要 `version11`）：
   - 纯函数 `decide_topk_dropout(held: Sequence[str], scores: Mapping[str, float], *, topk: int, n_drop: int) -> tuple[list[str], list[str]]` → `(buy, sell)`。
   - 严格按 plan §2：`last` 按分降序；缺分记 `score_missing` 且当极低分，**卖出数量仍 ≤ n_drop**；`today` = 未持仓最高 `n_drop+topk-len(last)`；`comb` 排序；`sell = last ∩ comb[-n_drop:]`；`buy = today[:len(sell)+topk-len(last)]`。同分用代码升序打破（与 MyQuant export 的 `score desc, instrument asc` 对齐：实现时 last/today 排序键统一写进 docstring）。
   - **不**在此函数里做涨跌停 / T+1；T+1 由引擎 `n_days >= 1` 保证，`sell_gate` 对 `n_days<1` 不要抢先卖（日线卖环已包在 `if n_days >= 1`）。
2. 新建 `strategy_topk_dropout_rules.py` + 在 `csv_strategy_books.py` `register`：
   - `name="topk_dropout"`，aliases `("topk", "version_topk")`。
   - `allow_add=False`。`take_profit` 对 BT-A 返回 `None`（无 trail）。`stop_pct=None`（BT-C 再打开）。
   - `record_params` 写入 `sell_book=topk_dropout`、`topk`、`n_drop`。
   - `HELP_LOCK` 写明：底座=qlib bottom dropout；不是 v6。
3. **唯一允许的引擎触点**（default-None，旧书行为零 diff）：
   - 在 `run_pool_buys_day` 取 `planned` 之后、遍历之前：若 `hooks`/`kwargs` 带 `planned_for_day(ds, held_codes) -> list[str]`，用其返回值替换 `planned`，再走现有 `apply_capital_ration`。
   - `held_codes` 必须是**当日卖环已经跑完之后**的持仓（`csv_daily_backtest.py` 里 `run_pool_buys_day` 在 :357，卖环在 :253-326）。不要在开盘用「昨收持仓」算 buy 长度。
   - 把该 hook 从 `apply_csv_strategy` `setdefault` 到 `None`；仅 `topk_dropout` 提供实现：内部 `decide_topk_dropout(held, scores[ds])[0]`，BT-B 再滤。
4. `sell_gate`：若 `code` 在 **当日开盘持仓** 上算出的 `decide(...)[1]` 里，返回 `"topk_drop:bottom"`。注意：卖环在买环之前，此时持仓尚未被当日 dropout 卖出；用开盘持仓算 sell 与 qlib「先决定再成交」一致。止损已在同一循环更早上手（:276），被止损掉的代码 `continue` 后不会再进 sell_gate。
5. CLI：`--pred-csv` 或 `--scores-dir`（买入日 `YYYYMMDD.csv`，列裸码+score）。缺分文件则 fail-closed，不要 silently 退回「只买池文件」。
6. 烟测窗可先直接读 MyQuant `预测结果_20260915T131732Z_51dde0bc_50n5.csv`（datetime=预测日）：买入日 T 用 pred[T−1]。

### 语义要点（勿推翻）

- 满仓真前 50 → 当天不换。
- 不是「池里没有就卖」。
- `--pool-dir` 仍要传（契约 / 日历对齐），但**淘汰不以这 50 行为准**，以 scores 为准。

### 测试

- 新 `tests/test_topk_dropout_rules.py`：plan §3.1 账 1/2/3，断言 buy/sell 集合。
- `tests/test_csv_strategy_books.py`：新书可 `apply_csv_strategy("topk_dropout")`；**version6 golden 一行不改**。
- 若动了 `run_pool_buys_day` 签名：旧调用全用默认 `planned_for_day=None`，现有买环测试仍绿。

---

## 2. 切片 BT-B · ST + 年龄只挡新开

### 锚点

- 名称 as-of / ST 板：`pool-csv-contract.md` P-R2；引擎已有名称含 ST 的 5% 板，**那是涨跌停宽度，不是买入资格**。
- 本仓若已有 ST 日 parquet / 年龄 map 的加载，复用，禁止看未来（`ymd<=ds`）。没有则读 MyQuant 同口径：`st_daily.parquet` as-of 买入日；年龄 = 上市满 60 个交易日。路径做成 CLI，缺档 fail-closed。
- `buy_gate`（`csv_simulate_loop.py:204`）可挡单只，但不够「沿序补满」。补位必须做在 `planned_for_day` 里：`buy` 被 ST/年龄踢掉后，沿 `pred_score` 未持仓序继续取，直到凑满原 `len(buy)` 或名单耗尽。

### 实施步骤

1. `eligible_buy(code, buy_date) -> bool`：非 ST PIT、年龄 ≥60。
2. 包进 `planned_for_day`：先 `decide` 得 `buy`，再 walk-down。
3. **不**在 sell_gate 里因「变成 ST」卖出。

### 测试

- 合成：`today` 第一名 ST → planned 第一名是下一只非 ST。
- 持仓代码当日变 ST → 不出现在 sell（除非同时落在 dropout sell 集）。

---

## 3. 切片 BT-C · 新书 10% 开仓价止损

### 锚点

- 日线止损已在 `csv_daily_backtest.py:276-299`：`trigger = pos.cost * (1-stop_pct)`；开盘≤trigger → `stop_loss:gap_open`；最低≤trigger → `stop_loss:touch`；跌停 defer / `pending_exit`。T+1：`if n_days >= 1`。
- 分钟触价：`csv_minute_backtest.py` `scan_held_day`（测试见 `tests/test_scan_held_day_numba_parity.py`）。
- v6 默认 `strategy6_rules.py:15` `STOP_PCT = 0.06` + trail。**禁止改这个常量。**

### 实施步骤

1. `topk_dropout` 的 `stop_pct` 默认 **0.10**。不要复用 `version6` 的 `--stop-pct` 覆盖去改 v6 默认。
2. `take_profit` 保持 `None`（无 trail）。这就是「薄书：卖 = dropout + 成本止损」。
3. 日线 / 分钟都走现有止损核，不要复制一套公式。
4. 止损当天卖掉后，同日 `planned_for_day` 看到的 `held` 已变少 → `today` 变长，允许补位（P-5 的「次日再买」之外，同日补也合法；若引擎当日现金/T+1 买不到，次日再补）。

### 测试

- 合成日 K：开盘缺口 / 盘中 lowest / 跌停 defer / `n_days==0` 不卖。
- `tests/test_csv_strategy_books.py`：`version6` 的 `stop_pct` 仍约 0.06；`topk_dropout` 约 0.10。
- 禁止改 `test_csv_strategy_books.py` 里 v6 golden 的期望值来「迁就」新书。

---

## 4. MQ-A（另一仓，本交接不写代码）

MyQuant Codex / 实现者：`export_daily_pool.py` 增加 scores sidecar。烟测未就绪前，本仓允许 `--pred-csv` 直读 `预测结果_*51dde0bc*.csv`。池目录已在：

`D:\PycharmProjects\MyQuant\exports\cat_50_raw_20260105_20260914\`

---

## 5. 门禁（合并前）

```text
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
```

- 新文件 UTF-8 无 BOM、NUL=0。
- `grep` 确认无 `import qlib`、无 `live_pool` sell 路径。
- 缺陷优先复核：v6/v8 测试文件 diff 应为空或仅注册表多一个名字。

## 6. 回写

- 本页标完成；plan 头改「✅ 已实施（PR #N）」。
- H-1 宿主数字不入库。
- 资金配给 plan 的 R-5 若仍写「禁止复刻 dropout 进引擎」，回写一句「策略书已允许，引擎仍禁止」（另 PR，可与本任务收尾一起）。
