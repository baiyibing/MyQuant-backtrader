# Human cut A — PR #481 cold-load identity (2026-10-16)

**Cut:** (A) conservative whole-file invalidation.

**Bound in plan:** `docs/backtest/plan-bar-cache-cold-load-2026-10-16.md` §4.2 (same-day r2 · cut A).

**Absorbs:** Codex HOLD (`codex.md`) + Grok AGREE-HOLD (`grok.md`, recommends A over B).

**Summary:**

- P1: symbol lake file stamp (`st_mtime_ns` / whole-file identity) invalidates **all** month shards for that symbol when the source file changes. No “+1 day only builds the new month”. No frozen old-month stamps.
- P3: keep G2 seven fields including `source_snapshot`. Sidecar `start`/`end` = **month-aligned shard bounds**, not the request window. Lake-wide shallow snapshot broad invalidation is intentional conservatism under A.
- Invalidation matrix: see plan §4.2.
- Knife order unchanged: S1.1 → S1 default OFF → S2 → S3 separate PR.
- Cut B (month-digest + manifest) deferred; not this cut.

Encode still requires Codex re-review GO; docs merge ≠ auto impl GO; do not merge encode without further human gate.
