# RB-13 opt-in side metrics pack (MIXED-a)

This artifact changes no economics or default export. Only explicit calls to
`compute_metrics_pack` / `write_metrics_pack`, or the standalone script, create
it. No lake, benchmark download, default CLI or HELP_LOCK changes are involved.

Inputs are chronological daily `date,equity` rows and optional analysis-export
normalized fills (`date,ymd,code,side,price,shares,notional,commission,reason`, with
optional position/lot identities). Alternatively trades may be the existing
paired lot frame (`status,realized_pnl,mtm_pnl,sell_reason`). Raw run CSV fills are
normalized with the existing loader by the standalone script. No inputs mutate.
Daily dates must be unique and increasing; equity must be finite and positive.
Missing dates are not filled. The first equity observation is the base, not an
inferred initial account; N observations produce N-1 observed daily returns.

- Daily return: equity[t] / equity[t-1] - 1; first row has no return.
- Annualised return: (last / first) ** (P / (N-1)) - 1.
- P defaults to 252 trading days/year, a conventional research scaling constant,
  not an assertion about any particular Chinese calendar. It is configurable.
- Annualised volatility: sample standard deviation (ddof=1) of daily returns
  times sqrt(P). Fewer than two returns makes volatility unavailable.
- Sharpe: mean(r - rf_daily) / sample_std(r) * sqrt(P), with
  rf_daily = (1 + risk_free) ** (1/P) - 1. risk_free is an annual effective rate,
  defaults to 0, and is recorded explicitly. Zero volatility is unavailable.
- Benchmark: caller-supplied `date,equity` positive level series only. Compute
  its returns before joining on return end dates; require identical interval
  start dates for matched returns. No interpolation. Excess is annualised
  arithmetic mean(r - benchmark_return); beta is sample covariance / sample
  benchmark variance; tracking error is sample_std(r - benchmark_return)*sqrt(P).
  At least two matching intervals are required; zero benchmark variance makes
  beta unavailable. Missing benchmark is unavailable with a reason.
- Win rate: closed-lot, not whole-position round-trip. Reuse
  `drawdown_and_win_rates` exactly: realized_pnl > 0 wins, zero loses, open_eod
  excluded. Normalized fills use existing `pair_round_trips` first.
- Turnover: sum absolute BUY/SELL notional / mean daily equity (two-sided,
  unannualised); excludes EOD_MARK. Paired lots alone cannot supply turnover.
- Fee drag: sum explicit fee series (or `commission` column in a fee frame),
  otherwise sum fill commissions, / mean daily equity; unannualised. Missing
  fee columns are unavailable, never guessed zero. Empty supplied fills = zero.
- Exposure: mean of daily gross_invested / equity, only with a supplied
  nonnegative finite `gross_invested` column; never infer gross from cash.
- Skip/defer rates: unavailable. Existing sim stats have reason counters, but
  these analysis frames lack those counters and a contractual attempt
  denominator. Do not infer attempts from fills or aggregate reason counters.

No new drawdown calculation, alpha, attribution, tax decomposition, benchmark
fetch, position reconstruction for exposure, cashflow-adjusted return, or RB-14+
metrics. Nonfinite/invalid supplied values fail explicitly. Computed scalar overflow or
nonfinite results make only that metric unavailable with a reason. The script
preserves missing commissions (including partial NaN) as unavailable fee drag;
commission column matching is case-insensitive. Insufficient samples
use `{status: unavailable, reason: ...}`; available scalar metrics use
`{status: available, value: ...}`. Canonical JSON sorts keys, uses UTF-8 without
BOM, two-space indentation, rejects NaN, and ends with one newline.

Standalone use: `D:\anaconda3\envs\vanna312\python.exe scripts/research/rb13_metrics_pack.py
--run-dir <existing-run> --out <explicit-json-path>`; optional `--benchmark`
accepts a local CSV only, and `--risk-free` / `--periods-per-year` record scaling.
