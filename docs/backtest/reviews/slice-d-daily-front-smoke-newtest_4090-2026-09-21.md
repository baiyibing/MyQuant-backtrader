# Slice D daily front smoke closure (paths-only) — newtest_4090

This note is **paths-only metadata** for Slice D daily smoke closure.
It intentionally makes **no NAV / returns / parity claims**.

## Scope

- Book set (daily): `s12_daily`, `s8_daily`, `s8_1_daily`, `s8_2_daily`, `s8_3_daily`
- Window: `20251023`–`20260909`
- Host/export root (citation only): `D:\exports\s12_slice_d_20260921\`

## Source tips (for traceability)

- Pre-merge branch tip: `ce29d46367781a805f49d94bf414b3e8754d1a31`
- Master merge tip: `013a2d520be97cc08c8a04dc8539e0bb14aa17ee`

## Export path map

- `D:\exports\s12_slice_d_20260921\s12_daily`
- `D:\exports\s12_slice_d_20260921\s8_daily`
- `D:\exports\s12_slice_d_20260921\s8_1_daily`
- `D:\exports\s12_slice_d_20260921\s8_2_daily`
- `D:\exports\s12_slice_d_20260921\s8_3_daily`

## Follow-up status

- Minute Slice D remains pending this follow-up PR.
- Locked convention for pending minute run: `--dividend-type none` (with daily signals in `front` domain).
