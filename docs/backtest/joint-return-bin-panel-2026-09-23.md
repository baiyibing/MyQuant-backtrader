# Research marks-v1 hot load: bin → DensePanel

`read_pack_panel(pack_root)` in `joint_return_qlib_bin_pack.py` reads checked
qlib bins directly into `(minute, instrument)` float64 arrays and uint8
`suspended`. It retains at most one instrument's decoded bin columns alongside
the panel; it never builds a full bar `list[dict]`. `read_pack` remains the
compatibility/materialization path and dual-read oracle. Both share axis,
mapping, density and bin integrity checks. Float32 disk values are widened;
this does not recover original JSON precision or confer a JSON seal.

Research replay accepts `--bars <pack-root> --validate-version v2`. JSON input
still works, and default validation remains v1. Pack replay verifies the pinned
MANIFEST `payload_files` byte hash, metadata/events hashes, optional typed table
hash, and exact session/universe coverage before lazy fill access. The payload
list must include the calendar, instrument index and every decoded feature bin;
hash order is exactly the manifest order. Existing timing-only `write_pack`
outputs lack these seals and deliberately fail replay until explicitly sealed.
The reader alone is not a seal validator. For pack runs, summary bars raw/content
identities refer to MANIFEST; `inputs.bars_seal_mode=byte` and the payload digest
make this distinction explicit.

CLOSE_TIME labels shift −60 seconds to the existing OPEN_TIME opportunity axis.
Absent high/low stay absent; partially missing optional bins/cells remain NaN
and fail v2's existing complete-column gates. No extrema are synthesized.
Byte-mode corporate-action replay remains fail-closed pending its separate
contract. Execution, fees, T+1, clocks and lazy Decimal access are unchanged.
qlib_bin marks-v1 remains the storage format; Arrow is not the default seal.

Research-only phase spans: `read_pack_panel` / `read_columnar_panel` accept an
opt-in `_timings` sink and report `validate_panel_load.pack_axes` and
`validate_panel_load.pack_decode` (bin decode remainder plus the nested
`.pack_decode.assemble`; Arrow/Parquet use a sibling `.pack_assemble`). Default
off reads no clock. Key table and `--profile-timings-json` live in
[`joint-return-frozen-explicit-price.md`](joint-return-frozen-explicit-price.md).

Tiny tests compare panel columns exactly to materialized float32-decoded rows,
exercise both label conventions, corrupt inputs and seal failures, forbid the
legacy reader on panel/replay paths, and compare replay CSV bytes. Full 4090
pack timing/RSS and K3 approval remain post-merge work; this is no default-flip
or original-JSON Decimal parity claim.
