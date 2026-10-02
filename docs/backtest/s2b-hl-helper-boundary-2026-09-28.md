# S2-B：hl helper 边界冻结（2026-09-28）

Human GO：**「批 B（边界文档化），开干」**。基线 `d1bb75bc03fa4379aebc395685252647c212eade`（`d1bb75b`，master after #238）。本批仅文档 / module docstring 澄清，无行为变化；**勿合，等待 Human「合」**。

## 模块职责

[`minute_stop_trigger.py`](../../backtest/research/minute_stop_trigger.py) 只拥有以下四个函数，签名与函数源码保持逐字节不变：

- `validate_minute_stop_trigger`：校验 `close|hl` 及现有互斥组合。
- `validate_low`：校验模式，并要求 hl 的 low 与 close 序列对齐。
- `blocked_bar`：保留开盘跌停禁售检查；hl 另检查 high 封死跌停的 bar。
- `target_fill`：仅计算已有固定向上目标的成交候选，须经原 `take_profit` 回调确认；不接管 trail / MA。

**hl scan/fill 语义仍在 simulate 扫描循环中**：普通扫描由 [`csv_minute_backtest.scan_held_day_python`](../../backtest/research/csv_minute_backtest.py) 承担；可恢复扫描由 [`minute_cash_order.HeldMinuteCursor.advance`](../../backtest/research/minute_cash_order.py)（含其 `_close` 路径）承担，供独立持仓及 X-02 时序现金路径使用。逐 bar / open-close 相位推进、止损优先级、峰值及书 hooks 仍在这些扫描路径；成交执行与现金 / 持仓记账仍由外围 simulate / 调度路径承担。小 helper 的 `target_fill` 返回候选不等于拥有完整成交循环；本批不向该模块搬 scan/fill。

## 既有合同保持

共享分钟 `--minute-stop-trigger` 默认 **`close`**；省略 / 显式 close 的现有行为保持，hl 仍是 opt-in Python 路径。hl 拒绝 version12（含入口规范化的别名）及 `--fix-s11-exit-domain`；`--fix-s12-price-domain` 只允许 version12，故与 hl 的实际组合也拒绝。v7 / 日线入口均未注册 `--minute-stop-trigger`，没有通过本批获得该参数。

hl 不是 Mode B **Q39**：前者按同 bar 保守止损优先，后者先 open、未成再 close，H/L 不触发。hl 也不是日线 **`--stop-fill`**；日线 `stop_fill=touch` 与分钟触发域分别冻结，共享分钟继续拒绝 `--stop-fill close`。X-02 的跳空止损在 open 阶段；H/L 触价及固定目标在 close 阶段观察结算，目标跳空取 open 报价不代表 open 阶段结算。完整行为沿用 [H/L P1 冻结说明](minute-stop-trigger-hl-p1-2026-09-27.md)；默认与比较资格统一见 [成交假设 SSOT H 行 / §4](minute-fill-policy-ssot.md)，本页不另建总表。

## 审批门与历史切片分开

成交假设基础设施计划的 **S0 / S1 / S2** 是审批门：S0 为已合入 #238 的 SSOT 文档；S1 为需独立 GO 的只读目录；S2 为逐 helper 单独 GO 的边界 / 抽取工作。本次 **S2-B 只授权边界文档化**，不授权抽取 scan/fill、S1 catalog 或 S2-C/D/E。

历史 H/L P1 的 **S1 / S2** 是实现切片名称：S1 指普通 / 独立持仓扫描，S2 指 X-02 `--fix-minute-cash-order` 路径；两者已随 #228 接入。它们不代表上述计划审批门获批，也不由本批重新实施。本批不翻默认、不读湖、不重跑收益、不合并。
