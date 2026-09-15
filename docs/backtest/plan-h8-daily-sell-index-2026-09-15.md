# H8：日线卖出环 DatetimeIndex / searchsorted 微优化

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)（软扩展；H1–H7 已收口）
- 相关：[plan-h5-daily-mark-micro-2026-09-15.md](plan-h5-daily-mark-micro-2026-09-15.md)、[plan-vectorized-hotpath-offload-2026-09-15.md](plan-vectorized-hotpath-offload-2026-09-15.md)
- 主题：**A**（H5 Grok 延期的卖出环 `.loc` / `index < day`）

## 目标

对日线 `simulate()` **卖出环**（及共用的 chase/pool quote 闭包）做不改成交语义的小步索引微优化：用有序 `DatetimeIndex.searchsorted` + `iloc` 取代每日 `day in index` / `.loc[day]` / `df.loc[df.index < day]` 布尔切片。公共 `simulate` API 不变。

## 静态热点（本切片）

| Site | Shape | Evidence |
|------|--------|----------|
| `csv_daily_backtest.simulate` 卖出环 | 日循环 × 持仓 code：`.loc[day]` + `index < day` 掩码拷贝 | H5 plan / Grok Issue 2 明确 defer |
| 同日 `_chase_quotes_for` / `_pool_quote_for` | 同一 `.loc` / `< day` 模式 | 与卖出共用 helper 则一并换，语义同构 |

成功不要求全市场湖 NAV；synthetic microbench + 既有 golden 即可。

## 安全目标（本切片采纳）

1. 抽出 `day_bar_and_prev_closes(df, day) -> Optional[tuple[Series, list[float]]]`：
   - `day` 不在 index → `None`（等同原 `day not in df.index`）
   - `day` 为首根 → `None`（等同原 `prev_rows.empty`）
   - 否则返回当日行 + **严格早于 day** 的 close 列表（等同 `df.loc[df.index < day]["close"].astype(float).tolist()`）
2. 卖出环与 chase/pool quote 闭包改用该 helper；**不改** `_sell` / limit-down defer / strategy books / 6/8 语义。
3. Microbench：`scripts/research/bench_daily_sell_index.py`（naive `.loc` vs searchsorted；输出值相等）。
4. 单元：helper 与 naive 路径 parity；既有 `test_csv_daily_backtest*.py` 绿。

## 明确不做

- 不改 fill/sell reasons、跌停顺延、策略书（6/8 等）
- 不重写日线卖出引擎；不合并日/分钟 `simulate()`；不用 Cerebro；无 LEBS；无 Cursor CloudAgent
- 不强制改 `market_close_mark` 的 halt 路径（H5 Grok Issue 1 仍可后续；本切片以卖出环为主）
- 不做投机性全表日历预计算 / 跨日 cursor（无更强 profiling 前 defer）

## 交付

1. 本 plan
2. `day_bar_and_prev_closes` + daily sell / chase / pool 接线
3. `scripts/research/bench_daily_sell_index.py`
4. pytest：`csv_daily*` + `research_face` + 新 parity
5. backlog 软扩展 H8；注明主题 A–F 仍开放
6. Grok → `docs/architecture/reviews/2026-09-15/h8-daily-sell-index/grok.md`；修有效 🔴；不 push

## 完成定义

- 卖出 / chase / pool 成交与改前一致（既有 golden）
- Bench 可跑且 naive vs new 值相等；Grok 无有效 🔴
