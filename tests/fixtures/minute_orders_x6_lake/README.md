# minute_orders_x6_lake fixtures

Read-only lake END / loader boundary meta for true-core X6 lake differential (#309).

- `boundary_ok.json` — happy-path lake + END + bucket_end meta
  (`lake boundary attestation != host PASS`).
- `synthetic_kind_rejected.json` — must be refused
  (`source_kind=synthetic_fixture` masquerade).
- `start_label_rejected.json` — must be refused
  (`bar_time_label=START`; Phase5 research path requires END).

Recipe e2e (separate GO) builds **tmp** lake+END recipes via `SyntheticCase` in
`tests/test_minute_orders_x6_lake_e2e.py` — it does not add checked-in lake bytes.

Not a lake writer. Not host attestation. Not a new economic contract / backend_id.
Does not unlock CLI `--evidence-level=lake`.
