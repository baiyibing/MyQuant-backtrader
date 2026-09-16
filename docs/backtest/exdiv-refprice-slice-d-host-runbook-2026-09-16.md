# 切片 D · 宿主验证 runbook（exdiv refprice）

> **日期**：2026-09-16。
> **状态**：📋 **host-only — NOT done in PR**。合入门不含本片；A/B/C 合入后由宿主本机执行。
> **权威**： [plan-exdiv-refprice-2026-09-16.md](plan-exdiv-refprice-2026-09-16.md) §4 D；[handoff](handoff-exdiv-refprice-codex-impl-2026-09-16.md) §4。

## 0. 硬边界

- 本短记**预写回收量级**：总亏损回收**上界 +35~125 万（≈0.01–0.025pp）**——防「假止损消失 ⇒ 回收 −196 万 / 12%」误读。
- 止损笔数预期：149 → **~120–144**（下界 144 = 5 笔可证实假止损消失；混合带部分转持有）。
- 不改湖数据、不改 `*_rules.py`、不接 v7。

## 1. 步骤（宿主）

1. 合入 `feat/exdiv-refprice`（或 cherry-pick）到本机研究环境。
2. 用 **v1 规则**重跑 5 亿分钟窗（与 er5-recheck 同口径）：
   ```powershell
   D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py --strategy version1 --start 20251023 --end 20260909 --cash-total 500000000
   ```
3. 对照 `research_false_stops_exdiv.csv` 前后：5 笔假 gap_open 应消失。
4. 顺带跑 facts §3 停牌三项（占位行 / front 连续性 / 无因子行码）最小验证。
5. 落短记到 `docs/backtest/`（含实际止损笔数与回收金额），**然后放行 v8 规则 v2 切片 D**。

## 2. 完成定义

短记落盘 + 宿主 agent 通知 v2 切片 D 可开。**本 PR / CI 不得勾选本切片为完成。**
