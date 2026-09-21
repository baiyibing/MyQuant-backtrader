<!-- agent=codex cmd-prefix=C:\nvm4w\nodejs\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】E:/PycharmProjects/MyQuant-backtrader/docs/backtest/plan-version11-machip-csv-2026-09-21.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-21\plan-version11-machip-csv/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本地 redis/数据库已就绪、国金 miniqmt 已登录；把握不准可读代码或做实验，以事实为准。

【裁决原则（重要）】
- 视自己与其他评审者为同行专家，**参考学习、互相验证、取长补短**：结论交叉核对、补彼此盲区，而非单纯挑错。
- **事实类断言**（函数位置 / SQL / 行为 / 数值等可验证项）→ **以代码与实验为准**：读代码取证，把握不准时跑最小实验，不靠票数下结论。
- **经验/取舍类断言**（该不该这样做、风险量级、更稳的写法）→ **以业内 A 股量化惯例与成熟开源实践为准**。
- **SSOT 一致性检查**：若方案涉及数据格式/符号规范/配置键/API 契约等，**必须对照仓库 SSOT 文档**（`docs/backtest/data/symbol-format-ssot.md`、`docs/SSOT.md`、`docs/operations/disclosure-data-source-ssot.md` 等）检查是否冲突。若方案与 SSOT 不一致，标记为 🔴 并指出具体 SSOT 文件及条目。
- **★ 安全阀/超时/并发类设计，必须跑最小实验验证行为**（不只读代码！）：timeout / budget / safety-valve / circuit-breaker / 并发锁 / 异步 / fallback / 重试——这些 bug 藏在 stdlib/框架行为里（如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效），**读代码看不出来**。实验格式：构造 slow fn + tight budget → 测调用方**何时返回**（`time.monotonic` 对比 budget_s vs 实际）。2026-07-04 实测：option-X budget docstring 宣称 "releases caller" 但实际 8s 才返（非 1s budget）——**docstring 不可信，实验为准**。**实验结论须附可复现脚本 + 完整原始输出**（含进程 pid/存活检查等），与官方文档/CPython 源码矛盾的结论标注「建议主持裁/下游复核」。2026-07-16 教训：r3 kimi 实验「subprocess.run(timeout) 不杀子进程」结论错，r4 qoder 引源码 + 主持裁亲自实验（child TERMINATED）才纠正——下游 incorporate 实验断言须亲自复现。

【输出格式】
按严重度分级，每条尽量带 file:line 证据：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险）
- 🟢 可选（nice-to-have）
- ✅ 做对的地方（保留）
末尾给一句总评 + 是否可进实现。

【你的评审侧重】优先审**实现可操作性**：函数名/文件位置/调用链/API 契约——程序员能否照此编码？哪里会卡住？哪些 import 是私有的需 wrapper？ <prompt> -->
评审意见（`plan-version11-machip-csv-2026-09-21.md`，侧重重：实现可操作性）

> 说明：本轮并行目录 `_parallel/{kimi,codex,claude,cursor-auto}/*.md` 我已读过——4 份都只有 `<!-- agent=... -->` 提示词头，**没有任何已完成的评审正文**，故本轮为独立评审、无交叉核对对象。另外该目录在我的可写根之外（沙箱只允许写 `E:\PycharmProjects\OSkhQuant1.3`），故按硬约束只输出意见、不落文件。

---

## 🔴 必须修

**R1. `compute_cyqk_series` 没有网格上限，而 canonical 路径有 250k 硬闸——「全市场一跑」可能 OOM（切片 B/D 的成败关键）**

`turnover-resist/src/lib.rs:97-115` 暴露的 `compute_cyqk_series(close,high,low,volume,shares,window,start_i,step)` **没有 `max_grid_points` 参数**；同一模块的 `compute_turnover_resist` 有（`lib.rs:18-27`），且受闸路径会报错而非静默：

```
algorithm.rs:301  let n_prices_raw = ((max_p - min_p) / step).ceil() as usize + 1;
algorithm.rs:302  let n_prices = n_prices_raw; // 不截断，接受极端高价股的大网格
algorithm.rs:560  if n_prices > max_grid_points { return Err(ComputeCurpdfError::GridTooLarge{..}) }
```

单窗内存 ≈ `window × n_prices × 8B`（`curpdfs`），且按日 rayon 并行 → 峰值 × 核数。实测（脚本见文末 Exp2）：窗口内价格跨度 600 元、`step=0.01`（网格 ~60.5k）时单票 250 根 **1.19s**，窄幅对照 0.22s（Exp1）；跨度 2000 元的妖股/次新量级即 ~200k 网格 → 单窗 ~320MB × 8 线程。plan 未点名该参数、也未给预算 → 实现者极可能直接调 series 并被单票拖死。**修法**：导出器侧自加 `window 内 (max(high)-min(low))/step` 预检 + 上限（复用 250k 量级）→ 超限该票该窗 skip 并记 manifest 计数；并把「全市场 ~5000 票 × 0.2–0.4s ≈ 20–35 min」写进 plan 作性能基线。

**R2. 200 日窗的「每日 asof 股本」取值源未 pin，且唯一 asof 访问器是私有 `_get_float_shares`**

```
oskh_factors/chip/shares.py:60   def _get_float_shares(stock_code: Optional[str] = None, date=None) -> float:
shares.py:64   """ 1. date is not None → free_float_shares.parquet → circulating_capital
shares.py:26   def _load_float_shares_map(...)  """加载流通股本 Parquet（当前快照）..."""
```

该函数是 `_` 私有件（`chip/core.py:21` 也是私有 import），语义：`date≠None` → `free_float_shares.parquet.circulating_capital`（Capital 表 backward merge_asof）；`date=None` → `float_shares.parquet.FloatVolume`（**当前快照，无时间维**）。而 Rust CLI/store 路径自身读的是 `FloatVolume` 快照（`turnover-resist/src/data.rs:66-73`）。后果有二：① 若实现者图省事用 `date=None` 版本喂 200 天窗 → **用今天的股本算两年前的换手，严重前视**（归档 §2 line 35 明确禁止「用 D 日一条股本铺整窗」）；② 该 asof 序列与 TR store 里已有的 `cyqk_t` **不同源不可比**（`oskh_data/turnover_resistance_store.py:26-33` 有 `cyqk_t/cyqk_t_1/profit_chip_diff` 列，PR #147/#148 刷新链已落地，见 `git log` `2336132/dc48500`）。plan 必须点名：源文件+列名+是否新增 public wrapper（建议在 `oskh_factors.bridge.turnover_resist` 加一个 `compute_cyqk_series_ffi`/`asof_shares_series` 薄壳，而不是让 `scripts/data/` 直接 import 私有件与裸 PyO3 扩展），并声明与 store `cyqk_t` 的差异原因（window=200 vs 1000、股本口径）。

**R3. 转录丢了归档 §2 的「价格/复权」行 → 信号口径无宿主，卖出比较在除权日会产生假信号**

归档锁定表原文：`价格 | 日线 period=1d adjust_type=front。禁止 load_single_stock_data`（`_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md:31`），新 plan §1 表（买入/成交/卖出/skip/仓位/费用）**无对应行**。而 CSV 引擎日线是 none：`ashare_bars.py:128 """Session 昨收 map. Lake none is the official-limit default."""`（`load_daily_ohlc(..., dividend_type="none")`）。两条具体后果：

- cyqk/MA20/60/布林若喂 none 价，除权缺口会在筹码分布上造出假筹码簇（front 是 QMT ground truth，见 `docs/backtest/data/daily-adjusted-update-ssot.md:16-23`）；
- 卖出规则「T 收盘 ≤ T-1 收盘」在引擎里拿到的是**未映射昨收**：`csv_daily_backtest.py:326` 的 `mapped_prev_close(...)` 只喂给涨跌停，卖点却是 `csv_daily_backtest.py:393 sell_gate(code, close, day, closes)`（`closes` 为原始 none 序列）→ **除权日必假「收阴」→ 次日开盘误卖**。切片 A/C 必须 pin：信号侧 front；卖侧比较用 `mapped_prev_close`/`k_for` 等价前复权（或明确接受 none+映射），并加「除权日不得产生卖出信号」pin 测试。

**R4. R10 的论据引错函数（结论可留，证据须换），且该条是**对归档口径的显式改口径**未登记**

plan §2 表与 R10 用 `oskh_factors/chip/core.py:580 compute_equal_weight_cyqk`（“等权法/无衰减”的**对比实现**）证明「Python 非等价回退」。但归档 §2:35 的回退指 canonical `oskh_factors.chip`（`core.py:70 daily_chip_distribution` + `core.py:513 compute_crossday_turnover_resistance`），其原语（`calc_single_day_curpdf_into` + `calc_cumpdf_decay`）与 Rust `compute_cyqk_ohlcv_window`（`algorithm.rs:352-430`）同族。照现写法，下游会误得「Python 全无等价实现」——这是错误事实。建议：R10 改述为「单一算法来源=可复现 + 避免两套数值并存」，并在页眉对抗回填区登记「本条是对归档 §2『失败回退 Python』的**显式改口径**」。

**R5. 前置 `ma_infra` 是未人裁草稿，切片 A/B 照 plan 无法开工（可操作性硬阻塞）**

`docs/backtest/plan-ma-infra-shared-2026-09-21.md:3`：**`v0.1 · draft（未评审、未人裁，GO 前禁编码）`**；version11 R8 与切片 A 却要求直接消费其 `sma_asof/sma_series/bb_asof/weekly_sma_asof`。目前这些符号在仓内**不存在**（`strategy4_rules.py:23-27` 才有 `sma_asof` 种子，布林「无存活实现」见 ma_infra §1）。修法：在 §7 切片 A 前加一行硬前置「ma_infra GO+合并后本 plan 切片 A 才可开工，PR 引用其 commit」；并补一句性能 pin：**每 symbol 调一次** `daily_to_weekly`+`weekly_sma_asof`（ma_infra 只给标量件），禁 `days × symbols` 次逐日 asof 调用（全市场 ~3M 次 resample 级开销）。

**R6. P1「09:30 新买钟」未落到函数级，且 volume=0/一字板在两个引擎的可达性未 pin**

现状（可复制的落点）：分钟买钟=`csv_minute_backtest.py:487-494 _buy_px`（`BUY_HM=14*60+55`，:120），volume 桶=`csv_minute_backtest.py:715 _volume_bucket_for(code, BUY_HM, 14*60+30)`，且**只在 `st.volume_cap is not None` 时才传**（:780）；拦截只有涨停价（`csv_simulate_loop.py:280-288 skip_buy_at_limit`）。同时分钟 loader 把 **volume=0 的整日删掉**：

```
ashare_bars.py:369  if has_volume:
ashare_bars.py:370      day_volume = out.groupby("ymd")["_volume"].transform("sum")
ashare_bars.py:371      out = out.loc[day_volume != 0].drop(columns="_volume")
```

→ 归档 FSM 的「volume=0 不成交、写 events」在分钟引擎**不可达**（只会表现为 `skip_no_bar`，且 `csv_simulate_loop.py:262` 当日即消耗）。plan 只写了「须带 volume=0 拦截测试」，没写期望行为与计数器。修法：切片 C 明确三件——(a) 新 `_open_quote_for`（首根 `open`）+ 配对 `open_volume` 桶（用 `_volume_bucket_for(code, AM_OPEN, AM_OPEN)`）替换 `pool_volume`；(b) 一字板=`open` 触涨停（`skip_buy_at_limit` 已覆盖）与 volume=0 在两引擎各自的判定点/计数器名；(c) 日线引擎里 volume=0 是否仍存在 bar 的 pin。

---

## 🟡 应修

**Y1. stale「>4 自然日」在导出器层没有产物定义。** plan 把该 FSM 放导出器（§3.3/R10/切片 B），但没说「命中后是 omit 该票还是照写让引擎 `skip_no_bar` 消耗」，也没给 manifest 计数/时间戳字段 → 切片 D 的「skip 语义差异清单」将无法与归档 `events.csv` 的 `skip_buy(stale)` 对读。建议：导出器写 `<out>/rejected.csv`（date,symbol,reason）+ manifest 汇总计数，并在 §2 表补一行「stale 判定=信号日 D 之后该票首个 bar 的 `date - D > 4 自然日`」。

**Y2. 池 CSV 契约与 R5 同批未 pin。** 引擎按 `YYYYMMDD.csv` + 无表头六位裸码 + `validate_pool_dir` 强校验读取（`csv_pool.py:48-53`、`csv_pool.py:88-96`），export9 先例也如此（`export_strategy9_pool.py:54-60`、`:62-63` 拒 `stock_pool/`）。切片 B 的 DoD 只写「拒绝 stock_pool/」，建议补「文件名=买日 T、无表头、裸六位码、LF、UTF-8、NUL=0」与 `validate_pool_dir` 冒烟。

**Y3. 数据源 resolver / 复权参数未点名。** R5 只说「走 resolvers」。可复制的既有件：`export_strategy9_pool.py:39 from common.infra.data_root import resolve_period_root`、`:41 from oskh_data.symbol_format import to_canonical_symbol, to_partition_key`（本仓**没有** `docs/backtest/data/symbol-format-ssot.md`，符号 SSOT 实为 `oskh_data/symbol_format.py`；建议 plan 引用它，避免下游按提示词文件名找不到）。另需 pin 信号侧 `dividend_type="front"`（见 R3）。

**Y4. version11 book 的注册面细节缺两键 + 会踩现成 RuntimeError。** `apply_csv_strategy` 强制要求 `take_profit`/`record_params`（`csv_strategy_books.py:137-140`），`limit_up_chase` 走 `setdefault`（`:134`）→ R9 的 False 必须由 `book.apply()` 返回值承载（不是文档约定）；`FORBIDDEN_DEFAULT_STOCK_POOL`（`:47`）与 `resolve_research_pool_dir`（`:371`）是 R5 的执行点；book 名单在测试里是**精确元组**（`tests/test_csv_strategy_books.py` `test_registered_books_are_explicit`），加 version11 会红，plan 已列该测试 ✅，但请补「apply 必返 take_profit/record_params/limit_up_chase=False」与 `engine_book` tag（如 `v11`）。

**Y5. P2「分钟侧 09:30 首根评 pending 卖」与现有卖侧次序未对齐。** 分钟卖侧是逐分钟 `scan_held_day` + `can_sell=t1_sellable(...)`（`csv_minute_backtest.py:649-678`），开盘价成交另有跌停 defer 与 `reason` 映射（:682-701）。新增「09:30 首根评 pending 卖」需 pin：是否绕过 stop/trail 次序、以 `open` 成交、与日线 `pending_exit`（`csv_daily_backtest.py:344-350`，`price_rule="daily_pending_next_open"`）同因同价，避免两引擎在 D+1 开盘的成交价/原因不一致。

**Y6. 卖出侧 SMA5 是否含当日收盘未 pin。** 归档 §2:38 只写「同日也评 SMA5」，未定义 SMA5 是否含 T 当日收盘；而引擎既有惯例是「**按截至昨日**的 SMA5 比今日价」（`strategy4_rules.py:36-41`，`sell_gate(code, px, day, daily_closes_ending_yesterday)`，`csv_minute_backtest.py:669-671` 传入 `prev_rows`）。切片 A 的 `exit_signal(t_close, prev_close, sma5)` 两种解释都能自洽 → 必须二选一并写进 pin 测试，否则与静态档案对照时会被当成引擎 bug。

---

## 🟢 可选

- 导出器 manifest 记录可复现参数：`cyqk(window=200, start_i, step)`、`bridge_mode()`/`is_ffi_available()`（`oskh_factors/bridge/turnover_resist.py:40-63` 已有探针）、网格上限值与 skip 计数。
- `--help` 带上 P0 结论（「cyqk>0.70 在仓内文档为抛压区，本版定位=框架验证」），避免半年后误读为已验证策略（归档 §3.3 同源措辞）。
- 切片 A 的 record/HELP_LOCK 里登记「D-1 为 NaN ≠ 边缘」「等号 fail-closed」「买入日禁卖」三条原文，便于 `--help` 自证。

---

## ✅ 做对的地方（保留）

- **§2 as-built 锚点逐条对得上代码**：`csv_ledger.py:79 pending_exit`；日线消费 `csv_daily_backtest.py:344-350`；分钟侧 `pending_exit` **零出现**（`scan_held_day` 为另一套，:338 起）；`csv_simulate_loop.py:262 skip_no_bar 当日消耗`、`:145-147 chase pending 保留到下一有 bar 日`；`ashare_session.py:39-41 t1_sellable`；日线买价=收盘（`csv_daily_backtest.py:451-458`）。这四类「无既有落点」的判定是**真缺口**，不是臆断。
- **R9 可实现**：`hooks.setdefault("limit_up_chase", True)`（`csv_strategy_books.py:134`）+ 两引擎 `hooks.get(...)`（`csv_daily_backtest.py:295`、`csv_minute_backtest.py:590`）。
- **R1/R2 与上游 `AGENTS.md:22` 原文一致**（「chip / ma_chip 对照产物为静态档案…version11 CSV 移植须另开计划并重裁成交时点语义」）；7 份静态档案在 `backtest_output/ma_chip_edge_*`（含 `_cyqk80/_cyqk90_nobb/_nocyqk/_noidx` 变体）→ P4/P6 的 seed-30 parity 有可比物。
- **R10「Rust 失败即 skip」在实现上站得住**：`compute_cyqk_series` 对任一日 `shares<=0/non-finite` 或 OHLCV 非有限 → 该窗 `None`→NaN（`algorithm.rs:380-389`，实测：单点股本 0 后 200 个窗全 NaN）；长度不一致直接 `ValueError`（实测）——即 fail-closed 是**结构性**的，不需要额外 try/except 兜住大片 NaN。
- **P1「先例无次日开盘买」判断正确**：分钟池买=14:55 收盘（`csv_minute_backtest.py:120/487-494`），chase=09:45（`csv_ledger.py:30`，`csv_minute_backtest.py:497-508`），日线=收盘 → 「D+1 开盘买」确需新钟；改造面很小（新增一个 `_open_quote_for` 返回首根 `open` 即可，`_chase_quotes` 已有 `float(day_df.iloc[0]["open"])` 范式）。

---

## 实验记录（最小实验，可复现）

**Exp1 / Exp2（`D:\anaconda3\envs\vanna312\python.exe`，`import turnover_resist`；cpu_count=8）**

```
# 1) 单票成本 + fail-closed 行为（600 根，window=200）
per-symbol 600bars window200: 0.3697s
nan head: True finite tail: True last=0.1309
mismatch raised: ValueError close/high/low/volume/shares must have the same length
zero-share-day -> nan count in tail: 200 of 401
nan-share-day  -> nan count in tail: 200
# 2) 网格成本随窗口价差线性放大
high-price(1700, 窄幅~60元) 250bars window200: 0.22s
wide-range(100->700元, 网格~60514) 250bars window200: 1.19s (grid~60514)
```

**Exp3（可 import 性 / SSOT 探针）**

```
D:\anaconda3\envs\vanna312\python.exe -c "import turnover_resist as t; print(t.__file__); print([x for x in dir(t) if 'cyqk' in x or 'series' in x])"
→ D:\anaconda3\envs\vanna312\Lib\site-packages\turnover_resist\__init__.py
→ ['compute_cyqk_series']
help(compute_cyqk_series) → compute_cyqk_series(close, high, low, volume, shares, window, start_i=0, step=0.01)
    滚动窗口盈筹率序列：窗内每一日用该日流通股本算换手。数组等长；out[i] 对应截至第 i 根（含）的 window 日窗口；start_i 之前（以及不满一整窗）为 NaN。
```

注：仓内 `turnover-resist/python/turnover_resist/turnover_resist.cp311-win_amd64.pyd` 为 cp311 陈旧件（plan §2 同判 ✅）；vanna312 走的是 site-packages 的 cp312 —— 故切片 B 的 `--help`/manifest 应打印 `__file__`+版本，避免「跑的是旧 pyd」这类不可复现事故（这条属建议主持裁的复现口径，非核心阻断）。

---

## 总评

这份 plan 的**锚点功夫很扎实**（P1/P2 的「无既有落点」三条、R9 的 setdefault 机制、静态档案与 AGENTS 引用，我逐条复核全部为真），骨架能直接转交编码；**扣分全在「信号数据装载」这一段的可操作性**：cyqk 的新 API 选择带来无上限网格与私有股本件（R1/R2）、转录漏掉复权行让卖侧在除权日假信号（R3）、R10 论据引错件（R4）、前置 ma_infra 尚未 GO 却已写进切片（R5）、P1 新钟没落到函数级（R6）。这 6 条都是**一两段文字级**的修订（点名源/列、加网格闸、加一行前置、补两条 pin 测试），改完即可 GO 编码；当前状态**不建议直接进实现**，按 R1–R6 修订到 v0.4 后可进。
