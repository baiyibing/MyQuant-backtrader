# L2 Phase3 read-only scratch fix — paper stage

Human GO: 2026-10-28 ~00:38 Asia/Shanghai, hostbot-4090 t1062u,
owner qt: fix first after Grok CLI GO-WITH-NITS on BT #514
(base squash `e04010ba`). Review: `/tmp/l2-phase3-speed-review/GROK_REVIEW.md`
§6, Windows archive-attribute issue.

The pipeline clears read-only on existing scratch RAR destinations before
replacement and on interrupted `.copying` files before copying again. After
successful extraction and `_extract_ready`, it makes the scratch RAR writable
before unlinking. Cleanup-only OSError is logged and the day proceeds to ETL.
CSV tree removal now retries permission failures after clearing read-only via
`rmtree(onerror=...)`, compatible with older Python versions.

Validation on the Grok Bot Linux VM with explicit `/usr/bin/python3`:

- `-m py_compile scripts/misc/l2_phase3_pipeline.py`: passed.
- `-m pytest tests/test_l2_phase3_pipeline.py -q`: 8 passed, 3 warnings.
  Warnings concern unavailable pytest plugin config options. The original six
  tests remain green; new temporary-tree tests simulate Windows replace/unlink
  checks, cleanup-only failure forwarding, and read-only CSV removal retry.

No native Windows, 7-Zip, DuckDB, or production lake validation was performed.
A held-open scratch RAR can still remain after a logged cleanup failure; this
must not stop an already extracted day. No hotcut or pipeline launch occurred;
4090 and live Phase3 PID 20908 were not accessed. Push, PR, merge, and any
operational cutover remain outside this change.
