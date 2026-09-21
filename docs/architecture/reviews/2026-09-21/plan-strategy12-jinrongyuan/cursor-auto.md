<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.18-9a7762b\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.18-9a7762b\index.js --model auto -p --output-format text --trust -f --mode plan --workspace E:\PycharmProjects\OSkhQuant1.3 <prompt> -->
评审已按当前工作树逐条对过锚点。本方案没有 timeout、熔断或并发锁，因此没有做「慢函数 + 紧预算」实验；股数守恒问题从 `_sell` 的分支结构就能确定。并行稿里 claude、codex 已写完，kimi 未完成，cursor-auto 只有提示词桩。

## 🔴 必须修

**R1. 减仓 50% 挂不进现有 `sell_gate`：它在逐 lot 循环里，返回值一有 reason 就整笔处理。**  
日线对每个 lot 调一次 `sell_gate`，不是按代码聚合一次。

```338:396:backtest/research/csv_daily_backtest.py
for pos in list(st.positions.get(code, [])):
    ...
    reason = sell_gate(code, close, day, closes) if callable(sell_gate) else ...
```

分钟侧同样是 `for pos` → `scan_held_day` → 首个触线 bar 就返回（`csv_minute_backtest.py:643-669`，`scan` 内 `316-324`）。P3 要的是「该码 t1 可卖合计 ×50%」，现有钩子表达不了，还会按 lot 重复触发。§2 把 `csv_daily_backtest.py:394-402` 写成「整仓卖出」也不对：`394-402` 只是 `same_bar` 判断；`ma_signal` 不在默认前缀 `("open_board",)` 里（`csv_strategy_books.py:127`），于是 `422-423` 写入 `pending_exit`，次日开盘才 `_sell`（`344-349`）。v4 的 HELP 也是这么写的（`strategy4_rules.py:17`）。

**R2. 默认路径上「只改卖出股数」会把剩余仓位删掉。**  
`pos.shares -= shares` 只在 `volume_cap` 或 `exdiv_economics` 分支里（`csv_ledger.py:400-407`）；否则 `408-411` 直接删掉整个 lot。日线引擎全文没有 `volume_cap`。研究默认路径（两者皆空）没有部分卖记账。切片 B 必须写明：余股保留 lot，股数与现金守恒，不能只加一个 `wanted_shares` 局部变量。  
与 codex R1 的结构判断一致。其实验 A（`cash=9990`、1000 股×10）是整笔卖出，没有构造 `wanted < pos.shares`，不能当作「部分成交丢股」的实验证明；丢股是 `400-411` 的控制流，不是那次打印。

**R3. R3 硬锁、建议项 P2-B、以及 `sma_live` 三者互相打架；「14:55 评估」也不是分钟卖出时钟。**  
R3（方案 §4）：现价不进入 MA 序列。P2-B 建议：昨收尾部 n−1 根 + 当前分钟价。`plan-ma-infra-shared-2026-09-21.md:32` 的 `sma_live` 就是把 `px` 加进均线，并注明为 P2-B 预留。页眉写「R3 已改成现价不入序列」，建议项却推荐 `sma_live`。二者必须留一个。  
另外，分钟 `sell_gate` 是逐 bar 首触即返回（`csv_minute_backtest.py:316-324`），不是 14:55 当根。14:55 是池买入时钟，不是卖出评估时钟。

**R4. §3 仍写 FIFO，与已改的 P3 矛盾。**  
§3 缺口 1：「跨 lot FIFO」。P3 与切片 B：「`is_step` 先卖、`lot_id==0` 最后」（锚在 `strategy8_rules.py:61-64`）。实施时两套顺序都会被当成正文。

**R5. 「买侧复用 v8 wiring」会把 v8 的成本止损和涨停开板整仓卖带进均线书。**  
`_apply_version8`（`csv_strategy_books.py:562-582`）固定：`stop_pct=STOP_PCT`（0.10，`strategy8_rules.py:20`）、`reserve_limit_up=True`、`daily_same_bar_prefixes=("open_board",)`。  
成本止损在 `sell_gate` 之前（日线 `csv_daily_backtest.py:353-378`；分钟 `292-296`），触发即整笔 `stop_loss:*`，不进减仓/止损双记忆。涨停开板路径 `reason="open_board"` 根本不调用 `sell_gate`（`384-390`）。v4 才是 `stop_pct=None` 且 `reserve_limit_up=False`（`csv_strategy_books.py:479-486`）。方案必须把 v12 这三个键写死，不能写「含 v8 wiring delta」。与 codex R3 一致，并补上 `STOP_PCT`。

**R6. 价域未声明，会继承成交核已经写明的假均线信号。**  
方案把 `engine-ashare-correctness.md` 列为成交核 SSOT，但没提 E-R5③ / E-R6②：v4 SMA 用截至昨收的**不复权** `closes`，除权日不换域，假 `ma_signal` **只为 v4 历史行为保留**（该文约第 124–125 行）。日线默认 `dividend_type="none"`（`csv_daily_backtest.py:540`）；`front` 会关掉 E-R6 remap（`600-604`）。新书把 MA10×0.90 当止损，除权跳变会直接整仓止损，不是 v4 那种可保留的历史噪声。必须在 R3/HELP_LOCK/切片 D 写明价域；若继续 `none`，要明确这是主动接受假突破，而不是「v4 先例所以正确」。  
`docs/backtest/data/symbol-format-ssot.md`、`docs/SSOT.md`、`docs/operations/disclosure-data-source-ssot.md` 不在本仓。符号仍走 `to_partition_key`（`csv_daily_loader.py:63`），与 1.3 的点分/下划线契约无新冲突。`daily-adjusted-update-ssot.md` §1 的 front=Ground truth 是数据落盘口径，不能代替上面的 E-R5 裁决。

**R7. 锚点有三处会指错函数（页眉称已全套勘误）。**

| 方案写法 | 实际 |
|---|---|
| `execute_buy` 无 shares 覆写在 `csv_ledger.py:219-229` | `219-229` 是 `_buy_size`；`execute_buy` 签名在 `232-244`，确无 `shares_override` |
| `pending_exit` 在 volume_cap 下全或无，`:333-336` | `333-336` 只是「有锁定送转股则整笔延期」。容量下的 atomic 在 `354`：`atomic=... or bool(pos.pending_exit)` |
| v8 `add_gate`「恒 True」（`:573`） | `:573` 只是绑到 `may_add`；函数体是 `bool(lots) and px>0`（`strategy8_rules.py:52-54`） |

`:347` 的 T+1 判断属实，且只在 `volume_cap is not None`（`339`）之内。日线/分钟的 T+1 在调用方：`csv_daily_backtest.py:352`、`csv_minute_backtest.py:656`、`t1_sellable`=`buy_date < session`（`ashare_session.py:39-41`）。

**R8. P3 先卖 `is_step` 会把 +20% 台阶计数打回去。**  
`n_steps` 只数仍活着的 `is_step` lot（`strategy8_rules.py:67-69`）。减仓把它们卖掉后，同一价格段 `step_add_due` 会立刻再真。这和「保 lot0 锚」的动机相冲，会叠仓。台阶计数要独立于存活 lot。

**R9. P6「沿用引擎单日上限」不成立；P9④ 的 100 万市值帽会把买回饿死。**  
同意 claude R-1、codex R4。池买与追买没有笔数闸（`csv_simulate_loop.py:252-255` 的 `skip_held` 仅在 `not allow_add` 时；v8 `ALLOW_ADD=True`）。「chase+池 2 笔」是两个时点的结果，不是闸。`run_step_adds_day:340` 只限制「每码每天最多一笔台阶」。P9④「市值+在途买回 ≤100 万」在多笔 100 万加仓后恒假，规则 5 的买回会永远 `skip`。上限必须改成「买回 ≤ 该通道记忆股数」，不能用持仓市值。

**R10. 「掉下五日线减仓 50%」在未收复期间是否每天再减，正文没有定义。**  
同意 claude R-2。不写死的话，实现会变成每日 50% 几何衰减，再按累加记忆一次性买回。建议：同一段 MA5 下方只减一次，收复清零后才允许再减。放进切片 C 的 pin。

## 🟡 应修

**Y1. P9③ / 切片 C「送转日缩放」在默认 CLI 上不会发生。**  
`exdiv_economics` 默认 `None`（`engine-ashare-correctness.md` 约第 260 行；`csv_daily_backtest.py:288-289`）。不传 lookup 就没有送转增股，书侧回调没有事件。DoD 要写明测试必须显式打开该层，冒烟 runbook 是否打开也要写。

**Y2. `ma_infra.py` 还不在树上。**  
`plan-ma-infra-shared-2026-09-21.md:3` 已是 **v1.0 已人裁 GO**，但全仓没有 `backtest/research/ma_infra.py`。切片 A 不能在该文件落地前开工。  
纠正 claude Y-4：不是「仍为 v0.1 未人裁」，而是「计划已 GO、代码未入库」。P2 未裁时切片 A 只应依赖 `sma_asof`。

**Y3. 前序链接是死链。**  
方案指向 `docs/backtest/_archive/plans/plan-v8-rules-v2-2026-09-16.md`。文件实际在 `docs/backtest/plan-v8-rules-v2-2026-09-16.md`。

**Y4. P4「买回后状态清零」与 P5「双记忆并存」没说清清的是哪一条。**  
应写成：MA5 收复只清减仓记忆，MA10 收复只清止损记忆。同日先卖后买。

## 🟢 可选

- R1 的「pytest 1399+」与 claude（约 877 个 `def test_`）、codex（约 783）口径不一致。我没有跑 collect-only，不要把这个数字当硬锁。
- 规则 6 写 `chase_decision` 在 `115-122`，函数体结束于 `121`。表内 `115-121` 是对的。

## ✅ 保留

- `version12` 不占 `version11`，与 `AGENTS.md:22` 一致。
- `Position` 字段 `70-82`、`step_add_due` `57-69`、v8 注册 `1018-1031`（`per_name` + `1_000_000`）、分钟喂数 `669`、stats 在 `384-397` 没有 `ma12:` 分支（会掉进 `sell_pos_trail`），这些锚点是对的。R5 要单独加桶，成立。
- 不复用 `pending_exit` 这个结论成立（它是 per-lot 字符串，`csv_ledger.py:79`；日线只存 reason 字符串，`416-423`）。错的只是把「全或无」安在 `333-336`。
- γ（默认 `None`、现有书零行为变化）比通用钩子合适。买回应新开一条买因，模板是 `run_step_adds_day`，不要塞进 `sell_gate` 的返回字符串。

## 总评

买侧复用和「最小引擎面」方向对，但卖出契约、v8 wiring、MA 是否含现价、除权价域、台阶计数和买回上限都还不能直接编码。**不可进实现。** 先把 R1–R10 收成一份自洽的 v0.5（签名、wiring 三键、价域、只减一次、买回上限=记忆股数），再裁 P2–P9。


[runner] cursor:auto 经 2 次尝试完成（含 rc=0 空输出自动重试）
