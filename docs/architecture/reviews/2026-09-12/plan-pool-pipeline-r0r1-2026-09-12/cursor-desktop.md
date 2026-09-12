# cursor-desktop 评审（由编排者填写）

> 待评审：docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md
> 状态：已综合 → `merge-consensus.md`（v1.2）。

主持裁复现（只读）：`000004_SZ` 日线 none parquet `rows=8668 zero_vol=458`，尾部 OHLC=2.76 / volume=0。

吸收：C 默认落地（加载丢零量行）；`name_asof` 改 `last_seen`；R0 日期来自 `日期:` 行；双通道 `by_day` 优先。

不吸收：转换器搬 MyQuant；ST 履历 / N 日失效。

对抗不计票。无新架构互斥，不另开 classic。
