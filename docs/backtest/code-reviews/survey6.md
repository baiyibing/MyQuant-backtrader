请作为一个backtrader专家和量化资金管理专家，仔细认真分析上传的程序和日志，分析以下异常日志的原因，从日志看
2025-10-23日600997.SH买单先被Canceled，然后又创建，又执行到第二天2025-10-24。
- 2026-03-06 00:38:06 [INFO] [rolling_investment_strategy:431 - _on_daily_close] 取消未成交订单: 603062.SH, 订单状态: Canceled
- 2026-03-06 00:38:06 [INFO] [rolling_investment_strategy:431 - _on_daily_close] 取消未成交订单: 600997.SH, 订单状态: Canceled 
- 2026-03-06 00:38:06 [INFO] [rolling_investment_strategy:670 - log_trade] 时间分析 - 600997.SH BUY: 决策2025-10-23 15:00:00到创建2025-10-23 15:00:00延迟 0.000秒
- 2026-03-06 00:38:06 [INFO] [rolling_investment_strategy:674 - log_trade] 时间分析 - 600997.SH BUY: 创建2025-10-23 15:00:00到执行2025-10-24 09:30:00延迟 66600.000秒，

从新日志的毫秒级时间戳可以看出，事件顺序与之前的分析完全一致：  
- 15:00:00 触发 `_on_daily_close` 取消未成交订单（600997.SH 和 603062.SH）。  
- 订单取消后立即触发 `notify_order` 回调（15:00:00.156–157）。  
- 紧接着（15:00:00.158），引擎再次调用 `next()`（因为订单状态变化会触发重绘），此时 `current_time` 仍为 15:00，导致 `_process_normal_buy_orders` 重新执行，用收盘价再次创建买单。  
- 由于已过交易时间，新订单只能在次日开盘成交。

**根本原因**：Backtrader 在订单状态变更后会重新执行 `next()`，而策略中没有防范收盘后继续下单，导致重复创建订单。

**解决方案**（与之前建议一致）：  
1. 在 `__init__` 中添加标志 `self._market_closed = False`。  
2. 在 `_on_daily_close` 末尾（或取消订单后）设置 `self._market_closed = True`。  
3. 在 `_process_buy_orders` 及其子函数开头检查 `if self._market_closed: return`。  
4. 在每日第一次 `next`（更新持仓天数时）重置标志 `self._market_closed = False`。

此改动可确保收盘后不再创建任何订单，避免重复下单和次日意外成交。