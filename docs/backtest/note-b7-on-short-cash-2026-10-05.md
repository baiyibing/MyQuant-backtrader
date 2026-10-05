# B7 on_short_cash

2026-10-05 23:08 Human GO：H-B7-01..07 推荐选项全部获准并实施。

共享 hooks 可设 `on_short_cash: "raise" | "skip"`；非法值初始化抛 ValueError。省略时 configure_s8 按规则实际绑定 S8 的 per_name 书（version6_*、version8、version8_N≠8_1）默认 raise，其余 skip。bare SimState 未解析时按当时 policy 推导。运行配置不进入 dataclass fields、book_state 或默认输出。

分支 tip 已 rebase 到 #394 V6F v21 的 master `d18df2f`；_configure_s8 已包含 version6_42–6_44，本次仅同步文档计数与范围。

支持 csv_ledger、csv_simulate_loop 的共享买侧与 minute_cash_order strict tail parent。v7、topk_minute_exec 专用执行、fullstrat_research_book、strategy9_2_engine 不接受显式 override，启动 fail-closed；共享 reclaim/topk 支持。无新 CLI flag，HELP_LOCK 原字节保留。共享 HELP 说 per_name skip_cash，与 S8 docstrings/书契约的不足停止存在历史冲突，本票如实保留。

helper 仅比较原 needed > available，不重算股份、费用或计数。pool/非 S8 step-add caller 计 skip_cash、预算 notional 并记录一次 rejection；reclaim/topk 计实际 notional、不记 rejection。ledger 仅 rejection。chase 保留 pop 和 chase_buy_fail*；price-add 成功标记不推进，breakout_pending 保留。strict tail parent skip 计一次 skip_cash、target_shares × opening_px notional 与一次 rejection，不建 children，已消费信号不回落；child 保留原片次和 ledger-only rejection。

原异常五字段/文本、容量前门槛和 tail opening_debit 保留。非 strict tail allocation clip 不变。B8 整手、STAR 200、top-up 与含费 clip 另票；本票拒绝 clip，不改 FillConfig。默认要求 byte-identical，旧 fixtures 永不覆盖；opt-in 结果变化属于独立研究实验，新增 baseline 另票。
