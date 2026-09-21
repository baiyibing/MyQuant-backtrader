# merge-consensus：plan-strategy12-jinrongyuan v0.4（2026-09-21）

四家独立评审（codex 268s / kimi 833s / cursor:auto 1014s 含一次空输出重试 / claude 418s，全 rc=0）。
证据裁决，不投票；cursor-desktop 席主持回避。**四家总评一致：不可进实现**——卖/买回还停在
口号层，须收成可编码契约（签名 + wiring 键值 + 价域 + 上限定义 + 重入语义）回填 v0.5，再人裁。
kimi 已核 docx 原文转录一致，并指出规则 5 在 docx 中标「**止盈**」（plan 未点破，补注）。

## 证据裁决表

| # | 面 | 裁决 | 证据（多路独立收敛） |
|---|---|---|---|
| **S1** | 默认路径部分卖**静默丢股** | **成立（2 组实验）** | codex E-A/kimi E1：`_sell` 的 `pos.shares -= shares` 仅在 volume_cap/exdiv 分支可达（`csv_ledger.py:400-411`）；默认（daily 全程、minute 未开 cap）→ 部分现金入账 + **整 lot 删除**，不抛异常。切片 B 必须重构该分支 + 「部分卖后 Σlot.shares 与 cash 守恒」pin |
| **S2** | 书↔引擎契约缺失 | 成立（3/4） | codex R2：三签名（`exit_plan(code,px,day,closes,lots)->(reason,shares)|None`、`buyback_plan(...)->int`、`run_buybacks_day` 照 `run_step_adds_day` 模板 `csv_simulate_loop.py:322-395`）；买回=第四买因；`csv_strategy_books.py:119-136` hooks setdefault 同步登记。claude Y-3：推荐书侧编排直调 helper，sell_gate 保持纯信号。cursor ✅ 同（勿塞进 sell_gate 返回串） |
| **S3** | v8 wiring 三键+STOP_PCT 冲突 | 成立（3/4） | codex R3 + cursor R5：`reserve_limit_up/daily_same_bar_prefixes=("open_board",)/defer_limit_up` 使涨停开板走**整仓卖绕过 sell_gate**（`csv_daily_backtest.py:384-390`）→ 双记忆失步；STOP_PCT 也在 stop 路径先于 sell_gate 整笔触发（`:353-378`）。kimi K4：`PEAK_GAP_MIN=15` 继承会把 MA 闸压后 15 分钟（`csv_minute_backtest.py:312-314`）。v12 四键 + MA 通道 peak_gap_min 须逐键裁决写死 |
| **S4** | P9④ 市值帽**饿死买回** | **成立（3/4，药方一致替换）** | codex R4 + kimi K3 + cursor R9：v8 名单全加+台阶下市值 ≫100 万是常态 → 「市值≤100 万」恒假 → 规则 5 永久 skip。**正确方向：买回上限=该通道记忆股数；新买入（池/chase）与记忆的冲抵规则**（清零 or 先冲抵，人裁两选项） |
| **S5** | **价域未定**（除权日假信号） | **成立（2/4 + SSOT）** | codex R5 算例：10 送 10 下 none 域 MA5/MA10 跳变 → **假整仓止损**；front 会关 E-R6 remap（`csv_daily_backtest.py:600-604`，二选一可执行）；分钟侧无开关（需 `--daily-source qlib_day` 或新参数）。cursor R6：E-R5③ 的 none 域 v4 先例是「历史噪声保留」，**不能**给 MA10×0.90 止损背书。v4 同源问题一并注明 |
| **S6** | 减仓**环内重入**未定义 | 成立（3/4） | claude R-2 + cursor R10 + kimi K8：连续 N 日 MA5 下方，字面实现=每日 50% 几何衰减+累加记忆一次性买回脉冲。**共识建议：同一「下方周期」只减一次（latch），收复清零后再武装**；逐分钟口径另有日内反复穿越 → 每通道每日一次 latch 选项；入切片 C pin |
| **S7** | §3 残留 FIFO 矛盾 | 成立（1/4 但确凿） | kimi K1：v0.4 回填只改了 P3，§3 缺口 1 仍写「跨 lot FIFO」——与「lot0 最后」直接冲突。回填 v0.5 统一 |
| **S8** | P2-B「14:55 假先例」 | 成立（1/4 实证） | kimi K2：分钟卖侧是**逐分钟扫描首触即发**（`csv_minute_backtest.py:285-329`），14:55 是**买侧**时钟。P2-B 改写为两选项：a) 逐分钟口径（sell_gate 天然）；b) 日内 latch（全新机制，自立论据：防盘中来回打脸）——人裁 |
| S9 | 台阶计数**重触发** | 成立（2/4） | cursor R8 + codex R7：`n_steps` 只数活着 的 is_step lot（`strategy8_rules.py:67-69`）→ 减仓卖掉后同价段立即重加，与买回叠加成换手循环。台阶改**单调记忆**（与 reduced/stopped 同处），pin「减仓后同段不重加」 |
| S10 | 实际成交回报契约 | 成立（2/4） | claude Y-2 + kimi K6/K7：locked bonus 静默缩减（`csv_ledger.py:332`）、cap 部分分配（`:359`）→ 记忆须按**实际成交量**更新；`shares_override` 的 `per=notional` 记账语义写进切片 B |
| S11 | 书侧 dict 跨 run 泄漏 | 成立（1/4） | codex R8：模块级 dict 在多 run/pytest 间串味 → 记忆挂 `st` 或 out-param 先例（`reserve_state`，`csv_minute_backtest.py:648,677`） |
| S12 | scan_held_day 5-tuple | 成立（1/4） | codex R9：24 个测试调用点按 5-tuple 解包 → 走 out-param，勿扩元组 |
| S13 | lot0 死亡边界 | 成立（1/4） | kimi K5：减仓可能耗尽 lot0 → 台阶永久停加。两选项：保留 lot0≥100 股 / 明示接受台阶终止——人裁 |
| S14 | ma_infra 前置 | **已缓解** | codex R10/claude Y-4/cursor Y2：今已 **v1.0 GO + PR #150**；切片 A 开工门槛=ma_infra 已合入；P2 未裁时只用 `sma_asof` |
| S15 | 送转缩放默认不发生 | 成立（1/4） | cursor Y1：`exdiv_economics` 默认 None → 切片 C 测试须显式开启；冒烟 runbook 声明 |
| S16 | 锚点三处指错函数 + 半勘误 | 成立（3/4） | cursor R7 + codex R13 + kimi K10：`execute_buy(:232-248)` vs `_buy_size(:219-229)`；pending_exit「全或无」实在 `:354` atomic 非 `:333-336`；`may_add` 非「恒 True」是 `bool(lots) and px>0`；§1 `115-122` vs §2 `115-121`；claude Y-5：里程碑行 HELP_LOCK pin 归属（`test_csv_strategy_books.py:176-179`）仍未回填。测试数以 kimi collect-only **1401** 钉死 |
| S17 | 死链 + γ 第三触点 + 中间层顺序 | 成立（3/4） | claude Y-6/cursor Y3：`plan-v8-rules-v2` 实在 `docs/backtest/` 根非 `_archive`；claude Y-1：exdiv 回调=γ 第三引擎触点，枚举如实扩；claude Y-7：中间层 lot 按 lot_id 升序（FIFO）补一句 |
| S18 | P6 失实前提 | 成立（2/4） | claude R-1 + cursor R9：引擎**无任何**单码单日买向闸，「2 笔」是调度涌现；加买回后日买向=池 1+chase 1+台阶 N+买回 2。P6 改真问题交人裁 |
| S19 | 小项打包 | 成立 | codex R15：`ma12:` 建议改用**既有 `ma_signal:` 前缀桶**（`:394` 已有分支）；codex R14：分钟 cap 卖出不整百 → HELP_LOCK「50% 为上限，实际以容量为准」；kimi K11：chase `px==open→abandon` 等值边界入 HELP_LOCK；cursor Y4：P4 清零=各清各的（MA5 清减仓、MA10 清止损），同日先卖后买；claude G-1：P8 补 v7 同族先例（`--pool-dir` 必填）；claude G-2：「逐字节等价」改「默认参数下 trades/equity 输出逐字节等价」 |

## 分歧与处置

- 逐分钟 vs 日内 latch（S8）：真分歧 → 升 P2 人裁（两选项各有理：语义忠实 vs 防打脸）。
- 价域（S5）：codex 建议 front、cursor 指出 E-R5 的 none 是 v4 历史包袱 → 升 P10 人裁，建议 front。
- `ma12:` 新前缀 vs `ma_signal:` 复用（S19）：codex 建议复用、对抗稿曾定新前缀 → **采纳复用**（少一套桶）。

## 人裁清单（v0.5 后）

P2（评估口径：逐分钟 vs 日内 latch）、P5（+止损日站回共存顺序）、P6（改写：单码单日买向闸）、
P7（上证闸）、P8（+v7 先例）、P9④（改写：记忆股数上限+冲抵规则）、P10（价域 front/none）、
P11（减仓重入 latch）、P12（wiring 四键+MA 通道 peak_gap_min）、P13（lot0 保底 vs 台阶终止）。

## 结论

修订 v0.5（S1–S17 全部落进 plan 文本：S1/S2/S10 进切片 B 契约、S3/S19 进 P12/HELP_LOCK、
S4 进 P9④、S5 进 P10+切片 D、S6 进 P11+切片 C pin、S7/S16/S17 勘误、S9 进切片 B/C、
S11/S12/S15 进切片 C、S14 记录门槛）后，按上表 10 问人裁；GO 后走 Codex 交接。
