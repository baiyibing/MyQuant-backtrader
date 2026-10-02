# B-native-CV-01 stdout duration mask — 2026-09-29

Human GO: `/workspace/handoffs/b_stdout_timing_20260929/HUMAN_GO.md`.
Base: `efdb5b9`. Scope: external lake-parity harness and data-free tests.

4090bot reported overall **FAIL**, exit 1, on `newtest_4090`, tip `fd74932`,
lake `E:\stock_data`, receipt `D:\exports\run-fd74932-4090`:

| Family | normal | low_cash | invalid_config | bad_output |
| --- | --- | --- | --- | --- |
| csv_minute | FAIL | PASS | PASS | FAIL |
| v7 | FAIL | FAIL | PASS | FAIL |

The reported CSV normal cell allowed the summary duration difference but rejected
`stdout/bytes`. The other failed cells reported stdout load/timing differences.
Data-free fixtures reproduce all five failures with CRLF stdout: the declared
duration patterns accepted LF only, so matching stopped before numeric captures
could be masked. These are representative fixtures, not a replay of the host's
raw files or new lake evidence.

The fix accepts LF, CRLF, or no final newline for the existing `耗时:`,
`loaded minute=lake daily=lake: … in Xs`, and `timing load=…` patterns.
Only named numeric duration captures are masked. Line endings, optional cache
suffixes, counts, and all other text remain in the residue and must match exactly
between native and L1. A difference between LF and CRLF still fails. With equal
residue, duration-only `stdout/bytes` and `summary.txt/bytes` are allowed; raw
digests and `byte_identical=false` remain visible. Existing manifest own-file
digest validation and exact JSON, trades, equity, stderr, and exit checks remain.

Validation: all 37 existing harness tests passed before the change. With new
regressions and the old matcher, 15 failed / 41 passed, including all five host
failure shapes. After the fix, all 56 tests passed. Coverage includes multi-line
stdout, LF/CRLF recognition, optional cache suffixes, duration-derived
summary manifest hashes, both bad-output exit-1 paths, and rejection of economic
or non-duration changes alongside allowed timings.

No engine/adapter edits or new engine imports. No lake rerun, SSOT R/S green, or
production_C change. Merge requires Human「合」; 4090 re-verification follows merge
and Human/4090bot coordination.
