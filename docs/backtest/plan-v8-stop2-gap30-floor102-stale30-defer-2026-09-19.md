# Plan：止损 2% + 峰差 30 分钟 + 6/10 保底 + 僵持 30 + 涨停顺延

> **日期**：2026-09-19
> **状态**：✅ **已落地并已跑分钟 5 亿**。目录 `_v8_stop2_gap30_floor102_stale30_defer`（489,758,066.92 / −2.05%）。未覆盖 `_v8_stop10_gap15_floors_stale30_defer` / `_v8_stop10_keep50_floor110_defer` / `_v8_stop20_tp10_floor102_cyb_defer` / `_v8_stop10_tp10_firstonly` / `_v8_stop10_tp10_reserve`。
> **风险档**：L2（卖点数字；峰差改 `PEAK_GAP_MIN`；成交核不改）
> **基线书**：stop10-gap15-floors-stale30-defer，产物 `_v8_stop10_gap15_floors_stale30_defer`（502,824,048.77 / +0.56%）

---

## 0. 一句话

只做首笔。止损 2%。峰值判定延时 30 分钟。[6%, 10%) 保底 ×1.02，≥10% 离场线 max(×1.10, 买价+50%涨幅)。满 30 日未触发则平仓。涨停当天不评，次日再判断。无 4–6% 保底。

---

## 1. 确认人原话

| 原话 | 锁定 |
|------|------|
| 止损 2%（T+1） | `STOP_PCT=0.02` |
| 峰值判定延时 30分钟 | `PEAK_GAP_MIN=30`。同会话创新高后 30 分钟内不评止盈/保底；隔夜/午休 gap&lt;0 视为满足 |
| [6%, 10%) 保底 ×1.02 | 峰值 `[6%, 10%)` 且现价 ≤ 买价×1.02 → `trail:band:6_10` |
| ≥10% 离场线 = max(买价×1.10, 买价+50%×涨幅) | `trail:max110_50` |
| 满 30 日未触发平仓 | `n_days≥30` → `force_sell:stale`（日线挂次日开盘） |
| 全市场涨停当天不评、次日再判 | `DEFER_LIMIT_UP=True`，不是开板必卖 |
| 只做首笔；上证十日线下方仍开新仓 | `ALLOW_ADD=False`，`INDEX_GATE_ON=False` |
| （未再写 4–6%×1.01） | 去掉 `FLOOR4` / `trail:band:4_6` |

---

## 2. 落地目录

`_v8_stop2_gap30_floor102_stale30_defer`

勿覆盖 `_v8_stop10_gap15_floors_stale30_defer` 及更早归档。

---

## 3. 落地

2026-09-19 确认人「修改后执行」后已换成上表。分钟 5 亿退出码 0：`backtest_output/csv_minute_v8_20251023_20260909_v8_stop2_gap30_floor102_stale30_defer/`。期末净值 **489,758,066.92 / −2.05%**，最大回撤 −2.79%。买入 4305、加仓 0、`skip_held` 176、止损 3155、锚定回撤 1133、强制 6、止盈 0、开板 0、`skip_cash` 0。相对上一包 gap15-floors（+0.56% / 止损 1007）止损笔数约 3 倍，净值转负。未覆盖既有归档。
