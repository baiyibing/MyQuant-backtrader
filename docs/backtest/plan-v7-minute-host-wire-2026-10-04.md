# version7 分钟 host 接线计划（2026-10-04）

本 PR 仅供四席评审的迁移计划；基线为 #343 后的 `dfa2dc9ada40b2197fac42cf4a884abdbfa35aee`。目标是让分钟 host 调用现有 runner，完整接入金榕元书。Baiyi 要求整本书接线，不能只做局部止盈扫描；这是回测，不新增交易所级规则。

## 现状与接线边界

`backtest/research/minute_bar_scan_host.py::run_simulate` 当前只接受 `csv_strategy_names()` 中的名称，调用 `csv_minute_backtest.simulate`。`version7` 未通过 `csv_strategy_books.register()` 注册；它的 runner 是 `csv_minute_backtest_v7.simulate_v7`。后续实现应让 host 接受 version7（注册或显式入口），分派到该 runner，禁止把 v7 路由到共享 `csv_minute_backtest.simulate`，也不把 v7 规则抄进 host。

4090 机器上数据已经存在。host 尚未接入的输入不等于数据不可用，不能据此跳过 version7。旧 v7 CLI 怎么加载，host 就调用相同的现有 loader；不规划新数据源、湖布局或除权／指数 feeder。

## 复用 `csv_minute_backtest_v7.main` 的加载链

默认接线按原 CLI 的 lake 路径，加载并传入以下六项，再调用一次 `simulate_v7`：

- `pool_days`：`load_pool_days(pool_dir, start, end)`，内部调用 `csv_pool.load_pool_day_map`。池目录必须由 `--pool-dir` 或 `OSKH_TURTLE_POOL_DIR` 提供，不回落 `stock_pool/`；`symbols` 取各日池代码并集。
- `minute_bars`：`_load_cli_bars(pool_days, start, end)` 的第一项；默认调用 `ashare_bars.bars_from_pool` 从湖加载分钟行情。
- `daily_bars`：同次 `_load_cli_bars` 的第二项，即 `bars_from_pool` 返回的 `daily_close`。
- `exdiv`：`ashare_session.load_limit_context(pool_dir, symbols, start, end)` 的第一项，由 `load_exdiv_ratios` 提供，结构为代码 → `{ymd: k}`。
- `names`：同次 `load_limit_context` 的第二项，即 `flatten_pool_names(load_pool_names_by_day(...))` 的最后出现池名称（ST 列）。该 loader **不加载涨跌停价格**。默认传 `names`，`names_by_day=None`；现有可选 `--asof-pool-names` 才单独调用 `load_pool_names_by_day` 并传 `names_by_day`、`names=None`。
- `index_days`：`csv_minute_backtest_v7.load_index_daily(start, end)`，通过 `resolve_index_daily_root` 读取锁定的上证 `000001.SH`、`dividend_type=none` 分区，返回含 11 个预加载交易日的 `{date: close}`，按 CLI 传给 runner。该 loader 内已调用 `build_index_gate` 校验；host 不再加指数构建器或新指数文件，runner 原有 gate 处理保留。空池保留 `main` 的既有日历分支，不另造数据约定。

`_load_cli_bars` 已有尾窗／参与率 volume 分支：调用 `ashare_bars.load_minute_from_lake` 加 `load_daily_closes`。host 不得用新来源替换它；本阶段只接默认路径，不扩展尾窗或参与率功能。资金、起止日期等调用参数沿用现有 CLI／runner 契约。

## 书内职责保持原位

现有签名（省略其他参数）：

```text
simulate_v7(minute_bars, daily_bars, pool_days, index_days=None,
            *, exdiv=None, exdiv_economics=None, names=None, names_by_day=None, ...)
```

日循环中的 `session_prev_close` 按除权系数 k 映射昨收；`session_limit_prices` 按映射昨收 × `(1±band)` 计算并取整到分。买入、加仓、止损、计时器、指数 gate、T+1、涨停跳买与跌停延卖均留在 `simulate_v7`／`strategy7_rules`，host 只负责加载与调用，不重实现。

## 后续实现 PR 的窄验收与排除项

后续只需一个代码 fixture，替身 loader／runner 验证：已注册或显式接入的 version7 host 入口调用 `simulate_v7`，不调用 `csv_minute_backtest.simulate`；调用收到 `load_index_daily` 的 `index_days`，以及 `load_limit_context` 的 `exdiv`、`names`。CI 不要求 4090 真湖。本 PR 不编写或运行测试。

本阶段不含 `topk_app_dropout`、重写 v7 规则、新数据源、交易所级规则；本 PR 不改策略代码、不改 `.py`，只提交此文档并开 Draft PR，不合并。
