# S1.1 minute cold-load probe scaffolding — 2026-10-16

Implements the first knife of [r2 + cut A](plan-bar-cache-cold-load-2026-10-16.md),
after [Codex GO-WITH-NITS](../architecture/reviews/2026-10-16/pr-481-bar-cache-cold-load-r2/codex-r2.md)
on [#481](https://github.com/baiyibing/MyQuant-backtrader/pull/481).
Human「通过就实施」2026-10-16 authorizes this encode. Grok [GO-WITH-NITS](../architecture/reviews/2026-10-16/pr-482-s11-probe/grok.md); nits addressed on this branch before merge.

This PR delivers **S1.1 scaffolding only**. It does not change `ashare_bars`,
callers, cache files, memory namespaces, cache status or any strategy. The
runtime remains monolithic. `OSKH_MINUTE_CACHE_SHARD` is not installed here;
future S1 must default OFF: unset/0 = unchanged monolith, 1 = only
`bar_cache/shards/`, illegal values fail closed, no mixed layout. No S2 or S3.

## Run on the configured frozen host

Use the selected repository Python. Example arguments for the topk loader
window (codes are an explicit sample, not a replacement for its full codeset):

```sh
"$OSKH_MERGE_PYTHON" scripts/diagnostics/probe_minute_cache_cold_load.py \
  --codes 600000.SH 600036.SH --start 20251227 --end 20260914 \
  --request-codes 5575 --workers 16 --open-repeats 20 \
  --output /existing/evidence-dir/minute-cold-load-probe.json
```

The root is resolved through `resolve_period_root("1m") / dividend_type=none`.
No root guessing or fallback. Missing configured root or requested sample
file fails. Output creation is exclusive; choose a new file for each run.
`--start/--end` are the actual loader parameter window including warmup;
the script does not guess the caller's warmup. Optional `--source-snapshot`
preserves explicit G2 token semantics. Lake files are never written.

The JSON records G2 identity, size/nanosecond source stamps, full-month
bounds, one full-window scan versus a scan per month, frame equality,
mean Parquet open/close overhead, time ratios, and file-count/fd projections
for the explicit full-request count. The probe is serial (one Parquet handle
at a time); projected concurrent handles assume one per worker. Total shard
files and opening all files simultaneously are separate projections, not
claims about current live descriptors. No frame or price data is exported.

These are ordered observations: the OS page cache is **not evicted**. Repeat
with controlled ordering/cache state on the host before making cold-time
claims. Stable size/mtime and G2 identity are checked before/after; this
cannot detect a concurrent writer that preserves metadata. Freeze the source.

## Evidence status and next knife

No configured source/authority root is available in the implementation
environment. Real-host numbers remain **PENDING**. Synthetic parquet tests
exercise actual scan equivalence, month coverage, absence errors and source
mutation rejection; they do not establish host performance or alpha.

`cut_a_modeled_counts` reports expected whole-file invalidation separately
for same-month and cross-month +1 under `scenarios.*`. Keys are
`scenario_base_end` / `scenario_extended_end` plus
`modeled_not_measured_request_ends: true` — these are **modeled demo ends**,
not live loader request ends; do not paste them into CLI `--end`. It is
**not** a measurement of rebuilt files (`actual_rebuilt_shards` is null).
Same-month means all existing covered months; cross-month includes all
historical covered months plus the new one. No digest manifests, frozen
stamps or incremental-only promise.

`fd_extrapolation.projected_shard_files` is `request_codes × month_windows`
(full-request shard-file projection). Do not read it as a single-symbol
count. Host probe JSON embeds absolute `resolver_identity`; keep evidence
output outside the repo (see `.gitignore`).

Before S1: collect representative host scan/open data and monolith versus
candidate shard write/read costs, choose grain from those measurements,
and record actual rebuilt-file counts with local append/repair fixtures
without mutating the consumed lake. Then run the plan's same-commit
unset/0 versus 1 CSV byte comparisons, monthly boundary/window-memory/span
checks, G2 mutation checks and bypass tests. S1 cold must not regress against
monolith; <=5min is not a solo S1 gate. Warm must be second hit/mem with zero
lake reads. Source freeze and F7 unique tmp/complete atomic publication and
F8 enabled no-monolithic-partial rewriting remain required.

S2 codeset owns its own reconciliation and parking-code audit. S3 Arrow
requires a separate GO/PR and the existing frame contract; no mmap. No P1
infra, P2 DB/sqlite, CI allowlist changes, cleanup script or lake changes.

## 2026-11-01 本机实测补充（P15 未关闭）

原实现环境缺湖的记录保留。现已在 `DESKTOP-M5HCFD6` 的配置湖上，原样执行上文
两股、`20251227..20260914` 的示例两次。原生探针及 loader 与已合提交
`3197ffa6310e3704f0fc4d24d18e295bb27f2c1b` 同树；无代码、行情或运行缓存写入。
[脱离宿主路径的测量摘要](../operations/evidence/p15-host-samples-2026-11-01/readout.json)
记录脚本/loader blob、原始报告 hash、两轮 source identity 和具体数值；原始宿主 JSON
仍保存在忽略的审计目录，不复制入仓。

| 轮次 / 股票 | 行数 | 打开均值 ms | 全窗一次扫描 s | 逐月 / 一次扫描 | 打开 / 扫描 |
|---|---:|---:|---:|---:|---:|
| 1 / 600000.SH | 49164 | 0.365 | 0.4112 | 0.997 | 0.089% |
| 1 / 600036.SH | 49164 | 1.257 | 0.3717 | 1.092 | 0.338% |
| 2 / 600000.SH | 49164 | 0.427 | 0.3956 | 1.037 | 0.108% |
| 2 / 600036.SH | 49164 | 0.335 | 0.3339 | 1.243 | 0.100% |

每轮一趟与十个月分别读取的 frame 精确一致，源 size/mtime 与 G2 identity 前后稳定。
这组样本中的打开开销不到扫描耗时的 0.4%，不足以支持“打开小文件主导”的假设；
它也不能代表全市场请求成本。`5575 × 10 = 55750` 仅沿用示例的文件数外推，
不是最新宇宙统计或实际并发句柄数；探针始终串行只持有一个 Parquet 句柄。

OS 页缓存没有清除，两个扫描路径的顺序固定，因此这不是冷缓存吞吐验收。
分片粒度仍待代表性请求、受控冷/暖读写成本及实际 append/repair 重建计数；
S1 默认关闭实现、S2、S3 均未由本片推进，P15 保持开放。

## 2026-11-03 单体缓存命中路径补测

在原两股探针之后补六股、250,158 行样本：独立进程私有缓存 miss 2.520s，独立进程 hit 0.234s，同进程 mem 0.117s；三者帧摘要一致。见[运行回执](../operations/evidence/consumer-host-2026-11-03/p15/acceptance.json)与[环境配方](../operations/evidence/consumer-host-2026-11-03/p15/recipe.json)。OS page cache 未清空，这些有序测量不是冷 IO 或全市场预算。没有 shard 实现/真实重建计数，不据此裁定粒度或关闭 P15。
