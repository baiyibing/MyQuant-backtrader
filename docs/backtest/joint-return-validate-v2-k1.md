# Joint-return validate-v2 K1 (research, default off)

`backtest/research/joint_return_validate_v2.py` provides `DensePanel`,
`ValidatedPanel` and `validate_bars_v2(..., enabled=True)`. Omitting the explicit
opt-in fails closed. Existing `validate_bars`, CLI defaults and replay are unchanged.
No CLI `--validate-version` is implemented here; K2 owns replay integration.

K0 locks: prices, limits and capacity are float64; suspended is uint8 {0,1}.
The lazy accessor converts only a touched cell with `Decimal(str(float(value)))`.
No fill, clock, fee or Decimal execution kernel changes. CLOSE_TIME bar labels
normalize by -60 seconds before indexing the session-derived OPEN_TIME axis.
High/low remain absent or pass through; they are never synthesized.

V0 streams SHA256 over `payload_files` in exactly the MANIFEST list order,
without separators; missing order fails `CONTRACT_MISMATCH`. Metadata and
corporate-actions hashes use the existing canonical JSON `content_hash` helper.
An optional `bars_table_sha256` verifies little-endian typed column concatenation:
`open,close,limit_up,limit_down,capacity,suspended`, then `high,low` when present.
Each column uses row-major (minute, instrument) order. Payload decoding is a
caller responsibility: without the optional table hash the byte seal authenticates
the files, not the caller-supplied arrays' relationship to those files.

V1 accepts prebuilt dimensions, sorted unique instruments, a bijective execution
symbol table and a strictly increasing session-derived minute axis. It checks
shapes, dtypes and axis alignment. Session membership/expansion, intent/initial
universe agreement, schema/kind/contract metadata parity, initial lots, reference
marks and expiry evidence remain deferred to integration. This is not a full v1
replacement. V4 rejects nonempty corporate actions until semantic validation is
integrated; empty events are sealed normally.

V2 scans NumPy arrays for finite positive prices/limits, inclusive open/close
limits, finite nonnegative capacity and valid suspension flags. Limit ties pass
as in v1; no epsilon is added. Equality is float64 equality: decimal literals that
round to the same binary value are indistinguishable. K3 must establish replay
bit parity before any default cutover. Optional high/low must be finite positive
but have no synthesized relationships. V3 checks every column's dense grid shape
and an optional boolean validity bitmap; false cells fail with instrument/minute
diagnostics. Suspended cells still occupy the grid.

The panel and validated view borrow arrays; callers must not mutate them during
validation or subsequent use. A future loader must reject duplicate input cells
and mark holes rather than silently densifying. K1 uses only tiny synthetic grids,
without a pack reader or full `list[dict]` materialization. RSS/timing receipts and
v1 fills/orders/NAV bit comparisons belong to K3 after K2.

Validation: `/workspace/vanna312/bin/python -m pytest -q tests/test_joint_return_validate_v2.py`.
Await Grok and human review; research defaults stay off.
