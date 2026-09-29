# B-native-CV-01 UTF-8 / GBK text LF parity — 2026-09-29

Human GO: `/workspace/handoffs/b_parity_lf_20260929/HUMAN_GO.md`.
Base: `1d0b21f`; follows [#261](https://github.com/baiyibing/MyQuant-backtrader/pull/261).
Scope: external harness compare entry, data-free tests, and this note.

Cross-platform parity compares LF text semantics: Windows CRLF output is not an
economic difference. This supersedes the LF/CRLF rejection in the
[#261 timing note](note-lake-parity-stdout-timing-2026-09-29.md); its named numeric
duration captures and all other economic equality rules remain unchanged.

GBK amendment evidence pointer:
`/workspace/handoffs/b_parity_lf_20260929/STEERING_ENCODING.md`
(4090 revalidation on `newtest_4090` at `1d0b21f`, 2026-09-29 ~18:56 CST).
The report has all four v7 cells PASS, but csv_minute normal and bad_output
still FAIL: Windows stdout's `耗时:` line is GBK while its counterpart is UTF-8.
Summary durations were allowed; `stdout/bytes` was not. No economic differences
were reported in those FAIL cells. This amendment reproduces the reported
encoding mismatch with data-free fixtures, not a replay of the host's raw files.

Text candidates are `stdout`, `stderr`, `.csv` / `.json` / `.txt` artifacts
(including `summary.txt`), and filenames explicitly listed in `duration_files`.
Each side independently uses strict `utf-8-sig` first; only a decode failure
tries strict `gbk` (Python's `cp936` alias uses the same codec). The GBK fallback
also strips exactly one leading UTF-8 BOM. Both decoded strings must pass the
text check: no C0/C1 controls except tab, CR, and LF. A successful UTF-8 decode
is never reinterpreted as GBK to bypass controls or a text mismatch. No lossy
replacement or ignored bytes. If either side fails both decoders or the text
check, compare the pair's original bytes exactly.
Other artifacts, including text-looking `.bin`, `.parquet`, or raw digest files,
remain byte-exact.

Before parsing or duration masking, strip exactly one leading UTF-8 BOM and
convert CRLF to LF. Lone CR also becomes LF, only after passing the text check.
Compare the resulting Unicode strings directly, including UTF-8 versus GBK or
GBK on both sides, then apply the existing named numeric duration captures.
Interior BOMs, extra blank lines, missing final newlines, spaces, CSV quoting,
JSON key order and numeric spelling still matter. Duration allowances remain
limited to declared files and opted-in stdout; stderr has no duration allowance.

Original bytes are never rewritten. Receipts retain their SHA-256 digests,
`byte_equal=false`, an allowed `/bytes` difference, and `byte_identical=false`
when only text representation changes. Manifest MD5/SHA-256 values are checked
against each original file; manifest JSON uses the same strict text decoder.
Derived digest differences are allowed only for
identical normalized text or the existing summary duration policy; artifact
comparison must also pass. Binary digest differences and forged hashes fail.

Validation: baseline **56 passed**; updated harness suite **122 passed**. Tests
cover LF/CRLF with equal or different durations, BOM and lone CR, exact economic
and serialization failures, binary boundaries, JSON field masking, and manifest
integrity. The two prior negative LF/CRLF cases now reject missing final newlines;
cross-platform acceptance has explicit coverage. Fixtures are not lake evidence.

GBK amendment validation: the prior **122 tests passed**; the extended suite
against the old UTF-8-only decoder produced **21 failed / 146 passed**. With the
strict fallback, **167 passed**. Coverage adds mixed UTF-8/GBK and both-GBK
stdout for the reported cells, BOM/LF handling, exact Chinese and economic-text
rejections across text candidates, unchanged stderr duration refusal, invalid
encoding/control boundaries, and original-byte manifest integrity.

No engine/adapter changes, production path changes, lake rerun, or SSOT green.
`production_C=frozen`. PR only; merge requires Human「合」.
