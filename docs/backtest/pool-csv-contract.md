# Pool CSV contract

Pool files are named `YYYYMMDD.csv`, encoded as UTF-8/UTF-8-SIG, and contain a
bare six-digit code in the first column. A header is optional. Missing dates and
empty or parse-empty files always mean “no buys”.

The map representation intentionally differs by engine. Strategies 6/8 omit an
empty file from their `YYYYMMDD`-keyed map (`empty_in_map=False`). Strategy 7
retains it as an empty list in its `datetime.date`-keyed map
(`empty_in_map=True`). Strategy 7 still requires an explicit `--pool-dir`; only
the 6/8 engines default to the repository `stock_pool/` directory.
