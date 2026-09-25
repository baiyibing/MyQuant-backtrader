# 计划：资金管理模式与策略族配对显式化（2026-09-25）

> **状态**：已人裁方向（"几种策略 × 几种资金管理，然后配对，不要过度设计"）；本 PR 实现最小配对。人裁合入生效。
> **起因**：2026-09-25 实验事故——复刻 qlib topk 锚（`replay_2025_8a061ea4_50n5_stag15`，+103.83%）时漏 `--daily-quota 100000000`，topk 书吃到 stock_pool 血统的 100 万默认配额，首日部署 9488 万 → 570 万，复跑只剩 +6.90%。逐笔 diff（首笔同价、份额 60,500 vs 600）+ 补旗标复跑（+102.25%，残差 1.58pp = ST 活表 9/17 后修订）定位为**配对缺失**，非代码回归、非数据漂移。

## 1. 资金管理就三种（不新增）

| 模式 | 语义 | 既有载体 |
|------|------|---------|
| **A 配额制** | 日额度 ÷ 当日名单均分 | `sizing=daily_quota`，默认 1,000,000/日（`csv_common.DEFAULT_DAILY_QUOTA`，stock_pool 系遗产） |
| **B 单票预算** | per_name 每码预算 | `sizing=per_name` + `--name-budget`（8.x 等） |
| **C qlib 现金部署** | `min(日额度,现金) × 0.95 ÷ n_buy`（#87 的 risk_degree） | topk 族；此前**要求显式传 `--daily-quota=现金` 才成立**（本次事故的坑） |

## 2. 配对表（本 PR 固化）

| 策略族 | 默认模式 | 显式覆盖 |
|--------|---------|----------|
| topk_dropout / topk_score_exit（qlib 联合书） | **C：日额度 = `--cash-total`** | `--daily-quota` |
| 其余全部（stock_pool 系 version 书、Mode A/B、v7/v9/v10/v11/12、8.x） | A 或 B 维持现状 | `--daily-quota` |

实现：`resolve_daily_quota(strategy, requested, cash_total=…, fallback_quota=…)`——显式旗标优先；否则 topk 族 → cash_total，其余 → 1,000,000。CLI `--daily-quota` 默认值从 1,000,000 改为 **None**（未传时按族解析）。

## 3. 透明化（事故教训）

- summary 回显新增 `daily_quota=<解析后的值>`——今天下午的混淆之所以可能，正是因为这个决定性参数不在回显里。
- topk HELP_LOCK 补"资金模式配对"段。

## 4. 回归锚

1. 本 PR 合入后，`csv_daily_backtest.py --strategy topk_dropout …`（**不带** `--daily-quota`）应复现 2026-09-25 实测 **+102.25%**（同输入栈；对照 9/17 锚 103.83%，残差 = ST 活表修订，见 §起因）。
2. 任一 stock_pool 系书（如 version8）不带旗标，行为与合入前逐字不变（默认仍 1,000,000/日）。
3. 单测：`test_resolve_daily_quota_*`（配对三向 + 显式覆盖）+ CLI 默认 None。

## 5. 受影响的既有产物（迁移说明）

9/22 oral4 批（分钟六本 + 日线闸梯 + `oral4_stag15`）与 9/21 `csv_daily_topk_dropout_qlib50n5_c5f4bccd` 烟测均在**旧默认（100 万）**下跑出，属 C 模式饿死状态，其数字不能当 qlib 对齐口径引用；如需引用按本 PR 默认重跑。

## 6. 不做（明确边界）

- 不建独立"资金管理模块/注册表"（人裁：不过度设计）；配对就是本 PR 的解析函数 + 配对表。
- 不动 `csv_simulate_loop` 的 sizing 公式、不动 `DEFAULT_DAILY_QUOTA` 常量、不动 ration/name_budget 语义。
- 不改 joint_return（冻结回放线 sizing 另属其合同）。

## 7. 维护

- 起草：zcode（4090 机）· 2026-09-25 · 实验证据链见本仓 oral4/verify/镜像 out 目录与当日会话记录。
