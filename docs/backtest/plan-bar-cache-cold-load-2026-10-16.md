# 计划：分钟 bar_cache 冷装载（2026-10-16 · r2 · cut A）

> **日期**：2026-10-16。**r2**（同日修订）：吸收 Grok 设计评审 **REQUEST_CHANGES**。r1 是已合并的 [#479](https://github.com/baiyibing/MyQuant-backtrader/pull/479)（master `ac5ff773`，正文 69 行）。**同日 cut A**：Human 书面绑定保守整文件失效（吸收 Codex HOLD + Grok AGREE-HOLD）。
> **状态**：**P1 / P3 身份合同已裁（Human cut A · 2026-10-16）**。其余 P2 / P4–P8 仍可用表内建议默认作 encode 门（须经 Codex 重评 GO）；合入本 docs PR **仍不是**自动 impl GO。身份阻断已解除，可开 encode 门评审。
> **评审**：Grok #479 **REQUEST_CHANGES**；Codex #481 **HOLD**（[codex.md](../architecture/reviews/2026-10-16/pr-481-bar-cache-cold-load-r2/codex.md)）；Grok #481 **AGREE-HOLD** 并推荐 cut A（[grok.md](../architecture/reviews/2026-10-16/pr-481-bar-cache-cold-load-r2/grok.md)）。#479 原文见 [PR #479 评论](https://github.com/baiyibing/MyQuant-backtrader/pull/479#issuecomment-6213298677) 与 [pr-479 grok.md](../architecture/reviews/2026-10-16/pr-479-bar-cache-cold-load/grok.md)。
> **上游**：[note-v653-host-perf-summary-2026-10-10.md](note-v653-host-perf-summary-2026-10-10.md) §5「另一刀」；[topk-joint-research-tracker-2026-09-22.md](topk-joint-research-tracker-2026-09-22.md) §6.11 首批分钟数据；[#476](https://github.com/baiyibing/MyQuant-backtrader/pull/476)（`47735bba`，per-pid tmp）；[#479](https://github.com/baiyibing/MyQuant-backtrader/pull/479)。身份守卫：[g2-minute-cache-identity-2026-09-28.md](g2-minute-cache-identity-2026-09-28.md)。
> **范围**：分钟 `bar_cache` 装载侧方案文档。**不动成交核、不动书、不动净值**；encode 须另开实现 PR，且默认关。
> **禁止**：不要按未改前的 69 行正文开 `ashare_bars` 实现 PR，也不要授权把探针、分片、代码集、Arrow 做进同一个 PR。刀序仍是 S1.1 → S1（缺省关）→ S2 → S3（单独 PR）。
> **对码**：master `ac5ff773`（#480 已合入后 tip 以 `origin/master` 为准）。下文行号是该 tip 的锚；行号漂移以符号名为准。

---

## 0. r2 怎么用

r1 把几件还没裁的语义写成了已定方案，并有三处和现码相反：整文件 stamp 做不到「追加一日只建新月」；月 shard 的裁剪 / `mem_key` / spans 没有合同；`codes_hint` 忽略了调用方已经传入的代码集。本修订把这些收成硬约束，并把选择收成八张卡。

方向（可复用分片、调用方缩小分钟装载集合、Arrow 直读单独一刀、不做 mmap）和现网瓶颈对齐。方向不是合同。

**2026-10-16 Human cut A**（书面）：P1 / P3 身份合同按 §4.2 绑定——保守**整文件**失效；不承诺「+1 天只建新月」；不冻住旧月 stamp。Grok 推荐 A 优于 B（B = 月 digest + manifest，日后再开）。其余 P2 / P4–P8 仍见表内建议默认；encode 门仍须 Codex 重评。

人裁顺序写在 §4.1。P1 已裁后，S1.1 的失效预期可按 §4.2 矩阵写出；P2 建议默认（F2）仍须在 encode 门一并确认。

---

## 1. 仍对齐的方向（不是已裁合同）

| # | 方向 | 未裁之前怎么读 |
|---|---|---|
| D1 | 单体整窗缓存改成可复用的分片。月份是候选粒度 | **P1 = cut A（已裁）**：整文件 stamp 参与身份；**不**承诺「只建新月」。跨窗复用靠月对齐 bounds，不靠追加增量 |
| D2 | 调用方缩小分钟装载集合 | 公式是 P4。未裁前保持现网并集，不新增调用方不传的 `codes_hint` |
| D3 | Arrow 直读单独一刀 | 帧形状是 P8。削的是命中后的解码。不做 mmap |
| D4 | `daily_equity.csv` 与 `trades.csv` 逐字节相同是硬门 | 必要，不够单独放行。比较基准与配方在 §7 |

成交核、策略书数字、净值口径不在本计划里改。

---

## 2. 问题与证据（口径已按现码改）

2026-10-16 topk 分钟实测。pred `8a061ea4`，CLI 窗 `20260106–20260914`。默认书的装载窗是 `warmup_start`（`WARMUP_DAYS = 10` 个自然日，`csv_daily_loader.warmup_start`）到结束日，即身份窗 `20251227–20260914`。

| 阶段 | 冷（缓存 miss） | 热（partial） |
|---|---|---|
| 墙钟 | 1201.5s | 89.9s |
| `t_minute_s` | **1153.7s（96%）** | 40.5s |
| `t_sim_s` | 31.4s | 30.5s |

1153.7s 是整段 `t_minute_s`，没有拆成读湖、写单体 zstd、再读回。40.5s **不是**纯 `hit` / `mem`。现码 `partial` = 身份命中后仍把缺码扫湖，再 `read_minute_cache(path, None)` 把**整个**单体读回来重写（`load_minute_ohlc`）。

现网冷路径绑在 `load_minute_ohlc` 的「整窗身份 + 单体 parquet」上。#476 只解决同一个 `.tmp` 被两个进程 unlink（Windows WinError 32）。

现身份不是 `{start, end, schema, 全湖浅快照哈希}`。`minute_cache_identity` 返回七个字段：

| 字段 | 现码 |
|---|---|
| `identity_version` | 整数 `1` |
| `start` / `end` | `_as_ymd` 之后的 `YYYYMMDD` |
| `dividend_type` | 显式 `"none"` |
| `schema` | **缓存** Arrow schema（`_cache_schema`）的 SHA-256，不是湖文件 schema |
| `resolver_identity` | `resolve(strict=True)` 之后的绝对根路径 |
| `source_snapshot` | 调用方显式 token，或默认 `shallow-v1:` + 根与**一层**子目录的 `[name, st_mode, st_size, st_mtime_ns]` |

浅快照不递归，不 `stat` `data.parquet`。G2 写明：深层原地修数可能不动父目录元数据；保留元数据的替换必须换显式 `source_snapshot` token。路径里的 12 位摘要不是认证。`_cache_identity_matches` 要求 sidecar 全字段类型和值一致。缺认证视为不可复用，并且禁止把未认证文件里的其他代码并进来。

单体文件是**该身份下请求代码并集**的 parquet，不是「湖上每一票都进了缓存」。全湖的是一层目录浅快照。`load_minute_from_lake` 只扫 `want`。5575 是这次请求集合的大小（`pool ∪ scores ∪ extra_load_codes_for_strategy`），不是 `dividend_type=none` 下的目录枚举。

书帧湖路径是一票一个文件，不是按月分区：

```text
symbol={partition}/data.parquet    # read_lake_minute_ohlc
```

这个文件装着该票全部历史。`read_lake_minute_ohlc` 先按 `utc_ms_range` 的闭区间过滤，再做 session 过滤、同分钟 keep-last、按日成交量滤零。缓存里存的是已经做完这些步骤的书帧。

换窗口会换路径里的 start/end 和整份身份的 12 位摘要，同票跨窗不能复用单体文件。这句和现码一致。

目标仍是：同湖同窗的冷装载从 20 分钟级降到分钟级；湖 stamp 稳定时不同请求窗可共享月 shard；暖读变短。冷/暖墙钟在 P6 未裁前**不是**验收数字。cut A 下**明确不承诺**「末日 +1 天只建新月」——源文件一变，该票覆盖窗内全部月份重建。`daily_equity.csv` 与 `trades.csv` 逐字节不变仍然是每一刀的硬门（§7）。

---

## 3. 硬约束 / 阻断项（F1–F6）

下面六条是阻断合同。它们约束任何未来实现。它们不是已经替 Human 选好的方案。F7 / F8 写在 §6，不单独立项。

### F1 失效单位与增量句

湖布局是一票一个 `symbol=*/data.parquet`，不是按月分区。**Human cut A（已裁，§4.2）**绑定保守整文件失效：该票源文件 stamp（`st_mtime_ns`，及等价整文件身份如 `st_size`）参与每个月 shard 的源身份；源文件任意追加 / 修正导致 stamp 变化时，该票覆盖窗内**全部**月份 shard 一起 miss——**不**承诺「+1 天只建新月」，也**不**声称未改字节的历史月在整文件 stamp 变化后仍可复用。

因此（cut A 下已是合同，不再是「未裁前禁止」）：

- **禁止**承诺「追加一日只建新月」。
- **禁止**「冻住旧月 stamp」。旧月跟随整文件源身份；为通过验收而冻住旧月会使该月修数静默陈旧。
- 「只有被写过的票失效」在 lake-wide 默认 `source_snapshot` 下**不**成立为全局保证（sibling 变更可全局 miss，见 §4.2）；在仅票级 stamp 视角下，被写过的票失效它的**每一个**覆盖月，不是「只失效新月」。
- 窗口身份与该票源身份是两个量。文件名里拆 `winhash` / `symhash` 时，正文不得再把 stamp 写进窗口哈希。
- stamp 精度：**`st_mtime_ns`（纳秒）**，不得只用秒级 mtime。秒级会把同一秒内两次修数收成同一 shard。

S1 验收**不得**写「只建增量」。探针必须分别报告：月末 +1 日（仍在当月）改写了几个 shard，跨月 +1 日改写了几个 shard。cut A 下两者对该票均为「覆盖窗内全部月份」。月字节 / 分区 digest（cut B）若日后需要，另开计划修订；本 cut **不**引入 digest manifest。

### F2 月 shard 的读契约

月 shard 若作为请求窗的超集存在（请求起止落在月中时，物理文件含月初和月末的 bar），返回给引擎的帧必须裁回请求闭区间。下面几条是合同正文，不是留给实现者猜的 side / 键 / 时区。

覆盖的月份是 `load_minute_ohlc` 的参数窗，含 `warmup_start` / `minute_load_start`，**不是** CLI `--start` / `--end` 的字面值。

- 普通书：`minute_load_start = warmup_start(start, WARMUP_DAYS)`，`WARMUP_DAYS = 10` 个自然日。证据里的 `20260106 → 20251227` 就是这条。
- `week_ma_gate` / `ma5_gate`：`minute_load_start = start`（CLI 起点）。分钟起点不再向前展开。
- version4 / version12 与 `--return-threshold-filter`、version9 / 9.1 / 10.1 会加大 `warm_days`。月份覆盖跟最终传进 `load_minute_ohlc` 的那一对起止。

裁剪谓词（与 `utc_ms_range` 同一套 `YYYYMMDD` 闭区间，含起始日和结束日的全部 session bar）：

```text
request_start <= ymd <= request_end
```

等价下标（这是**装载侧日期裁剪**，不是 note §5 的模拟侧 `searchsorted`，也不是 S3 的 Arrow 解码）：

```text
searchsorted(request_start 日 00:00, side="left")
  .. searchsorted(request_end 的下一天 00:00, side="left")
```

`searchsorted(结束日 00:00, side="right")` 会丢掉结束日整天。结束日买卖消失，`trades.csv` 会变。这条读法禁止。

同时：

- 月份之间按 `ymd` 不重叠。
- 拼接后的帧按时间单调，并且和单窗 keep-last 的去重结果一致。
- `mem_put` 和交给 `resolve_day_spans` 的对象只能是**裁剪后的帧**。
- `mem_key` 的 `extra` 必须含本次请求的 start/end。现码 `mem_key("minute", identity)` 只含身份字典；`mem_get` 在 `want ⊆ codes` 时原样返回帧，不再裁窗。同进程第二次 `run()` 走的就是这条（`status["cache"] = "mem"`）。身份若只剩月份，先跑的短窗会把短帧留给后跑的长窗，或先跑的未裁剪月帧被后跑的短窗拿去。
- spans 指纹对着裁剪后的帧。现码指纹是 `[len, ymd[0], ymd[-1]]`，绑定返回给引擎的那一帧。月 sidecar 的 iloc 不能直接套到裁剪后的帧上。指纹不合时现码会重建，这是安全的。为了让 sidecar 命中而跳过指纹，就会切错日。
- 身份 `.json` 已走 #476 的 pid + uuid tmp 再 `replace`。`*.spans.json` 今天是 `write_text` 直写。分片后半截 JSON 最多让本次重建 spans。阻断点是指纹对象，不是半截写本身。
- 引擎主循环按 `_slice_day`（`ymd → iloc`）切日，不会主动扫月末。这只在「返回帧的 bar 集合 = 现网 `[minute_load_start, end]` 闭区间」时成立。`_previous_rows` 对缺口日会落到更早的一根。月 shard 若把 `minute_load_start` 之前的 bar 留在帧里，缺口日的前收会变。

一趟扫描写出该票全部覆盖月份，还是每个月再扫一遍同一份 `data.parquet`，是 P2 的未裁项。约 10 个月的窗口若每月一趟，冷读按月数放大。未裁前两种都不得编码。

### F3 G2 认证字段

**P3 已裁（Human cut A · §4.2）**：G2 七字段**全留**于 shard sidecar 并参与 typed equality / 文件名摘要输入：`identity_version`、`start`、`end`、`dividend_type`、`schema`、`resolver_identity`、`source_snapshot`。票级源 stamp（`st_mtime_ns` / 整文件身份）归 P1，叠进源身份（可进 sidecar 扩展字段或与摘要输入绑定，但不得用秒级 mtime 顶替）。

角色写死（不得静默改语义）：

- sidecar 的 `start` / `end` = **月对齐分片窗**（该月闭区间 `YYYYMMDD` 对），**不是**本次请求窗。请求窗只进 F2 裁剪与 `mem_key.extra`。
- 默认 `source_snapshot` = 今日 lake-wide shallow。sibling / 父目录 mtime 变化可导致**全局** miss——cut A 下这是**有意保守**（与今日单体同类），不是 bug，禁止靠「悄悄丢掉该字段」来「修」。
- 显式 `source_snapshot` token **保留**，作为 metadata-preserving 替换（`cp -p` / `rsync -t` / utime）的逃逸口。

其余硬约束不变：

- 「湖目录改名 / 搬仓会整体 miss」只有在根 token（现码是 `resolver_identity`）还在身份里时才成立。只剩文件 mtime/size 时，新根上时间戳相同的树会命中旧 shard 里的价格。备份恢复保留了时间戳但价格已改，就是错价。
- 短文件名摘要不是认证。sidecar 全字段类型和值一致才算命中。认证失败禁止把未认证文件里的其他代码并进来（`tests/test_minute_cache_identity.py` 对七个字段的 missing / mismatch 有钉）。
- 旧单体路径不迁移、不自动复用。G2 对无摘要旧路径的句子是：旧 `minute_none_{start}_{end}.parquet` 不迁移、不删除、永不自动复用。分片开关打开后，现行 `minute_none_{start}_{end}_{digest}.parquet` 同样不读、不写、不迁进 shard。
- `dividend_type=front` 今天整段绕过共享缓存，`status["cache"] = "front_uncached"`。volume / amount 在 `load_minute_ohlc` 入口返回，`off:volume_required`。这两条旁路继续绕过。shard 前缀写成 `minute_none_` **不能**代替身份里的价格域字段。

### F4 分钟代码集

扫描前的分钟代码集就是调用方已经传入 `load_minute_ohlc` 的那个集合。现网在进 loader 之前拼完：

```text
all_codes = union(pool_days)
all_codes |= codes_from_scores(scores_by_day)
all_codes |= extra_load_codes_for_strategy(strategy)
```

`codes_from_scores` 的用途是湖装载，不限于 TopK 池。topk 冷跑的 5575 与池并集的差，主体是分数宇宙，不是 loader 多扫了池外湖文件。

硬约束：

- **删掉或改写** r1 的 `codes_hint`。不新增一个调用方不传的 hint 参数。`load_minute_ohlc(codes, start, end)` 已经只装 `codes`。
- `version6_53` 的停车码必须留在分钟集合里。`extra_load_codes_for_strategy("version6_53")` 返回 `PARKING_SYMBOL`（`600036.SH`，与 6.47–6.56 / 10.2 同一支）。这支代码经常不在池 CSV 里。扫描前持仓是空的，分钟入口没有 initial positions。停车码既不在池里，也不在扫描前的已持里。漏掉则停车买卖的分钟切片不存在，`version6_53` 的逐字节验收会失败，或在 `minute_bars[code]` 上 KeyError。
- 持仓是扫描的结果，不能在扫描前并入集合。扫描前能算的超集只来自池、分数、策略强制码和调用方显式预载。
- loader 对缺 bar **省略，不 raise**。`got` 只保留 `want` 里缓存里有的代码。缺行计数在跑完之后放进 `st.stats["codes_missing"]`。会抛错的是调用方少数路径（front 分钟缺行、`participation_rate` 缺量）。默认书是跳过该票。禁止把「缺行 fail-closed」实现成 loader 里对默认书 raise，否则今天能跑完的缺 bar 票会变成中止，净值对账不可比。
- 对账在代码集那一刀自己的 PR 里做完，**不推到 S3**。r1 第 41 行「漏并靠 S3 对账」作废。
- 同一 `all_codes` 还喂给日线、除权、`codes_missing`。分钟集合若收窄，日线该留宽的地方继续留宽。只改 `ashare_bars.py` 的签名、调用方仍把宽集合传进 `codes`，湖扫描张数不变。真正的改动面包括 `csv_minute_backtest.py` 与 `fullstrat_research_runners.py` 的分钟集合。日线写入不在分钟 PR 里改（见 §8）。
- 分数宇宙进不进分钟，是 P4，未裁。未裁前不得改调用方集合。

### F5 预算归属与 S3 帧

冷窗墙钟 ≤5min **不**单独挂在 S1。1153.7s 没有拆开。S1 不减少票数。这段时间如果主要是逐票读 `data.parquet`，分片写盘削不动它。如果主要是单体压缩写入，分片可能够。没有拆分之前，≤5min 不能当 S1 的通过线。

≤5min 只许绑在「读湖时间已经被探针拆开，并且票数或扫描次数真的下降」的那一刀上。除非探针把读湖时间拆开，并且票数或扫描次数真降，否则这道预算不挂在 S1。

S1.1 的失败条件必须含：

- 一趟扫描对每月一趟扫描的倍数；
- 月末 +1 日与跨月 +1 日各自改写的 shard 数；
- 打开耗时 / 单票扫湖耗时的倍数，以及外推到本次请求票数（证据约 5575）时的 fd 数量。没有这组数，探针报告无法裁粒度。

S3：

- 返回帧保持 DatetimeIndex（`ns`、无时区）+ `ymd` + float64 OHLC + int64 `hm`。`build_day_spans` 没有 `ymd` 就返回空。`_frame_from_cache_group` 把 `time` 收成 `DatetimeIndex.as_unit("ns")`，`hm` 收成 int64。湖侧价格是 float64。只交 numpy 五列 `open/high/low/close/hm` 会改变 `load_minute_ohlc` 的返回形状。
- S3 削的是命中后的解码，不是 partial 里的湖时间和整文件重写。note §5 的 14.9s 是当时那次热文件解码，不是这张表上的 40.5s。
- S3 单独 PR，不做 mmap。这点和 note §5 一致。

暖读的定义未裁（P6）。建议口径写在 P6：第二次、`hit` 或 `mem`、零湖读。40.5s 的 partial 不能当这条预算的对照。

### F6 开关缺省与状态字

`OSKH_MINUTE_CACHE_SHARD` 在仓库里还不存在。r1 只写了 `=0` 当回滚，没有缺省、空串和非法值。

**未裁 P5 之前，实现 PR 没有安全的落地姿态。** 禁止照抄 `OSKH_BAR_MEM`：那个开关把 `0` / `false` / `off` / `no` 当关，**缺省是开**。缺省开等于分片路径一合并就替换全部分钟书的缓存。

建议（仍是 P5，未裁）：缺省关，只有 `1` 打开，其他值 fail-closed 退出。`=0` 与未设置走今天的单体路径。

`=0` / 未设置时，`status["cache"]` 与现码逐值相同。现网值是：

```text
mem / hit / partial / miss / miss:identity / rebuild / off / off:volume_required
```

调用方另有 `front_uncached` 与 `qlib_1min`。G2 把文件态写成合同，并要求 volume / amount 保持 `off:volume_required`。`mem` 是进程内命中。

禁止用 `miss` / `shard-miss` / `shard-partial` / `hit` 覆盖同一个字段。分片计数走附加字段（建议名在 P8，未裁）。覆盖后，回滚路径和分片路径的日志无法跟今天的探针比，`tests/test_minute_cache_identity.py` 的字符串断言会整组失效。

---

## 4. 人裁点（P1–P8）

**P1 / P3 = Human cut A（2026-10-16）已裁。** 其余行：建议默认仍供 encode 门（Codex 重评）绑定；建议不是自动批准。合入本 docs PR 不把未裁行改成已裁。

| 卡 | 要裁的内容 | 绑定内容 / 建议默认 | 状态 |
|---|---|---|---|
| **P1** 失效单位 | 整文件 stamp，或该月字节 / 分区 stamp。`st_mtime_ns` 还是秒级 mtime | **已裁 = cut A**：该票整文件源身份（`st_mtime_ns`，及等价如 `st_size`）参与每个月 shard；源 stamp 变 → 该票覆盖窗**全部**月 miss。**不**承诺「+1 天只建新月」。**禁止**冻住旧月 stamp。不做月 digest / manifest（那是日后 cut B） | **已裁 · cut A** |
| **P2** 读契约 | 裁剪谓词、月份不重叠、一趟扫描写多月还是每月一趟、`mem_key` extra、spans 只描述返回帧、旧单体路径不读 | 采用 §3 F2 的 `ymd` 闭区间。`mem_key` 含请求 start/end。spans 对裁剪帧重建。建议一趟扫描写出该票覆盖月份；每月一趟未否决，探针必须报出倍数 | **未裁**（建议默认） |
| **P3** G2 字段 | 七个认证字段哪些留在 shard sidecar 且参与文件名。显式 `source_snapshot` 是否保留。认证失败是否仍禁止合并其他代码 | **已裁 = cut A**：七字段全留。sidecar `start`/`end` = **月对齐分片窗**（非请求窗）。默认 `source_snapshot` = lake-wide shallow（广域 miss = 有意保守）。显式 token 保留。短文件名非认证；全字段 typed equality；认证失败禁止合并其他码。票级 `st_mtime_ns` 精度归 P1 | **已裁 · cut A** |
| **P4** 分钟代码集 | 扫描前公式；日线是否仍用宽集合；分数宇宙进不进分钟；停车码谁负责 | 分钟 = `union(pool_days) ∪ extra_load_codes_for_strategy(strategy)`。分数宇宙留在日线，除非点名某条分钟读分数码的路径。停车码经 `extra_load_codes_for_strategy`，不另做 hint。缺 bar 不在 loader raise。不新增调用方不传的 `codes_hint` | **未裁**（建议默认） |
| **P5** 开关 | 未设置、空串、`0`、`false`、`off`、`no`、其他。其他值是退出还是当成关 | 缺省关。未设置与 `0` 走今天的单体函数，含 partial 整文件重写，`status["cache"]` 逐值不变。只有 `1` 打开。空串、`false`、`off`、`no` 与其他值 fail-closed 退出，不静默当开、也不静默当关 | **未裁**（建议默认） |
| **P6** 预算归属 | ≤5min 属于哪一刀。暖读的定义。+1 日指标 | 5min 不挂在单独的 S1 上。暖读 = 第二次且 `hit` 或 `mem` 且零湖读。S1 的冷预算是「不慢于单体冷路径」，直到 P4 合入。+1 日分两行计数：当月内一日、跨月一日，各打印 rebuilt shard 数（cut A 下对该票均为全覆盖月） | **未裁**（建议默认） |
| **P7** 残留文件 | 旧 stamp shard 的保留代数；tmp 清理；批成员的稳定分桶；writer 何时可以 replace | 引擎不自动扫盘删除。脚本只删「stamp 与当前源不一致」且 mtime 老于 N 日的 shard。不删 `*.tmp`，除非对应 pid 已不存在。批按代码排序后的固定区间分桶，批哈希覆盖批内全部成员的 stamp，不是本次请求的子集。writer 写完整个 shard 身份才 `replace`，失败不替换 | **未裁**（建议默认） |
| **P8** S3 与状态字 | 返回帧列与 dtype。`cache` 是替换还是附加。S3 是否允许改 `mem` 里的对象类型 | 书帧形状不变：DatetimeIndex(ns)、无时区、`open/high/low/close` float64、`hm` int64、`ymd` 与现网同值。`cache` 枚举冻结。附加 `shard_hit` / `shard_miss` / `shard_rebuild` 计数。S3 单独 GO。不做 mmap | **未裁**（建议默认） |

### 4.1 人裁顺序

**P5 → P3 → P1 → P2 → P7 → P4 → P6 → P8。**（逻辑顺序；P1/P3 已由 cut A 满足。）

P5 建议缺省关，避免「一合并就替换全部分钟缓存」。P3 / P1 已按 cut A 写死（§4.2）。P7 的残留规则跟着 P1 的整文件 stamp 走。P4 的集合公式独立于分片布局，但 S2 对账要等它写完。P6 的数字归属等探针条件（P2）和集合（P4）有着落再定。P8 留给 S3，不挡前面的刀。

**P1 已裁**：S1.1 失效预期按 §4.2 矩阵可写。P2 仍建议采用 F2；encode / 探针 PR 须在 Codex 重评 GO 后开。刀序不变：**S1.1 → S1（`OSKH_MINUTE_CACHE_SHARD` 缺省关）→ S2 → S3（单独 PR）**。

### 4.2 Human cut A（2026-10-16）— 身份合同 + 失效矩阵

来源：Human「按 A 改计划」；吸收 Codex [#481 HOLD](../architecture/reviews/2026-10-16/pr-481-bar-cache-cold-load-r2/codex.md) 与 Grok [#481 AGREE-HOLD](../architecture/reviews/2026-10-16/pr-481-bar-cache-cold-load-r2/grok.md)（**推荐 A 优于 B**）。B（月 digest + 认证 manifest + 重定义 snapshot 作用域）若日后需要增量追加，另开计划修订；**本 cut 不实现 B**。

#### 身份绑定

1. **失效单位（P1）** = 该票湖文件的整文件身份（至少 `st_mtime_ns`；实现可并列 `st_size`）。该 stamp 参与**每一个**月 shard 的源身份。源文件任意使 stamp 变化的追加 / 修正 → 该票在覆盖窗内的**全部**月 shard miss。
2. **明确不承诺**「末日 +1 天只建新月」；**禁止**冻住旧月 stamp；**禁止**声称「未改字节的历史月在整文件 stamp 变化后仍可复用」。
3. **G2 七字段（P3）全留**，含默认 `source_snapshot`。sidecar 的 `start`/`end` = **月对齐分片窗**；请求窗只进 F2 裁剪与 `mem_key.extra`。
4. 默认 lake-wide shallow `source_snapshot` 导致的广域 miss = **有意保守**，与今日单体同类；不得靠丢掉字段「修复」。显式 token 保留。
5. 跨窗复用：仅当源 stamp（及七字段相等）稳定时，不同请求窗可共享同一月对齐 shard。追加增量主义**不是**本 cut 的目标。

#### 失效矩阵（cut A 期望）

| 场景 | 该票月 shard | 其他票月 shard | 说明 |
|---|---|---|---|
| **同月追加**（末日 +1 日仍在当月，整文件 stamp 变） | 覆盖窗内**全部**月 miss / rebuild | 若仅票级 stamp：可仍 hit；若默认 lake-wide snapshot 因父目录 mtime 变：可能**全局** miss | 不存在「只建当月」 |
| **跨月追加**（+1 日落在新月，整文件 stamp 变） | 覆盖窗内**全部**月 miss / rebuild（含历史月与新月） | 同上（snapshot 广域规则） | 不存在「只建新月」 |
| **旧月修正**（改写历史月字节，整文件 stamp 变） | 覆盖窗内**全部**月 miss / rebuild | 同上 | 禁止冻住旧月 |
| **无关票替换**（另一 `symbol=*/data.parquet` 被替换） | 该票：若自身 stamp 未变且 snapshot 未变 → hit | 被替换票：其全部月 miss；若 shallow 父目录 mtime 变 → **全局**可能 miss | 广域 miss = 有意保守 |
| **显式 `source_snapshot` token 变更** | 凡 sidecar 带旧 token 的 shard **全部** miss | 全部 miss（token 在身份里） | 逃逸口；用于 metadata-preserving 替换后的强制失效 |
| **仅元数据替换**（`cp -p` / `rsync -t` / utime，size+mtime 不变） | 票级 stamp **可能不** miss | 默认 shallow **可能不** miss | **必须**换显式 token（或接受陈旧风险）；cut A 不静默宣称能检测此类替换 |

S1.1 探针须按上表打印 rebuilt-shard 计数（当月 +1 与跨月 +1 分行），不得把「只建新月」写成通过句。

---

## 5. 回滚三句（建议 · 仍未裁）

这三句绑在 P5 上。Human 未书面批准之前，它们是建议，不是已落地开关。避免实现者各写各的：

1. `OSKH_MINUTE_CACHE_SHARD` 未设置或 `0`：走今天的 `minute_cache_identity` / 单体路径 / 今天的 `status["cache"]` 字符串。partial 整文件重写留在这条路径上，包括「认证失败禁止合并未请求代码」。
2. `=1`：只写 `bar_cache/shards/`，不读不写单体 `minute_none_*.parquet`，不把单体内容迁移进 shard。
3. 从 `1` 回到 `0`：shard 文件留在磁盘，单体路径按自己的身份重新 miss / hit。不存在「半片 shard、半片单体」拼出来的第三次布局。

空串与 `false` / `off` / `no` / 其他非法值的退出行为见 P5 建议，不塞进上面三句。

---

## 6. 切点附带（F7 / F8）

这两条跟着 F1 和回滚开关走。不单独立项。未写进实现 PR 的切点说明之前，分片 PR 不得开。

### F7 并行只覆盖 #476 的 tmp 文件名

#476 的事实可以保留：tmp 是 `{path.name}.{pid}.{uuid8}.tmp`，身份 json 同一模式，`replace` 之后最后一次原子替换获胜。分片沿用这个名字，可以避开两个进程 unlink 同一个 `.parquet.tmp`。

下面几件现码不提供，r1 写成「分片天然并行安全」的部分作废：

- 同一目标路径、两边内容不同：最后一次 `replace` 获胜。文件名不变时，后来的读者不会因为 stamp 再 miss。典型窗口是两边 `stat` 到同一个 mtime/size，读到的字节却不同（跑的过程中湖在动）。G2 的前提是运行期间源冻结。这个前提保留。
- 批分片若允许「只写入本进程要的代码、文件名却用整批哈希」，后写的进程会把先写进程的代码从批文件里拿掉。现网单体 partial 已经是这个丢失更新。各进程内存里的 `got` 仍是自己的，所以单次净值通常还在；缓存会抖动，下一轮再扫湖。分片把丢失范围从整窗文件缩小到同一 shard。读者继续做 `missing = want - present`。writer 要么写完该身份下的全部代码，要么失败时不 `replace`。
- `writer.close()` 之后、`replace` 之前若异常，`finally` 不再删 tmp（`writer` 已置空）。票 × 月之后，崩溃残留的 tmp 按 shard 个数涨。清理规则归 P7：不能删仍在写的 pid。
- 老 stamp 的 shard 不会被新文件名替换掉，会留在盘上。票 × 月 × 每次源 stamp 变更是一组新文件。没有保留代数时磁盘没有上界。这和 F1 叠在一起：整文件 stamp 每日都变时，历史月的旧文件每天留一套。保留代数归 P7。引擎不自动扫盘。
- 批的成员必须稳定。按「本次请求的顺序切 500」会让同一票在不同运行落入不同批，批哈希永远 miss。稳定分桶键与「批哈希覆盖批内全部成员」归 P7。S1.1 用打开开销决定单票还是批，决定不了成员规则。

### F8 partial 重写在开关打开时停用

`load_minute_ohlc` 在身份命中且有缺码时，把单体文件全部读回、合并、整文件重写。分片之后若把这段包一层继续调用 `write_minute_cache`，会把已命中的 shard 再打成一个单体，两个布局叠写。

- `=0` / 未设置：这段原样留下。
- `=1`：缺的是 shard，只写缺的 shard，不读回其他票，不调用单体 `write_minute_cache`。

旁路不变量（分片 PR 必须保持，并且不产生 shard）：

| 路径 | 今天的 `cache` | 分片 |
|---|---|---|
| `include_volume` / `include_amount` | `off:volume_required` | 不建身份、不写 shard |
| `use_cache=False` | `off` | 不写 shard |
| `dividend_type=front` | `front_uncached` | 不进 shard |
| `minute_source=qlib_1min` | `qlib_1min` | 不进 shard |
| `load_session_bars` 的湖源 | 写死 `use_cache=False` | 继续绕过。性能目标不要写成「所有分钟入口」 |

`version11` 与 `--tail-window-buy` 走 `include_volume` / `include_amount`，不在 §7 点名的两支逐字节配方里。它们靠上表的不变量守住，不靠那两支 CSV 对账。

---

## 7. 刀序与逐字节 DoD

实现顺序仍是下面四刀。**仅在该刀依赖的 P* 有书面选择之后**才允许对应实现 PR。每一刀独立 PR，各自对账。Arrow 不和分片同 PR。

| 顺序 | 刀 | 依赖的书面裁 | 这一刀交付 | 通过 / 失败 |
|---|---|---|---|---|
| 1 | **探针 S1.1** | **P1 已裁（cut A）**；P2 须在 encode 门确认建议默认。P6 未裁时可以量数，不能把 ≤5min 写成通过线 | 脚本 + 数据段回填本文。不改默认装载 | 失败条件：一趟扫描 vs 每月一趟的倍数；月末 +1 日与跨月 +1 日各自改写的 shard 数（cut A：对该票均为覆盖窗全月，见 §4.2）；打开开销 / 单票扫湖倍数，以及外推到请求票数的 fd。粒度（单票或稳定批）由这组数裁，不由「小文件打开主导」一句口头裁 |
| 2 | **分片 S1** | **P1/P3 已裁（cut A）**；P2、P5、P7 须在 encode 门确认建议默认。冷预算用 P6 的「不慢于单体」，直到 P4 合入 | `ashare_bars` 的 shard 读写。**缺省关**（P5）。不改日线写入 | 同提交上 `OSKH_MINUTE_CACHE_SHARD=0` 对照，`daily_equity.csv` / `trades.csv` 逐字节等。`=0` 的 `status["cache"]` 与现码逐值相同，且不产生 shard。不慢于单体冷路径，直到 P4 合入。不等则该刀回滚 |
| 3 | **代码集 S2** | P4 须先有书面选择 | 改调用方的分钟集合。日线该留宽的地方留宽。自己对账 | 同提交逐字节等。对账在本刀 PR，不推到 S3。漏码、停车码缺失都算本刀失败 |
| 4 | **Arrow S3** | P8 单独 GO | 命中后的解码。帧形状不变。不做 mmap | 合成测试先比帧：索引单位 ns、无时区、OHLC float64、`hm` int64、`ymd` 与现网同值。两支配方是这组单测绿了之后的集成门。削的是解码，不声称削掉 partial 里的湖时间 |

### 7.1 比较基准

比较基准是**同一提交**上 `OSKH_MINUTE_CACHE_SHARD=0` 的输出。用昨天留下的单体缓存当「旧结果」，会把身份漂移和本次改动混在一起。

`PYTHONHASHSEED=0`。不等则该刀回滚，不带着差合入。

### 7.2 配方钉死

两支都走 `load_minute_bars`。各跑基窗，再各加一轮「结束日 +1 且仍在当月」和「结束日 +1 且跨月」。基窗的 +1 都还在 9 月，不能代替跨月样本。跨月那一轮的月末日按湖日历钉在探针记录里，必须跨过 `YYYYMM`。

**topk_dropout**（tracker §6.11 的首批分钟，pred `8a061ea4`，`replay_20260917_current_ruler`）：

```text
set PYTHONHASHSEED=0
csv_minute_backtest.py --strategy topk_dropout --pred-csv <pred 8a061ea4 的冻结 CSV> ^
  --start 20260106 --end 20260914 --stop-pct 0.10 ^
  --cash-total 21000000 --dividend-type none --minute-source lake ^
  --out-dir backtest_output\csv_minute_topk_dropout_20260106_20260914_<stamp>
```

装载窗（默认书，非 week_ma / ma5 闸）= `20251227–20260914`。无 ST / 年龄 / 15% / buy-state 闸。资金用书默认 2100 万，不换成 1e8。当月 +1 的结束日是 `20260915`。

**version6_53**（note §6）：

```text
set PYTHONHASHSEED=0
csv_minute_backtest.py --strategy version6_53 --start 20251023 --end 20260909 ^
  --cash-total 27000000 --name-budget 10000 --rule-profile industry ^
  --out-dir backtest_output\csv_minute_v6_53_20251023_20260909_industry_<stamp>
```

停车码 `600036.SH` 必须在分钟集合里。当月 +1 的结束日是 `20260910`。

已有目录拒绝覆盖。数字产物不入库。

### 7.3 逐字节门抓住什么、抓不住什么

能抓住的：价格变了、结束日被裁掉、停车码没装上、topk 真用到的分钟代码被集合丢掉、行序变了且这两份 CSV 的行序跟着变。主循环的成交顺序来自池和持仓，不来自缓存字典序。裁错日和漏码会改 CSV。

不放进逐字节门：

- 窗的起止正好是自然月边界时，裁剪是空操作。所以配方必须含月中的基窗，外加当月 +1 与跨月 +1。
- partial / 纯 `hit` / 同进程第二次 `mem`。CSV 相同也可以是每次都重新扫湖。暖读预算要同时要求零湖读和 `cache` 状态（定义归 P6）。
- float 收窄。S3 若把 float64 收成 float32，CSV 格式化有时仍能撞上同一串。帧的 dtype 单测在集成门之前。
- `profile_sim.json`、日志、`codes_missing`。分片计数一变，profile 必然不同。把 profile 放进同一条 `cmp` 会迫使实现者伪造旧计时字段。验收要的增量证据是 **rebuilt shard 计数**，不是每票打一行 shard 路径。5575 行路径倾倒淹没计数。
- 旁路五条（volume、amount、front、`use_cache=False`、`qlib_1min`）的状态字与「不产生 shard」。两支配方不走这些旁路，所以要单独列成不变量（§6 F8），不靠 CSV `cmp`。
- 其他仍调用 `load_minute_bars` 的入口（`fullstrat_research_runners.py`、Mode B `load_monitor_bars`）。两支配方绿了，不代表这些入口的代码集已经被 P4 覆盖。P4 没点名的入口，分钟 PR 不顺手改它们的集合。

---

## 8. 非目标

| 不做 | 原因 |
|---|---|
| 本 PR 或未裁卡上的 `ashare_bars` / 引擎 / 缓存实现 | 状态是待裁。r1 的 69 行不是施工图 |
| 改成交核、改书的规则数字、改净值口径 | 装载侧。逐字节门就是为了证明没改这些 |
| 开新策略版本 | 仓库约定：未批准不开下一个版本号 |
| mmap、跨进程常驻、改湖内 parquet 布局 | 文件缓存仍是跨进程真源。`bar_store` 只跳过同进程第二次解码 |
| 分钟 PR 里改日线缓存写入 | 日线身份在 `csv_daily_loader.py`，有自己的浅快照和 #476 tmp。同构是二期，本计划不给日线 PR 授权 |
| 把旧单体迁进 shard，或让 `=0` 与 `=1` 拼一种混合布局 | §5 回滚三句 |
| 冻住旧月 stamp | F1。不在 P1 的选项里 |
| 新增调用方不传的 `codes_hint`，或在 loader 里对缺 bar raise | F4 |
| 用新枚举替换 `status["cache"]` | F6 / P8 |
| 把性能目标写成所有分钟入口 | `load_session_bars` 湖源继续 `use_cache=False` |
| 引擎自动扫盘删除 shard / tmp | P7。清理是脚本，且不删活着的 pid |

---

## 9. 勘误（r1 易误导处，本修订吸收）

| r1 写法 | r2 口径 |
|---|---|
| 「全湖单文件」 | 该身份下请求代码并集的单体 parquet。全湖的是一层目录浅快照 |
| 暖路径 40.5s 是热读 | partial：缺码扫湖 + 整文件重写。不是纯 `hit` / `mem` |
| note §5「两刀不混」= S1/S2/S3 | note §5 的两刀是已经落地的**模拟侧** `searchsorted`，和**装载侧** Arrow 解码。本计划的日期裁剪是第三处，用 §3 F2 的闭区间谓词命名，不叫「模拟器里那把 searchsorted」 |
| 日线同构、二期跟进 | 指针在 `csv_daily_loader.py`。二期未开。分钟 PR 不改日线写入 |
| 验收第 ③「只建增量（日志可证）」 | 要计数：当月 +1 与跨月 +1 各自的 rebuilt shard 数。不是路径倾倒。**cut A 下禁止写成「只建新月」**；期望见 §4.2 矩阵 |
| `codes_hint` = 池 ∪ 已持，扫描前传入，漏并靠 S3 | 作废。见 F4 / P4 |
| `cache` 改为 `miss/shard-miss/shard-partial/hit` | 作废。枚举冻结，计数走附加字段 |
| 身份 = `{start, end, schema, 全湖浅快照哈希}` | 七字段见 §2。schema 是缓存 schema 哈希。快照是根 + 一层子目录的纳秒 stamp |

---

## 10. 链接与修订

| 项 | 位置 |
|---|---|
| 本计划 | `docs/backtest/plan-bar-cache-cold-load-2026-10-16.md`（r2 在同一文件上修订，不另开平行文件名） |
| 已合并 r1 | [#479](https://github.com/baiyibing/MyQuant-backtrader/pull/479) · `ac5ff773` |
| Grok 评审 | [评论](https://github.com/baiyibing/MyQuant-backtrader/pull/479#issuecomment-6213298677) · [grok.md](../architecture/reviews/2026-10-16/pr-479-bar-cache-cold-load/grok.md)（`docs/architecture/reviews/2026-10-16/pr-479-bar-cache-cold-load/grok.md`） |
| 上游测量 | [note-v653 §5 / §6](note-v653-host-perf-summary-2026-10-10.md) · [tracker §6.11](topk-joint-research-tracker-2026-09-22.md) |
| 并行 tmp | [#476](https://github.com/baiyibing/MyQuant-backtrader/pull/476) |
| 身份合同 | [G2](g2-minute-cache-identity-2026-09-28.md) |

| 版本 | 日期 | 内容 |
|---|---|---|
| r1 | 2026-10-16 | docs-only 首版，随 #479 合入。状态待裁。正文 69 行，若干未裁语义写成了已定方案 |
| r2 | 2026-10-16 | 吸收 Grok **REQUEST_CHANGES**。F1–F6 收成硬约束。P1–P8 保持未裁。回滚三句与刀序改到「P* 裁完才允许对应实现」。**仍是待裁 / 非 impl GO。** 不要按 r1 开 `ashare_bars` 实现 PR |
| r2 · cut A | 2026-10-16 | Human 绑定 **(A) 保守整文件失效**。P1/P3 **已裁**；§4.2 身份合同 + 失效矩阵。吸收 Codex HOLD + Grok AGREE-HOLD（荐 A 不荐 B）。刀序不变。身份阻断解除；encode 仍须 Codex 重评 GO，且缺省关、不 merge |

下一份需要评审的是 **cut A 之后**的计划 tip（本文件）。r1 的 69 行与 r2 未裁身份一句话不再当作 encode 合同。

## 11. S1.1 encode status (2026-10-16)

Codex [cut A re-review GO-WITH-NITS](../architecture/reviews/2026-10-16/pr-481-bar-cache-cold-load-r2/codex-r2.md)
binds P2/P4–P8 suggested defaults through Human「通过就实施」2026-10-16.
First delivery is [S1.1 probe scaffolding](note-minute-cache-cold-load-s11-2026-10-16.md)
only; no runtime shard path. Real-host measurements, actual rebuilt-file
counts and grain decision remain PENDING because no lake root is configured
in the encode environment. No performance or CSV acceptance claim follows.
S1 default-OFF shards, S2 and separate S3 remain subsequent knives.
