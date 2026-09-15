# Merge Consensus：plan-money-modes-v8-pername 评审裁决（2026-09-16）

## 评审方

| Host | 角色 | 结论 | 发现 |
|------|------|------|------|
| zcode-facts | pattern-evidence / 事实锚点核查 | READY-AFTER-FIXES | 3🔴 / 7🟡 / 7🟢 + 锚点勘误表 |
| zcode-domain | domain-safety + dissent-steelman | READY-AFTER-FIXES | 6🟡 / 2🟢 + 人裁建议 P1–P4 |

证据裁决（非投票）：每条采纳/驳回均以下列证据链为准。

## 双方一致

- 双模式框架方向正确（策略书级 sizing、M-R5 逐字节回归锁可行——tests 无全量快照断言）。
- 无破坏成交核（E-R\*）的发现；v7 对照与差异区分准确。
- P2 取消加仓（含跌停尾部 -34%~-51% 量化理由）。

## 裁决清单

| # | 发现（来源） | 裁决 | 回写 |
|---|--------------|------|------|
| 1 | 🔴1 v8 止损双真源：Cerebro `ProfitStrategy.py:760` 预设是测试真源，仅改 strategy8_rules 动不到 :313 等测试（facts） | **升级为人裁，用户已裁：全局退 Cerebro** → 新开 [plan-cerebro-retire-2026-09-16.md](../../../../backtest/plan-cerebro-retire-2026-09-16.md) 先行；P5 消解 | P5 重写；§1#2 加 ⚠️ 注 |
| 2 | 🔴2/🔴3/🟡4 测试清单漏 3 个文件（facts） | 采纳 | §5-B、§7 补全 |
| 3 | 🟡1 skip_cash 名单序偏差（现实池代码升序、早期窗 ~45% 买不进）+ 观测面不足（domain） | 采纳：保留 skip 语义 + 偏差声明 + skip_cash_notional + 逐日 bought/skip/宽度表；新 P4 | M-R2、切片 D |
| 4 | 🟡2 chase 不预冻结 + 弃单终态声明 + chase_buy_fail 拆分（domain） | 采纳 | M-R3、§8 |
| 5 | 🟡3 止盈「涨幅」= 峰值涨幅唯一自洽解读 + 日线/分钟时机差距声明（domain） | 采纳：§1 加解读锁定段 + 声明族 | §1、M-R4 |
| 6 | 🟡4 P1 建议翻转：SMALL_ARM 是 20% 时代口径，30% 组合未经业务确认（domain；facts 反对仅基于改动成本） | **分歧呈报**：v1.1 默认翻转为按 docx 去武装，两路意见与恢复成本均入 P1，最终人裁 | P1 |
| 7 | 🟡5 per_name 须 hook 层强制 allow_add=False + 单测硬锁（domain） | 采纳 | M-R3、切片 A/B |
| 8 | 🟡6 混 sizing 对照 + maybe_compare_daily caption 误归因（domain） | 采纳：新 M-R8 + P3 | M-R8、切片 C/D |
| 9 | 🟢 force-min 非死代码（--name-budget 激活）且 v7 无此行为（domain）+ 单测写法（facts 🟢） | 采纳：措辞修正 + 小预算构造单测 | M-R2、切片 A |
| 10 | 🟡7 P1 备选成本低估、🟡8 stats setdefault、🟡9 chase 无需透传、🟡10 菜单文案、🟢 pre_er1 fixture 禁重生成、🟢 daily_quota_used vestigial（facts） | 采纳 | P1 成本、M-R5、§7、（菜单文案随裁决 1 归 cerebro-retire）、§8 |

## 结论

- plan v1.1 已按裁决回写完毕 → **READY，待人裁 GO（P1–P4；P5 已裁）**。
- 前置依赖：cerebro-retire plan 先行（其自身待人裁 GO）。
- 人裁 GO 后：交接文档 [handoff-money-modes-v8-pername-codex-impl-2026-09-16.md](../../../../backtest/handoff-money-modes-v8-pername-codex-impl-2026-09-16.md) 生效，交 Codex 实施。
