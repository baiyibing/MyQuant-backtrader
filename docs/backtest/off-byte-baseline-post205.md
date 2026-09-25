# OFF 字节基线与 #205 参数回显

`tests/fixtures/off_byte_baseline_eff77f3.json` 继续保存原始 eff77f3
的字节和账户快照，不覆盖、不重新命名。SHA-256 为
`3bfe51b6d3e20b665c3fed0449ebf8569988022719da275b7fcc9635a9988c6c`。

## master 为什么红

父链为 `eff77f3 → 6c438d8 (#205) → fdb5158 (#202)`。
[#202 成功 CI](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/36147213447)
测试的是 `1e50ee12` 合入 eff77f3 的临时 merge `a17dbd8`，未包含 #205。
随后 #205 先合入，新增 `SimState.stats.daily_quota` 用于 summary 回显；
#202 的历史 structured 比较因这一新增键在 master 出现 76 failed / 3 passed。
原测试先检查 production/library CSV hashes 和 fill_counts，再检查 structured；
此次独立重跑也验证了这些比较，未依赖断言短路顺序。

## 历史核实

在三个提交的原样生产源码上运行同一份 fdb5158 capture harness：
19 本 × 日线/分钟 + 独立 v7 分钟 = 39 组，省略开关/显式关闭各一遍。
共 234 captures、468 份生产 CSV；同时核对 library serialization。

| 对比 | trades/equity 原始字节、两套 SHA-256、fill_counts | structured |
| --- | --- | --- |
| eff77f3 重生成 vs 原 golden（两种 OFF） | 全相同 | 全相同 |
| eff77f3 → 6c438d8（两种 OFF） | 全相同 | 每个非 v7 组合仅新增 `stats.daily_quota = 1000000.0`；v7 无变化 |
| 6c438d8 → fdb5158（两种 OFF） | 全相同 | 全相同 |
| 每个提交 omitted → explicit-off | 全相同 | 全相同 |

现金、持仓、成交、权益曲线、费用及所有既有 stats 均不变。
唯一新增键来自 [#205](https://github.com/baiyibing/MyQuant-backtrader/pull/205)
的 `init_sim_state`：日线/分钟 simulate 将已有 quota 传入并记录。
summary 的 quota 回显不属于 structured 或 trades/equity CSV。
该矩阵显式传入 1M quota，直接调用 simulate；不经过 CLI 的资金模式解析。
#205 对未显式指定 quota 的 topk CLI 默认行为确有改变，本结论不覆盖该场景。

## 比较契约（方案 B）

`post205_expected_case` 仅在历史 expected 的副本中为非 v7 添加
`structured.stats.daily_quota = 1_000_000.0`，并先断言历史 stats 不含此键。
随后仍全量比较 structured：新字段必须存在且等于固定值，其它新增字段、
所有旧字段漂移仍失败。v7 不作适配。CSV 两套哈希和 fill_counts 全量比较不变。
pytest 和生成器 `--check` 共用该规则；原始生成的 HEAD/禁止覆盖保护保留。
此方案保留与 eff77f3 的直接证明，避免复制近乎相同的新 golden。

复查入口：`tests/test_off_byte_baseline.py`（79 项）及
`scripts/research/generate_off_byte_baseline.py --check`。
完整逐组旧→新字段表、三版本快照、原始 CSV 和运行日志归档于
`/home/box/agent-data/bt-minute-fix-2026-09-25/baseline205/`，见
`root-cause.md`、`comparison.json`、`capture-manifest.json`。
