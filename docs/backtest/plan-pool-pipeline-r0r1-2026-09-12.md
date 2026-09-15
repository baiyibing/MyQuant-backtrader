# Plan：名单管道 R0/R1 + A–E 剩余正确性

> **落盘**：2026-09-12。
> **状态**：📄 **v1.2 · classic 已回填 · 可进人裁「按 plan 实施」**。未说该句前不改业务代码。
> **风险档**：**L1**（契约 + 名称 as-of + 加载侧丢 volume==0 + 一次性管道胶水；不重写引擎 / 不改卖点 / 不改 `presets.py`）。
> **fan-out**：2026-09-12 classic，四家 rc=0（codex 224s / kimi 677s / auto 147s / claude 446s）。综合：`docs/architecture/reviews/2026-09-12/plan-pool-pipeline-r0r1-2026-09-12/merge-consensus.md`。
> **范围**：MyQuant-backtrader 为主。MyQuant `position_analysis.txt` 只读输入。1.3 只读对照。
> **定位 SSOT**：[engine-positioning-ssot.md](engine-positioning-ssot.md)。成交核现锁：[engine-ashare-correctness.md](engine-ashare-correctness.md)（E-R1–E-R4，PR #18）。
> **上游**：MyQuant `docs/plan-three-repo-roadmap-2026-09-12.md` §3 R0/R1、§3.1、§6（外仓路径，不作本仓入口）。人裁「以本仓为主：A–E 后剩下的正确性 + 名单管道 + 轻量清债，不重写引擎」。
> **对抗**：dissent-steelman / domain-safety / pattern-evidence（不计票）。勘误 §8。综合草案：`docs/architecture/reviews/2026-09-12/plan-pool-pipeline-r0r1-2026-09-12/review-by-cursor.md`。

---

## 0. 一句话

书和成交核已经齐。本轮只把 **日名单管道跑通一次**，并修 A–E 留下的两处债：**ST 名称按日 as-of（禁止看未来）**、**加载侧丢弃 `volume==0` 占位 K（≡ 缺 K）**。不拆模块、不改卖点、不加印花、不碰路线图 R2/R3/R5。

```text
MyQuant position_analysis.txt
        ↓  本仓一次性胶水（不是第二份导出 SSOT）
exports/r0_*（gitignore，不入库）
        ↓  parse_pool_csv + validate_pool_dir
csv_daily --strategy version6 --pool-dir <out>
        ↓
summary.txt   只验收管道，不看赚亏，不当 E-R2 验收
```

---

## 1. A–E 之后还剩什么（禁止重做已落地项）

已落地，本轮 **禁止重开 E-R\***：

| 已落地 | 锁 |
|--------|----|
| 北交 30% / 689·20% / ST 名称列 5% / 未知板块 skip | E-R2 |
| 全卖因跌停 defer | E-R1 |
| Decimal `limit_prices`，`1.65×10%` → 1.49 | E-R3 |
| 缺 K 冻仓、净值 last close、追买保留 pending | E-R4 |
| 账本 `csv_ledger.py` | 切片 E 已合 |

真正剩下的：

1. **ST as-of**。`csv_pool.load_pool_name_map`（约 L68–89）把 `[start,end]` 第二列并成一张 `dict[code,name]`，后日覆盖前日。`csv_daily_backtest.run` L518 与 `csv_minute_backtest.run` L805 把这张表一次塞进 `simulate(..., pool_names=)`。契约 [pool-csv-contract.md](pool-csv-contract.md) 写的是「文件名 = 买入日 T」。现行为会让窗口末日的 `*ST` 污染前日主板档（`tests/test_csv_pool.py` `test_load_pool_name_map_keeps_st_column` 正是后日赢）。**生产路径必须按日，且 `ymd<=ds`。**
2. **停牌 volume=0**。E-R4 只处理「当日无 K」。日线/分钟加载器 **不读 `volume`**（`csv_daily_backtest.py` 约 L213；分钟约 L156）。F 湖 **不省略**停牌日，写成 `volume==0` 占位 K（主持裁复现 `000004_SZ`：8668 行中 458 行零量、OHLC 平推）。切片 C **默认落地**：加载侧丢这些行，交易环与净值环走既有缺行路径。
3. **R0 贯通**。MyQuant `my_scripts/position_analysis.txt` 2026-03-02~03-23 窗已含 `BJ920014`，无名称列，03-02 空仓。缺的是胶水 → `--pool-dir` → 日线 `version6` 出 `summary.txt`。不写 `stock_pool/`，不喂策略 7，不看赚亏。
4. **R1 契约**。已有格式 + as-of + 名称列 + `empty_in_map` 分叉。缺：名称 as-of 谓词、方言链、`validate_pool_dir`（严格契约门）。不要为凑「30 行」灌水。路线图 R4（本仓 README「主入口 LEBS」）已修。外仓 README / MyQuant 路线图 §8 **不进本仓完成定义**。

R0 无名称列：真 ST 按代码前缀分板（600→10%，300/301/688→20%，920→30%）。不编造 ST 名。该窗 **不得** 当 E-R2 / 涨跌停验收。

---

## 2. 非目标 / 禁改

| 不做 | 原因 |
|------|------|
| 再拆 `csv_daily` / `csv_minute` / 改 `execute_buy` / `_sell` 公式 | P-R1 |
| 改 1–8 卖点 / `register(version7)` / 改 `presets.py` | 书契约与 1.3 共享卖核 |
| 改佣金 / 加印花 / 新股首日无板 / 复牌特限 / ST 履历库 | P-R7 |
| v7 接名称列 | R0 不喂 7 |
| MyQuant `export_daily_pool.py`（R2）/ 修训练走查（R3）/ alpha158 闭环（R5） | 住 MyQuant |
| 用 R0 窗净值或涨跌停统计判断名单/档位质量 | 路线图 M5；§3.1 |
| 为 R0 编造名称列 | 源文件没有名称 |
| 复活 `engine.py` / 拷 LEBS·MockQMT / 用 Qlib·Cerebro 净值验收 | 第四套引擎禁令 |
| 改 `docs/architecture/reviews/**` 历史评审原文 | 考古 |
| 本仓切片完成定义包含改 MyQuant / 1.3 README 或路线图 §8 | 外仓债；不阻塞 |
| 转换器放进 `scripts/research/` 或 import `qlib` / `chip_indicator` / `StockDataReader` | 该目录是筹码 / TR |
| 保留「后日赢」作为生产语义或未改名的绿测 | 双 SSOT |

---

## 3. 现锁（P-R*）

| ID | 锁 |
|----|----|
| **P-R1** | 不重写引擎。禁止再拆日线/分钟文件，禁止改 `execute_buy` / `_sell` 成交公式，禁止改 1–8 卖点，禁止 `register(version7)`，禁止改 `presets.py`。B 只改怎么取名称。C 在 **加载器** 丢 `volume==0` 行，不改 `simulate` 买卖公式、不改 `last_close_mark` 公式。不改公式 ≠ 不改成交集合。 |
| **P-R2** | **谓词**（进契约）：`name_asof(code, ds) = 当日非空名，否则 last_seen[code]`。`last_seen` 仅在 `ymd<=ds` 且名称非空时覆盖（= 取 `max ymd ≤ ds` 的那条名，**不是**对 name 字符串取 max）。每个日历日开盘前 ingest 当日池名。空名单元格不覆盖 `last_seen`。**禁止 `ymd>ds`**。新增 `load_pool_names_by_day(...) -> dict[str, dict[str, str]]`（外键 `YYYYMMDD`）。`run()` **只走** by_day，禁止再调 `load_pool_name_map`。`simulate` **只加**可选 `pool_names_by_day`；扁平 `pool_names: dict[str,str]` 保持原类型。**两者同传：`pool_names_by_day is not None` → 只走 as-of，忽略扁平。** 分钟对等注入。`load_pool_name_map`：删除或改写后日赢断言后标废弃。 |
| **P-R3** | **C 默认落地**。`_read_one_daily` / `_read_one_minute` 多读 `volume`（schema 已有，零迁移）。**加载后丢弃 `volume==0` 行**（分钟：按日 `volume` 合计 ==0 则整日丢行；列已在分钟 parquet）。丢行后既有 `day not in index` 自动满足：不评卖（含 pending）、不新开、追买不 pop、不更新 peak、净值走 `last_close_mark` 缺行分支。禁止「交易跳过但行留在 index」。缺 `volume` 列：先看 schema 或降级重读，**不得**落入现有 `except: return None`（否则整票消失）。测试夹具无该列 = 不冻。禁止 `StockDataReader` / `chip_indicator`。禁止造停牌状态机 / 复牌特限 / `pos.cost` 回潮。同步改 E-R4 文案。C 与 D **禁止同窗互验**。 |
| **P-R4** | 人裁本仓为主：一次性胶水可留本仓，但 **不是** 第二份 Qlib 导出 SSOT，也 **不得** 进 `scripts/research/`。路径：`scripts/data/r0_positions_to_pool.py`。禁止 import `qlib` / `chip_indicator` / `StockDataReader`。`--src`：环境变量 `OSKH_R0_POSITIONS`，否则仓库根的 `../MyQuant/my_scripts/position_analysis.txt`（不存在 → SystemExit，文案带尝试过的路径）。`--out-dir` 默认 `exports/r0_20260302_20260323/`；gitignore `exports/r0_*/`。**解析**：日期取自每个 `持仓标的列表:` **之前最近的** `日期:` 行；持仓 **只** 来自该 list；`[]` → 不写文件。不解析其下表格。`SZ300190` / `BJ920014` → 裸六位。仓内最小 utf-8 fixture。禁止写 `stock_pool/`。docstring 写明：源列表是 Qlib **当日收盘持仓**，不是当日新买；引擎对已持仓走 `skip_held`。 |
| **P-R5** | R0 验收：① converter 单测（03-02 无文件、有持仓日含 `920014`）；② `parse_pool_csv` 能吃；③ `canonical_from_bare_code("920014")=="920014.BJ"` 是已有 SSOT，不得单独当完成定义；④ 本机 `csv_daily_backtest.py --strategy version6 --pool-dir <out> --start 20260303 --end 20260323` 出 `summary.txt`。产物不入库。失败只报管道。禁止把该窗净值或涨跌停桶当模型/档位结论。HELP/docstring 写明 **全板块** 无名 ST 按前缀档。version8 可选。D 不依赖 C 落地。 |
| **P-R6** | R1 补 [pool-csv-contract.md](pool-csv-contract.md)：**名称 as-of 谓词**（P-R2）+ 方言链 `Qlib SZ300190 → CSV 裸 300190 → 湖 300190_SZ → 交易层 300190.SZ`。不要凑行数。`validate_pool_dir` = **严格契约门**：文件名 `YYYYMMDD.csv`；数据行首列必须恰好六位数字（`SZ300190` 在 CSV 里校验失败，解析器 `_cell_to_bare` 仍宽松）。复用现有扫盘，禁止第二套 split/表头逻辑。失败模式：R0 胶水与单测调用；`run()` **不**因 validate 失败 SystemExit（现网 `stock_pool/` 保持宽松解析）。本仓 README / `docs/backtest/README.md` 链契约。MyQuant / 1.3 链接 **不** 写进本仓完成定义。 |
| **P-R7** | 不重开：费率、新股首日无板、复牌特限、ST 履历库、v7 名称列、R2/R3/R5、Qlib/Cerebro 净值对照。盈筹率不适用。复权保持 `none`。C 必须同步改 `engine-ashare-correctness.md` 的 E-R4 文案（加载丢零量行 ≡ 缺 K），不能只改本文。 |

---

## 4. 切片（评审通过且人裁「按 plan 实施」后才做）

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · R1** | 契约补 as-of 谓词 + 方言链；`validate_pool_dir` + 单测 | 严格门：非恰好六位被收集；`parse_*` 仍宽松。`run()` 成交循环无 diff |
| **B · ST as-of** | `load_pool_names_by_day`；日线+分钟 `run`/`simulate` 按 `name_asof`；`last_seen` 只向前推进 | **三条**单测：① D1「浦发」/ D2「*ST」→ D1 10%、D2 5%；② 持仓日名单无该码 → 回退昨日名；③ D3 才出现 `*ST`，D2 不得 5%。后日赢旧测改写或标废弃。扁平 `pool_names` 类型不变 |
| **C · 停牌** | 日线+分钟加载丢 `volume==0` 行；改 E-R4 文案 | 零量占位日：不卖、不买、追买仍 pending、净值=昨收。夹具无 volume 列行为不变。单独 commit，不与 D 绑 |
| **D · R0** | `scripts/data/r0_positions_to_pool.py` + fixture + `exports/` gitignore + 本机 version6 | converter 单测绿；有持仓日 CSV；03-02 无文件；`summary.txt` 落地。产物不入库 |
| **E · 清债** | 本仓 `docs/backtest/README.md` 补 `--pool-dir` 例；根 README 链契约 | 本仓三入口不漂。**不含**改外仓 |

禁止 A–D 同一 commit。B 与 C 禁止绑在一起。

验收（实施阶段；本草案不跑 R0 真窗）：

```text
D:\anaconda3\envs\vanna312\python.exe -m pytest -q `
  tests/test_csv_pool.py tests/test_market_layer.py `
  tests/test_csv_daily_backtest.py tests/test_csv_daily_backtest_v8.py `
  tests/test_csv_minute_backtest.py tests/test_csv_minute_backtest_v8.py
```

另：converter fixture 单测（随 D 落地，文件名实施时定）。

---

## 5. 代码落点

| 文件 | 动作 |
|------|------|
| `backtest/research/csv_pool.py` | `load_pool_names_by_day`；`validate_pool_dir`；处理 `load_pool_name_map`（删或废弃） |
| `backtest/research/csv_daily_backtest.py` | `run` 走 by_day；`simulate` 加 `pool_names_by_day`；`name_asof` |
| `backtest/research/csv_minute_backtest.py` | 同上 |
| `scripts/data/r0_positions_to_pool.py` | **新建**胶水 |
| `tests/fixtures/` 下 R0 最小 txt | 转换器单测 |
| `.gitignore` | `exports/` |
| `docs/backtest/pool-csv-contract.md` | as-of 谓词 + 方言链 + 校验门 |
| `docs/backtest/engine-ashare-correctness.md` | C 探测结论 |
| `docs/backtest/README.md` / `README.md` | `--pool-dir` 例 + 契约链 |
| `tests/test_csv_pool.py` 与日线/分钟 ST 单测 | as-of 三条 + validate |

禁止改：`csv_ledger.py` 的 `execute_buy` / `_sell`、`market_layer.limit_pct` 档位表、`csv_minute_backtest_v7.py`、`csv_strategy_books.py`、`presets.py`、`docs/architecture/reviews/**`。

---

## 6. 风险 / 已知失真

- R0 无名称列 → 真 ST 按板块档（10/20/30），不是 5%。全板块都如此。接受，并写进脚本 docstring；该窗不当 E-R2 验收。
- `name_asof` 在名单断档时可能落后于交易所 ST 变更日（fail-open 偏宽板）。比后日赢安全。本轮不建履历库。
- R0 真窗依赖 F 湖 2026-03 日线（含 `920014`）。缺分区 = 管道失败。
- 摘帽/离池后 `last_seen` 仍带着旧 `*ST` → 5% 窄板（少卖）；断档无名 → 偏宽板。比后日赢安全。本轮不建履历库、不加 N 日失效开关。
- 全零价占位（OHLC=0）在 C 落地前只靠 `px<=0` / `hit_limit_down(0,0)` 巧合守卫；落地后随丢行消失。
- `run()` 不跑严格 validate：现网名单里带后缀的行仍会被 `_cell_to_bare` 吃掉。

---

## 7. 修订程序

改 P-R\* 须改本文。改成交核（跌停范围、档位、涨跌停价算术、缺 K 净值/追买）须改 [engine-ashare-correctness.md](engine-ashare-correctness.md) 的 E-R\*。对抗 🔴 回填 §8.1；classic 🔴 回填 §8.4。未说「按 plan 实施」前不改业务代码。

---

## 8. 对抗勘误（v1 → v1.1）

主持裁让步必须落笔。对抗草案不计独立票。

### 8.1 主笔让步

1. **P-R2 必须锁 `ymd<=ds`。** 「向前扫描已加载」无上界可复现后日赢。补断档回退与「后日 `*ST` 不得污染前日」单测。分钟对等注入。
2. **扁平 `pool_names` 保持 `dict[str,str]`。** 只加可选 `pool_names_by_day`。后日赢不得继续当生产契约。
3. **C 默认文档降级。** 加载器今天不读 `volume`。落地必须 ≡ 缺 K（pending / 追买不 pop / 不更新 peak / 净值按缺行），同路径探测，禁止筹码读法，禁止与 D 互验。
4. **R0 单一解析：只认 `持仓标的列表:`。** 仓内 fixture。胶水不进 `scripts/research/`，改 `scripts/data/`。不是第二份导出 SSOT。
5. **R1 去掉「约 30 行」。** validate = 严格六位门；`run()` 不 SystemExit。外仓 README / 路线图 §8 移出完成定义。
6. **无名 ST 失真扩到 300/688/920。** 不当 E-R2 验收。

### 8.2 未让步

- 不重写引擎；不改卖点；不改 `presets.py`。
- R0 不写 `stock_pool/`；不喂策略 7；不用 R0 净值判断模型。
- 不在本仓实施 R2/R3/R5。
- 不为 R0 编造名称列。
- 不删 Cerebro；不复活 `engine.py`。
- **胶水可留本仓**（人裁「以本仓为主」）。反对「必须搬去 MyQuant」；同意「不是 Qlib 导出 SSOT / 不进 research 目录」。

### 8.3 条目对照

| 对抗 | 回填 |
|------|------|
| 三路：名称回退看未来 | P-R2 `ymd<=ds` + 三条单测 |
| dissent：扁平签名不可逆 | 只加 `pool_names_by_day` |
| 三路：后日赢双 SSOT | `run()` 禁 `load_pool_name_map` |
| 三路：加载器无 volume | P-R3 默认降级 |
| domain：pending/追买/peak | 落地才 ≡ 缺 K |
| dissent：R0 双源解析 | 只认列表 |
| pattern：`scripts/research/` | 改 `scripts/data/` |
| pattern：外仓完成定义 / 30 行 | P-R6 / 切片 E |
| domain：无名 ST 全板块 | §1 / P-R5 / §6 |

### 8.4 classic fan-out（v1.1 → v1.2）

| 票 | 原 ID | host |
|----|-------|------|
| codex R1 / kimi K1 | C 默认降级前提被湖实验推翻 | **吸收**：C 默认落地；加载丢 `volume==0`。主持裁复现 `000004_SZ` 458 行零量平价 |
| auto R1 / claude R2 / kimi K4 | `max{name:…}` 字典序歧义 | **吸收**：改 `last_seen` / `max ymd` |
| claude R1 / kimi K2 | P-R4 只认列表锁死日期 | **吸收**：日期取自之前最近 `日期:` 行 |
| 四方 | ≡缺 K 剔除点 | **吸收**：加载侧丢行，禁止双路径 |
| auto Y1 / claude Y1 / kimi K7 | 双通道优先级 | **吸收**：`by_day is not None` 优先 |
| claude Y2 / kimi K6 | 缺 volume 列被 `return None` | **吸收**：schema / 降级重读 |
| kimi K5 | 分钟自带 volume | **吸收**：按日合计==0 整日丢行 |
| claude Y6 | `--src` 探测未定义 | **吸收**：`OSKH_R0_POSITIONS` 或 `../MyQuant/...` |
| kimi K9 | 持仓≠新买 | **吸收**：胶水 docstring |
| codex R2 | 旧名永久 5% | **降 🟡**：§6 补双向失真；不加 N 日失效（P-R7） |

claude / auto 总评「C 降级安全」：只核了加载器不读 volume，未探湖。以实验为准，不另开一轮 classic。
