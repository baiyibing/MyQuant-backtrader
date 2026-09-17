# 模式 B · 宿主跑数短记（统一卖出规则网格，切片 E；待回填）

> **模板日期**：2026-09-17；实际运行日期：TBD。
> **状态**：⏳ **宿主未跑**。本文件是空白模板，不是 E 完成记录。
> **runbook**：[host-runbook-unified-exit-modeb-2026-09-17.md](host-runbook-unified-exit-modeb-2026-09-17.md)；A–D 实现已合 PR #95（`8db98de`）。
> **本次代码 tip / 机器 / 内存**：TBD。
> **数据版本 / resolver 路径 / 缓存 meta**：TBD；预期缓存 key `minute_none_20251013_20260909`，实际 hit：TBD。
> **命令 / 起止时间 / 退出码 / 耗时 / 峰值内存**：TBD。
> **口径**：P1=A 窄网格；none 日线 close 买入、分钟 high/low 触发、分钟 close 成交；11 亿基数。Mode A/B 不混排。

## 1. Sanity 对照（待跑）

| 项 | 核对口径 | 实测 | 判定 / 差异原因 |
|----|----------|------|-----------------|
| 名单实例 / 跳过买入 / 实开 | none 买入域；与 A 按实例键追差 | TBD | TBD |
| distinct 实开码 / 分钟覆盖 / 缺码 | 本次 B 码集，不复用 A 覆盖结论 | TBD | TBD |
| 缓存 | warmup 超集 key；hit | TBD | TBD |
| 网格 / 锚线 | 排名 19 行；四锚线 | TBD | TBD |
| 受冻 / 期末估值 / delist_zero | Q12 / Q33；未平仓不强卖 | TBD | TBD |
| 峰值并发资金 | 触 11 亿须显著标记 | TBD | TBD |
| 分钟成交 / 缺 K / 跌停 | Q7 / Q32 / Q36；末 session close；缺分钟顺延 | TBD | TBD |
| N=1 / oracle | Q37 不要求等价；Q38 仅排除跌停分钟 close | TBD | TBD |
| 除权缩放 | Q29 cost/peak ×k、shares ÷k；无现金红利 | TBD | TBD |

## 2. 结果摘要（仅 Mode B；全部待回填）

**四锚线**：

| 锚 | 总收益率 | 每实例均值 | 胜率 | 最大回撤 | 平均持有 |
|----|----------|------------|------|----------|----------|
| anchor_hold_end | TBD | TBD | TBD | TBD | TBD |
| r1_n1 | TBD | TBD | TBD | TBD | TBD |
| oracle（分钟可成交 close 事后上界） | TBD | TBD | TBD | TBD | TBD |
| delist_zero | TBD | TBD | TBD | TBD | TBD |

**Top 5**：

| 名次 | 参数标签 | 总收益率 | 峰值并发资金 | 备注 |
|------|----------|----------|--------------|------|
| 1 | TBD | TBD | TBD | TBD |
| 2 | TBD | TBD | TBD | TBD |
| 3 | TBD | TBD | TBD | TBD |
| 4 | TBD | TBD | TBD | TBD |
| 5 | TBD | TBD | TBD | TBD |

**稳健性四件套**：

| 项 | 结果 | 解读 |
|----|------|------|
| 半窗（19 行窄网格勿仅看 top20 交集） | TBD | TBD |
| 邻域平台（仅本次窄网格范围） | TBD | TBD |
| 板块 + 按月 | TBD | TBD |
| 次日开盘买（top5 + r1_n1） | TBD | TBD |

## 3. 研究结论（模式 B）

TBD。与 [Mode A 短记](unified-exit-modea-host-note-2026-09-17.md) 仅作独立文字比较：价域、入场实例集合及分钟退出差异须先说明，不拼接 A/B NAV / 总收益率排名表，不预设 B 优于 A。

## 4. Nits / 异常与 STOP 项

| 问题 / 样本 | 影响 | 处置 / 是否阻挡结论 |
|-------------|------|---------------------|
| TBD | TBD | TBD |

TBD 表示尚未检查，不表示「无异常」。

## 5. 后续建议与 E 完成证据

后续研究建议：TBD（宿主结果出来后再写，不在此重开 A–D 编码）。

| 证据 | 宿主实际路径 / 留痕 |
|------|---------------------|
| ranking.csv | TBD |
| instance_detail_top.csv（含 sell_hm） | TBD |
| summary.json（含 robustness 四件套） | TBD |
| 命令日志 / cache hit / 墙钟与内存 | TBD |

- [ ] 宿主运行结束，报告完整，sanity 与异常已说明。
- [ ] 本短记已回填真实数字与运行信息；后续单独确认 E 完成。

**本 docs PR 不勾选以上两项；数字产物不入库。**
