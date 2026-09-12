# Pre-E-R1 6/8 synthetic trades snapshot

Generated **before** slice B (all-reason limit-down defer) so 6/8 NAV
changes after E-R1 can be compared by reason / fill, not old equity.

Window: 20251103–20251107, injected daily bars, `version6` and `version8`.
Regenerate only if you need a new baseline from the pre-B engine:

```text
D:\anaconda3\envs\vanna312\python.exe tests/fixtures/csv_engine_pre_er1/generate_snapshot.py
```
