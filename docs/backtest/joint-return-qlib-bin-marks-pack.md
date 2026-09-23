# Mode B qlib_bin marks research pack

`backtest.research.joint_return_qlib_bin_pack` exposes `write_pack(bundle_or_json_path,
pack_root)` and `read_pack(pack_root)`. Format version:
`joint-return-bars-qlib-bin-marks-v1`; format `qlib_bin`; schema `joint-return-v1`.

The new destination contains `MANIFEST.json`, the full `metadata.json` (including
unchanged `reference_marks`), `corporate_actions.json`, `qlib_bin/calendars/1min.txt`,
and `qlib_bin/features/<qlib_inst_dir>/*.1min.bin`. Extras policy A writes open,
close, limit_up, limit_down, suspended (float32 0/1) and capacity. Each little-endian
float32 bin starts with reference index zero. `index/instruments.json` preserves
original instrument/execution_symbol mappings and lists the emitted features.

High/low are **passthrough only, never synthesized** from open/close or any other
values. Non-null source cells are retained. If a column is absent/null throughout
an instrument, its bin is omitted; partial missing cells use NaN and reconstruct
without that key. MANIFEST records `high_low=passthrough` if any source extrema
exist, otherwise `high_low=source_absent`. Indexed missing bins fail closed.

Calendar labels are sorted unique source timestamps normalized to Shanghai local
minutes (naive timestamps mean Shanghai). Reconstructed timestamps use `+08:00`.
Duplicate rows, symbol collisions, nonfinite source features and sparse grids are
rejected. `dense_complete` describes the source calendar × instruments only;
it does not certify metadata session coverage. A new output directory is required.
MANIFEST is written last; interrupted writes have no completed manifest.

This is **timing-only research I/O**, with float32 conversion of Decimal/string bar
values. JSON-compatible metadata/events are preserved without numeric conversion.
No content or payload hashes are emitted or promoted from the JSON twin, and the
reader does not return `content_sha256`. It does not certify marks against intents:
existing `validate_reference_marks` predicates and session/coverage checks remain
replay gates. Decimal bit-compare and seal authority are later work.

CLI default remains `json`; no replay loader/fill/clock/fee/Decimal changes.
Round-2 write/read bench follows merge on 4090: same 62/614-instrument,
3,630,906-row CLOCK_PATCH-614 subset, median of at least three runs, with RSS/disk
and explicit passthrough/source_absent receipt. No dispatch is part of this PR.
Await Grok review and human merge.
