# Pool CSV contract

Pool files are named `YYYYMMDD.csv`, encoded as UTF-8/UTF-8-SIG, and contain a
bare six-digit code in the first column. A header is optional. Missing dates and
empty or parse-empty files always mean “no buys”.

**As-of**：文件名日期就是买入日 T（当日名单、当日尾盘/收盘成交）。不是 T+1
信号日，也不是导出日。

**名称列**：第二列可选，给 ST / `*ST` 用。有名称且含 `ST`/`*ST` 时按 5% 板；
无名称时按代码前缀分板（主板 10% / 创科 20% / 北交 30%）；前缀无法分板则
`skip_unknown_board`，不交易。

The map representation intentionally differs by engine. Strategies 6/8 omit an
empty file from their `YYYYMMDD`-keyed map (`empty_in_map=False`). Strategy 7
retains it as an empty list in its `datetime.date`-keyed map
(`empty_in_map=True`). Strategy 7 still requires an explicit `--pool-dir`; only
the 6/8 engines default to the repository `stock_pool/` directory.
