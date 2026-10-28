# L2 ETL CSV encoding stall — paper stage

Human GO: 2026-10-28 ~09:10 Asia/Shanghai via hostbot-4090 t1092u,
owner qt: 「先修 encoding 再续跑」. Base: `b74c2e52` (#517).

Reported incident (not independently inspected on 4090): Phase3 PID 44704
stopped after three consecutive ETL failures on 2023-08-01/02/03; traceback
identified `UnicodeDecodeError` in `_is_header_only_csv`. Code inspection
confirms the UTF-8 probe caught only OSError, allowing decode errors to escape.
It is the only stock-CSV text open in `etl_day.py`; other text opens are JSON
manifests and remain UTF-8.

The two-record probe now tries UTF-8 with optional BOM, then GB18030 (a GBK
superset). Decode failure retries from the start; exhausted encodings and
OSError retain the empty/header-only result. No loader, schema, orchestration,
stop policy, lake path, or environment-default changes.

Validation with explicit `/workspace/.venvs/bt-ci/bin/python`:

- `-m py_compile l2_analytics/etl_day.py`: passed.
- `-m pytest tests/test_l2_etl.py -q`: 31 passed in 2.67s.
- `-m pytest tests/test_l2_phase3_pipeline.py -q`: 16 passed in 0.13s.

Fixtures cover GBK/GB18030/UTF-8/UTF-8-sig Chinese headers, both header-only
and with one trade, through the probe and day ETL; empty, undecodable, and
missing files are also covered. Initial `/usr/bin/python3` test collection
failed because DuckDB was absent; the existing bt-ci environment needed no
package installation. Edited Python/Markdown files have zero NUL bytes.

Residual limits: synthetic Linux fixtures only; no incident scratch files,
native Windows, or production lake verification. This change does not add
DuckDB transcoding for non-UTF-8 data fields. Text buffering may read ahead,
but no whole-file scan or encoding conversion is introduced. Truly undecodable
files remain classified empty. No SSH, 4090 access, hotcut, or resume occurred.
Draft PR only; no merge or undraft. Hostbot owns runtime after merge, with a
separate Human GO required for resumption.
