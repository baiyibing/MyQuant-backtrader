# Pool CSV contract

Pool files are named `YYYYMMDD.csv`, encoded as UTF-8/UTF-8-SIG, and contain a
bare six-digit code in the first column. A header is optional. Missing dates and
empty or parse-empty files always mean “no buys”.

**As-of**：文件名日期就是买入日 T（当日名单、当日尾盘/收盘成交）。不是 T+1
信号日，也不是导出日。

**名称 as-of（P-R2）**：`name_asof(code, ds)` 取 `ds` 当日非空名称，否则取
`last_seen[code]`。`last_seen` 只在 `ymd <= ds` 且名称非空时推进，即取
`max ymd <= ds` 对应的名称，不是对名称字符串取字典序最大值；禁止读取
`ymd > ds` 的名称。

**名称列**：第二列可选，给 ST / `*ST` 用。有名称且含 `ST`/`*ST` 时按 5% 板；
无名称时按代码前缀分板（主板 10% / 创科 20% / 北交 30%）；前缀无法分板则
`skip_unknown_board`，不交易。

**方言链**：Qlib `SZ300190` → CSV 裸码 `300190` → 湖分区键 `300190_SZ` →
交易层 `300190.SZ`。

**严格校验门**：`validate_pool_dir` 要求文件名为合法的 `YYYYMMDD.csv`，且
每个数据行首列在去除空白和引号后恰好为六位数字。`SZ300190` 等带前缀单元格
校验失败；宽松的 `_cell_to_bare`、`parse_pool_csv` 和
`parse_pool_csv_entries` 仍接受这类输入。成交引擎的 `run()` 不调用严格校验。

The map representation intentionally differs by engine. Strategies 6/8/9/10 omit
an empty file from their `YYYYMMDD`-keyed map (`empty_in_map=False`). Strategy 7
retains it as an empty list in its `datetime.date`-keyed map
(`empty_in_map=True`). Strategies 7, 9 and 10 still require an explicit
`--pool-dir`; only the 1–6/8 engines default to the repository `stock_pool/`
directory. Strategies 9 and 10 also refuse that tree when it is passed
explicitly.
