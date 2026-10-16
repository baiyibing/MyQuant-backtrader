# Grok review — PR #481 cold-load r2 + Codex HOLD

Verdict: **AGREE-HOLD**

Date: 2026-10-16 (Asia/Shanghai). Reviewed tip `7357230` (Codex artifact on
`4b2eb2a` plan + this HOLD). Scope: r2 plan
`docs/backtest/plan-bar-cache-cold-load-2026-10-16.md`, Codex HOLD
`codex.md` in this directory, prior Grok on #479
`../pr-479-bar-cache-cold-load/grok.md`, and the live G2 identity path in
`backtest/research/ashare_bars.py` (`minute_cache_identity`,
`_cache_identity_matches`, shallow `st_mtime_ns` snapshot).

This is an independent plan-level re-review of Codex's HOLD. No
implementation, no merge, no encode PR.

## 1. Does Codex's blocker correctly name a missing semantic cut?

**Yes.** It is not pedantry.

r2 correctly absorbed #479 F1–F6 into hard constraints and kept P1–P8
**未裁**. The suggested defaults in the P-table are still not jointly
executable:

| Suggested default | Alone | Collision with the other |
| --- | --- | --- |
| **P1** 该月字节身份 + `st_mtime_ns` | Sounds like month-digest reuse | Does not say whether whole-file `st_mtime_ns` is *inside* each month identity (append → every month of that symbol misses) or only a *trigger* to recompute digests (unchanged month bytes can survive). Those two readings produce different mandatory S1.1 +1-day rebuilt-shard counts. |
| **P3** 七字段全留，含默认 `source_snapshot` | Matches today's G2 equality set | Default `source_snapshot` is **lake-wide shallow** (`shallow-v1:` + root + one-level child `[name, mode, size, mtime_ns]`). One symbol rewrite can bump a parent-dir mtime and flip the token for every symbol. Retaining that token as an equality field means month digests cannot keep other symbols' shards warm. The plan does not say whether that global miss is intentional (parity with monolith) or whether the default snapshot role must be redefined for shards. |
| Month digests in practice | Lake is one `symbol=*/data.parquet`, not month partitions | Obtaining/verifying a month digest requires either a lake rescan on every lookup (conflicts with P6 warm = zero lake reads) or an authenticated digest manifest stamped against the file. Neither contract is written. |

Until one of those cuts is written, encoding the "suggested defaults" would
silently choose a semantic that Human has not authorized. That matches
Codex's stop condition. Agree with the P1/P3 identity blocker as **encode
gate**, not a style nit.

One sharpening Codex stated briefly and this review elevates: **P3's
`start`/`end` equality fields must not be the request window if month
shards are meant to be reusable across windows.** If each shard sidecar
authenticates the caller's `[minute_load_start, end]`, two different
request windows cannot share the same physical month file even when lake
bytes are unchanged — which removes the main frozen-lake win of month
sharding. Month-aligned shard bounds (e.g. calendar month closed
`YYYYMMDD` pair) and request bounds (`mem_key.extra` / F2 clip) are
different quantities. r2 F2 already separates clip from identity; P3's
"七字段都留" still needs that split named, or implementers will copy
monolith `start`/`end` into every month sidecar and defeat reuse.

## 2. F2 / F4–F8 once P1/P3 identity is fixed

Agree with Codex's coherence table:

| Constraint | This review |
| --- | --- |
| F1 | Correctly bans frozen old-month stamps and false +1-day promises. Still needs the explicit A/B cut below before a concrete identity exists. |
| F2 | Coherent and encode-ready: parameter-window months, closed `ymd` clip, non-overlapping months, `mem_key.extra` request bounds, spans on clipped frames, one-scan-vs-per-month left to P2/S1.1. |
| F3 | Coherent safety posture (full typed equality, root pin, explicit token, no monolith migration). Relationship to shard identity is exactly the P1/P3 repair. |
| F4 | Coherent with suggested P4 (narrow minute = pool ∪ strategy extras; daily stays broad; omit missing; no `codes_hint`). |
| F5 | Correct budget placement; S1.1 probe numbers required before grain; no cold-time claim from docs alone. |
| F6 | Coherent OFF-by-default / exact `0`/`1` / fail-closed other values. |
| F7 | Coherent parallel/tmp/membership limits; batch membership independent of request subset. |
| F8 | Coherent: monolith partial rewrite only with switch OFF; enabled path never calls monolithic merge/write. |

So the plan is **substantially improved over #479** and is close; the
remaining encode blocker is the reusable shard identity cut, not a
re-opening of F2/F4–F8.

## 3. Recommended Human cut: **(A)** primary

**Primary recommendation: (A) conservative whole-file invalidation, with
an explicit written refusal of any "+1 day only builds the new month"
promise.**

Why A over B for the next written cut:

1. **Matches F1's already-authorized fallback.** F1 says that until
   month-byte / month-partition identity exists, S1 must not claim
   incremental-only builds, and probes must report same-month vs
   cross-month rebuilt counts separately. Cut A is that fallback made
   binding, not a new invention.
2. **No new digest-verification machinery.** The lake is still one file
   per symbol. Cut B needs either lookup-time rescans (hurts P6 warm) or
   a stamped digest manifest (new authenticated object, not sketched).
   Encoding B without that contract recreates today's HOLD.
3. **Still delivers the frozen-lake cross-window win.** Under A, when the
   lake stamp is stable, different request windows can share month shards
   *if* shard identity uses month-aligned bounds (not request
   `start`/`end`). Daily appends rebuild that symbol's months (and, with
   lake-wide snapshot retained, may miss globally) — same source
   sensitivity class as today's monolith, sharded for window reuse rather
   than for append incrementalism.
4. **S1.1 expected counts become writable immediately.** Same-month
   append and cross-month append both rebuild all covered months of the
   touched symbol under A; that is an honest probe line, not a fake
   "only new month" line.

**(B) month-digest + snapshot-role contract** remains the right *later*
destination if Human wants append incrementalism. It is not the
recommended first cut: it needs verification + snapshot-role text that
r2 does not yet contain. Choosing A now does not forbid a later B plan
revision; it unblocks probe/S1 design under an explicit non-promise.

## 4. Knife order / separate-PR for S3

**Confirm Codex.** Plan §7 is correct:

`S1.1 probe → S1 shards (default OFF) → S2 codeset → S3 Arrow`, each its
own PR; Arrow must not share a PR with sharding. User preference for one
PR does not override that conditional. Rollback three lines (§5) remain
sound once P5 is written as approved.

Nit only: S1.1 still cannot open until P1 (and P2) have a *written*
choice — cut A above is exactly that written choice for P1; P2 can keep
the F2 suggested default when Human approves the P-table rows.

## 5. Other HOLD-worthy holes Codex did not fully expand

None that independently overturn the rest of r2, but these must ride with
the identity repair (not deferred nits):

1. **Request `start`/`end` vs month-aligned shard bounds** (elevated in
   §1). Must be in the minimal repair text.
2. **Invalidation matrix** (Codex listed; restating as required plan
   prose, not reviewer folklore): same-month append; cross-month append;
   old-month correction; unrelated-symbol replacement; explicit
   `source_snapshot` token change; metadata-preserving replacement
   (`cp -p` / `rsync -t` / utime). Each row: which shards miss, whether
   lake-wide snapshot forces global miss, whether explicit token is
   required.
3. **`run_book_data` / P4 caller audit** — Codex's must-fix-with-impl
   note stands; not a reason to HOLD the *plan* beyond identity, but must
   not be dropped when encode is later allowed.
4. No additional blocker found in F7/F8/rollback/DoD recipes beyond what
   Codex already recorded.

## Minimal plan text before encode is allowed

Human (or a follow-up docs commit Human authorizes) must add, before any
`ashare_bars` shard encode PR:

1. **P1 written choice = cut A** (or an equally explicit B with full
   digest+manifest+snapshot-role contract — not the current ambiguous
   "月字节 + st_mtime_ns" one-liner):
   - 失效单位 = 该票整文件 `(st_size, st_mtime_ns)`。
   - 每个月 shard 的源身份含该整文件 stamp；源 stamp 一变，该票覆盖窗内
     **全部**月份 miss。
   - **明确不承诺**「末日 +1 天只建新月」。禁止冻住旧月 stamp。
   - S1.1 / S1 验收只报 rebuilt-shard 计数（当月 +1 与跨月 +1 分行），
     不得把「只建新月」写成通过句。
2. **P3 written choice with roles**:
   - 七字段仍可全留，但 sidecar 里的时间界必须是 **month-aligned shard
     bounds**；请求窗 `start`/`end` 只进 F2 裁剪与 `mem_key.extra`，不得
     作为月 shard 跨窗复用的相等字段。
   - 默认 `source_snapshot` 角色写死：保留 lake-wide shallow（接受任意
     sibling 变更 → 全局 miss，与今日单体同类），**或** 改为 per-symbol
     / 显式-token-only 并写清与 G2 的差异。不可「七字段都留」却让实现者
     猜作用域。
   - 显式 token 保留，作为 metadata-preserving 替换的逃逸口。
   - 短文件名摘要仍非认证；全字段 typed equality；认证失败禁止合并其他码。
3. **Invalidation matrix** for the six cases in §5 above, filled for the
   chosen A (or B) cut.
4. Header / P-table rows for P1 (and the P3 role paragraph) flipped from
   **未裁** to **已裁** only after Human's written approve. Docs merge
   alone still does not equal encode GO for untouched rows (P2/P4–P8 as
   applicable per knife).

Until those land, verdict stays **AGREE-HOLD**: no impl PR, no merge of
an encode branch from this review.

## Stop

Artifact only. `grok` CLI hung on the delegated exec script; this file
was written in-process against the same brief. No code changes. No merge.
