# 筹码因子文档索引

## 主文档

| 文档 | 说明 |
|------|------|
| [`turnover_resistance.md`](turnover_resistance.md) | **换手阻力**索引页（算法 + 运行手册） |
| [`turnover_resistance_algorithm.md`](turnover_resistance_algorithm.md) | 算法核心：公式、调用链、qlib_cost 数学层、各层实现、附录 A/B |
| [`turnover_resistance_runbook.md`](turnover_resistance_runbook.md) | 运行手册：回测框架、选股规则、脚本 CLI、参数速查 |
| [`turnover_resistance_rust.md`](turnover_resistance_rust.md) | Rust 高性能重写（全市场 ~5500 只，window=1000，~100 秒） |

## 关键工程约定（摘要）

详见 [`turnover_resistance_algorithm.md`](turnover_resistance_algorithm.md) **§4.6**：

1. **规范路径**： →  →  → （）。
2. **截面日**：T 日 80 窗 vs T-1 窗； 为每日截面参考实现。
3. **P0-18**： 须 ；缺流通股本抛错，主路径不用 100 亿默认。
4. **换手率双轨**：CSV （静态 parquet）vs （history/adapt）；对比前须对齐。
5. **列名**： /  / 。

## 关联文档

- [cost-migration-implementation-plan.md](cost-migration-implementation-plan.md)
- [../data/float_shares_time_dimension_plan.md](../data/float_shares_time_dimension_plan.md)
- [../../prompts/prompt-canonical-turnover-resistance.md](../../prompts/prompt-canonical-turnover-resistance.md) — canonical 换手阻力全市场计算 runbook
- [../../knowledge/incidents/winning-chip-bias/winning_chip_bias_diagnosis_plan.md](../../knowledge/incidents/winning-chip-bias/winning_chip_bias_diagnosis_plan.md) — 赢面 chip 偏差事件记录

## 验证

date=20260515 samples=19 window=80
turnover aligned: 19/19  resist aligned: 19/19
Saved: E:\PycharmProjects\OSkhQuant1.3acktest_outputerify_turnover_resist_align_20260515.csv
