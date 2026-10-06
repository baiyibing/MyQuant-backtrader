# RB-15 CLI/config combination acceptance table (2026-10-06)

H-RB-09 / RB-15, ZERO-DIFF. Derived from current code and
`tests/test_rb15_cli_combo_order_lock.py`, committed first and passing against
RB-14 tip `edfd953`. No runtime extraction, flags, defaults, HELP_LOCK,
fixtures, baselines, book ordering, output changes, or L1/L2 work.

Ranks below describe the shared `csv_minute_backtest.run` validation sequence
before pool resolution. Rejections have exact literal exception messages;
accepted means this validation boundary passes, not that data or execution
succeeds. Nested ranks follow the existing helper order.

## Extraction decision

No validation leaf was extracted in this PR. A verbatim move is not provably
safe because the current order includes local tail-unit normalization, repeated
book normalization, and `warn_stale_period_env()` before the volume-source
rejection; extraction is also not needed to deliver RB-15's tests-and-table
scope. Existing staged validators remain authoritative, and every table row is
therefore **not extracted**. The order-lock tests are the guard for any future
extraction: it must preserve the same exception types, literal messages, and
precedence before production code is moved.

## Run boundary rejection table

| Rank | Invalid option combination | Accepted? | Error type | Exact message | Check location | Extraction |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `version9_sell='bad'` (otherwise version6/defaults) | No | `ValueError` | version9_sell requires version9 and one of ('mean_tr3_tp10', 'range_amp_tp_amp', 'mean_tr2_or_prior10_low') | `backtest/research/strategy9_rules.py:112` | not extracted |
| 2 | `strategy='version9', version9_sell='mean_tr2_or_prior10_low', max_hold=True` (otherwise version6/defaults) | No | `ValueError` | mean_tr2_or_prior10_low rejects max_hold | `backtest/research/strategy9_rules.py:114` | not extracted |
| 3 | `max_hold=True` (otherwise version6/defaults) | No | `ValueError` | max_hold is supported only by version9 | `backtest/research/minute_entry_validation.py:13` | not extracted |
| 4 | `participation_rate=0.1, minute_source='qlib_1min'` (otherwise version6/defaults) | No | `ValueError` | participation_rate requires raw lake minute volume in shares | `backtest/research/participation_rate_precheck.py:49` | not extracted |
| 5 | `participation_rate=0.1, tail_window_buy=True, tail_volume_unit='lots'` (otherwise version6/defaults) | No | `ValueError` | participation_rate requires shares, not tail volume lots | `backtest/research/participation_rate_precheck.py:51` | not extracted |
| 6 | `fix_s81_band_precision=True` (otherwise version6/defaults) | No | `ValueError` | fix_s81_band_precision is supported only by version8_1 | `backtest/research/csv_minute_backtest.py:1385` | not extracted |
| 7 | `minute_stop_trigger='bad'` (otherwise version6/defaults) | No | `ValueError` | --minute-stop-trigger must be hl or close | `backtest/research/minute_stop_trigger.py:22` | not extracted |
| 8 | `strategy='version12', minute_stop_trigger='hl'` (otherwise version6/defaults) | No | `ValueError` | --minute-stop-trigger hl rejects version12 and --fix-s11-exit-domain | `backtest/research/minute_stop_trigger.py:24` | not extracted |
| 9 | `topk_limit_rule='bad'` (otherwise version6/defaults) | No | `ValueError` | unknown --topk-limit-rule 'bad'; choose qlib or real | `backtest/research/topk_minute_exec.py:88` | not extracted |
| 10 | `topk_exec='bad'` (otherwise version6/defaults) | No | `ValueError` | unknown --topk-exec 'bad'; choose close, open, intraday or vwap | `backtest/research/topk_minute_exec.py:90` | not extracted |
| 11 | `topk_exec='vwap', limit_walkdown=True` (otherwise version6/defaults) | No | `ValueError` | --topk-exec vwap x --limit-walkdown is refused | `backtest/research/topk_minute_exec.py:92` | not extracted |
| 12 | `topk_exec='open'` (otherwise version6/defaults) | No | `ValueError` | --topk-exec open/intraday/vwap, --limit-walkdown and --topk-limit-rule real apply only to topk_dropout | `backtest/research/topk_minute_exec.py:97` | not extracted |
| 13 | `tail_window_buy=True` (otherwise version6/defaults) | No | `ValueError` | --tail-window-buy requires --fix-minute-cash-order | `backtest/research/tail_window_buy.py:33` | not extracted |
| 14 | `tail_window_buy=True, fix_minute_cash_order=True, tail_volume_unit='bad'` (otherwise version6/defaults) | No | `ValueError` | tail volume unit (--tail-volume-unit) must be shares or lots | `backtest/research/tail_window_buy.py:25` | not extracted |
| 15 | `tail_window_buy=True, fix_minute_cash_order=True` (otherwise version6/defaults) | No | `ValueError` | --tail-window-buy applies only to version8 / version8.x in the shared entry | `backtest/research/minute_entry_validation.py:19` | not extracted |
| 16 | `strategy='version8', tail_window_buy=True, fix_minute_cash_order=True, daily_source='qlib'` (otherwise version6/defaults) | No | `ValueError` | --tail-window-buy requires raw lake minute and daily data | `backtest/research/csv_minute_backtest.py:1394` | not extracted |
| 17 | `fix_s11_exit_domain=True` (otherwise version6/defaults) | No | `ValueError` | fix_s11_exit_domain is supported only by version11 | `backtest/research/minute_entry_validation.py:25` | not extracted |
| 18 | `strategy='version11', fix_s11_exit_domain=True, daily_source='qlib'` (otherwise version6/defaults) | No | `ValueError` | fix_s11_exit_domain requires raw lake execution + independent lake front | `backtest/research/csv_minute_backtest.py:1399` | not extracted |
| 19 | `stop_fill=' CLOSE '` (otherwise version6/defaults) | No | `SystemExit` | --stop-fill close is daily EOD close only; minute entry refuses it (bar close is not 当日收盘) | `backtest/research/csv_minute_backtest.py:1401` | not extracted |
| 20 | `fix_s12_price_domain=True` (otherwise version6/defaults) | No | `ValueError` | --fix-s12-price-domain requires version12 + lake/lake + --dividend-type none | `backtest/research/csv_minute_backtest.py:1410` | not extracted |
| 21 | `s12_price_transform_file='unused'` (otherwise version6/defaults) | No | `ValueError` | --s12-price-transform-file requires --fix-s12-price-domain | `backtest/research/csv_minute_backtest.py:1412` | not extracted |
| 22 | `strategy='version9_1', fix_minute_cash_order=True` (otherwise version6/defaults) | No | `ValueError` | --fix-minute-cash-order is not applicable to version9_1 | `backtest/research/minute_entry_validation.py:22` | not extracted |
| 23 | `strategy='version12', audit_sink=True` (otherwise version6/defaults) | No | `ValueError` | X-02 execution audit is not applicable to version12 | `backtest/research/csv_minute_backtest.py:1415` | not extracted |
| 24 | `strategy='version12', daily_source='qlib'` (otherwise version6/defaults) | No | `ValueError` | version12 minute requires lake daily/minute and --dividend-type none&#124;front | `backtest/research/csv_minute_backtest.py:1418` | not extracted |
| 25 | `dividend_type='front'` (otherwise version6/defaults) | No | `ValueError` | minute --dividend-type front is supported only by version12 | `backtest/research/csv_minute_backtest.py:1422` | not extracted |
| 26 | `strategy='version11', minute_source='qlib_1min'` (otherwise version6/defaults) | No | `ValueError` | version11 requires lake minute volume; qlib_1min frames do not carry it | `backtest/research/csv_minute_backtest.py:1426` | not extracted |

The participation-rate finite `[0,1]` check precedes its raw-source and unit checks:
`ValueError("participation_rate must be finite and in [0, 1]")` at
`backtest/research/ashare_volume_cap.py:45` (conversion failure at :43).
This is rank 3.5, before table rank 4; omitted/None is a no-op.
Unsupported/absent strategy normalization is unchanged in
`csv_strategy_books.py:308` / :312; it occurs inside the initial sell stage.
The table does not claim acceptance of unknown strategies or additional flags.

## Accepted boundary examples

| Combination | Accepted? | Error type/message | Check location | Order rank |
| --- | --- | --- | --- | --- |
| version6, defaults | Yes | none | `csv_minute_backtest.py:1373–1426` | all run checks |
| version8_1 + fix_s81_band_precision | Yes | none | `csv_minute_backtest.py:1384` | 6 |
| version8 + tail_window_buy + fix_minute_cash_order, raw lake/lake | Yes | none | `csv_minute_backtest.py:1388–1394` | 13–16 |
| topk_dropout + topk_exec=vwap, walkdown OFF | Yes | none | `topk_minute_exec.py:93` | 9–12 |
| version12 + dividend_type=front, lake/lake | Yes | none | `csv_minute_backtest.py:1416` | 24 |
| version11 + fix_s11_exit_domain, raw lake/lake, no qlib roots | Yes | none | `csv_minute_backtest.py:1395` | 17–18 |

All six accepted run examples stop via a test sentinel at pool resolution, after
real validation. No market lake is needed. These are examples, not newly admitted
families. Existing guards define the full acceptance complement of each rejection.

## apply_csv_strategy entry

| Rank | Combination | Accepted? | Error type / exact message | Check location | Extraction |
| --- | --- | --- | --- | --- | --- |
| A0 | absent / unsupported strategy | No | ValueError; existing dynamically enumerated book names | `csv_strategy_books.py:308,312` via `get_book` at :348 | not extracted |
| A1 | version9_sell supplied outside version9 or invalid mode | No | ValueError; version9_sell requires version9 and one of ('mean_tr3_tp10', 'range_amp_tp_amp', 'mean_tr2_or_prior10_low') | `strategy9_rules.py:112`, call `csv_strategy_books.py:349` | not extracted |
| A1.1 | version9 + mean_tr2_or_prior10_low + max_hold | No | ValueError; mean_tr2_or_prior10_low rejects max_hold | `strategy9_rules.py:114` | not extracted |
| A2 | fix_s81_band_precision outside version8_1 | No | ValueError; fix_s81_band_precision is supported only by version8_1 | `csv_strategy_books.py:351` | not extracted |
| A3 | version6 defaults / version8_1 precision fix / version9 mean_tr3_tp10 | Yes | none | `csv_strategy_books.py:347` | not extracted |

A1 wins over A2; A2 wins over invalid ration_seed conversion. The run-only
max_hold guard is intentionally absent from this apply entry when sell mode is
None. The `ration_seed` conversion is at `csv_strategy_books.py:354`, followed
by book-specific `book.apply` validation at :355; this table does not move or
reinterpret that downstream validation.

## CLI parse boundary

| Rank | Combination | Accepted? | Error type / stderr substring | Check location | Extraction |
| --- | --- | --- | --- | --- | --- |
| P0 | --topk-exec bad | No | SystemExit(2); unknown --topk-exec 'bad'; choose close, open, intraday or vwap | `topk_minute_exec.py:107`, parser :1747 | not extracted |
| P1 | participation rate incompatible raw source/unit | No | ValueError with same run precheck message | `csv_minute_backtest.py:1812` | not extracted |
| P2 | version12 + --minute-stop-trigger hl + --topk-exec open | No | SystemExit(2); --minute-stop-trigger hl rejects version12 and --fix-s11-exit-domain | `csv_minute_backtest.py:1821–1824` | not extracted |
| P3 | version6 + --topk-exec open | No | SystemExit(2); --topk-exec open/intraday/vwap, --limit-walkdown and --topk-limit-rule real apply only to topk_dropout | `csv_minute_backtest.py:1822–1824` | not extracted |

P2 wins over P3 after parsing. Argparse choices and required arguments keep their
existing parse-time order; no parser code changes. HELP_LOCK is untouched.

## RB-04 book capabilities (reuse, no inheritance)

| Book capability / combination | Accepted? | Error type/message | Check location | Order rank |
| --- | --- | --- | --- | --- |
| name in PRICE_ADD_ELIGIBLE_BOOKS AND sizing=per_name | price add eligible | none; predicate | `book_capabilities.py:163` | independent capability predicate |
| name in S8_INDEPENDENT_BOOKS AND sizing=per_name | independent binding eligible | none; predicate | `book_capabilities.py:168` | independent capability predicate |
| version8_2 / version8_6 with per_name | independent only | none; price-add false | same frozensets/predicates | independent capability predicate |
| version8_1 | explicit prefix family opt-out | none; both predicates false | `book_capabilities.py:126` | admission classification |
| either set member with sizing other than per_name | neither capability | none; false | same predicates | independent capability predicate |

The two existing frozensets in `book_capabilities.py` are the SSOT. They are not
interchangeable and do not authorize CLI options by name prefix. Existing RB-04
tests freeze their membership and sizing requirements; RB-15 introduces no new
capability table in runtime code.

## Verification

The order-lock suite passed on unchanged production code before the first commit.
It is rerun after this documentation-only RB-15 change. Adjacent rejection pairs,
rate/source/band collisions, apply sell/band/ration collisions, and CLI HL/TopK
collisions lock which error fires first. Shared required marker:
`not production and not benchmark` from `scripts/ci_pytest_marker.txt`.
