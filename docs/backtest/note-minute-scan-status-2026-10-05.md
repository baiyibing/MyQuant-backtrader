# 分钟扫描现状 · 供后续 agent 决定下一步（2026-10-05）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-05（Asia/Shanghai） |
| 基线 | `master` `386d1dc4e8443a0558127e81dfe8be3bac6abe70`（Merge PR #363） |
| 性质 | 现状分析。汇总当日人机会话与四席两轮只读评审 |
| 授权 | **无。** 本文不批准改 `simulate`、不批准合并扫描、不批准改默认成交、不批准开新策略版本 |

后续 agent 若要动代码，先读本文第 8 节。缺单独的人裁 GO 时，停在文档。

---

## 1. 人要解决的问题

人的原意是统一分钟线回测引擎，为此做了多日「新引擎」工作。外部说法把仓库描述成「33 本策略书、主 CSV 引擎 + 分钟 bar-scan host 双引擎可用」。人要求核对：

1. 分钟 bar-scan host 是不是新做成的成交引擎。
2. 从 #304 起被称为新引擎的那条线，和主 CSV 引擎是什么关系，有没有提升，有没有必要保留。
3. 是否把「成交时机和成交价可配」并进主引擎，作为全局配置，然后退役 `bar_scan_exit` 与 wire。
4. 这几天的工作有没有意义，下一步怎么走。
5. 「分钟卖出扫描还没收成同一份代码」与「向量化引擎」是否冲突。
6. 收成同一份扫描有没有必要、是否可行，与第 3 点是不是同一件事。

本文按代码与已锁文档回答。评审是只读的，没有改策略规则，没有跑新的全量回测。

---

## 2. 三块代码，不要再叫成两台引擎

| 块 | 路径 | 实际职责 | 谁在用它算订单 |
|---|---|---|---|
| 主 CSV 引擎 | `backtest/research/csv_minute_backtest.py` 的 `simulate` → `scan_held_day`；日线是 `csv_daily_backtest.py`；version7 / topk_app 走 `simulate_v7` | 名单、现金、费用、整手、T+1、涨跌停、卖出扫描、净值 | 已注册书的研究回测 |
| 分钟 bar-scan host | `backtest/research/minute_bar_scan_host.py` 的 `main` / `run_simulate` / `run_version7` / `run_topk_app_dropout` | 读 qlib 1 分钟或数据湖，从空仓把已注册书转去调上面的 `simulate` 或 `simulate_v7` | 不单独撮合。CLI 打印的 `equity` / `return_pct` 来自旧账本收盘权益 |
| 扫线 | `backtest/research/bar_scan_exit.py` + `minute_true_core_wire.py` | 一根 K、一个持仓，成交或跳过；分类表把书挂到止损比例和书内卖点函数上 | 没有。`csv_minute_backtest.py` 不引用这两份模块 |

Host 文件头是 “Read-only minute host”。`main()` 拒绝 `--cost` / `--peak` / `--held`。`--fill-bar` / `--fill-price` 标成 legacy，不传入 `simulate`。

`scan_version1_round_trip` / `run_round_trip` 仍会自己算一份单码 `RoundTripSummary.equity`，只覆盖 version1–6。`main()` 不走它。那份权益是诊断，不是研究结果。

定位文档里的「向量化」是本仓这一台研究引擎的名字，用来和 1.3 的 LEBS、MockQMT 真栈分开。见 `docs/backtest/engine-positioning-ssot.md` §1、§3.1。它不是「卖出扫描必须是一份向量化内核」的实现声明。热路径是逐分钟 Python 状态机，行情批量装入。扫描有几份拷贝，不构成第二台引擎，也不推翻这个定位。

---

## 3. 多日工作实际留下了什么

提交信息里的「新引擎 / 真核」有两条线，后来被说成一件事。

### 3.1 2026-10-02 · minute_orders 旁路（#304 在这里）

#304 是 TC2 窄 X1：`backtest/research/minute_orders_intent_x1/`。在撮合外把限价意图冻成一批 `SubmitOrder`，再调用已有的 `run_minute_orders_research`。价格模型仍是 `completed_bucket_close`。文档写明不改 `simulate` / MatchCore / Fees。见 `docs/backtest/note-true-core-tc2-x1-intent-adapter-2026-10-02.md`。

同日前后还有 TC1 合同、TC3 具名消费者、TC4 X8 对照桥、X6 真湖边界等文档切片。它们没有变成 33 本书的成交器。

### 3.2 2026-10-03 起 · 扫线与 host（这才是口头说的「新引擎」）

| 交付 | 提交 / PR | 留下的东西 |
|---|---|---|
| 当根 K 成交或跳过 | #320 `0104e67` / `5a5346f` | `bar_scan_exit.scan_bar_exit`。人裁：不建交易系统，不改 `simulate`。不含手续费、T+1、跌停 |
| 成交时点 | #321 `fdab0f0` | `FillTiming = same_bar \| next_bar`。`next_bar` 仍用本根判断，成交价改为下一根开盘，不重判 |
| 书接到扫线 | #322 `48ee7ec` 及随后 topk 接线 | `minute_true_core_wire.py` 分类表。旧分钟入口保留 |
| 读行情 | #325 / #327 / #328 | host 按窗口读 qlib bin 与湖，日历和行情只读一次 |
| 单码现金往返 | #330–#342 一带 | version1–6 曾在 host 内自算买卖、佣金、T+1 |
| 命令行接回旧引擎 | #343 `dfa2dc9`、#345、#347 | 已注册书走 `csv_minute_backtest.simulate`；version7 与 topk_app_dropout 走 `simulate_v7` |
| 补接口 | #363 `1712cd0`，合并为 `386d1dc4` | 恢复 `FillPrice`；给 version6_2–6_12 做分类。`501de569` 上的 `bar_scan_exit.py` 没有 `FillPrice` |

`FillPrice` 只有 `"stop"` 和 `"close"`。`"close"` 只在 `same_bar` 把触价止损的成交价改成本根收盘。跳空仍按开盘，回撤止盈仍按收盘。不是开/高/低/收或任意指定价的菜单。

`version9_1` / `version9_2` 在 `_BOOK_TAKE` 里是恒返回 `None` 的 `_version9_1_take` / `_v9_2_take`，分类状态仍是 wired。`scan_held_bars` 调用 `invoke_minute_strategy` 时不传 `daily_bars`，version9 的区间止损在这条 held-scan 路径上默认不触发。`wired` 表示已分类，不表示卖点与 `simulate` 一致。

### 3.3 这几天买到了什么

买到的是：一根 K 的卖点可以不读湖、不跑整本账本做合成验收；新书若漏进分类表，测试收集会失败；host 在成为第二份净值之前接回了旧账本。

没有买到的是：一台更赚或更快的成交器，以及分钟卖出扫描的去重。没有任何一本书的订单由 `scan_bar_exit` 执行，因此没有收益或速度可以和主引擎比较。

---

## 4. 外部全景说法的核对

说法来源：Claude 对 `386d1dc4` 的仓库全景，以及随后把「新引擎 = #304 的 bar_scan」写进计划的一段口述。四席只读核对（成交完整性、研究问题、维护漂移、合并反方），第二轮对计划投票。

| 说法 | 判定 | 证据 |
|---|---|---|
| 33 本书全部注册 | 成立 | `csv_strategy_books.py` 的 `register()`；`tests/test_off_byte_baseline.py` 覆盖当前注册表 |
| 双引擎可用 | 说大了 | host CLI 调用 `simulate` / `simulate_v7`。生产成交只有主 CSV 引擎 |
| off-byte 含字节阶段全绿、平台无关 | 说大了 | `386d1dc4` 的 `python-tests` 已成功（GitHub Actions run `37257115086`，约 3 分钟）。工作流以 `pytest -m "not production and not benchmark"` 会收集 `tests/test_off_byte_baseline.py`。字节阶段在 pandas 版本不一致时 `pytest.skip`，跳过前语义断言必须先过。祖先提交 `4ffb1fa` 说明仍写「待授权机录制」 |
| version9 三书 = #361 形态 | 成立 | `git diff f708c43 HEAD -- strategy9_rules.py strategy9_1_rules.py strategy9_2_rules.py` 为空。`f708c43` 是 #361 |
| 无未合并分支债务 | 会话当时如此描述 | 本文不复验 open PR。以 GitHub 当时状态为准，不要从本文推断永远为零 |
| host 不是独立新引擎 | 成立 | `minute_bar_scan_host.py` `run_simulate` 调用 `csv_minute_backtest.simulate` |
| 新引擎是 #304 的 `bar_scan_exit` + wire | **不成立** | #304 是 `minute_orders_intent_x1`。扫线是 #320 / #321 |
| #363 只恢复接口，没有书的订单由扫线执行 | 成立 | `csv_minute_backtest.py` 零引用 `bar_scan_exit` / `minute_true_core_wire` |
| 扫线要接替主引擎里三份分钟卖出扫描，然后 version1 切过去 | 不是已锁计划 | 无此锁定术语。见第 5 节 |
| 扫线相对主引擎有净值或速度提升 | 不成立 | 无书经扫线出过订单 |
| 扫线多出来的是可配的开高低收或指定价，并入主引擎后 version1 自动用上 | 说大了 | `FillPrice` 只有 `stop\|close`。生产分钟默认是 `minute_stop_trigger=close`。扫线默认是跳空按开盘、low 触及按止损价，对应另选的 `hl`。`--stop-fill close` 在分钟路径被拒绝（日线日终专用） |
| 「33 书 + off-byte 全绿」在 `386d1dc4` 上还没核、CI 还没出来 | 已过时 | 同上，`python-tests` 已成功。本文没有在本机重跑 off-byte |

第二轮对「把 timing/price 收成主引擎全局配置，退役扫线，version1 自动用上」：四席 **REJECT**。

---

## 5. 分钟卖出扫描现在有几份

「三份」不是仓库里的锁定术语。和「收成同一份」相关的是下面这些，不要和扫线混在一个合并里。

| 实现 | 路径 | 角色 |
|---|---|---|
| 普通整天扫描 | `csv_minute_backtest.scan_held_day_python`，门面 `scan_held_day` | 共享分钟入口的参考实现。默认 `minute_stop_trigger="close"`：非跳空时用收盘相对成本的跌幅判断，按收盘价成交。`hl` 为 opt-in：low 触及按止损价 |
| 可恢复扫描 | `minute_cash_order.HeldMinuteCursor` | 文件头写明是 `scan_held_day_python` 的可恢复等价。每个时点先 open 再 close；返回候选后本 lot 扫描结束，即使外层涨跌停或容量门拒绝、部分成交。服务独立持仓与 X-02 时序现金 |
| numba 子集 | `_scan_held_day_numba_trail` | 仅当 close 域、无 sell_gate / take_profit / close_clear / reserve / defer / exit_plan / version9 时可由 `scan_held_day` 分流。不是第三套完整规则 |
| 扫线 | `bar_scan_exit.scan_bar_exit` | 旁路纯函数。不在 `simulate` 热路径 |
| 书级日循环 | `strategy12_engine.run_minute_day`、`strategy9_2_engine.run_minute_day` | 编排或另一套卖逻辑。不是 `scan_held_day` 的第三份拷贝 |
| 日线卖出 | `csv_daily_backtest` | 引擎地图写明与分钟扫描故意分开 |

已锁约束：

- `docs/backtest/note-minute-engine-unify-ceiling-u1-2026-10-02.md`：统一运行上限是现有薄封装（H-U1=B）。H-U4 禁止为统一去改 `simulate` / MatchCore / Fees。
- `docs/backtest/README.md` 引擎地图：日线卖循环与 `scan_held_day` 保持分开，禁止 big-bang 合并。
- `docs/backtest/s2b-hl-helper-boundary-2026-09-28.md`：扫描留在 `scan_held_day_python` 与 `HeldMinuteCursor`。S2-B 只批准边界文档，不批准把 scan/fill 抽走。
- `docs/backtest/note-true-core-bar-scan-exit-2026-10-03.md` 与 fill-timing note：不删 `csv_minute_backtest.py`，不改旧入口默认，不改 `simulate`。
- `docs/backtest/engine-positioning-ssot.md`：不要把不同引擎合成一台，不要互比净值。
- `docs/backtest/minute-fill-policy-ssot.md`：共享分钟默认 `minute_stop_trigger=close`。

因此：成交权威已经是一套；扫描实现还没有收成一份。两者不冲突。收成一份是这台向量化引擎内部的去重，不是再造一台引擎，也不是扫线已经完成的工作。

---

## 6. 收成同一份扫描：必要、可行、和全局配置的关系

### 6.1 有没有必要

研究问题「这本规则赚不赚」不依赖去重。必要的理由只有维护：同一卖出规则写在 `scan_held_day_python` 和 `HeldMinuteCursor` 两处，改一处漏一处会静默分叉。

numba、日线、version7、strategy9_2、strategy12 不要放进这次「同一份」。

### 6.2 是否可行

可行的切片是抽出逐根判定，两个调用方共用，行为与现在一致：

- `scan_held_day_python` 仍按整天循环，遇到卖点即返回。
- `HeldMinuteCursor` 仍按 open/close 相位推进，外层可以拒绝后续跑。调度不合并。合并调度会改变独立持仓和现金顺序，净值会变。
- 默认保持 `minute_stop_trigger=close`。
- numba 仍只服务纯回撤子集。
- 用现有 off-byte 基线验收。对不上就停。

不可行的是一个函数同时「整天扫完返回」和「每根中间把现金账停住」。

此切片改 `simulate` 热路径。H-U4 与 S2-B 都没有授权。开工前要单独的人裁，范围就写成上面四条。建议的票面用语：

> 不动 `csv_minute_backtest.simulate` 的默认成交，不合并日线卖循环，不把 numba 当成唯一核心，不让 version1 改走 `bar_scan_exit`。只让 `scan_held_day_python` 与 `HeldMinuteCursor` 共用同一个逐根判定，off-byte 与现有分钟默认保持不变。

### 6.3 和「成交时机、成交价做成全局配置」无关，不要绑在一起

| | 收成一份扫描 | 时机 / 价格可配 |
|---|---|---|
| 回答的问题 | 今天的规则只留一处实现 | 增加今天没有的行为：本根还是下一根，触价按止损价还是按收盘 |
| 默认 | 必须仍是收盘触发、收盘成交 | 扫线默认是 `hl` 语义（跳空开盘、low 触及止损价） |
| 放进同一次改动的后果 | 净值变化分不清是去重还是改规则 | 若把扫线默认收成全局配置，共享分钟从 `close` 变成 `hl`，研究净值改变 |

配置若以后要做，只能是默认关闭的开关，并且不要把 `FillTiming` / `FillPrice` 当作扫描核心的接口。分钟路径拒绝 `--stop-fill close`，那个开关和扫线的 `price=close` 不是同一个词。version1 的生产路径不读这两个枚举，统一扫描不会让它自动用上扫线。

四席对「并进全局配置后退役扫线」的一致意见是拒绝。扫线留下，身份是探针和分类栅栏。

---

## 7. 建议的下一步（未批准）

供其他 agent 讨论。人还没有对下面任何一条说「批准实施」。

1. **跑数继续只用主入口。** 日线 `csv_daily_backtest.py`，分钟 `csv_minute_backtest.py`。version7、topk_app 仍走各自入口。Host 的 `return_pct` 与 `scan_version1_round_trip` 的权益不作为研究结果。
2. **扫线冻结在现范围。** 不为了「接到新引擎」再给新书填 wire。9.1 / 9.2 的空卖点不要读成与 `simulate` 对齐。
3. **若人确认要去重，** 只开第 6.2 节那张窄票。默认成交不动，先对账再改调用点。
4. **时机和价格可配另票，且排在去重之后。** 默认关闭。先有 off-byte，再考虑是否给 `scan_held_day` 加开关。

不要做：

- 把 host 或扫线写成第二台净值引擎。
- 用扫线替换 `scan_held_day`，或让 version1 默认切到扫线。
- 把 Python 扫描、Cursor、numba、日线卖出、v7 收成一个大合并。
- 为了统一去改 MatchCore、Fees、`simulate` 的默认。
- 拿扫线 fill 计数和主引擎净值对打。

---

## 8. 证据索引

- 引擎定位：`docs/backtest/engine-positioning-ssot.md`
- 统一上限 H-U1=B / H-U4：`docs/backtest/note-minute-engine-unify-ceiling-u1-2026-10-02.md`
- 成交假设：`docs/backtest/minute-fill-policy-ssot.md`
- 扫线范围：`docs/backtest/note-true-core-bar-scan-exit-2026-10-03.md`、`docs/backtest/note-true-core-fill-timing-config-2026-10-03.md`、`docs/backtest/note-minute-strategies-bar-scan-wire-2026-10-03.md`
- #304 身份：`docs/backtest/note-true-core-tc2-x1-intent-adapter-2026-10-02.md`
- 扫描落点：`docs/backtest/s2b-hl-helper-boundary-2026-09-28.md`
- 代码：`csv_minute_backtest.py`（`scan_held_day_python`、`scan_held_day`、`_scan_held_day_numba_trail`）、`minute_cash_order.py`（`HeldMinuteCursor`）、`bar_scan_exit.py`、`minute_true_core_wire.py`、`minute_bar_scan_host.py`
- 基线：`tests/test_off_byte_baseline.py`，`scripts/research/generate_off_byte_baseline.py`
- 合并点：`386d1dc4`；扫线断点当时在祖先 `501de569`（缺 `FillPrice`）；version9 规则文件对齐 #361 的 `f708c43`
