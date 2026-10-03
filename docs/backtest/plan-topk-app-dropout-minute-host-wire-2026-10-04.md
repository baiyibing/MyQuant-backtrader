# topk_app_dropout 分钟 host 接线计划（2026-10-04）

本 PR 仅供四席评审的迁移计划；基线为 `origin/master f365fcd3cd47cd9627d61bd06ec8f52f4546cabe`。后续让分钟 host 复用旧 topk_app CLI 的同一批 loader，再调用一次 `simulate_v7`。本 PR 只新增此 Markdown，不改代码或测试，不合并。

## 现状与接线边界

`csv_strategy_books.register()` 的注册末尾为 `topk_dropout`、`topk_score_exit`，没有 `topk_app_dropout`。`minute_true_core_wire.EXTRA_MINUTE_STRATEGIES` 已列出 `("version7", "topk_app_dropout")`，但仅用于 bar-scan 接线，不是本任务。`minute_bar_scan_host.run_version7` 与 `tests/test_minute_bar_scan_host_v7.py` 已在 master，不重做 version7。

4090 上旧引擎已经能加载的数据可用；host 缺输入选项不等于缺数据。旧入口 `backtest/research/csv_minute_backtest_topk_app_dropout.py` 怎么加载，host 就调用相同 loader，不新增数据源、湖布局或 feeder。这是回测，持仓规则留在 `simulate_v7`／`strategy7_rules`；交集排名留在 `topk_app_dropout.py` 的 `load_pred_frame`、`qlib_topn_by_buy_day`、`intersect_app_qlib`，host 只加载与调用。

## 后续显式入口与两条池路径

在 `minute_bar_scan_host` 增加与 version7 同形的显式入口：`--strategy topk_app_dropout` 分派到**拟新增**的 `run_topk_app_dropout`。禁止 `register()`，禁止走 `run_simulate` 或 `csv_minute_backtest.simulate`。不复用 `load_scores_from_args`／`--pred-csv`，它们服务于 `topk_dropout`、`topk_score_exit`。

- 新增仅供本书使用的 `--app-pool-dir`、`--pred`、`--asof`；`--asof` 默认 `pred_minus_one`，另可选 `identity`。可复用 `--pool-dir`、`--topk`，但不改其他书默认值。本书 `--topk` 默认 `50`（旧 CLI 的 `DEFAULT_TOPK = 50`，定义于 `topk_app_dropout.py`，由 `csv_minute_backtest_topk_app_dropout` 导入并作为 `--topk` 默认），`--cash` 默认 `500_000_000`（旧 CLI 的 `DEFAULT_CASH_TOTAL = 500_000_000.0`），不沿用 v7 的 2100 万；`BOOK_TAG = "topk_app_dropout"`。
- 与 version7 一样要求 `--source lake`，拒绝 `--qlib-root`／`--lake-root` 覆盖，因为 `_load_cli_bars` 默认 lake。
- **预制池路径**：设置 `--pool-dir` 时，仅调用 `csv_minute_backtest_v7.load_pool_days(pool_dir, start, end)`；无需 app/pred，也不调用 `build_intersect_pool_days`。同时给了 app 目录时仍以 pool-dir 为准。
- **交集路径**：未设置 pool-dir 时，必须同时提供 app 目录与 pred 文件，沿用旧 CLI 的路径存在性检查；调用 `csv_minute_backtest_topk_app_dropout.build_intersect_pool_days(app_dir, pred_path, start_ymd, end_ymd, topk=topk, asof=asof, dump_dir=None)`。实际形参名为 `start/end`，此处按位置传 YYYYMMDD；返回日期 → 代码列表。
- 两条路径均不满足时，在任何 loader 前失败。不回落 `OSKH_TURTLE_POOL_DIR` 或 `stock_pool/`。

`build_intersect_pool_days` 的 `dump_dir=None` 跳过写出。旧 CLI 的 `main()` 未给 dump 时会写 `exports/{BOOK_TAG}_{start}_{end}`，调用 `write_topk_app_dropout_pool` 与 `write_overlap_report`，并拒绝写仓库 `stock_pool/`。dump／overlap report 保持 CLI 专属副作用，不是新数据源；host 不写这些目录或报告。

## 同一加载链，再调用一次 runner

两条池路径汇合后，按旧 topk_app CLI 的默认契约加载：

- `minute, daily = csv_minute_backtest_v7._load_cli_bars(pools, start, end)`；本阶段不传 `include_volume`。旧 CLI 仅在设置 `--participation-rate` 时打开它。
- `index = csv_minute_backtest_v7.load_index_daily(start, end) if pools else []`；空池传空列表且不加载指数，不复制 version7 host 的日期日历分支。
- `name_dir = pool_dir if pool_dir is set else app_pool_dir`，`symbols` 为各日池代码并集；调用 `ashare_session.load_limit_context(name_dir, symbols, start, end)` 得到 `exdiv, names`。该 loader 不加载涨跌停价格。

随后仅调用一次：

```text
state = simulate_v7(minute, daily, pools, index, cash_total=cash,
                    start=start, end=end, exdiv=exdiv, names=names)
return minute_bar_scan_host.summarize_simulate(
    state, bars=sum(len(f) for f in minute.values()), total_cash=cash)
```

摘要返回方式参照 `run_version7`；不调用旧 CLI 的 `write_run_artifacts`／`summarize_v7`。本阶段不传参与率、volume 选项、尾窗或 `names_by_day`；旧 topk_app CLI 没有 `--asof-pool-names`，不移植 version7 的该行为。

## 后续实现 PR 的窄验收与排除项

参照 `tests/test_minute_bar_scan_host_v7.py`，仅用 mock 验证两条池路径，无需 4090 真湖：`simulate_v7` 恰调用一次并收到 `exdiv`、`names`、`index` 与默认资金 `500_000_000`（旧 CLI 的 `DEFAULT_CASH_TOTAL`）；空池收到 `index=[]` 且 `load_index_daily` 未调用；`csv_minute_backtest.simulate` 未调用。交集路径断言 `build_intersect_pool_days(..., dump_dir=None)`，传入的默认 topk 为旧 CLI 的 `DEFAULT_TOPK`（50）；预制池路径断言它未调用。缺池输入在任何 loader 前失败。本计划 PR 不新增或运行测试。

排除：version7 重接线、`csv_minute_backtest` 默认值、000739 fixture、已合并书、bar-scan 接线（含 `scan_held_bars`、`minute_true_core_wire` 及传 `stage=` 的测试）、参与率、尾窗、新数据源、规则重写、`register()` 与合并。
