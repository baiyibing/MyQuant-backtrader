# B-native-CV-01 text LF parity — 2026-09-29

Human GO: `/workspace/handoffs/b_parity_lf_20260929/HUMAN_GO.md`.
Base: `1d0b21f`; follows [#261](https://github.com/baiyibing/MyQuant-backtrader/pull/261).
Scope: external harness compare entry, data-free tests, and this note.

Cross-platform parity compares LF text semantics: Windows CRLF output is not an
economic difference. This supersedes the LF/CRLF rejection in the
[#261 timing note](note-lake-parity-stdout-timing-2026-09-29.md); its named numeric
duration captures and all other economic equality rules remain unchanged.

Text candidates are `stdout`, `stderr`, `.csv` / `.json` / `.txt` artifacts
(including `summary.txt`), and filenames explicitly listed in `duration_files`.
Both sides must decode as strict UTF-8, with no C0/C1 controls except tab, CR,
and LF. Invalid UTF-8 or binary controls on either side force byte comparison.
Other artifacts, including text-looking `.bin`, `.parquet`, or raw digest files,
remain byte-exact.

Before parsing or duration masking, strip exactly one leading UTF-8 BOM and
convert CRLF to LF. Lone CR also becomes LF, only after passing the text check.
Interior BOMs, extra blank lines, missing final newlines, spaces, CSV quoting,
JSON key order and numeric spelling still matter. Duration allowances remain
limited to declared files and opted-in stdout; stderr has no duration allowance.

Original bytes are never rewritten. Receipts retain their SHA-256 digests,
`byte_equal=false`, an allowed `/bytes` difference, and `byte_identical=false`
when only text representation changes. Manifest MD5/SHA-256 values are checked
against each original file. Derived digest differences are allowed only for
identical normalized text or the existing summary duration policy; artifact
comparison must also pass. Binary digest differences and forged hashes fail.

Validation: baseline **56 passed**; updated harness suite **122 passed**. Tests
cover LF/CRLF with equal or different durations, BOM and lone CR, exact economic
and serialization failures, binary boundaries, JSON field masking, and manifest
integrity. The two prior negative LF/CRLF cases now reject missing final newlines;
cross-platform acceptance has explicit coverage. Fixtures are not lake evidence.

No engine/adapter changes, production path changes, lake rerun, or SSOT green.
`production_C=frozen`. PR only; merge requires Human「合」.
