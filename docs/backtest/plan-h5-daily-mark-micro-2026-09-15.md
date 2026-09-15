# H5：日线 mark / 循环微优化

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)
- 相关：[plan-vectorized-hotpath-offload-2026-09-15.md](plan-vectorized-hotpath-offload-2026-09-15.md)

## 目标
对日线（及共用骨架）**净值 mark** 做不改成交语义的小步微优化；有 plan + microbench/测试。不重写日线卖出引擎，不改策略书。

## 静态热点（本切片）

| Site | Shape | Evidence |
|------|--------|----------|
| `csv_simulate_loop.append_equity_and_eod_marks` → `last_close_mark` | 每个持仓 lot 一次 pandas `day in index` / `.loc[day]` 或 `df.index < day`；同 code 多 lot 与 EOD_MARK 二次遍历重复 | 静态：每日 `simulate()` 末尾；与持仓 lot 数成正比 |
| `csv_daily_backtest.simulate` 卖出环 `bars[code].loc[...]` | 日循环 × 持仓 code 的 `.loc` / `index < day` | **本切片不改**（卖出语义风险）；留 backlog / 后续 golden |

成功不要求全市场湖 NAV；synthetic microbench 即可。

## 安全目标（本切片采纳）

1. **按 code 缓存当日 mark close**：同 code 多 lot 与 equity+EOD 两次遍历只算一次 data-driven close；无 bar / 无 prior 时仍按 lot 用 `pos.cost` fallback（与现 `last_close_mark` 一致）。
2. 抽出 `market_close_mark(df, day) -> Optional[float]`；`last_close_mark` 保持薄封装，公共 API 不变。
3. Microbench：`scripts/research/bench_daily_mark.py`（仿 `bench_scan_held_day`）。
4. 既有 golden：`test_halt_day_equity_uses_last_close_not_cost` 等；可加多 lot 同价断言。

## 明确不做

- 不重写日线卖出环 / 不改 fill·sell 语义
- 不改策略书（6/8 等）
- 不合并日/分钟 `simulate()`；不用 Cerebro；不 push；无 Cursor CloudAgent
- 不做投机性 prev_close / calendar 全表预计算（无 golden 前 defer）

## 交付

1. 本 plan
2. `market_close_mark` + `append_equity_and_eod_marks` 按 code 缓存
3. `scripts/research/bench_daily_mark.py`
4. pytest：`csv_daily*` + `research_face`
5. Grok → `docs/architecture/reviews/2026-09-15/h5-daily-mark-micro/grok.md`；修有效 🔴
6. backlog H5 ✓；hotpath plan 补一句 daily mark 小步

## 完成定义

- Mark 数值与改前一致（halt / zero-volume / EOD_MARK）
- Bench 可跑；Grok 无有效 🔴
