# Plan:分钟 bar_cache 冷装载增量(装载侧「下一刀」)

- 日期:2026-10-16
- 状态:**待裁**(本文只是方案,不是 impl GO)
- 上游:[note-v653-host-perf-summary-2026-10-10.md](note-v653-host-perf-summary-2026-10-10.md) §5「另一刀」;[topk-joint-research-tracker-2026-09-22.md](topk-joint-research-tracker-2026-09-22.md) §6.11 首批分钟数据
- 范围:`ashare_bars.py` 分钟缓存(日线 `csv_daily_loader` 同构,二期跟进)。**不动成交核、不动书、不动净值。**

## 1. 问题与证据(2026-10-16 实测)

topk 分钟冷跑(pred 8a061ea4,窗 20260106–20260914 → 缓存身份窗 20251227–20260914):

| 阶段 | 冷(缓存 miss) | 热(partial) |
|---|---|---|
| 墙钟 | 1201.5s | 89.9s |
| `t_minute_s`(扫湖建缓存) | **1153.7s(96%)** | 40.5s |
| `t_sim_s` | 31.4s | 30.5s |

瓶颈不是模拟(v653 已砍),是**逐票扫湖建单一大文件**。当前身份 = `{start, end, schema, 全湖浅快照哈希}`(ashare_bars.minute_cache_identity):

- 换窗口 = 新身份 = **全量重建**(哪怕只是窗尾多 3 天);
- 湖每天增量写入会动浅快照 = **昨天建好的缓存今天就全废**;
- 单文件 ~5500 票 × 全窗,写 zstd 大 parquet,暖读也要整读(40.5s)。

目标:同湖同窗冷窗墙钟 20 分钟级 → **分钟级**;日常追加窗(末日 +N 天)→ **只建增量**;暖读 ≤15s。成交键与 `daily_equity.csv` **逐字节不变**是硬验收。

## 2. 方案(分三刀,可独立合,不混)

### S1 按票分片缓存(per-symbol shards)——主刀

- 缓存单元从「全湖单文件」改为「symbol 分片」:`bar_cache/shards/minute_none_{code}_{winhash}_{symhash}.parquet`,窗口哈希只含窗口与该票源文件 stamp(该票 parquet 的 mtime/size),**不含全湖快照**。
- 身份判定按票:湖增量只动被写过的票 → 只有那些票的 shard 失效重建;换窗只影响窗口哈希不同的票(见 S1.2 兜底)。
- 读侧:分片命中后拼装成现行 `bars` dict,引擎零改动(契约点只有 `load_minute_ohlc` 返回形状)。
- 写侧:沿用 #476 的 per-pid tmp + 原子 replace;分片天然并行安全。
- S1.1 探针(先跑):抽样 100 票,量「单票扫湖成本」与「分片小文件 × N 的打开开销」;若小文件打开主导,改为**票批分片**(每批 ~500 票,批哈希 = 批内票 stamp 排序哈希)。
- S1.2 窗口语义:窗口属于身份 → 换窗仍会重建。缓解:shard 窗口**对齐到月边界**(身份记 [month_start, month_end]);任意请求窗 = 覆盖月份 shard 的并集 + 首尾月裁剪。追加新一天 = 只建新月份 shard。**月 shard 内部**的窗口差异靠读侧 `searchsorted` 裁剪,不重建。

### S2 按需加载(池驱动)——省「根本不用载的票」

- topk 分钟冷建扫了 5575 票,而窗内池代码并集远小于此。探针先量:`distinct(pool ∪ held)` 到底多少票(topk 全市场分数池估计 ~1000–3000)。
- `load_minute_ohlc` 增 `codes_hint`:引擎在调度扫描前把「会进持仓/池」的代码集传下去,只扫这些票。缺行 fail-closed 语义不变(该到的票没有 bar 仍按现行规则报缺)。
- 风险:池外的已持票(前窗遗留)要并入 hint;漏并 = 净值变。验收用 S3 逐字节对账兜住。

### S3 Arrow 直读 + 暖读瘦身(v653 §5 原建议,顺路)

- 读缓存时 `pa.parquet.read_table(...).to_numpy()`/列直取,跳过 `to_pandas()`;只取 `open/high/low/close/hm` 列。
- 只削 40.5s 暖读的一部分,放最后,单独一 PR。

## 3. 实施顺序与验收

| 刀 | 交付 | 验收 |
|---|---|---|
| S1.1 探针 | 脚本 + 数据段(追加进本文) | 单票/批扫湖成本、小文件开销量化,决定票分片粒度 |
| S1 分片 | `ashare_bars` shard 读写 + `OSKH_MINUTE_CACHE_SHARD=0` 回滚开关 | ① 同窗复跑 `daily_equity.csv`/`trades.csv` 逐字节等旧缓存结果;② 冷窗墙钟 ≤5min;③ 末日 +1 天复跑只建增量(日志可证);④ 暖读 ≤15s |
| S2 按需 | `codes_hint` 贯穿 | 同窗逐字节等 S1 结果;`t_minute_s` 随池宽线性降 |
| S3 直读 | 读路径 Arrow 化 | 暖读再降;逐字节不变 |

对账配方(每刀必跑):`--strategy version6_53` 与 `--strategy topk_dropout` 各一窗,新旧行为 `daily_equity.csv` `cmp` 逐字节;不等 = 回滚重来。

## 4. 风险与不做

- **不做** mmap、不做跨进程常驻、不做湖内格式改动(parquet 仍是真源);
- 分片数量失控:票批粒度兜底 + `bar_cache/shards/` 定期清老窗(手动/脚本,不入引擎);
- 身份语义放宽的安全边界:票级 stamp 只看该票自己的源文件,湖目录改名/搬仓会整体 miss(可接受,宁可重建不可错价);
- 两刀不混装:S1/S2/S3 各自独立 PR,各自对账(v653 §5 原话)。

## 5. 与现网的接缝

- #476 已让并行写缓存安全;分片后并行更自然(每票/批独立 tmp+replace);
- `profile_sim.json` 的 `cache` 字段值域扩为 `miss/shard-miss/shard-partial/hit`(读侧汇总),对比批一眼看出增量建了多少。
