# Pre-E-R1 6/8 synthetic trades snapshot

Generated **before** slice B (all-reason limit-down defer) so 6/8 NAV
changes after E-R1 can be compared by reason / fill, not old equity.

Window: 20251103–20251107, injected daily bars, `version6` and `version8`.
**Do not regenerate** for v8 rules v2 (snapshot would expire). Historical note only — regenerate only if you need a new baseline from the pre-B engine (not for v8 v2):

```text
D:\anaconda3\envs\vanna312\python.exe tests/fixtures/csv_engine_pre_er1/generate_snapshot.py
```

> **禁再生成（v8 规则 v2）**：v8 卖点/加仓语义已变，本目录快照仅作 pre-E-R1 历史锚点；**禁止**再运行 `generate_snapshot.py` 覆盖（存在性断言仍绿，无内容逐字节要求）。详见 [plan-v8-rules-v2-2026-09-16.md](../../../docs/backtest/plan-v8-rules-v2-2026-09-16.md) 切片 C。
