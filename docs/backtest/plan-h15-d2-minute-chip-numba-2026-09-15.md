# H15 = D2：numba / 向量化 `minute_chip_distribution`

- 日期：2026-09-15
- 状态：已完成（语义锁 + 可选 numba；hybrid/curpdf/cumpdf leave；Grok 核无有效 🔴；已开 PR）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md) · [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)（D2）
- 前置：H14/D1 [plan-h14-d1-minute-chip-profile-2026-09-15.md](plan-h14-d1-minute-chip-profile-2026-09-15.md) · [chip/h14-d1-minute-chip-profile-results-2026-09-15.md](chip/h14-d1-minute-chip-profile-results-2026-09-15.md)
- 主题：**D2 chip offload**（本仓 minute 路径；**非** MyQuant CYQ feeder；**非** Rust）

## 目标

按 D1 判据：对 `oskh_factors.chip.core.minute_chip_distribution` 增加 **可选 numba 热核**（默认仍 Python 参考路径），与 Python 参考在 fixtures 上 **bit-close 对拍**；bench 对比 python vs numba。hybrid / `calc_curpdf` / `calc_cumpdf` **leave**。

## 交付

1. 本 plan
2. `oskh_factors/chip/core.py`：`minute_chip_distribution_python` 参考；numba kernel；`minute_chip_distribution(..., use_numba=)` + env `MINUTE_CHIP_BACKEND=numba`（仿 `scan_held_day` / `CSV_SCAN_HELD_DAY_BACKEND`）
3. `tests/test_minute_chip_numba_parity.py`（无 numba 时 skip）
4. `scripts/research/bench_minute_chip_hotpath.py`：有 numba 时对比 python vs numba
5. Backlog **H15 ✓**；next-heavy D2 ✓ → next **C soft+**；inventory §D 刷 minute 行为
6. Grok → `docs/architecture/reviews/2026-09-15/h15-d2-minute-chip-numba/grok.md`；修有效 🔴；**push + PR → master**

## 门禁（与 H6 / scan_held_day 对齐）

| 开关 | 行为 |
|------|------|
| 默认 / `use_numba=False` / `MINUTE_CHIP_BACKEND=python` | Python 参考 |
| `use_numba=True` 或 `MINUTE_CHIP_BACKEND=numba`（或 `jit`） | numba（若可用）；否则回落 Python 并保持可测 |

不把 numba 设为默认后端。

## 明确不做

- 不改卖点 / 不改 hybrid / curpdf / cumpdf 语义
- 不 Full Rust rewrite / 新 PyO3；不复刻 MyQuant CYQ / `winner_ratio` feeder（H13）
- 不删 Cerebro；不扩 L2；无 Cursor CloudAgent；无 F 湖全市场跑

## 完成定义

- Parity 绿（有 numba）；bench 打印两侧 ms/call；文档/backlog/inventory 同步；Grok 无有效 🔴；分支已 push 且 PR → master

## 跑法

```bash
python scripts/research/bench_minute_chip_hotpath.py
python -m pytest tests/test_minute_chip_numba_parity.py -q
# host tip: prefer the project vanna312 interpreter when available
```
