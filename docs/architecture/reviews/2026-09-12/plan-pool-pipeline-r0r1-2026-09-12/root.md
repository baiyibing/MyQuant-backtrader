# 评审：plan-pool-pipeline-r0r1-2026-09-12（侧重实现可操作性）

评审员：root（侧重「程序员能否照此编码：函数名/文件位置/调用链/API 契约」）。独立完成，未读到其他评审员已完成意见（`_parallel/` 下只有 prompt 占位）。
本评审不修改任何文件；所有实验只读 F 湖 parquet + 临时脚本（见文末附录原始输出）。

---

## 🔴 必须修

### R1. P-R3「默认只写文档」的前提被实测推翻：F 湖**确实**在停牌日写 `volume==0` 且 OHLC 非空的行

plan §0/§1/P-R3/§6 的整条推理是：「湖省略停牌日 → E-R4 已覆盖 → 所以 C 默认只写文档」。探测证明前提不成立：

```
backtest/research/csv_daily_backtest.py:213
        table = pq.read_table(path, columns=["time","open","high","low","close"])
```

（加载器确实不读 `volume`，这点 plan 说对了。）但只读探针实测（附录 EXP6/EXP7/EXP9）：

```
EXP7 symbol=000004_SZ rows>=2000: 6426 zero: 382  last: 2026-06-22
EXP8 000004_SZ 2026-06-15..06-22 六个交易日 open=high=low=close=2.76 volume=0；06-23 复牌 0.27/0.31
EXP9 前 400 个 symbol：98 个 symbol 在 2023-01-01 后仍有 volume==0 行，共 656 行
     ('symbol=000016_SZ', 20, '2024-12-30', '2026-09-10')
```

即：湖**不省略**停牌日，而是写成「平量平价的占位 K」。当前热路径会把这种 K 当正常交易日 → 停牌日仍可 `execute_buy` / `_sell`、`pos.peak` 会被 placeholder 的 high 更新、`hit_limit_up` 用 placeholder close 判定。这不是「已知失真」级别的文档注脚，而是**让回测在不可成交日按可成交记账**的系统性错误（98/400 ≈ 24% 的样本股近三年都被污染）。

**修法（推荐，且是「激进一次到位」而不是默认降级）**：把 C 的落地分支升为默认必做，判据改为「探测（或直接在加载器里带出 `volume` 列）到 `volume==0` → 该行 ≡ 缺 K」，并让探测**复用加载器本身**：

```
EXP6 dividend_type=none/symbol=000001_SZ/data.parquet schema:
     ['time','open','high','low','close','volume','amount']      # 列已存在，读 volume 零 schema 变更
```

最省事、零重复的契约：`_read_one_daily` 多读一列 `volume`，`load_daily_bars` 返回的 DataFrame 带 `volume`；`simulate` 把「`day not in index` 或 `volume==0`」统一成同一个 `missing_bar` 谓词。这样「同路径探测」不再是额外脚本，也就没有第二套读法（正好满足 P-R3 想要的约束）。若坚持保留探测脚本，至少要在 plan 里写死：路径必须是 `resolve_period_root("1d")/"dividend_type=none"/f"symbol={to_partition_key(code)}"/"data.parquet"`，并与 `csv_daily_backtest.py:238` 完全一致，否则会去读 `dividend_type=front` 得到相反结论。

**为什么必须升 🔴**：P-R3 现在把「不改热路径」当默认，成果是「文档写了、`git diff` 为空」——但实测数据说默认这条路会让 R0/R1 之后所有用 CSV 书的回测（不只 R0 窗）继续错记停牌日成交。这会直接误导后续所有结论。

### R2. `name_asof` 的**前向**（stale-forever）分支会把「防后日赢」变成「防不了旧名污染未来」，且 §6 的「fail-open 偏宽板」理由与代码事实相反

plan P-R2 定了 `name_asof(code, ds) = 当日非空名，否则 max{name : ymd<=ds 且非空}`，并把它描述为「比后日赢安全」。前半句对，后半句只对「无名」这一支成立：

```
market_layer.py:57
def limit_pct(code: str, name: str = "") -> Optional[float]:
    if is_st_name(name):
        return 0.05            # ST = 更窄的板
    return board_limit_pct(code)   # 无名 = 10/20/30%
```

于是两个方向不对称：
- **无名方向**（fail-open）：按宽板（10/20/30%）→ 只会漏判涨停/跌停，偏激进，符合 §6 描述。
- **有名方向**（stale）：一旦某 code 在窗口内任意一天出现非空名（尤其含 `ST`/`*ST`），该名字此后**永久**生效，5% 窄板 → 会给涨到 +5% 的股票判「涨停禁买」，或给跌 5% 的持仓判「跌停卖不出/`defer_sell_limit_down` 虚增」。这正是 plan 自己想消除的那类伪成交，只是换了个时间方向。§6 把整条 `name_asof` 概括为「fail-open 偏宽板」，与 `market_layer.py:63-64` 的事实相矛盾，属逻辑不一致。

**数据面更严重**：pool CSV 是**候选名单**不是全市场快照，历史窗里绝大多数 code 在大多数日子**没有行**；「当日非空名」是常态缺口。再加上这些历史名单的「名称」列往往是导出时用**当期名字**回填的（项目历史教训同类问题），`ymd<=ds` 只能挡「代码读未来」，挡不住「数据本身把今天的 ST 标签写进了三年前的 CSV」。

**修法**：把 name 的有效期/来源写进契约与单测，二选一或叠加：
1. `name_asof` 只在「该 code 在 `ymd<=ds` 的**最近一次**观测内」生效，超过窗口（如 N 个交易日或 N 个自然日）回退到板块档；
2. 或加 `pool_names_max_age_days` 开关（默认有限值），并在 pool CSV 契约里写明「名称列是观测，不是履历」；
3. 至少必须补一条「旧 `*ST` 名不得在 N 天后继续把主板压到 5%」的回归测，否则 B 的单测①（D1 10% / D2 5%）只锁了前向，没锁反向。

### R3. P-R2/B 缺可编码的 helper 契约：`simulate` 内部所有取名单点都要换源，plan 只说了「加参数」

`names` 在 `simulate` 顶部只赋值一次、之后所有 `_named_limits` 共用：

```
csv_daily_backtest.py:261-262   def _named_limits(code, prev_close, names): return resolve_limit_prices(code, prev_close, names.get(code, ""))
csv_daily_backtest.py:312       names = dict(pool_names or {})
csv_daily_backtest.py:326/413/451   limits = _named_limits(code, prev_close, names)   # 3 个调用点
csv_minute_backtest.py:593/611/685/731 同构（4 个调用点）
```

`simulate` 的 per-day 值必须在**每个 `i` 循环**变成「as-of 该日」的表，否则加了 `pool_names_by_day` 参数也会成为死代码。plan 只写「`simulate` 只加可选 `pool_names_by_day`」，没给函数名/签名/取值算法，程序员会各自发明（最容易踩的坑：写成对整窗做 `max(k for k in by_day if k<=ds)`，见 R6 的性能问题）。

**建议写死的契约（照抄即可实现）**：
```python
# backtest/research/csv_pool.py
def load_pool_names_by_day(pool_dir, start, end) -> dict[str, dict[str, str]]:  # {YYYYMMDD: {canonical: name}}，空文件不入表
def resolve_pool_names_for_day(by_day: dict[str, dict[str, str]], ds: str) -> dict[str, str]:  # 累积 ymd<=ds 的最新生效名，按日缓存
# csv_daily_backtest.py / csv_minute_backtest.py
simulate(..., pool_names: dict[str,str] | None = None, pool_names_by_day: dict[str, dict[str,str]] | None = None)
```
语义：`pool_names_by_day` 非 None 时按日解析并**忽略** `pool_names`（否则两源打架）；`pool_names` 保持今天的扁平语义（冻结给旧测）。两条 engine 必须同签名同语义，并把 3/4 个 `_named_limits` 调用点改为传「当日表」——这是 B 的真正工作量，plan 应把它写成完成定义的一部分。

### R4. 停牌「≡ 缺 K」在日线 `simulate` 里做不到「无 K」，因为缺 K 的既有分支是 `continue`——会把停牌日静默变成「不评卖也不评买（含 pending 不成交）」，而 plan 想要的正是这个，但没写清 `last_close_mark` 的取值来源

```
csv_daily_backtest.py:318-320
        for code in list(st.positions):
            if code not in bars or day not in bars[code].index:
                continue
```
这条 `continue` 在「湖省略停牌日」时是对的（等价于 plan 要的语义）。一旦湖**有**占位行（R1 已证），要实现「volume==0 ≡ 缺 K」就必须在第一层判断里加 `or volume==0`，且估值循环同样要跳过：

```
csv_daily_backtest.py:468-472
        eq = st.cash
        for code, lots in st.positions.items():
                eq += pos.shares * last_close_mark(df_c, day, pos.cost)
```
`last_close_mark(df_c, day, pos.cost)` 在「day 存在但 volume==0」时会拿到**占位 close**（通常等于前收，但长期停牌后复牌前一日可能出现与实际脱节的价），plan 写的「净值按缺行走 `last_close_mark`」并不足以保证「不把零量 close 标进净值」——必须把传入的 `day` 回退到「最近一个 volume>0 的交易日」。plan 里「由调用方按缺行处理」一句没有指明这个回退点，程序员会照字面实现成「当日 close」。

---

## 🟡 应修

### R5. `load_pool_names_by_day` 的**键缺口语义**必须显式写进契约（否则 as-of 回退会吞掉「当日空名单」）

现有 `load_pool_day_map` 用 `empty_in_map` 明确区分「缺文件」与「空文件」：
```
csv_pool.py:107-113
        if codes or empty_in_map:
            map_key = ...
            days[map_key] = codes
```
`load_pool_names_by_day` 若照抄 daily 的 `empty_in_map=False`，则「D2 文件存在但该 code 不在名单/空文件」时不会有 `D2` 键，`name_asof` 会回退到 D1 的旧名 —— 这正是 R2 的 stale 洞在**正常空名单日**的复现。契约（pool-csv-contract.md）目前只写「缺日 / 空文件 = 当日不买」（第 5 行），没有写「空日不得继承旧名/旧板」。建议明写：**名称 as-of 只看非空观测，且日期键缺失与空值等价于「当日无新观测」**，并把 R2 的时限规则一起写进同一节。顺带把 `run()` 里 `load_pool_names_by_day(...)` 的调用位置挪到 `if not pool_days: raise` 之后（现在是先取名再判空，见 `csv_daily_backtest.py:517-521`），语义更顺。

### R6. as-of 解析的性能/正确性实现细节：不要用「对整窗 dict 做 max」，也不要用「依赖 dict 插入序向前扫描」

plan 说「实现用循环内推进的 `last_seen`，或查 by_day 时过滤 `ymd<=ds`。禁止对已加载整窗做无上界 `max`」。方向对，但没给判据。R0 窗 3 周、`names` 调用发生在每个持仓×每个交易日的内层（`csv_daily_backtest.py:326/413/451`；分钟更密），写成 O(#days) 的过滤虽正确但会把 `t_sim_s` 放大。建议：`sorted(by_day)` 一次 + `bisect_right(keys, ds)-1`，然后**按 ds 缓存**合并表（一个窗口内最多 #days 次合并，之后 O(1)）。这也顺带消掉「dict 插入序恰好是升序」这种隐式依赖（`csv_pool.py:80` 的 `sorted(glob)` 才是升序来源，别依赖）。

### R7. 分钟链的 T+1 / pending 语义与日线**不同构**，plan 的「分钟必须有对等注入」没提这点

`csv_minute_backtest.py` 没有 `pending_exit` 这套状态机（全文 `pending_exit` 0 命中），它靠 `scan_held_day(can_sell=(n_days>=1))` 在**当日分钟序列内**出场：
```
csv_minute_backtest.py:630
                    can_sell=(n_days >= 1),
```
而日线是「收盘触发 → 次日开盘 `pos.pending_exit` 成交」（`csv_daily_backtest.py:334-339`）。两者都合规（无未来 bar），但**默认参数下同一策略日线/分钟结果天然不同构**。plan §P-R1 说「C 若落地可改 `simulate` 控制流」，对分钟只写了 volume 对等，没写清楚「volume==0 ≡ 缺 K」在分钟侧怎么落到 `_slice_day`/`build_day_spans`（整日 volume==0 时 `day_m` 可能仍是 None 或全 0 量行）。建议在 C 的落地分支里显式给分钟侧写一条：`day_m` 为空**或**整日 volume 全 0 → 同缺 K 分支，且 `pending_chase` 不 pop。否则「分钟整日跟日线 volume」无法编码。

### R8. `validate_pool_dir` 的返回契约、宽松解析边界、以及 formula 形态未定

plan P-R6 只说「严格契约门：文件名 `YYYYMMDD.csv`；数据行首列必须恰好六位数字；失败模式：R0 胶水与单测调用；`run()` 不因 validate 失败 SystemExit」。没写函数签名/返回类型（抛异常 vs 返回错误列表）——A 切片的完成定义是「非恰好六位被收集」，说明期望**收集**而非抛出，那就应写 `def validate_pool_dir(pool_dir, start=None, end=None) -> list[str]`（或 `list[tuple[Path,int,str]]`）。另外两个边界必须在契约里定死：
- 现有解析器接受 Excel 公式 `="000688"`（`tests/test_csv_pool.py:27-30` 冻结），严格门会把它判失败；这是有意的还是遗漏，需要一句话。
- 「文件名 `YYYYMMDD.csv`」与现有 `glob("*.csv")` + `stem` 校验（`csv_pool.py:80-82`）重复；P-R6 说「复用现有扫盘，禁止第二套 split/表头逻辑」，但 `validate_pool_dir` 仍需自己走一遍文件名校验，建议直接复用 `_window_ymd` + 同一 `stem` 判据，避免两处对「8 位数字」的定义漂移。

### R9. R0 胶水（`scripts/data/r0_positions_to_pool.py`）缺可测性与路径解析契约

- **可测性**：plan 说「仓内最小 utf-8 fixture + 单测」，但没写「纯函数 / I-O 分离」。若 `parse` 直接读文件，单测就得造 MyQuant 目录树。建议契约写成 `parse_positions_text(text: str) -> list[str]`（`持仓标的列表:` 后取 Python list；`[]`/缺行 → `[]`）+ `write_pool_csvs(positions_by_day, out_dir)`，`main()` 只做 `--src`/`--out-dir` 与 `SystemExit`。这样 P-R5 的 ①②③ 四个验收点全部可在本仓无外仓依赖跑通。
- **导入/路径**：新脚本要 import `oskh_core.a_share_symbol_normalize`（见 `csv_pool.py:18`）与可选 `validate_pool_dir`。`scripts/data/` 现有脚本的同族做法是 `scripts/_script_bootstrap.py` 的 `ensure_repo_on_syspath(__file__)`；plan 只写了「禁止 import qlib/chip_indicator/StockDataReader」，应补一句「必须 bootstrap 仓根进 sys.path（或 `sys.path.insert`），否则 `scripts/data/` 直跑 ImportError」。
- **默认输出目录写死窗口**：`--out-dir` 默认 `exports/r0_20260302_20260323/` 把窗口硬编码进了默认值；一旦换窗口必须显式传参。建议默认由 `--start/--end` 派生（或要求必填），否则易产出「文件名窗口与内容窗口不符」的名单，而这一层恰恰没有校验。
- **`.gitignore` 写 `exports/`**：现有 `.gitignore` 未见该条（本次只读抽查未命中），实施时注意不要写成 `exports` 之外的模式，也别把 `exports` 目录建在仓库外。

### R10. 日线 `run()` 先加载 names 再判空、且 `_named_limits` 是模块私有但跨引擎重复定义；建议顺手统一

`csv_daily_backtest.py:517-521` 与 `csv_minute_backtest.py:804-808` 各有自己的 `load_pool_days`/`_named_limits`/`load_pool_name_map` 调用，改动点分散。plan §5 落点表已列出四个文件，但没有说明「两个 `run()` 的改动必须同一形状」，也没有说明 `load_pool_name_map` 删除/废弃后 `tests/test_csv_pool.py:61-66` 这条「后日赢赢家」断言如何改写。P-R2 已写「删除，或改名为测试专用并改写后日赢断言」——但「改写后日赢断言」与 plan §2 禁改项「保留后日赢作为生产语义或未改名的绿测」需要一致：改名后测试必须断言**旧行为已被拒绝**（比如断言 `load_pool_name_map` 不再被生产代码引用，或直接删除该测），不能留一条断言 `names["600000.SH"]=="*ST 浦发"` 的绿测，否则双 SSOT 仍活着。

---

## 🟢 可选

- **G1** `load_pool_names_by_day` 与 `load_pool_day_map` 可共用一个内部扫盘函数（`_iter_dated_pool_csvs(root,start,end)`），把「8 位数字 + 窗口过滤」的定义收成一处；P-R6 的 validate 也复用它，符合「复用现有扫盘」。
- **G2** HELP/docstring 里 R0 的无名 ST 失真（10/20/30% 而非 5%）可以顺手加一条 `stderr` 警告：当名单目录里**没有任何**第二列名时打印「名称列缺失，ST 按板块档」。零成本，防止后人把 R0 净值当档位验收（plan §6 已有文字要求）。
- **G3** 建议给 `names` 取表加一个 `stats["names_asof_stale_days_max"]`（或在 `r0` 脚本里打印名单覆盖到日比例），把 R2 的 stale 风险量化出来，多轮评审时不用打架。

---

## ✅ 做对的地方（保留）

- **T+1 / 无未来 bar**：日线 `n_days = i - pos.entry_idx`（买入日 0）→ `n_days>=1` 才评卖（`csv_daily_backtest.py:332-341`）；`pending_exit` 次日开盘成交（:334-339）；`same_bar` 白名单才允许当日收盘成交（:383-388）；`prev_rows = index < day`（:322）与 `daily_closes_ending_yesterday`（分钟 :643）都只喂 T-1 及以前。分钟 `can_sell=(n_days>=1)`（:630）。这一块没有偷价。
- **复权口径单一口径**：日线 `dividend_type=none`（:238）+ 分钟 `dividend_type=none`（:334）+ 文档 :237「与分钟链 align」；成交量探针实测也在 `dividend_type=none` 子树下。计划「复权保持 none」与代码一致。
- **筹码不越界**：plan P-R7 明确「盈筹率不适用」，且 R0 胶水禁止 import `chip_indicator`。本仓 `cyqk` 0–1、默认 front 的坑没有被带进 1–8 书。
- **涨跌停档位**：`_BOARD_20=("300","301","302","688","689")`、`_BOARD_30=("920","430","83","87","88")`、`_BOARD_10` 主/中小，未知前缀 fail-closed（`market_layer.py:17-22,43-54`），ST 名称列 5%（:57-65）——与 plan §1 表格一致。
- **名单缺日/空文件语义**：`empty_in_map=False`（`csv_pool.py:107-113`）+ `pool_days.get(ds, [])`（daily :434 / minute :706）保证「缺日 = 不买」。
- **平面 `pool_names` 保持 `dict[str,str]` 只增可选参**：`simulate(..., pool_names=...)` 在 daily :281 与 minute :565 已存在且被 `tests/test_csv_daily_backtest.py:780-787` 冻结，plan 选择兼容式扩展而非换签名，方向正确（只需按 R3 把 by_day 的取值点写清）。
- **包边界**：R0 胶水放 `scripts/data/` 而非 `scripts/research/`（`scripts/data/` 已存在同族脚本），v7 明确不喂名称列（`csv_minute_backtest_v7.py` 只 import `load_pool_day_map`，:39/:414-417），Cerebro/LEBS/MockQMT 不进本 plan。

---

## 附录：最小实验与原始输出（可复现）

环境：`D:\anaconda3\envs\vanna312\python.exe`，只读 F 湖；脚本写在 `%TEMP%`，不落仓库。

**EXP1/EXP3 — 后日赢（前向污染）可复现**
```python
# 取 D2 才有 *ST 的窗口，把 load_pool_name_map 结果喂回 simulate 于 D1
(tmp/"20251103.csv").write_text("600000,NoST")
(tmp/"20251104.csv").write_text("600000,*ST")
print(load_pool_name_map(tmp, "20251103","20251104"))
# D1 close 恰好 = 昨收*1.05
sim.simulate(bars, {"20251103":["600000.SH"]}, "20251103","20251107",
             strategy="version6", pool_names={})                # 无名字
sim.simulate(..., pool_names={"600000.SH":"*ST"})               # 后日赢平面表
```
输出：
```text
EXP1 flat map over full window: {'600000.SH': '*ST'}
limit_pct 600000.SH with *ST: 0.05 -> (10.5, 9.5)
limit_pct 600000.SH bare: 0.1 -> (11.0, 9.0)
EXP3 bare:     buys=1 skip_limit_up=0
EXP3 *ST flat: buys=0 skip_limit_up=1 chase_abandon=1
```
结论：同一根 D1 bar，只因 D2 的名字被平面表提前套用，买入判定就反转 → plan P-R2「按日 + `ymd<=ds`」是必须的（不是风格问题）。

**EXP4 — 两个新 API 都不存在（计划的落点是真新增）**
```text
has load_pool_names_by_day: False
has validate_pool_dir: False
public names: [... 'load_pool_day_map', 'load_pool_name_map', 'parse_pool_csv', 'parse_pool_csv_entries']
```

**EXP6/EXP7/EXP8/EXP9 — 停牌占位行（本评审 🔴R1 的根据）**
```text
symbol=000001_SZ/data.parquet schema: ['time','open','high','low','close','volume','amount']  rows=8723
000004_SZ  rows>=2000: 6426  zero-volume: 382  last zero: 2026-06-22
000004_SZ 2026-06-10..06-22: open=high=low=close=2.76 volume=0（连续 8+ 个交易日）；
          2026-06-23 复牌 open=0.27 close=0.31 volume=251734
前 400 个 symbol（>=2023-01-01）：98 个 symbol 有 volume==0 行，共 656 行
  ('symbol=000004_SZ', 38, '2023-06-27', '2026-06-22')
  ('symbol=000016_SZ', 20, '2024-12-30', '2026-09-10')
  ('symbol=000008_SZ',  5, '2026-07-07', '2026-07-13')
  ('symbol=000407_SZ', 10, '2025-10-28', '2025-11-10')
```
结论：湖里停牌日**以 `volume==0` 的平价 K 存在**；plan C 的「省略 → E-R4 已覆盖」前提不成立，默认降级会把停牌日当正常交易日成交。附：`EXP6/EXP9` 全部为只读 `pq.read_table`，无写操作；`volume` 列已存在，加读该列无 schema/迁移成本。

---

## 总评

plan 的骨架（T+1/复权/包边界/不重写引擎/按日 as-of 的方向）是对的，A/B/E 切片基本可编码；但**两条 P-R3/P-R2 的事实前提**需要改：C 的「湖省略停牌日」被 F 湖实测推翻（98/400 样本股近三年有 `volume==0` 占位 K，最近到 2026-09-10），B 的 `name_asof` 只修了后日赢、没修旧名永久生效，且 §6 把「5% 窄板」写成 fail-open 与代码相反。另有若干「函数签名/取值点/可测性」空白（R3/R4/R8/R9），是实施时最可能卡住程序员的地方。建议：**C 升为默认落地（读 volume 列，`volume==0 ≡ 缺 K`，含估值回退到最近有量日）、B 增加名称有效期/回退边界、补齐 R3/R9 的 API 与单测契约后即可进实现**；在此之前按 v1.1 原样实施不通过。

