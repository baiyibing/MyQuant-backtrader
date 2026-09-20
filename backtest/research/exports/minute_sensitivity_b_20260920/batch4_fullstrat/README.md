# batch4_fullstrat · 全策略 NAV / DD / 引擎内排名

只读研究导出。数值由 4090 在 `--execute` 后填入；VM 仅 stubs / DATA_GAP。

- 设计：`docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md`
- 结果桩：`docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md`
- Book / v7 / Mode B **分列**；禁止跨引擎优劣表
- clock 交换与 slip 全策略轴：**DATA_GAP**（无 research-only hook）
- 费用：`DEFAULT_SCHEDULE` / Mode B 双边 10bp；单轴矩阵见 `matrix.csv`
