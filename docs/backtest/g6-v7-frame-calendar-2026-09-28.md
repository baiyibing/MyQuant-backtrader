# G6 · v7 frame-map 缺省日历合同（2026-09-28）

Human 单独 GO；仅修 `simulate_v7` API 边界。选择并冻结 **frame 日期构造**，不选强制显式日历。依据：[审计 §G6](industry-gaps-bt-2026-09-28.md#g6v7-dataframe-api-在未给日历时可能只跑名单日m)、[D23 X-11](../reviews/2026-09-25-minute-engine-review/README.md)。本 PR 勿合。

## 冻结合同

当 `_is_frame_map(minute_bars)` 成立且 `index_days` 为 `None` 或空序列（如 `[]` / `()`），日历为 **所有 frame index 中日期的去重并集 ∪ pool 日期**，按日期升序排列，再应用原有 inclusive `start` / `end` 过滤。空 frame 不贡献日期；无行情的 pool 日期仍保留；未持有、未入池的其他 symbol frame 也贡献日期。日期转换沿用 `_as_date`，不填充自然日或猜测交易所会话。

frame 沿用既有输入合同：时间索引与用于切日的 `ymd` / `date` 列（若有）须一致，行保留成交所需的 `hm` / OHLC。此刀不新增任意索引、混合输入或日期列修复适配。构造只读取索引，不把全量 frame 转成 records。

显式非空日期列表仍单独决定日历；`Mapping` 仍先走指数收盘价 gate 分支，包括原有 11 会话预热要求。**空 Mapping `{}` 仍报预热不足**，不被缺省构造吞掉。records 输入仍使用原来的 `sorted(set(minutes) | set(pools))`。标准 CLI 已传 `index_closes`，其加载、参数和调用均未修改。

## 与 records 路径的等价目标

同一组有效分钟数据分别表达为 frame-map 与 records、相同 pool 和其他参数、均未提供显式日历时，两者应访问相同的观测日期与 pool 日期。非名单持仓日因此继续触发既有止损、timer、估值及显式应收到账流程；不改变策略7成交或退出规则。

这不是完整交易所日历：所有 frame 与 pool 都没有的日期不被补出，与 records 缺省路径一致。需要覆盖这些日期的调用方继续传显式日历。合成对照验证 trades、positions、cash、equity_curve；不把此日历修复宣称为所有 frame/records 输入格式或策略收益的全面等价证明。

## 合成验证

`tests/test_v7_frame_calendar.py` 覆盖：

- `None` / 空 list / 空 tuple 下，非 pool 日期的持仓估值与次日止损，frame/records 完整结果对照；现金时序开关两态。
- trial 第十个后续会话 timer 清仓；现金时序开关两态。
- 多 frame、重复/乱序日期、空 frame、pool-only 日期，以及 start/end 单侧、双侧与空区间过滤。
- 显式 list 不吸收额外 frame 日；CLI-shaped Mapping 保持 gate、预热和权威日历，records/frame 两态。
- 仅其他未持有 symbol 有 bar 的付款日仍被访问；现金应收结清且 NAV 守恒，frame/records 对照。

运行（Linux 显式选择已有 vanna312 环境，不隐式使用 system Python）：

```bash
"$OSKH_MERGE_PYTHON" -m pytest -q tests/test_v7_frame_calendar.py tests/test_csv_minute_backtest_v7.py tests/test_v7_cash_chronology.py tests/test_tail_window_v7.py tests/test_strategy7_rules.py tests/test_ashare_simulate_import_fence.py
```

结果：**177 passed**（其中 G6 新增 19 项）。仅合成测试；无 lake / 4090。G7/G8 不实施；G2–G5、TopK、hl/fen、δ*、Cerebro/PortAna 与 joint-return 内核均不重开。
