# S2-C：X-02 cash-order 边界冻结（2026-09-28）

Human GO：**「批 C（边界文档化），开干」**。基线 `d1bb75bc03fa4379aebc395685252647c212eade`（`d1bb75b`，master after #238）。本批仅文档 / module docstring 澄清，无调度重写、逻辑或签名变化；**勿合，等待 Human「合」**。开工时 [S2-B #239](https://github.com/baiyibing/MyQuant-backtrader/pull/239) 尚未合并，本批直接基于 master，不等待、不纳入或操作 #239 的合并。

## 模块职责与调用边界

[`minute_cash_order.py`](../../backtest/research/minute_cash_order.py) 拥有以下三处实现，函数 / 类源码与签名保持不变：

- `HeldMinuteCursor`：保存持仓扫描状态，按 `advance(idx, phase)`（含 `_close`）推进并返回退出候选；保留 peak / peak_hm、reserved、首个退出尝试、真正末根及缺 15:00 的清仓回退。返回候选不等于成交，限价 / 容量门及记账仍由外围调用完成。
- `advance_independent_exit`：以独立信号持仓的整体成本 / 状态评估退出，经既有 `_sell` 结算可卖 lot；保留 T+1、pending tail、限价 / 容量门与审计相位。pending 无容量约束时尝试 open，有 completed-volume cap 时在 close 尝试，不借未完成量。
- `run_chronological_day`：在共享分钟账户内按 `hm → open/close → 既有稳定次序` 调度持仓退出和买侧调用；保留书 hooks、chase / pool / step、TopK / 尾盘窗各自的既有报价与预算合同。账本的费用、股数、现金和成交门仍由原账本函数执行。

[`csv_minute_backtest.simulate`](../../backtest/research/csv_minute_backtest.py) 负责选择每日调度路径。**legacy 独立仓分支也调用 `HeldMinuteCursor` / `advance_independent_exit`**，包括既有 14:55 后续扫；不能从 import、游标调用或局部 open/close 相位推断整个账户已启用 chronological。普通扫描 `scan_held_day_python` 仍在共享入口，未搬入本模块。

[`minute_stop_trigger.py`](../../backtest/research/minute_stop_trigger.py) 只提供校验、bar 阻断及固定目标候选等小 helper；hl 的扫描优先级 / 状态推进仍在共享扫描器和 `HeldMinuteCursor.advance` / `_close`，成交结算仍经外围调度 / 账本。与 [S2-B 边界文档 PR #239](https://github.com/baiyibing/MyQuant-backtrader/pull/239) 交叉引用；本基线未包含其新文档，现行合同可直接查 [SSOT H / X2 行及 §4](minute-fill-policy-ssot.md) 和 [H/L P1 冻结说明](minute-stop-trigger-hl-p1-2026-09-27.md)。

## 开关与有效调度

- 共享分钟与 v7 的 `--fix-minute-cash-order` 默认 **OFF**，库参数均为 `fix_minute_cash_order=False`；本批不翻默认。日线没有该开关。
- 共享 version12（含规范化别名）收到 X-02 **ON 明确拒绝**，继续保留自有 `run_minute_day` hook；不是把其自有路径接到本模块。
- 通过现有校验的 TopK `--topk-exec open|intraday|vwap` 或 `--limit-walkdown` **自动进入共享 chronological 调度**，即使 X-02 flag 为 OFF。`close + walkdown OFF` 不自动切换；单独 `--topk-limit-rule real` 也不切换。`vwap × walkdown` 及 `topk_score_exit` 非默认组合的既有拒绝保持，自动调度不扩展兼容矩阵。
- 比较 / 审计须同时记录原始 flag 与**实际生效的 cash-order policy**。TopK 自动调度时不能拿 CLI OFF 当 legacy 基线；同引擎受控 OFF/ON 比较沿用 SSOT 的绿 S 条件，不据此跨入口混排。

## 分钟相位与现金边界

共享 chronological 路径按同 hm 先 open、后 close 推进，每相位先处理独立卖出，再调对应买侧；同 hm close 卖出的**实际净款**可供随后 close 买入，但不能倒供该 hm 更早的 open 买入。既有稳定顺序、首个退出候选后的扫描停止、限价 / 容量拒绝与独立仓 pending-tail 规则分别保持，不把它们泛化成统一重试规则。

决策钟与报价钟分开：共享普通 chase / pool 缺目标根时，仍按原 09:45 / 14:55 决策，报价可沿用原更早 bar，容量仍取报价桶。X-02 不消除陈旧报价，不把所有买单改成 next-open；version11、TopK 和尾盘窗继续沿各自已有的报价 / 缺根合同。历史合同与审计说明见 [X-02 冻结说明](x02-minute-cash-order-2026-09-25.md)。

**hl 相位沿用 S2-B / SSOT §4**：跳空止损在 open 阶段；low 触价止损与固定目标在 close 阶段观察 / 结算，同 bar 保持止损优先。固定目标跳空可以取 open 报价，但仍在 close 阶段评估，不是 open 阶段已到账。游标保留 high 先于 gap-open 检查的 OHLC 近似；这些相位是研究记账约定，**不证明 tick 级先后或可执行收益**。

## v7 独立顺序

[`csv_minute_backtest_v7._run_chronological_day`](../../backtest/research/csv_minute_backtest_v7.py) 自有实现与账本，**不归本模块调度**。v7 ON 在同 hm 先处理独立止损（首根 gap open / close 止损），再处理当刻买侧，最后在该股真正末根按买后状态评估 timer。成功加仓可续期；timer 卖款不倒补同 hm 已失败的买单。它没有共享 09:45 chase / 目标分钟 fallback，也没有共享 `--minute-stop-trigger` 参数，不能将共享“close 卖先买后”解释成 v7 timer 也先卖后买。

## 本批范围与验收

本批只新增本页、强化 [唯一成交假设总表的 X2 行及短指针](minute-fill-policy-ssot.md)，并修改 `minute_cash_order.py` 的 **module docstring**。验收以 allowlist、移除 module docstring 后源码逐字节 / AST 一致、链接与 UTF-8 无 BOM / NUL=0 为准；既有数据无关测试的本次结果另记外部回执，不重录 golden，不据此宣称真湖或收益验证。

本次 S2-C 是成交假设基础设施计划中单独获批的边界文档化；历史 H/L 的 S2 实现切片不是此审批门。不抽取或重排调度、不改默认、不扩 JR / Mode B、不实施 S2-D/E、不读写湖、不合并任何 PR。
