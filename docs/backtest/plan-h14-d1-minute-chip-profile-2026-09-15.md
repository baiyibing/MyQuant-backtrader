# H14 = D1：本仓 minute / hybrid chip hotpath profile

- 日期：2026-09-15
- 状态：已完成（合成 microbench + 结果注记；Grok 核无有效 🔴；已开 PR）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md) · [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)（D1）
- 主题：**D1 profile only**（本仓 minute/hybrid；**非** MyQuant CYQ feeder）
- 前置：H11 inventory §D later offload · H13 CYQ/TR 边界

## 目标

对本仓 `minute_chip_distribution` / `hybrid_chip_distribution` 及 `qlib_cost.cyq` 短窗热核做 **合成 microbench + 短 cProfile**，产出数字与 **D2**（numba / leave / Rust）判据。不改算法语义；不跑全市场湖。

## 交付

1. 本 plan
2. [`scripts/research/bench_minute_chip_hotpath.py`](../../scripts/research/bench_minute_chip_hotpath.py) — 无湖合成 bench；可选 `--profile`
3. 结果注记：[chip/h14-d1-minute-chip-profile-results-2026-09-15.md](chip/h14-d1-minute-chip-profile-results-2026-09-15.md)
4. Backlog **H14 ✓**；next-heavy 把 D1 标完成、刷新 D2 / C soft / run-manifest
5. Inventory §D 一行指针到本结果（recommendation 仍 later offload，待 D2）
6. README / chip README 短指针
7. Grok → `docs/architecture/reviews/2026-09-15/h14-d1-minute-chip-profile/grok.md`；修有效 🔴；**push + PR → master**

## 明确不做

- 不改 `minute_chip_distribution` / `hybrid` / `calc_curpdf` / `calc_cumpdf` **语义**
- 不在本仓复刻 MyQuant 日频 CYQ / `winner_ratio` feeder（H13）
- 不 Full Rust rewrite / 新 PyO3 API；不删 Cerebro；不扩 L2；无 Cursor CloudAgent
- 不要求 F 湖 / 全市场真实数据跑通

## 完成定义

- Bench 可在无湖环境跑出排名；结果注记含 D2 建议；文档/backlog 同步；Grok 无有效 🔴；分支已 push 且 PR → master

## 跑法

```bash
python scripts/research/bench_minute_chip_hotpath.py
python scripts/research/bench_minute_chip_hotpath.py --profile
# host tip: prefer the project vanna312 interpreter when available
```
