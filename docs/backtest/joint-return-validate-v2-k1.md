# Joint-return validate-v2 K1 / K2 (research, default off)

`backtest/research/joint_return_validate_v2.py` provides `DensePanel`,
`ValidatedPanel` and `validate_bars_v2(..., enabled=True)`. Omitting the explicit
opt-in fails closed. CLI/API defaults remain v1. K2 adds opt-in replay
integration as described below; the following K1 notes describe the byte API.

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


## K2: opt-in JSON replay wiring

`joint_return_replay.main` accepts `--validate-version {v1,v2}` (default **v1**).
Both `replay(...)` and `run_replay(...)` accept `validate_version="v2"`; omission
continues to use `validate_bars`. Existing CLI arguments remain required.
For example, append `--validate-version v2 --profile-timings` to an existing
`python -m backtest.research.joint_return_replay` invocation.

K2 implements SPEC §9's research JSON→DensePanel path (option B), not a columnar
pack loader. `--bars` must still be a sealed JSON file. No MANIFEST is needed:
its existing `content_sha256` canonical JSON seal is verified. There is no CLI
`--seal` override; byte sealing remains available through the K1 panel API.
Directories, unsealed JSON, and the timing-only qlib_bin pack fail closed; that
pack currently lacks the K0 seal hashes and must not be silently reconstructed
and certified. A future sealed columnar loader remains separate work.

Metadata/session expansion, initial lots, symbol mapping, expiry evidence and
corporate-action checks share the v1 predicates. Frozen reference-mark checks
remain unchanged. JSON records convert once into float64/uint8 arrays with a
coverage bitmap. Duplicate cells, holes, invalid symbol/time labels, nonnumeric
prices, and nonboolean suspension flags fail closed. V2 requires a nonempty dense
universe even for synthetic fixtures; sparse synthetic inputs remain v1-only.
Optional high/low pass through only when explicitly present in every cell of a
present column; partial optional columns fail closed rather than being filled.

After conversion, vectorized scan/coverage use only arrays. Lazy mappings expose
minute bars and closes, and each touched cell supplies Decimal through
`ValidatedPanel.bar_open`, `bar_capacity`, or `bar_decimal`. Views are ephemeral:
there is no full `(time, instrument) -> bar` dict, closes record list, or persistent
cell cache. Session/minute/instrument indexes and day-symbol coverage remain.
The existing replay still visits all marks and capacities per minute; this is
validation integration, not a replay speedup. Input JSON stays caller-owned and
immutable and may remain resident; JSON parse/canonical hashing and conversion
costs are not eliminated. K3 must measure peak RSS as well as timings.

With v2, profiling reports `validate_metadata`, `validate_panel_load`,
`validate_seal`, and `validate_panel_scan` (including coverage). `validate_bars`
is emitted only by v1. Existing load, replay, reference-mark and write phases
remain. No fill, clock, fee, T+1, limit or order-machine arithmetic was changed;
only the bar-number representation boundary accepts the panel's lazy Decimal.

Tiny tests byte-compare fills/orders/daily_nav and CLI CSV artifacts between v1
and v2, cover both fill modes, OPEN_TIME/CLOSE_TIME, partial fills, fees,
suspension, corporate actions and frozen reference marks, and forbid v2 calling
v1 validation. Prices/quantities in parity fixtures use float-exact values
(including 10.25); arbitrary decimal literals are not a parity claim.

**K3 is still required:** pinned mini + 10%/full-pack bit-compare, same-machine
validation timings and RSS RECEIPT, followed by human GO. K2 does not authorize
any default flip. This PR stacks on #177 / includes K1 while #177 remains open.

K2 verification:
`/workspace/vanna312/bin/python -m pytest -q tests/test_joint_return_validate_v2.py tests/test_joint_return_replay.py tests/test_joint_return_qlib_bin_pack.py`.
