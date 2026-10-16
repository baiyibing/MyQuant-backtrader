VERDICT=REQUEST_CHANGES

# PR #479 分钟 bar_cache 冷装载计划 — 人裁前设计评审

> 日期：2026-10-16
> 角色：Grok 设计评审（只审；不改计划、不写实现、不重开 PR）
> 对象：已合并 docs-only PR #479，master `ac5ff773`，单文件 `docs/backtest/plan-bar-cache-cold-load-2026-10-16.md`（69 行，状态仍是**待裁**）
> 对码：`backtest/research/ashare_bars.py`、`backtest/research/bar_store.py`、`backtest/research/market_layer.py`、`csv_minute_backtest.py` 装载段、G2 合同、`note-v653` §5、#476 `47735bba` 的 per-pid tmp
> 本文不构成 impl GO。计划正文按下面阻断项改完之前，不能当作 Codex 的已裁合同。

## 摘要

方向（单体窗口缓存改成可复用的月份分片、调用方缩小分钟装载集合、Arrow 直读单独一刀、不对 mmap）和现网瓶颈是对齐的。现网冷路径的墙钟确实绑在 `load_minute_ohlc` 的「整窗身份 + 单体 parquet」上，#476 也只解决了同一个 `.tmp` 被两个进程 unlink 的问题。

这份 69 行计划把几件还没裁的语义写成了已定方案，而且有三处和现码相反：

1. 票级 stamp 取的是整份 `symbol=*/data.parquet` 的 mtime/size，月份 shard 仍会在任意一日增量时全体失效，「末日 +1 天只建新月」在现网湖布局上不成立。
2. 读侧裁剪、`mem_key`、`resolve_day_spans` 没有合同。月 shard 物理上含请求窗外的 bar；裁错或把月 iloc 用到另一段窗口上，会改 `daily_equity.csv`。
3. `codes_hint` 忽略了调用方已经传入的 `codes`。现网集合是 `pool ∪ scores ∪ extra_load_codes_for_strategy`。`version6_53` 的停车码不在池里。计划写的「缺 bar 仍 fail-closed」在 loader 里不存在。

另外：丢掉 G2 的 `identity_version` / `schema` / `dividend_type` / `resolver_identity` 之后，「搬仓整体 miss」这条安全句是假的；`OSKH_MINUTE_CACHE_SHARD` 只有回滚取值、没有缺省；S1 的冷窗 ≤5min 绑在一段没有拆开的 1153.7s 上；S3 的列清单少了引擎还在用的 `ymd` 和 DatetimeIndex。

人裁要先补 P1–P8，再开实现 PR。S1.1 探针可以在切点写明之后单独开，但不能带着现在的 S1 验收表开工。

## Findings（严重优先）

### F1 阻断 — 整文件 stamp × 月 shard，增量句是假的

计划 S1：shard 名 `minute_none_{code}_{winhash}_{symhash}.parquet`，stamp = 该票 parquet 的 mtime/size。S1.2：窗口对齐自然月，追加一天只建新月份 shard。

现网书帧湖路径是一票一个文件，不是按月分区：

```377:377:backtest/research/ashare_bars.py
path = Path(root) / f"symbol={to_partition_key(code)}" / "data.parquet"
```

这个文件装着该票全部历史。mtime/size 一变，所有月份的 `symhash` 一起变。每日增量写进这一个文件时，已经建好的历史月 shard 全部 miss，要重扫重写。计划第 35 行的「追加新一天 = 只建新月份 shard」和第 31 行的「只有被写过的票失效」不能同时成立：被写过的票会失效它的每一个月，而不是失效新月。

更危险的读法是：为实现「只建新月」，实现者把旧月 shard 的 stamp 冻住、不再跟随文件。那样一月里的修数不会使一月 shard 失效，价格会静默陈旧。

计划正文对 stamp 的说法也不一致：第 30 行写窗口哈希含 stamp，文件名又把 `winhash` 和 `symhash` 拆开。

S1.1 没有把「月末 +1 天（仍在当月）改写了几个 shard、跨月又改写了几个」列为探针失败条件。S1 验收第 ③ 条「只建增量（日志可证）」会在按文字实现后直接失败，或者逼实现者去做上面那种冻住旧月的错法。

### F2 阻断 — 月 shard 含窗外出界 bar；裁剪 / mem / spans 没有可执行合同

S1.2 写「月内窗口差异靠读侧 `searchsorted` 裁剪」。没有 side、没有键、没有时区、没有和现网闭区间对齐的谓词。

现网湖过滤是闭区间，含起始日和结束日的全部 session bar：

```25:31:backtest/research/market_layer.py
def utc_ms_range(start: str, end: str) -> tuple[int, int]:
    """Convert a closed YYYYMMDD range to UTC-midnight milliseconds."""
    ...
    t1 = int((last + timedelta(days=1)).timestamp() * 1000) - 1
```

`read_lake_minute_ohlc` 先按这个范围过滤，再做 session 过滤、同分钟 keep-last、按日成交量滤零。缓存里存的是已经做完这些步骤的书帧。

若实现者对 DatetimeIndex 做 `searchsorted(end 日的 00:00, side="right")`，结束日整天会丢掉。`_slice_day`（`csv_minute_backtest.py:1191`）靠 `ymd → iloc`。结束日被裁掉，当日买卖消失，`trades.csv` 会变。

月 shard 是请求窗的超集（请求起止落在月中时，物理文件含月初和月末）。下面三条现网机制计划都没写，任何一条接错都会把超集送进引擎：

- `mem_key("minute", identity)`（`ashare_bars.py:709`，`bar_store.py:29`）只含身份字典。`mem_get` 在 `want ⊆ codes` 时原样返回帧，不再裁窗（`bar_store.py:36-42`）。同进程第二次 `run()` 走的就是这条（`status["cache"]="mem"`，`:713-720`）。身份若只剩月份，先跑的短窗会把裁过的帧塞进 store，后跑的长窗直接拿到短帧；或者先跑的未裁剪月帧被后跑的短窗拿去，短窗看见月末 bar。note §5 已经把「同一进程第二次 run 走 bar_store」当成既成事实。
- `resolve_day_spans` / `write_span_sidecar`（`ashare_bars.py:615,741`，`bar_store.py:111-184`）用 `[len, ymd[0], ymd[-1]]` 指纹绑定**返回给引擎的那一帧**。月 sidecar 的 iloc 不能直接套到裁剪后的帧上。指纹不合时现码会重建，这是安全的。为了让 sidecar 命中而跳过指纹，就会切错日。
- span 文件今天是 `write_text` 直写，不走 #476 的 pid+uuid 原子替换。分片后半截 JSON 最多让本次重建 spans，结果仍可正确。阻断点是指纹必须对着**裁剪后的帧**，不是半截写本身。

引擎主循环按日历 `_slice_day`，不会主动去扫月末。但这只在「返回帧的 bar 集合 = 现网 `[minute_load_start, end]` 闭区间」时成立。`_previous_rows`（`:1203`）对缺口日会落到更早的一根；月 shard 若把 `minute_load_start` 之前的 bar 留在帧里，缺口日的前收会变。装载窗口本身也不是 CLI `--start`：`csv_minute_backtest.py:2492-2494` 先做 `warmup_start`（普通书 10 个自然日），`week_ma_gate` / `ma5_gate` 的分钟起点又等于 `--start`。计划问题陈述里的 `20260106–20260914 → 身份窗 20251227–20260914` 就是这条 10 日展开，S1.2 却没有写「月份覆盖的是 `load_minute_ohlc` 的参数窗」。

可执行的裁剪谓词（要写进计划，而不是留给实现者猜）是：拼接各月之后，只保留 `request_start <= ymd <= request_end` 的行；`ymd` 与 `utc_ms_range` 用的是同一套 `YYYYMMDD`。等价的下标形式是 `searchsorted(start 日 00:00, side="left")` 到 `searchsorted(end 日的下一天 00:00, side="left")`。月份之间按 `ymd` 不重叠。拼接后的帧要按时间单调，并且和单窗 keep-last 的去重结果一致。`mem_put` 和交给 `resolve_day_spans` 的对象只能是这帧。`mem_key` 的 extra 必须含本次请求的 start/end。

### F3 阻断 — 丢掉 G2 认证字段之后，计划自己的失效句不成立

计划把现身份写成 `{start, end, schema, 全湖浅快照哈希}`。现字典比这多，而且 schema / 快照都不是计划字面上的那种哈希：

```496:498:backtest/research/ashare_bars.py
return {"identity_version": 1, "start": _as_ymd(start), "end": _as_ymd(end),
        "dividend_type": "none", "schema": _identity_hash(schema),
        "resolver_identity": str(root), "source_snapshot": source_snapshot}
```

`schema` 是**缓存** Arrow schema 的 SHA-256，不是湖文件 schema。`source_snapshot` 默认是 `shallow-v1:` 加上根目录和**一层**子目录的 `[name, st_mode, st_size, st_mtime_ns]`（`:471-492`）。不递归，不 `stat` `data.parquet`。G2 合同写明：深层原地修数可能不动父目录元数据；保留元数据的替换必须换显式 `source_snapshot` token。路径里的 12 位摘要不是认证，sidecar 全字段类型和值一致才算命中（`_cache_identity_matches`，`:512-519`；G2 文「缺认证视为不可复用」）。

计划的票级文件 mtime/size 对「普通覆写、mtime 会变」比目录戳更严，同一 size 也会 miss。真正还会静默命中的是 size 与 mtime **都**保持的替换（`cp -p` / `rsync -t` / utime 回拨）。计划没有保留显式 token，这条 G2 补丁路径没有替代物。计划只写 `mtime`，没写 `st_mtime_ns`。现码浅快照用纳秒。秒级 mtime 会把同一秒内的两次修数收成同一 shard。

「湖目录改名/搬仓会整体 miss」在提议的身份下不成立。现网 miss 是因为 `resolver_identity` 是 `resolve(strict=True)` 之后的绝对路径，换根就换文件。只剩文件 mtime/size 时，新根上时间戳相同的树会命中旧 shard 里的价格。shard 里是 bar 的副本：内容碰巧相同则命中是对的；备份恢复保留了时间戳但价格已改，则是错价。计划把 miss 当成安全方向，身份里却没有根 token。

湖级 schema / 缓存列布局变化同样没有失效位。源文件 mtime 不变、读代码改了列解释或 `_cache_schema` 时，文件名仍命中。现网把 `identity_version` 和 schema 哈希放进身份，版本不对是 `miss:identity`，而且禁止把未认证文件里的其他代码并进来（`tests/test_minute_cache_identity.py` 对七个字段的 missing/mismatch 都有钉）。计划的文件名没有这些字段，也没有写「旧 `minute_none_{start}_{end}_{digest}.parquet` 不迁移、不读取」。G2 对旧路径的句子就是这句。

`dividend_type=front` 今天整段绕过缓存（`csv_minute_backtest.py:2546-2556`，`cache=front_uncached`）。shard 前缀写死 `minute_none_`。身份里没有价格域字段时，后续只要有人把 front 根目录指进同一套 shard，前复权价格会进 none 书。这条旁路要写成不变量，不能靠前缀字符串碰运气。

### F4 阻断 — `codes_hint` 的集合、时机、失败语义都和调用方不符

`load_minute_ohlc(codes, start, end)` 已经只装 `codes`。冷构建不会扫湖上的其他票。`load_minute_from_lake` 的期货字典就是 `wanted`（`:446-453`）。5575 是这次请求集合的大小，不是 `dividend_type=none` 下的目录枚举。

请求集合在进 loader 之前就拼完了：

```2476:2480:backtest/research/csv_minute_backtest.py
all_codes = {c for codes in pool_days.values() for c in codes}
all_codes |= codes_from_scores(scores_by_day)
all_codes |= extra_load_codes_for_strategy(strategy)
```

`codes_from_scores` 的 docstring 写的是「for lake load, not just TopK pool」（`topk_dropout_scores.py:161-164`）。topk 冷跑的 5575 与「池并集更小」的差别，主体是分数宇宙，不是 loader 多扫了池外湖文件。

`extra_load_codes_for_strategy("version6_53")` 返回停车码（`csv_simulate_loop.py:1293-1311`；`strategy6_53_rules.py:41` 为 `600036.SH`）。这支代码经常不在池 CSV 里。计划的 hint 是「池 ∪ 已持」，并且「在调度扫描前」传下去。扫描前持仓是空的，没有仓位文件（分钟入口没有 initial positions）。停车码既不在池里，也不在扫描前的已持里。它被漏掉时，停车买卖的分钟切片不存在，`version6_53` 的逐字节验收会失败或在 `minute_bars[code]` 上 KeyError。计划第 41 行只写了「前窗遗留已持」，没有写这支策略强制码。

同一 `all_codes` 还喂给日线、除权、`codes_missing`。S2 若只给分钟加一个新参数、调用方仍把宽集合传进 `codes`，湖扫描张数不变。真正要改的是 `csv_minute_backtest.py` 和 `fullstrat_research_runners.py:62-110` 的分钟集合，日线该留宽的地方继续留宽。计划范围写「`ashare_bars.py`」，S2 在这个范围里做不成。

失败语义也被写反了。loader 对没有 bar 的代码是省略，不抛错（`:739` `got = {code: cached[code] for code in want if code in cached}`）。缺行计数在跑完之后放进 `st.stats["codes_missing"]`（`csv_minute_backtest.py:2761`）。会抛错的是调用方的少数路径：front 分钟缺行、`participation_rate` 缺量。默认书是跳过该票。计划第 40 行「缺行 fail-closed 语义不变（该到的票没有 bar 仍按现行规则报缺）」若被实现成 loader 里 raise，今天能跑完的缺 bar 票会变成中止，净值对账直接不可比。

第 41 行把 hint 漏并的兜底写成「验收用 S3 逐字节对账」。第 54–57 行又要求每一刀都对账。两句冲突。按松的那句，S2 可以在错误集合上先合进去。

持仓是扫描的结果，不能在扫描前并入 hint。扫描前能算的超集是：`union(pool_days) ∪ extra_load_codes_for_strategy(strategy) ∪ 调用方显式预载`。分数宇宙进不进分钟，要单独裁：日线门槛、MA 闸用的是日线；分钟主循环切的是池内代码和持仓。这个裁没做之前，S2 没有可写的集合公式。

### F5 阻断 — 硬验收绑错刀；S3 的帧契约会改书

验收表把「冷窗墙钟 ≤5min」放在 S1。证据表的 1153.7s 是整段 `t_minute_s`，标注「扫湖建缓存」，没有拆读湖、写单体 zstd、再读回。S1 不减少票数。这段时间如果主要是逐票读 `data.parquet`，分片写盘削不动它，5 分钟会失败。如果主要是单体压缩写入，分片可能够。计划没有这条拆分，S1.1 的失败条件里也没有。

还有一个未写的读放大：每个月 shard 若各自再扫一遍同一份 `data.parquet`，约 10 个月的窗口把冷读乘以月数。一趟扫描写出该票全部月份，才和「冷窗变快」同向。计划两头都没指定。

「暖读 ≤15s」的对照是表上的「热（partial）40.5s」。现码 `partial` 不是纯命中：身份命中后仍把缺的代码扫湖，再 `read_minute_cache(path, None)` 把**整个**单体读回来重写（`:728-738`）。40.5s 里夹着湖和全量重写。S3 的 Arrow 直读削的是解码，削不到这段湖时间。note §5 的原句是：Arrow 列直取只削当时那次 14.9s 解码的一部分；parquet 仍是跨进程真源；同进程第二次走 `bar_store`；不要 mmap；两刀不要混。计划把 S3 对上 40.5s，又把 note 的「两刀」说成 S1/S2/S3。测量对象换了。

S3 列清单是 `open/high/low/close/hm`，跳过 `to_pandas()`。现网书帧还有 `low` 已经在清单里，但还有 `ymd` 和 `DatetimeIndex`（ns、无时区）。`build_day_spans` 没有 `ymd` 就返回空（`bar_store.py:76-86`）。`_frame_from_cache_group` 把 `time` 收成 `DatetimeIndex.as_unit("ns")`，`hm` 收成 int64（`ashare_bars.py:619-628`）。湖侧价格是 float64（`:417`）。只交 numpy 五列，`load_minute_ohlc` 的返回形状就变了，和计划第 32 行「引擎零改动、契约只有返回形状」冲突。note 允许的是跳过 `to_pandas` 的解码成本，不是改掉书帧。

S3 仍应单独 PR、不做 mmap。这点和 note §5 一致。不一致的是列契约和它声称要削的那 40.5s。

### F6 高 — 回滚开关没有缺省；状态枚举覆盖会拆掉 G2 可观测性

计划第 52 行把 `OSKH_MINUTE_CACHE_SHARD=0` 写成回滚。未设置、空串、`false`/`off`/`no` 时的行为没有写。现网同类开关 `OSKH_BAR_MEM` 把 `0/false/off/no` 都当成关，缺省是开（`bar_store.py:20-22`）。照抄缺省「开」等于分片路径一合并就替换全部分钟书的缓存。缺省未裁之前，实现 PR 没有安全的落地姿态。

计划第 69 行把 `profile_sim.json` 的 `cache` 改成 `miss/shard-miss/shard-partial/hit`。现网值是 `mem` / `hit` / `partial` / `miss` / `miss:identity` / `rebuild` / `off` / `off:volume_required`（`:692-752`）。G2 把前六个里的文件态写成合同，并要求 volume/amount 保持 `off:volume_required`。`mem` 是进程内命中，计划的新枚举里没有它。覆盖同一个字段后，回滚路径和分片路径的日志无法跟今天的探针比，`tests/test_minute_cache_identity.py` 的字符串断言会整组失效。分片计数应是附加字段；`=0` 时原枚举冻结。

### F7 高 — 并行「天然安全」只覆盖 #476 的 tmp 文件名

#476（`47735bba`）的事实与现码一致：tmp 是 `{path.name}.{pid}.{uuid8}.tmp`，json sidecar 同一模式，`replace` 之后最后一次原子替换获胜（`ashare_bars.py:556-613`）。分片沿用这个名字，可以避开 Windows 上两个进程 unlink 同一个 `.parquet.tmp`（WinError 32）。这句话可以保留。

下面几件计划写成了「分片天然并行安全」，现码并不提供：

- 同一目标路径、两边内容不同：最后一次 `replace` 获胜，文件名不变，后来的读者不会因为 stamp 再 miss。典型窗口是两边 `stat` 到同一个 mtime/size，读到的字节却不同（跑的过程中湖在动）。G2 的前提是运行期间源冻结。计划把这个前提丢了。
- 批分片若允许「只写入本进程要的代码、文件名却用整批哈希」，后写的进程会把先写进程的代码从批文件里拿掉。现网单体 partial 已经是这个丢失更新：B 读到旧文件、写回时覆盖 A 刚并入的代码。各进程内存里的 `got` 仍是自己的，所以单次净值通常还在；缓存会抖动，下一轮再扫湖。分片把丢失范围从「整窗文件」缩小到「同一 shard」。前提是读者继续做 `missing = want - present`，并且 writer 要么写完该身份下的全部代码，要么失败时不 `replace`。计划没写这条。
- `writer.close()` 之后、`replace` 之前若异常，`finally` 不再删 tmp（`:586-596` 把 `writer` 置空）。票×月之后，崩溃残留的 tmp 按 shard 个数涨。计划只写了手动清老窗，没写 tmp 的清理规则（不能删仍在写的 pid）。
- 老 stamp 的 shard 文件不会被新文件名替换掉，会永久留下。票 × 月 × 每次源文件 stamp 变更是一组新文件。没有保留代数、没有「与当前 stamp 不一致即可删」的判定，磁盘没有上界。这和 F1 叠在一起：若整文件 stamp 每日都变，历史月的旧文件每天留一套。

S1.1 用 100 票量打开开销，决定单票还是约 500 票一批。批的成员规则没写。按「本次请求的顺序切 500」会让同一票在不同运行落入不同批，批哈希永远 miss。需要稳定的分桶键（例如代码排序后的固定区间），并且批哈希覆盖批内全部成员的 stamp，而不是本次 hint 的子集。

### F8 中 — partial 重写路径必须在分片开关打开时停用

`:728-738` 在身份命中且有缺码时，把单体文件全部读回、合并、整文件重写。分片之后若把这段包一层继续调用 `write_minute_cache`，会把已命中的 shard 再打成一个单体，两个布局叠写。`OSKH_MINUTE_CACHE_SHARD=0` 必须原样留下这段，包括「认证失败禁止合并未请求代码」。开关打开时，缺的是 shard，只写缺的 shard，不读回其他票。

volume / amount 在函数入口就返回，不建身份（`:692-697`）。`use_cache=False`、`qlib_1min`、front、v7 不走这条共享缓存。这些旁路要列为分片 PR 的不变量。`version11` 和 `--tail-window-buy` 走 `include_volume` / `include_amount`，不在计划点名的两支验收配方里。

## Blockers（若 REQUEST_CHANGES）

下面六条不补进计划，就不能对人裁「可以开实现 PR」：

1. **F1** 票的失效单位必须写成和增量目标一致的规则。整文件 mtime/size 做不到「只建新月」。要么 stamp 绑定该月字节（或该月分区文件），旧月仅在自己的 stamp 变化时重建；要么承认追加一日会重建该票全部月份，并改掉 S1 验收第 ③ 条。禁止第三种：为了验收通过把旧月 stamp 冻住。
2. **F2** 写明裁剪谓词、月份不重叠、`mem_key` 含请求窗、spans 指纹对着裁剪后的帧。覆盖的月份是 `load_minute_ohlc` 的参数窗（含 `warmup_start` / `minute_load_start`），不是 CLI `--start/--end` 的字面值。
3. **F3** G2 字段的去留要逐项裁：`identity_version`、缓存 `schema` 哈希、`dividend_type`、`resolver_identity`、显式 `source_snapshot` token、`st_mtime_ns`。搬仓 miss 只有在根 token 还在时才成立。旧单体路径不迁移、不自动复用。front / volume / amount 继续绕过。
4. **F4** 删掉或改写 `codes_hint`。扫描前的分钟集合公式、日线和分钟是否拆开、`version6_53` 停车码、分数宇宙是否进入分钟，都要有一句人裁。loader 对缺 bar 保持省略，不新加 raise。对账放在 S2 自己的 PR，不推到 S3。
5. **F5** 冷窗 ≤5min 只许绑在「读湖时间已经被探针拆开、并且票数或扫描次数真的下降」的那一刀上。S1.1 增加失败条件：一趟扫描对每月一趟扫描的倍数；月末 +1 日与跨月 +1 日各自改写的 shard 数。S3 的返回帧保持 DatetimeIndex(ns) + `ymd` + float64 OHLC + int64 `hm`，并写明它削的是命中后的解码而不是 partial 里的湖时间。
6. **F6** `OSKH_MINUTE_CACHE_SHARD` 的缺省、空串和非法值。建议缺省 `0`，DoD 绿了再单独 PR 把缺省改成开。`=0` 时 `cache` 字符串与现码逐值相同；分片计数走附加字段。

F7、F8 写进同一份切点即可，它们跟着 F1 和回滚开关走，不单独立项也能挡实现。

## Nits（非阻塞）

1. 「全湖单文件」容易读成「湖上每一票都进了缓存」。现文件是该身份下请求代码的并集；全湖的是一层目录浅快照。建议改这六个字，避免 S2 再去减一批并不存在的扫描。
2. 日线「同构、二期」没有指针。日线身份在 `csv_daily_loader.py`，有自己的浅快照和 #476 tmp。二期未开之前，分钟 PR 不要改日线写入。
3. S1.1「小文件打开主导就改批」没有数。至少要有打开耗时 / 单票扫湖耗时的倍数，以及外推到 5575 票时的 fd 数量。否则探针报告无法裁。
4. 计划第 65 行把 note §5 的「两刀不混」说成 S1/S2/S3。note 的两刀是已经落地的模拟侧 `searchsorted`，和装载侧 Arrow 解码。S1.2 又引入一个日期 `searchsorted`。三处不是同一把刀，计划里应分开命名，避免实现者以为裁剪已经在模拟器里做过。
5. `load_session_bars` 对湖源写死 `use_cache=False`（`ashare_bars.py:296-300`）。分片上线后这条仍绕过缓存。不是错，但性能目标不要写成「所有分钟入口」。
6. 缓存命中后的 `print` / `profile` 若把 shard 路径每票打一行，5575 行日志会淹没「建了多少增量」的证据。验收第 ③ 条要的是计数，不是路径倾倒。

## 对码取证（kin）

| 计划断言 | 现码 | 判定 |
|---|---|---|
| 身份 = `{start, end, schema, 全湖浅快照哈希}` | `minute_cache_identity` `:496-498`：另有 `identity_version`、`dividend_type`、`resolver_identity`；schema 是缓存 schema 的哈希；快照是根 + 一层子目录的 `[name, mode, size, mtime_ns]` | GAP |
| 换窗口即新身份、整文件重建 | 路径含 start/end 和整份身份的 12 位摘要 `:501-509`。同票跨窗不能复用 | PASS |
| 湖每日增量必动浅快照，昨天的缓存今天全废 | 仅当 `dividend_type=none` 的**目录项**元数据变化。G2 写明原地改 `data.parquet` 可能不动父目录。rename 写入通常会动目录 mtime | GAP |
| 冷路径逐票扫湖，约 5500 票进一个大文件 | `load_minute_from_lake` 只扫 `want` `:446-453`。单体文件是该身份上积累的请求并集。partial 会整文件读回重写 `:728-738` | GAP（「全湖」过宽；重写行为属实） |
| 暖路径 40.5s 是热读 | 表自己标了 partial。partial = 缺码扫湖 + 整文件重写，不是 `hit`/`mem` | GAP |
| shard 沿用 #476 per-pid tmp，最后一次 replace 获胜 | `write_minute_cache` `:556-613`：`{name}.{pid}.{uuid8}.tmp`，json 同模式，`Path.replace` | PASS（仅限 tmp 名） |
| 分片后并行天然安全 | 同一路径内容不同仍是 last-wins；批子集写会丢代码；tmp 在 close 之后失败会残留；旧 stamp 文件不删除 | GAP |
| 月对齐后，追加一天只建新月 | 书帧源是一票一个 `data.parquet` `:377`。整文件 stamp 变化使该票所有月 shard 同时 miss | GAP |
| 月内差异用 `searchsorted` 裁，书不变 | loader 没有这步裁剪。现成闭区间是 `utc_ms_range` `:25-31`。`mem_get` 不二次裁窗。spans 用整帧 iloc | GAP |
| 读侧拼回现行 `bars` dict，引擎零改动 | 契约还包括 `day_spans`、`mem_key`、`ymd`、DatetimeIndex。`simulate` 用 `_slice_day` `:1191` | GAP |
| `codes_hint` 在扫描前传池 ∪ 已持，漏并靠 S3 对账 | 调用方已传 `all_codes = pool ∪ scores ∪ extra_load` `:2476-2480`。`version6_53` 含停车码。扫描前无持仓。第 41 行与第 54 行对账时机冲突 | GAP |
| 缺 bar 仍按现行 fail-closed 报缺 | loader 省略缺码 `:739`。raise 只在 front / participation 等调用方 | GAP |
| S3：`read_table.to_numpy()`，只要 OHLC+`hm`，削 40.5s 的一部分 | 现读是 `read_row_group` + `to_pandas()` `:631-662`。帧含 `ymd` 与 ns 索引 `:619-628`。note §5 的 14.9s 不是这 40.5s。mmap 不做：与 note 一致 | GAP（列与测量）；PASS（不 mmap、单独 PR） |
| 不做跨进程常驻，parquet 仍是真源 | `bar_store` 模块 docstring：文件缓存是跨进程真源，内存只跳过第二次解码 | PASS |
| `cache` 改为 `miss/shard-miss/shard-partial/hit` | 现值含 `mem/hit/partial/miss/miss:identity/rebuild/off/off:volume_required` `:692-752` | GAP |
| 回滚 `OSKH_MINUTE_CACHE_SHARD=0` | 仓库里还没有这个变量。缺省未定义 | GAP |
| 逐字节验收：`version6_53` 与 `topk_dropout` 的 `daily_equity.csv` 和 `trades.csv` | 这两支都走 `load_minute_bars` `:2569`。v6.53 另有停车码。topk 另有分数宇宙。volume/front 不走缓存 | PASS（配方存在）；GAP（覆盖面，见 Hard DoD） |
| 两刀不混，对齐 note §5 | note §5 禁止把模拟刀和 Arrow 解码混在同一次改动。S1/S2 是另一组刀 | GAP（引用对象）；PASS（S3 单独 PR、不做 mmap） |

## 切点缺口（Human 裁前建议补的 P* / 默认 / 回滚语义）

计划没有 #478 那种「未裁 / 已裁」的 P 卡。S1.2、stamp、hint、状态枚举读起来像已经选定。建议在正文里改成下面八张未裁卡，裁完再允许对应的实现 PR。未裁的卡不准编码。

| 卡 | 要裁的内容 | 建议默认（仍要人写「批准」） |
|---|---|---|
| P1 失效单位 | 整文件 stamp，或该月字节/分区 stamp。写明「冻住旧月」不在选项里。`st_mtime_ns` 还是秒级 mtime。同一秒修数算不算 miss | 该月字节身份 + `st_mtime_ns`。做不到月级字节身份之前，不承诺「+1 天只建新月」 |
| P2 读契约 | 裁剪谓词、月分区不重叠、一趟扫描写多月还是每月一趟、`mem_key` extra、spans 只描述返回帧、旧单体路径不读 | 采用 F2 的 `ymd` 闭区间。`mem_key` 含请求 start/end。spans 对裁剪帧重建 |
| P3 G2 字段 | 七个认证字段哪些留在 shard sidecar 且参与文件名。显式 `source_snapshot` 是否保留。认证失败是否仍禁止合并其他代码 | 七字段都留。短文件名摘要仍不是认证，sidecar 全字段相等才命中 |
| P4 分钟代码集 | 扫描前公式；日线是否仍用宽集合；分数宇宙进不进分钟；停车码谁负责。不新增一个调用方不传的 `codes_hint` | 分钟 = `union(pool_days) ∪ extra_load_codes_for_strategy`。分数宇宙留在日线，除非点名某条分钟读分数码的路径。缺 bar 不在 loader raise |
| P5 开关 | 未设置 / 空串 / `0` / `false` / `off` / `no` / 其他。其他值是 fail-closed 退出还是当成关 | 缺省关。只有 `1` 打开。其他值退出。`0` 走今天的单体函数，含 partial 整文件重写 |
| P6 预算归属 | ≤5min 属于哪一刀。暖读的定义（第二次、`hit` 或 `mem`、零湖读）。+1 日指标：当月内一日、跨月一日，各打印 rebuilt shard 数 | 5min 不挂在单独的 S1 上。暖读按零湖读定义。S1 的冷预算是「不慢于单体冷路径」直到 P4 合入 |
| P7 残留文件 | 旧 stamp shard 的保留代数；tmp 清理；批成员的稳定分桶；writer 必须写完整个 shard 身份才能 replace | 引擎不自动扫盘删除。脚本只删「stamp 与当前源不一致」且 mtime 老于 N 日的 shard。不删 `*.tmp` 除非 pid 不存在 |
| P8 S3 与状态字 | 返回帧列与 dtype。`cache` 是替换还是附加。S3 是否允许改 `mem` 里的对象类型 | 书帧形状不变。`cache` 枚举冻结。附加 `shard_hit` / `shard_miss` / `shard_rebuild` 计数。S3 单独 GO |

回滚语义建议写成三句，避免实现者各写各的：

- `OSKH_MINUTE_CACHE_SHARD` 未设置或 `0`：字节级走今天的 `minute_cache_identity` / 单体路径 / 今天的 `status["cache"]` 字符串。
- `=1`：只写 `bar_cache/shards/`，不读不写单体 `minute_none_*.parquet`，不把单体内容迁移进 shard。
- 从 `1` 回到 `0`：shard 文件留在磁盘，单体路径按自己的身份重新 miss/hit。不存在「半片 shard、半片单体」拼出来的第三次布局。

## Hard DoD sufficiency

`daily_equity.csv` 与 `trades.csv` 逐字节相同，是必要门，不够单独放行。

它能抓住的：价格变了、结束日被裁掉、停车码没装上、topk 真用到的分钟代码被 hint 丢掉、行序变了且这两份 CSV 的行序跟着变。主循环的成交顺序来自池和持仓，不来自缓存字典序，所以「shard 插入序」本身不太会改 CSV；裁错日和漏码会改。

它抓不住的：

- 窗的起止正好是自然月边界时，裁剪是空操作。计划只写「各一窗」，没有钉死不齐月的日期。证据里的 topk 窗 `20260106–20260914`（身份窗从 `20251227` 起）和 note §6 的 `version6_53` 窗 `20251023–20260909` 都落在月中，应该写死为配方，并各加一轮「结束日 +1 且仍在当月」和「结束日 +1 且跨月」。
- partial / 纯 `hit` / 同进程第二次 `mem` 三种状态。CSV 相同也可以是「每次都重新扫湖」。暖读预算要同时要求零湖读和 `cache` 状态。
- float 路径。S3 若把 float64 收成 float32，CSV 格式化有时仍能撞上同一串。合成测试要比帧：索引单位 ns、无时区、`open/high/low/close` float64、`hm` int64、`ymd` 与现网同值。DoD 两支配方是在这组单测绿了之后的集成门。
- `include_volume`、`include_amount`、`dividend_type=front`、`use_cache=False`、`qlib_1min`。这五条必须仍是今天的 `off:volume_required` / `front_uncached` / `off` / `qlib_1min`，并且不产生 shard。`version6_53` 与默认 `topk_dropout` 不走这些旁路。
- `profile_sim.json`、日志、`codes_missing`。不要放进逐字节门。分片计数一变，profile 必然不同。把 profile 放进同一条 `cmp` 会迫使实现者伪造旧计时字段。
- 其他仍调用 `load_minute_bars` 的入口（`fullstrat_research_runners.py`、Mode B `load_monitor_bars`）。两支配方绿了，不代表这些入口的代码集被 P4 覆盖。

比较基准必须是**同一提交**上 `OSKH_MINUTE_CACHE_SHARD=0` 的输出。用昨天留下的单体缓存当「旧结果」，会把身份漂移和本次改动混在一起。

验收命令要写明：`PYTHONHASHSEED=0`、策略、起止（CLI 窗和由此展开的装载窗）、资金与 `--rule-profile`、topk 的 pred id。note §6 的 v6.53 命令可以当 v6.53 那一臂的起点；topk 一臂要把 pred `8a061ea4` 和窗 `20260106–20260914` 写进计划。不等则该刀回滚，这句可以保留。

## Human 下一步

1. 不要按当前正文开 `ashare_bars.py` 的实现 PR，也不要授权 Codex 把 S1/S2/S3 一起做。
2. 先改计划（仍是 docs-only）：把 F1–F6 收成上面的 P1–P8，每张卡保持未裁，直到有书面选择。性能数字从「S1 必达 5 分钟」改成 P6 的归属。
3. 人裁顺序建议：P5 缺省关 → P3 认证字段 → P1 失效单位 → P2 读契约 → P7 残留 → P4 代码集 → P6 预算 → P8 留给 S3。P1 与 P2 没裁之前，S1.1 探针的通过条件写不出来。
4. P1–P7 有书面答案之后，实现顺序仍是探针 → 分片（默认关）→ 代码集 → Arrow。每一刀自己对账，Arrow 不和分片同 PR。这点和计划第 3 节的顺序一致，可以保留。
5. 本评审不要求把 #479 拆开或撤回。它已经合并，状态仍是待裁。下一份需要评审的是补了 P 卡的计划 diff，不是这份 69 行的复读。

VERDICT=REQUEST_CHANGES
