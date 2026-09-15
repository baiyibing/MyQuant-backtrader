# Next heavy slices（头脑风暴续 · 2026-09-15）

- 日期：2026-09-15
- 状态：队列草案（H1–H13 软卫生已收口后的 **重活** 顺序）
- 父：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)
- 边界：[plan-h13-cyq-tr-boundary-2026-09-15.md](plan-h13-cyq-tr-boundary-2026-09-15.md) · [chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md) §D/§E

软队列 H1–H13 已覆盖 docs/CLI/L2 fence/CI gates/list-quality/chip inventory/CYQ–TR 边界。下列为 **继续 brainstorm / 开片** 的有序重活；**不是**已批准的实现承诺。

## 有序队列

| 序 | ID | 主题 | 切片意图 | 明确不做 |
|----|----|------|----------|----------|
| 1 | **D1** | D（chip hotpath） | **Profile** 本仓 `minute_chip_distribution` / `hybrid_chip_distribution`（及 `qlib_cost.cyq` 短窗热核）；产出数字与是否值得 numba/Rust offload 的判据 | 不复刻 MyQuant 日频 CYQ feeder；不改卖点；非 full Rust rewrite 除非 profile 证明 |
| 2 | **C soft+** | C（list-quality） | 在 H9 之上 **加深** list-quality（更多直方图 / overlap / 目录健康检查；仍吃契约 CSV） | **非** run-manifest hard；不接 MyQuant manifest 消费 |
| 3 | **run-manifest hard** | 跨仓契约 | 本仓消费 `myquant.run-manifest/1`（若产品需要） | **仍延期**；另开片；见 [myquant-progress-sync-2026-09-13.md](myquant-progress-sync-2026-09-13.md) |

## 仍开放、未排入上表

- 主题 A 更重：分钟卖环 / 更大 unify（勿 big-bang merge 日线与分钟卖书）
- 主题 E/F：湖门禁进 CI、更重 path/lake 契约（当前 CI 保持 data-free）
- Inventory §D 其它 later offload（随 D1 数字再切）

## 禁区（继承 backlog）

改 6/8 卖点、重开 `--asof`、PortAna 定胜负、本仓复刻 LEBS/真栈、缺行 fail-closed→跳过、Cerebro 物理删除、Cursor CloudAgent、**本仓复刻 MyQuant CYQ feeder**。
