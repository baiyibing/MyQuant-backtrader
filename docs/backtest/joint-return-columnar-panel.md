# Arrow IPC / Parquet DensePanel interop

`backtest.research.joint_return_columnar_pack` provides research twin writers
`write_pack_parquet(source, new_root)` and `write_pack_arrow(source, new_root)`.
Source may be a bundle dict, bundle JSON path, or existing qlib_bin marks-v1 pack.
The destination must not exist. Bundle inputs stage through the existing bin
writer in a temporary directory to share its validation and float32 rounding;
existing bin packs are decoded as arrays. Source seal hashes are not copied.
These are research writers, not production export or seal commands.

`read_columnar_panel(root)` dispatches on `MANIFEST.format` (`parquet` or
`arrow_ipc`) and returns the same `DensePanel` interface as `read_pack_panel`.
No full bar dict list, pandas conversion, or materialize-then-convert path is used.

The pinned versions are `joint-return-bars-parquet-panel-v1` and
`joint-return-bars-arrow-ipc-panel-v1`. Each pack contains:

- `MANIFEST.json`, `metadata.json`, and `corporate_actions.json`.
- `index/instruments.json`: instrument → execution symbol and feature inventory.
- `index/minutes.json`: sorted unique Shanghai timestamp labels.
- `bars.parquet` or `bars.arrow` (Arrow IPC **file**, not stream).

Table rows are minute-major, sorted-instrument-minor. Columns are `minute_i` and
`inst_i` (uint32), then `open`, `close`, `limit_up`, `limit_down`, `suspended`,
`capacity`, and source-present `high`/`low`. Numeric features are float32 on disk;
`suspended` is uint8. Readers verify schema, coordinates, density/counts, mapping,
feature inventory and finite required values before reshaping into float64/uint8
panels. Values exactly match float32-decoded bin twins. Optional missing cells
remain NaN; globally absent extrema are omitted. High/low are never synthesized.
Partial optional extrema still fail the existing v2 validation scan.
CLOSE_TIME labels use the existing −60-second conversion.

Replay accepts these pack roots only with `--validate-version v2`. It requires
`payload_files` to cover the table and both index files, verifies the raw payload
hash in the manifest's pinned order, and checks metadata/corporate-action hashes
using the existing seal path. Timing-only writer output intentionally lacks these
hashes and cannot be replayed as a sealed pack. Byte-mode corporate-action
semantics remain deferred and fail closed.

This is interop / research dual-read only. Seal default remains **qlib_bin**;
validate default remains **v1**. Execution fill, clock, fee, T+1 and Decimal math
are unchanged. Full-pack timing on 4090 remains post-merge work.
