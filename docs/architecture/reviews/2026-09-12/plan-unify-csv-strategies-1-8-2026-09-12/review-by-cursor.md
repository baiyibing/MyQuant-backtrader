# cursor 对抗综合（host，不计独立票）

评审对象：`docs/backtest/plan-unify-csv-strategies-1-8-2026-09-12.md` **v1**  
三路：dissent-steelman / domain-safety / pattern-evidence（2026-09-12）  
回填：plan **v1.1**

## 1. 主笔让步

1. **「只加两只钩子就接完 3/5」作废。** `take_profit(px,cost,peak,n_days)` 看不见 `hm` / `is_limit_up`。3 要独立保留扫描 + 日线第三成交钟；5 的 14:50 是引擎时钟。
2. **`stop_pct is None` 会炸现引擎**（`csv_daily_backtest.py:430`、`csv_minute_backtest.py:413,433`）。必须先短接再 register 4/5。4/5 禁止走 6/8 的 `None→默认`。
3. **reason 改回 `profit_take:drawdown` 家族。** v1 的 `drawdown:50` 会废掉化石/Rolling/SSOT 的对照货币。
4. **撤回「日线 15:00=已过 14:50」。** 否则每个可卖收盘都 force，+2% 永不当选，买入日挂 pending 会冲破 T+1。日线 5 只留 +2% pending。
5. **策略 4 不新开引擎、不改 6/8 `Position`。** 卖点走卖槽，但不得叙述成止盈公式。SMA 预载按 **交易日 ≥10（实现 11）**，不靠 `WARMUP_DAYS=10` 日历。
6. **`csv_pool` 不得 `pool_dir=None` 回落 `stock_pool/`。** 7 空 CSV 仍进 map（保指数日历）。6/8 不换用 v7 `_as_datetime` 建索引。
7. **`limit_pct` 本轮只搬家。** 北交/ST 声明不建模，不 silently 改 6/8/7 热路径档位。
8. **实施序：引擎短接 → register → names 元组。** 文档书单不随切片 A 漂。1–5 `peak_gap_min=0`。开板收盘必须查跌停；`reserved` 压过 20% 目标。

## 2. 未让步

- 1–8 这轮都接到向量化（不是只做 6/8/7）。
- 7 不进 BOOKS；不拷 LEBS/MockQMT；不改 `presets.py`。
- 不删除 Cerebro；化石门留切片 E。
- 本轮不改 6/8 停牌追买 `pop` / 净值标成本。
- 本轮不把北交改成 30%。

## 3. 勘误表（已回填 v1.1）

| 对抗 | 回填 |
|------|------|
| 三路：None 止损炸引擎 | U-R3 |
| 三路：5 的 14:50 / 日线 force 自相矛盾 | U-R8 / U-R18 / U-R25 |
| 三路：3 超出可选钩子；pending 互斥；跌停误卖；20% 板 | U-R6 / U-R19 / U-R20 |
| dissent / pattern：SMA 日历 10 天不够 | U-R21 |
| dissent：reason 前缀对照黑洞 | U-R22 / U-R4 |
| 三路：先改 BOOKS 不可逆 | U-R23 / U-R28 |
| 三路：统一 load_pool 误伤 7 | U-R24 / U-R10 |
| domain：北交/ST | U-R12 声明不建模 |
| domain：停牌 | U-R27 声明不改 |
| 三路：市场层叶子 / 6/8 日历 | U-R11 |
| 三路：peak_gap 15 误伤 1–5 | U-R17 |
| dissent：追买不过 gate | U-R26 |

## 4. 结论

v1 按原文 fan-out 会让评审员在「两只钩子」假类比上空转。v1.1 已拆开 1/2、3、4、5、7 五条落点，并锁实施序。对抗不计票。下一步 classic fan-out（codex + Cursor Kimi + cursor:auto + claude），host 综合 `merge-consensus.md`。
