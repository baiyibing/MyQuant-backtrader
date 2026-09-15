# Next heavy slices（头脑风暴续 · 2026-09-15）

- 日期：2026-09-15
- 状态：队列草案（H1–H13 软卫生 + **H14/D1 ✓** + **H15/D2 ✓** + **H16/C soft+ ✓** 后的 **重活** 顺序）
- 父：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)
- 边界：[plan-h13-cyq-tr-boundary-2026-09-15.md](plan-h13-cyq-tr-boundary-2026-09-15.md) · [chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md) §D/§E
- D1 结果：[chip/h14-d1-minute-chip-profile-results-2026-09-15.md](chip/h14-d1-minute-chip-profile-results-2026-09-15.md) · [plan-h14-d1-minute-chip-profile-2026-09-15.md](plan-h14-d1-minute-chip-profile-2026-09-15.md)
- D2 计划：[plan-h15-d2-minute-chip-numba-2026-09-15.md](plan-h15-d2-minute-chip-numba-2026-09-15.md)
- C soft+ 计划：[plan-h16-c-soft-list-quality-2026-09-15.md](plan-h16-c-soft-list-quality-2026-09-15.md)

软队列 H1–H13 已覆盖 docs/CLI/L2 fence/CI gates/list-quality/chip inventory/CYQ–TR 边界；**D1（H14）+ D2（H15）+ C soft+ list-quality deepen（H16）已完成**。下列为继续 brainstorm / 开片的有序重活；**不是**已批准的实现承诺。

## 有序队列

| 序 | ID | 主题 | 切片意图 | 明确不做 |
|----|----|------|----------|----------|
| 1 | **D1** ✓ | D（chip hotpath） | Profile 本仓 `minute_chip_distribution` / `hybrid` / `cyq` 短窗；合成 bench + 排名 | 不复刻 MyQuant feeder；不改卖点；无语义变更 |
| 2 | **D2** ✓ | D（chip offload） | **H15**：numba/向量化 `minute_chip_distribution`（语义锁 + 对拍；Python 默认）；hybrid/curpdf/cumpdf **leave** | 非 full Rust rewrite；非 MyQuant CYQ feeder；不改卖点 |
| 3 | **C soft+** ✓ | C（list-quality） | **H16**：JSON/markdown；top-N；day-over-day churn；invalid calendar stems（仍吃契约 CSV） | **非** run-manifest hard；不接 MyQuant manifest 消费 |
| 4 | **run-manifest hard** | 跨仓契约 | 本仓消费 `myquant.run-manifest/1`（若产品需要） | **仍延期**；另开片；见 [myquant-progress-sync-2026-09-13.md](myquant-progress-sync-2026-09-13.md) |

## D1 → D2 判据（摘要）· D2 / C soft+ 已落地

- `minute_chip_distribution` ~**50.7 ms**/call（80×240）；cProfile：Python `for` + 每 bar `np.zeros` → **D2 = numba 优先**（**H15 ✓**）
- `hybrid` ~**1.0 ms**；`calc_cumpdf` 已 numba ~**0.02 ms** → **leave**
- Rust：暂不（非生产 TR SSOT）
- **C soft+ / H16 ✓**：list-quality deepen（JSON/md、top-N、churn、日历 stem）
- 下一项队列头：**run-manifest hard**（仍延期）

## 仍开放、未排入上表

- 主题 A 更重：分钟卖环 / 更大 unify（勿 big-bang merge 日线与分钟卖书）
- 主题 E/F：湖门禁进 CI、更重 path/lake 契约（当前 CI 保持 data-free）
- Inventory §D：hybrid / `calc_curpdf` 短窗仍 **leave / later**；minute 已 optional numba

## 禁区（继承 backlog）

改 6/8 卖点、重开 `--asof`、PortAna 定胜负、本仓复刻 LEBS/真栈、缺行 fail-closed→跳过、Cerebro 物理删除、Cursor CloudAgent、**本仓复刻 MyQuant CYQ feeder**。
