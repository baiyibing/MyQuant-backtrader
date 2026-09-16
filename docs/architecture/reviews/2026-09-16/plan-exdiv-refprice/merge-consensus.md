# Merge Consensus：plan-exdiv-refprice 评审裁决（2026-09-16）

| Host | 结论 | 核心发现 |
|------|------|----------|
| zcode-facts | READY-AFTER-FIXES | 4🔴：pool 买侧第 5 触点遗漏；检测源层级与 survey C2 相反；OSKH_ADJ_FACTOR 不存在；simulate 布线未钉（golden 湖依赖风险） |
| zcode-arch | READY-AFTER-FIXES | 方向 A（修 cost/peak）胜出（0/1 次齐次论证 + 舍入域 + peak 复利三重对抗）；🔴-2 pnl/净值残留未声明（回收上界仅 +35~125 万）；16 条边界向量 T1–T16 |

## 双方一致采纳（v1.1 已回写）

1. 检测门改回 **ex_date_index 主 ∪ 跳变>1e-2 兜底**，k 恒因子行比（PX-4）；否则 145 个噪声日错误缩放。
2. X-R3 全集 = **5 触点**（含 pool 买侧涨停拦截/挂 chase）。
3. **布线锁 `simulate(..., exdiv=None)`**（仅 run() 加载）。
4. cost/peak 落点 = `csv_ledger.rescale_position(pos,k)` 纯函数（定稿）。
5. E-R6 残留三句（跨除权 pnl/净值 (1−k) 失真、v4 SMA 域、噪声带 ≤0.5%）+ 切片 D 预写回收上界 + 三份历史文档「修正前口径」脚注（PX-6）。
6. v7 不接（PX-7）+ 假成交消失断言；k 用行到行 LAG；读窗含 warmup；stats 条件打印。
7. 方向裁决：修参考量（A）而非价格上折（B）——B 在舍入域/peak 复利/成交记账三处劣。

## 结论

plan v1.1 回写完毕 → READY，待人裁 GO（PX-1–PX-7，全部建议「是」）。GO 后开 `feat/exdiv-refprice` 交 Codex；切片 D 完成后放行 v2-D。
