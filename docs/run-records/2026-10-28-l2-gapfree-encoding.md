# L2 gap-free exchange CSV encoding follow-up

Authorization: 2026-10-28 ~09:33 Asia/Shanghai, hostbot-4090 t1096u,
Human「安排codex先修吧」; owner qt. t1097u specifies no Grok verification.
Follow-up to [#518](https://github.com/baiyibing/MyQuant-backtrader/pull/518)
Claude GO-WITH-NITS: header-only GBK handling was fixed, but gap-free sniffing
could still reject data-bearing GBK CSVs and fail a Phase3 day.

Reproduced locally on DuckDB 1.5.6: a synthetic day mixing GBK, UTF-8 and
UTF-8 BOM Chinese headers with data rows raised InvalidInputException in the
old grouped read. No production data was used.

Fix: keep one filename-grouped query and the existing stratified target selection;
use the same explicit positional VARCHAR schema and auto_detect=false as
_write_chunk. Cast TranID to BIGINT before min/max to preserve numeric ordering.
No per-file fallback or encoding extension is needed for these fixtures.

Regression coverage includes full and stratified scans, contiguous IDs through
10, minimum ID above 1, and maximum ID unequal to row count. Existing #518
encoding sniff cases remain green.

Validation with explicit /workspace/bt-venv/bin/python:
- py_compile l2_analytics/etl_day.py: passed.
- pytest tests/test_l2_etl.py -q: 37 passed.
- pytest tests/test_l2_phase3_pipeline.py -q: 16 passed.

Limits: the fixed exchange column order remains required; this is header-sniff
avoidance matching the writer, not arbitrary GBK text transcoding. Synthetic
validation only; 4090, live Phase3, production lake and batch-stop policy were
untouched. Draft PR only; no merge, undraft, Grok or hostbot messaging.
