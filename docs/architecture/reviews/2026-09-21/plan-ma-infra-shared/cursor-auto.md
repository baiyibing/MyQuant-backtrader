<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.18-9a7762b\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.18-9a7762b\index.js --model auto -p --output-format text --trust -f --mode plan --workspace E:\PycharmProjects\OSkhQuant1.3 <prompt> -->
并行目录里的 kimi、claude、codex、cursor-auto 截至读取时只有提示词，没有写完的结论，下面独立成文。本方案没有 timeout、budget、并发锁或重试，因此不做 slow-fn 实验；周线 `resample` 和 `std` 的默认行为用 pandas 2.3.3 做了最小实验。

## 🔴 必须修

**R1. `daily_to_weekly` 写不成「移植副本」，返回的日期键会选错。**  
源函数是 DataFrame 进、DataFrame 出，且强制 OHLC：

```86:104:E:/PycharmProjects/MyQuant-backtrader/oskh_factors/weekly_macd_divergence.py
def _daily_to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """日线 → 周线（W-FRI）。``_last_day`` = 该周最后交易日（signal_date 真源）。"""
    ...
    weekly = d.resample(WEEK_RULE).agg({..., "close": "last", "_last_day": "max"})
    return cast(pd.DataFrame, weekly.dropna())
```

草案签名是 `daily_to_weekly(dates, closes) -> list[tuple[date, float]]`，又要求标量件零第三方依赖（方案 R2）。这三件事不能同时成立。实验（pandas 2.3.3）：只有 `close` 时按源函数聚合会 `KeyError: ['high','low','open','volume']`。合成日 `2024-09-16/17/18`（周一到周三）得到周标签 **2024-09-20**、`close=12`、`_last_day=2024-09-18`。归档口径的 asof 键是 `_last_day`，不是周五标签：

```34:34:E:/PycharmProjects/MyQuant-backtrader/docs/backtest/_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md
| 20 周均线 | ... asof 键 = `_last_day`，只 backward 到 D。...序列末端未完成周若 `_last_day<=D` 可参与
```

`weekly_sma_asof(dates, closes, n)` 没有 asof 日。若元组里的 date 用周五标签，D=周三时标签已落到未来周五，backward join 会丢掉本周（归档明确要求参与）。必须写死：返回键 = `_last_day`；周五只作分桶；末端未完成周在 `_last_day<=D` 时入窗。并给一个数值 pin：上述三天、n=1、D=2024-09-18 → `12`，不是 `None`。

**R2. R4 把「截至昨收」写成了所有 asof 件的输入，和 version11「含 D」冲突。**  
方案 R4：「书侧拿到的 `daily_closes_ending_yesterday` 喂 asof/live 件」。策略 4 确实不含今日：

```1:1:E:/PycharmProjects/MyQuant-backtrader/backtest/research/strategy4_rules.py
"""策略 4 均线买卖闸；均线输入刻意不含今日收盘。"""
```

归档与 version11 相反：信号日 D 的 SMA/布林含 D。

```32:33:E:/PycharmProjects/MyQuant-backtrader/docs/backtest/_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md
| 比均线 | 在日 D 评 cond[D] 时 SMA 输入止于 D（sma 含 D 合法）。
| 布林上轨 | ... SMA20(close)（含 D），上轨 = 中轨 + 2σ，σ=rolling.std(ddof=1)
```

种子实现并不丢最后一根，只对传入序列取尾窗（`strategy4_rules.py:23-27`）。截止权在调用方这句话是对的，但 R4 的例子会让 version11 整段滞后一日。应改成：`sma_asof` / `sma_series` / `bb_asof` 不解释「最后一根是不是今天」；只有 `sma_live` 才是「昨收尾部 n−1 + 现价」。页眉「收敛全部均线口径」改成「只收敛算子，不收敛 PIT 终点」。

**R3. 复权域不能被「全仓 SSOT」收成一种。**  
引擎现锁是不复权，且 v4 均线在除权日不换域：

```125:125:E:/PycharmProjects/MyQuant-backtrader/docs/backtest/engine-ashare-correctness.md
E-R5 ... ③v4 SMA 门用截至昨收的原始 closes，除权日不换域（...历史行为保留）。
```

日线装载默认 `dividend_type="none"`（`csv_daily_loader.py:108-111`，`csv_daily_backtest.py:540`）。version11 的价格锁是 `adjust_type=front`（归档 §2「价格」行）。提示词点名的 `docs/SSOT.md`、`docs/backtest/data/symbol-format-ssot.md`、`docs/operations/disclosure-data-source-ssot.md` 在本仓不存在；上面这条 E-R5 才是会冲突的 SSOT。模块禁止复权是对的，但必须写明：禁止为了统一口径把 v4 改成前复权；v11 自行传入 front 序列。本 API 无证券代码，与符号格式无冲突。

**R4. 刀 B 的 DoD 自相矛盾，照着做会改行为或过不了 diff 检查。**  
P3 说只 re-export、gate 不动。刀 B 同时要求 `import sma_asof as sma_asof`、调用点改向、以及 `git diff` 仅 import 行。现函数体在 `strategy4_rules.py:23-27`，`buy_gate`/`sell_gate` 在 `:32`、`:38` 调本地名。搬走函数体必然不止一行 import。外部 pin 是 `tests/test_strategy4_rules.py:5-6` 的 `rules.sma_asof`。改成：删本地定义、同模块 re-export、gate 仍调这个名字；DoD 改为「gate 函数体零 diff + 既有断言不改」。`tests/test_ma_infra.py` 那条快检命令应加上 `tests/test_strategy4_rules.py`，否则 R1 不在快路径上。

**R5. 与 version11 R3 对周线的归属相反。**  
version11 R3 写「周线计算复用 `oskh_factors`」；同文 R8 又要求周线只走 `ma_infra`。本方案 R3 是移植副本、两处并存、不改因子库。实施时两把锁必有一把被破。本方案应写明：version11 的周线改挂 `weekly_sma_asof`；`_daily_to_weekly` 保持私有，不成为研究侧 import。因子库里的周线 MA200（`weekly_macd_divergence.py:183`，`rolling(200).mean()`）不迁、不删。

## 🟡 应修

**Y1. 盘点「全仓唯一 MA」「布林无存活实现」不成立。**  
日线 asof 标量确实只有 `sma_asof`（`:23-27`，行号正确）。但周线 MA200 在 `:183`；价格同公式的 TR 布林在 `oskh_factors/chip/bands.py:27-49`（`ddof=1`，不足窗口返回 NaN，且 `round(..., 4)`）。禁止把 `tr_bollinger_bands` 套到收盘价上，四位舍入会改「high > 上轨」的边缘。另有 `scripts/data/full_market_chip_resist.py:49` 的 `std(ddof=0)`，不要抄。实验：`[1,2,3,4,5]` 的 `rolling(5).std()` 默认 = ddof=1 = **1.5811388300841898**；ddof=0 = **1.4142135623730951**。归档锁定的是前者（与 pandas / turnover-resist 对齐，不是通达信总体标准差）。pin 必须写这个数。

**Y2. R2 的 import fence 并不禁 pandas。**  
`tests/test_ashare_simulate_import_fence.py:39-57` 只拦 `qlib`、`trade_fee_policy`、`backtest.lebs`、`ashare_fill_clock`。`csv_strategy_books.py:18` 会 import `strategy4_rules`。`ma_infra` 顶层一旦 `import pandas`，热路径会带上 pandas，而 fence 仍绿。标量件（含周线）保持标准库；pandas 只允许出现在本刀明确不做的 `*_frame` 里，且用函数内 import。

**Y3. `sma_live` 的拼接还没钉到会亏钱的那种错法。**  
R5 只说长度 ≥ n−1。必须 pin：时间升序、取尾部 n−1 根再加 `px`，不是前缀，也不是再取 n 根。例：`prev=[1,2,3,4], px=10, n=3` → `(3+4+10)/3`，不是 `(2+3+4)/3`。`sma_series` 必须与输入等长，`i < n-1` 为 `None`，否则 version11 的 `cond[D]` 与 `cond[D-1]` 会错位。

**Y4. 种子对 NaN / n≤0 的行为要写进 R5，避免「清理」改语义。**  
同一段逻辑：窗口含 NaN 时返回 `nan` 而不是 `None`（实验 `sma_asof([1, nan, 3], 3) → nan`）；`n<=0` 返回 `None`；`int(2.9)` 截成 2，尾窗均值为 3.5。gate 对 NaN 和 None 碰巧都不买不卖，但 `is not None` 分支不同。原样搬家就保持现状，不要改成一律 None。

**Y5. 「低 / 零风险」只覆盖刀 B。**  
刀 B 是行为零变更。刀 A 的周线键和布林 σ 就是 version11 的买卖条件。风险档拆开写。

## 🟢 可选

- 盘点写的 HEAD `40f660d` 仍是代码祖先。当前 HEAD 是 `4adad96`（仅本 plan 文档提交），`:23-27` 未漂。
- `import sma_asof as sma_asof` 只有在本模块不再调用该名时才用来消 F401；gate 继续调用则不需要这个别名。
- 快检命令补上 `tests/test_strategy4_rules.py`。`pytest tests/` 可以留在刀 B，不必升成唯一门。

## ✅ 做对的地方

- 种子 API 用现成 `sma_asof`，不新造一套；行号 `strategy4_rules.py:23-27` 与代码一致；测试已锁尾窗与不足 n 根（`test_strategy4_rules.py:4-6`）。
- 不改 `oskh_factors` 公共 API、不做 EMA/WMA、本刀不做 `*_frame`，符合小团队一次把算子收干净、但不把因子库和引擎搅在一起。
- 放在 `backtest/research/` 而不是因子库：三个消费方里两个在书侧，且源周线函数是私有 OHLC 管线，不该变成研究侧依赖。
- ddof=1 与归档 §2、`bands.py` 默认、pandas 2.3.3 实测一致；不要改成通达信 ddof=0。
- 模块不读湖、不做复权，和「截止权、复权域都在调用方」的方向一致；缺的是把两个消费方的终点和复权域写明，而不是把计算搬进模块。

## 实验

无安全阀类设计，未做 budget 实验。复现（只读，无写文件）：

```python
import pandas as pd
s = pd.Series([1.0,2.0,3.0,4.0,5.0])
print(float(s.rolling(5).std().iloc[-1]), float(s.rolling(5).std(ddof=0).iloc[-1]))
idx = pd.to_datetime(["2024-09-16","2024-09-17","2024-09-18","2024-09-23","2024-09-26"])
df = pd.DataFrame({"open":[1,2,3,4,5],"high":[1,2,3,4,5],"low":[1,2,3,4,5],
                   "close":[10,11,12,20,21],"volume":[1,1,1,1,1]}, index=idx)
df["_last_day"] = df.index
w = df.resample("W-FRI").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum","_last_day":"max"}).dropna()
for ts, row in w.iterrows():
    print(ts.date(), row["close"], pd.Timestamp(row["_last_day"]).date())
```

原始输出要点：`pandas 2.3.3`；std 默认/ddof=1 = `1.5811388300841898`，ddof=0 = `1.4142135623730951`；周行 `2024-09-20 close 12 last_day 2024-09-18` 与 `2024-09-27 close 21 last_day 2024-09-26`；仅 close 列 → `KeyError`。种子逻辑另测：NaN 窗 → `nan`；`n<=0` → `None`；`n=2.9` → `3.5`。

## 总评

方向对：一个纯函数算子、策略 4 原样搬家、周线不回写因子库。v0.1 还不能进实现。先改 R1–R5（周线键用 `_last_day`、asof 件不要绑死昨收、复权域按 E-R5 与 front 分家、刀 B 的 diff 口径、以及 version11 R3/R8 的周线归属），再人裁 GO。
