# 模式 B · 宿主业务网格 runbook（统一卖出规则网格，切片 E）

> **日期**：2026-09-17
> **状态**：⏳ **宿主未跑 / 待切片 E**。A–D 已合 PR #95（master `8db98de`）；本篇只交付跑数步骤，不代表 E 完成。
> **权威**：[plan](plan-unified-exit-modeb-2026-09-17.md) P1–P5 / Q36–Q38 / cache 补裁；[handoff](handoff-unified-exit-modeb-codex-impl-2026-09-17.md)；[提案](stock-backtest-unified-exit-proposal-2026-09-17.md) Mode B / Q7 / Q12 / Q29 / Q32。
> **前置记录**：[分钟就绪短记](unified-exit-modeb-minute-ready-2026-09-17.md)（smoke 已完成）；**回填位置**：[Mode B 宿主短记模板](unified-exit-modeb-host-note-2026-09-17.md)。

## 0. 硬边界与机器

- 不改湖数据；不改策略书、`*_rules.py` 或成交核。只消费 F 湖，路径经 resolvers；不补名单、不下载行情。
- **P1=A**：只跑默认冠军族窄网格。**P2=A**：业务网格优先高配 / 4090 宿主（约 128G 内存）；约 40G 宿主只用于已完成的 smoke，不据此承诺业务耗时。4090 是机器选择，CLI 无 GPU 开关。
- 分钟 OHLCV 使用 `bar_cache` 加载并驻留进程内存，**不用 Redis**。缓存与数字产物不入库。
- **P4 锁**：Mode A/B 永不混排 NAV / 总收益率表。产出限定在 `backtest_output/unified_exit_modeb/`（可用其下独立运行子目录），报告必须标明价域。
- E = **host-only，非 CI / 实现合入门**；本 docs PR 不跑湖、不勾选 E 完成。

## 1. 前置检查（宿主）

- [ ] 仓库根执行；`git rev-parse HEAD` 留存实际 tip，且包含 `8db98de`（`git merge-base --is-ancestor 8db98de HEAD` 返回 0）。A–D 已合，不重新开编码。
- [ ] vanna312 环境可用；F 湖 `1m/none` 与 `day/none`（磁盘 `period=1d/dividend_type=none`）可达，市场日历和 P3=A 的 `ex_date_index` / `exdiv_map` 数据可读。
- [ ] 现成 `backtest_output/bar_cache/minute_none_20251013_20260909.parquet` 及 `.json` meta 可读，热路径命中 `hit`。迁机时把缓存及 meta 放到指定缓存目录，保留原 key。
- [ ] 确认 `stock_pool` 与窗口；缺 20260525 / 20260605 名单按当天无名单，不补造。
- [ ] 读 [Mode A 宿主短记](unified-exit-modea-host-note-2026-09-17.md)：5061 名单实例、4167 实开实例（2080 distinct 码）、795+99 跳过、9 笔受冻仅作比较基线；不是 Mode B 必须复现的数字。

只读路径检查：

```powershell
D:\anaconda3\envs\vanna312\python.exe -c "from common.infra.data_root import resolve_period_root; roots=[resolve_period_root(p)/'dividend_type=none' for p in ('1m','1d')]; print([(str(p),p.is_dir()) for p in roots])"
```

缓存检查沿用 [smoke 短记 §2–§3](unified-exit-modeb-minute-ready-2026-09-17.md)，只读热加载可用：

```powershell
D:\anaconda3\envs\vanna312\python.exe -c @"
from pathlib import Path
from backtest.research import unified_exit_modea as a
from backtest.research.unified_exit_modeb import load_monitor_bars
sessions = a.load_session_calendar('20251023', '20260909')
codes = {code for code, name, day in a.iterate_pool_entries(Path('stock_pool'), sessions)}
status = {}
bars = load_monitor_bars(codes, '20251023', '20260909', cache_dir=Path('backtest_output/bar_cache'), status=status)
print('cache', status, 'requested_codes', len(codes), 'loaded_codes', len(bars))
"@
```

先确认文件和 meta 存在再热加载；若未命中，记录原因并排查缓存目录 / 码集 / meta，不反复扫湖。`load_monitor_bars` 调用 `warmup_start(start, days=10)`，因此业务窗 20251023–20260909 对应 **`minute_none_20251013_20260909`**。**不要重建字面 `20251023` key**。热检查进程退出后再跑业务，避免同时驻留两份数据。

## 2. 运行默认业务网格

在仓库根 PowerShell 执行，并留存命令、起止时间、退出码、峰值内存与 stdout：

```powershell
D:\anaconda3\envs\vanna312\python.exe scripts/research/run_unified_exit_modeb.py --start 20251023 --end 20260909 --pool-dir stock_pool
```

可选参数以 [CLI 库 `main`](../../backtest/research/unified_exit_modeb.py) 的 argparse 为准：`--cache-dir` 指向已有缓存目录；`--workers` 默认 8，是读取线程数；`--out-dir` 默认 `backtest_output/unified_exit_modeb/`，复跑可指定其下子目录避免覆盖。`--none-root` 默认经 resolver 取不复权日线，通常不传；`--tol` 保持默认。当前 CLI 没有全网格 / GPU / rebuild-cache 开关。

**默认 P1=A 范围（以 `iter_grid` / `run_modeb` 为准）**：

| 项 | 构成 / 数量 |
|----|-------------|
| 冠军族 | r2：X∈{5,7,10}% × Y∈{5,10,∞}% × N∈{8,10}，**18 组**；∞ = 不设止损 |
| `iter_grid` | 18 组 + `anchor_hold_end` + `r1_n1` = **20 项** |
| 运行矩阵 | 再加 `oracle` / `delist_zero` = **22 个标签** |
| 排名 | 18 组 r2 + `r1_n1` = **19 行**；后者也出现在四锚线中，不重复算新组 |
| 四锚线 | `anchor_hold_end` / `r1_n1` / `oracle` / `delist_zero` |

不沿用 smoke 短记的「约 24 组」成本估计，也不套 Mode A 全量 280 / 有效 233 的计数或耗时。

## 3. Sanity 与比较清单

- [ ] `summary.json`：`meta.mode=B`，价域为 **none 日线 close 买入 → 分钟 open 缺口再 close 触价/成交**（high/low 不触发）；窗口正确，名义现金池 11 亿；每笔目标 100 万、整百股、双边佣金 0.1%、无印花税。
- [ ] stdout `n_strategies=19`，四锚线齐全；`n_opened` 与明细按实例键去重后的实开数一致（明细跨策略重复，不能直接数总行数）。记录实开实例数与 distinct 码数，分清两者。
- [ ] 复核 `meta.minute_coverage` 的 requested / covered / missing；smoke 的 2080/2080 属于 Mode A 实开码覆盖，不能代替本次 B 覆盖。缺码 / 无 session 分钟须列原因。
- [ ] 与 A 比较名单装配、实开 / 跳过、受冻及峰值并发。**B 买入价域是 none close，A 是 front close**；封板判断、整百股数量和实开数可能不同，按实例键追差，不强制对齐 4167。A 的 max 904 lots / 9.04 亿仅作基线；B 实测触 11 亿须显著标记，不直接套 A 上界。
- [ ] 抽查明细 `sell_hm` / `sell_price`：生产 session 过滤使用 `hour*60+minute`（570–690 / 780–900），不是 HHMM（#95，`9c39c90`）。买入日不可卖；同分钟先评开盘缺口再评收盘、止损优先；缺口成交用 open，否则用 close；影线（仅 high/low 穿阈）不得成交。
- [ ] **Q7 / Q32 / Q36**：N 按市场交易日推进；实际规则卖出遇跌停则当日阻挡、下一交易日重评。到期无更早成交时用当日最后一根 session 分钟 close；缺尾用实际末根，当日无分钟则顺延，不回退日线 close。
- [ ] **Q37**：B 不要求 r2 N=1 ≡ r1_n1，盘中先触发可不同价；默认窄网格也不含 r2 N=1。勿照抄 A 的 42/42 等价验收。
- [ ] **Q38**：oracle 为「分钟可成交 close 事后上界」，从 T+1 起仅排除跌停分钟 close，同日其他分钟可候选，不模拟更早失败卖出；实际规则仍遵守 Q7。
- [ ] **Q29 / Q12**：除权 cost/peak ×k、shares ÷k，仅 B 模块内执行，现金红利不入账。期末未平仓按最后可得 close 估值，不记强卖；停牌冻仓与 delist_zero 敏感性分列。
- [ ] 通读 B 排名、四锚线与稳健性四件套：半窗、邻域平台、板块+按月、次日开盘买（top5 + r1_n1）。窄网格排名仅 19 行，半窗 top20 交集可能覆盖全部标签，需结合名次和收益变化，不能仅凭交集判「稳定」；邻域结论仅限本次窄网格。

A 短记中的冠军 +1.50%、hold_end −24.36%、oracle +129.64% 是 **A 已有比较基线**，不是 B 预期值或通过门槛。只在独立段落讨论方向 / 差异原因，**不把 A/B 放进同一 NAV 或收益率排名表**。异常未解释前不写完成结论。

## 4. 产物与完成定义

| 产物（宿主保留，不入库） | 核对 |
|------------------------|------|
| `backtest_output/unified_exit_modeb/ranking.csv` | B 的 19 行排名 |
| `backtest_output/unified_exit_modeb/instance_detail_top.csv` | 冠军 + 四锚线明细，含 `sell_hm` |
| `backtest_output/unified_exit_modeb/summary.json` | meta / top20 / anchors / n_opened / n_strategies；稳健性四件套在 `robustness` 内，无独立第四文件 |

若用了运行子目录，短记写实际路径。宿主跑完后回填 [短记模板](unified-exit-modeb-host-note-2026-09-17.md)：实际日期 / 代码 tip / 机器 / 数据与缓存版本 / 命令 / 耗时内存 / sanity / B 独立结果 / 异常与结论。**短记 + 报告产物齐全且异常已说明**，才另行记录 E 完成；本 PR 中短记保持「⏳ 宿主未跑」，所有 B 数字 TBD。
