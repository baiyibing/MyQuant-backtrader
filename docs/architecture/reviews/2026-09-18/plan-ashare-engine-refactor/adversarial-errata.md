# plan-ashare-engine-refactor v1.1 — 主笔侧三路对抗评审 · 勘误表（host 裁决）

> 日期：2026-09-18
> 路线：dissent-steelman / domain-safety / pattern-evidence（按 [`docs/prompts/prompt-adversarial-subagent-review.md`](../../../../prompts/prompt-adversarial-subagent-review.md)）
> 对象：[plan v1.1](../../../backtest/plan-ashare-engine-refactor-2026-09-18.md) + [handoff 草稿](../../../backtest/handoff-ashare-engine-refactor-codex-impl-2026-09-18.md)
> 计票：**对抗草案不计独立票**（workflow）。host 已对全部 🔴 证据逐条亲验（见下）。
> 结论：**回填 plan → v1.2 后进一轮多模型 fan-out；P1–P5 人裁未动。**

---

## 三路总裁决

| 路线 | 裁决 | 要点 |
|---|---|---|
| dissent-steelman | **BLOCKING** | D1「唯一账本」名不副实；D2 `n_days` 重建口径未钉（本船唯一能改成交数字处）；D3「golden 字节级」无指涉物、无基线落盘步骤 |
| domain-safety | **BLOCKING** | S1 v7 卖/加仓侧缺昨收（limits=None）谓词放行=fail-open，plan 未钉失败方向；S2 围栏「simulate 热路径」未枚举文件集合，且 `research/engine.py` 现存 `trade_fee_policy` import，按 rglob 实现上线即红 |
| pattern-evidence | **NITS** | handoff 符号锚点全数命中；§0.3 五处文档零漂移；切片 B 改动半径未被低估；E-1 缓存合并路径整仓物化（实测 6.6–6.7GB）为 OOM 复发主向量，未进 DoD |

两票 BLOCKING 均为 **plan 文本未钉死 / DoD 不可执行** 级，非方向性推翻：回填即解，不动 R\* 硬边界、不改 P\* 建议默认。

---

## host 抽验记录（🔴 逐条亲验，file:line 可复核）

- **S1 ✅** `ashare_session.py:63-70`（previous=None → limits=None）、`:77-78`（`defer_sell_at_limit(px, None)→False`）；`csv_minute_backtest_v7.py:335` / `:395` 卖侧拿到 False 直接成交；对照买侧新名单 `:379-384` 有 `skip_no_prev_close`/`skip_unknown_board` 收口——**卖/加仓侧不对称放行**。
- **S2 ✅** `backtest/research/engine.py:21-24` import `trade_fee_policy`（`build_stamp_tax_exempt_symbol_keys` 等）；`tests/test_research_face_imports.py:110-119` 现有 AST 围栏机器 = rglob 全 `backtest/research/**/*.py`；`:122-126` 保 engine 测试态可导入。
- **D2 ✅** `csv_simulate_loop.py:176/289/293` `execute_buy(..., day_i, ...)`（entry_idx=联合日历下标，日历=全 symbol bar 日期并集）；`csv_daily_backtest.py:325` `n_days = i - pos.entry_idx` 喂 `pending_exit`/defer/止盈分层。**plan §7 落点表未列 `csv_simulate_loop.py`**。
- **D3 ✅** `csv_ledger.py:271-272` 未知 reason 前缀静默落 `sell_pos_trail`（桶污染入口）；仓库无 trades.csv 字节级 golden 入库。
- **E-1 ✅** `docs/backtest/unified-exit-modeb-minute-ready-2026-09-17.md` §3：2080 码 / 1.128 亿行，热路径峰值 **6.6GB**、冷读 6.7GB（cache 1.75GB）；`ashare_bars.py:573` 缓存命中缺码时无过滤整读缓存再合并。

---

## 勘误表（回填 v1.2）

| # | 严重度 | 来源 | 勘误 | 回填落点 |
|---|---|---|---|---|
| E-01 | 🔴 | D1 | P1=A 交付物实为「T+1/涨跌停**谓词统一** + `entry_idx` 日历映射」，非「唯一账本」：改造后 `csv_ledger.Position` 与 v7 `Lot` **双账本保留**（另有 `unified_exit_modea.Instance` 第三套持仓跟踪，住网格模块不进本船）。v7 账本分离应显式声明，且双套 fill 语义有硬分叉（csv_ledger force_min 补 100 股 `csv_ledger.py:181-191` vs v7 shares=0 直接 skip `v7:206-209`；两套费率 API） | plan §3 P1、§5-B |
| E-02 | 🔴 | D2+E-9 | 切片 B 须钉死：`entry_idx→日历日` 映射**只服务 T+1 谓词与日期打印**；`n_days` 一律仍按**联合日历下标计数**（`i - entry_idx`），禁止按个股自身有 K 日数重建——否则停牌缺口下策略书分层/止盈/`trail:T+{n}` 全变、NAV 静默漂移 | plan §5-B、handoff §2 |
| E-03 | 🔴 | D3 | 「策略书 golden 字节级」补指涉物：(a) tests 内合成 golden；(b) 宿主**改造前**短窗 trades/summary 基线**先落盘**（host 步骤，data-free CI 外）。切片 D「比 reason 桶」需先给两套词表映射：1–10 = 前缀分类计数器（未知前缀静默落 `sell_pos_trail`）vs v7 = trades 自由字符串 | plan §5-B/D、§6 |
| E-04 | 🔴 | S1 | 已知留存分叉（**本船不改、Q40+ 另裁**，R9）：v7 卖出（止损/timer）与加仓买在缺昨收（limits=None）时谓词放行=fail-open；书引擎同场景冻结拒卖（`csv_common.py:39-44` 等 continue）。切片 B 补 None-limits 卖侧合成向量**记录现状行为**，防静默漂移；改方向=改 v7 成交数字，须人裁 | plan §5-B |
| E-05 | 🔴 | S2 | 围栏「simulate 热路径」改为**枚举文件集合**（11 个，见 plan §5-C v1.2），禁 rglob 全 `research/` 目录——否则 `research/engine.py:21` 现存 `trade_fee_policy` import 上线即红或被排除后围栏失义。`research/engine.py` 与 `legacy/engine.py` 的 import 处置**另开卫生票** | plan §5-C、§7 |
| E-06 | 🟡 | S3 | 双分钟加载器六项实质差异（compact 全 `*.parquet`+无 low/volume+无盘中过滤+无去重+无 E-R4 零量日删+直读湖 vs 书格式逐项相反）：reason 计数一致**护不住价格已变**。切片 A DoD 须加 **trades 价格列**一致；六差异任一触发漂移→列允许漂移并 STOP | plan §5-A |
| E-07 | 🟡 | E-1 | OOM 复发主向量=缓存命中缺码合并路径整仓物化（实测 6.6–6.7GB）。切片 A DoD 加**内存门**：该路径不得整仓读缓存合并（缺码重算，不整读） | plan §5-A |
| E-08 | 🟡 | E-2 | 「按日切片」语义钉死：**整载 `load_minute_ohlc(start,end)` 后按日切片**；禁逐日调 loader（缓存文件按日爆炸）、禁整载物化全市场（书帧比 compact 更重：多 low 列+DatetimeIndex） | plan §5-A、handoff §1 |
| E-09 | 🟡 | D4+S4+E-5 | compact **不可直接删除**：`load_minute_ohlc` 无 source 参数，v7 `--minute-source qlib_1min` 唯一路径=compact→`qlib_bin_1min`；topk_app_dropout 经 `bars_from_pool`→compact 吃数据。降级为模块私有并保留该链（或裁 Q40+）；连带 `load_session_bars`/`bars_from_pool` 死链处置写明；§7 补 `qlib_bin_1min.py` 与 topk 行 | plan §5-A、§7 |
| E-10 | 🟡 | S5 | v7 ST 名称经 `flatten_pool_names` 取**窗末**名=非 PIT（书引擎为 as-of 单调 resolver，pool-csv-contract P-R2）。已知留存分叉，本船不动、记录在案 | plan §5-B |
| E-11 | 🟡 | S6 | P2=A「对齐口径」是**近似**：`FeeSchedule` 三浮点（buy/sell rate+min）表达不了 live 的沪市过户按码启发式、印花豁免前缀、最低过户 1 元（`trade_fee_policy.py:191-247`）。选项文本声明近似边界；接线模式可照抄 `--qlib-cost` 覆盖式（`csv_daily_backtest.py:681-683`） | plan §3 P2 |
| E-12 | ⚪ | D5+E-6 | 基线陈旧：#104/#105 均已合（tip `a61b1ad`）；plan §1「#104，待合」与头部基线 `4a3e5fe` 刷新 | plan 头部、§1 |
| E-13 | ⚪ | E-3 | 1–10 分钟加载经**别名**：`load_minute_bars = load_minute_ohlc`（`ashare_bars.py:591`），调用点 `csv_minute_backtest.py:800`。锚点表加注，防 Codex 按字面搜落空 | handoff §0 |
| E-14 | ⚪ | E-4 | v7 涨跌停/T+1 **已经**在调 `ashare_session`（#104 后既成，`v7:23-51` import）；切片 B 对 v7 一半是防回归指令，非新迁移 | plan §1 |
| E-15 | ⚪ | S7 | `minute_cache_path` 仅按 `(start,end)` 键、无新鲜度守卫（`ashare_bars.py:397-399`）：切片 A 把 v7 也挂上此风险，记录在案 | plan §5-A |
| E-16 | ⚪ | host | plan §7 落点表缺 `csv_simulate_loop.py` / `csv_common.py` / `csv_strategy_books.py`——`entry_idx` 赋值与 `n_days` 消费的真正所在地 | plan §7 |

---

## 核实为属实（无需动作）

- **文档同构零漂移**：positioning §3.2–§3.3（parity 免责 / 验收唯一入口）、README SSOT 行 + 1.3 段、AGENTS 引擎定位、correctness E-R1–E-R6、pool 契约「文件名=买入日 T」五处与 plan §0.3/R4 一致（E-7）。
- **Mode B 边界**：`shares/=k` 仅 `unified_exit_modeb.py:418/648/801`；`csv_ledger.rescale_position`（`csv_ledger.py:141-150`）只动 cost/peak，shares untouched（E-8）。
- **handoff 符号锚点全数命中**（session/bars/fees 行号精确；ledger/v7 ±1 内）（E-9）。
- **T+1 下标语义与日历语义现状同构**（entry_idx 恒为 fill 日下标、日历严格排序，`i>entry_idx ⟺ buy_date<session`）——三路独立一致（D2 反面结论 + S1 + E-9）。风险不在 T+1 本体，在 n_days（E-02）与 None-limits（E-04）。
- **停牌缺 bar = 全引擎冻仓拒卖**（不卖不 defer，pending 留存），fail-closed ✓（S8，符合 E-R4）。

---

## 对 §3 P1–P5 的路线立场（不投票，供人裁参考）

| 点 | dissent-steelman | domain-safety | pattern-evidence |
|---|---|---|---|
| P1=A | 反对（按 v1.1 文案；按 E-01 改述后可支持） | 支持（须连 E-04 一起钉） | 支持（改动半径与估计相符） |
| P2=A | 支持 | 支持（附 E-11 近似边界） | 支持 |
| P3=C | 支持 | 支持 | 支持 |
| P4=A | 支持 | 支持 | 支持 |
| P5=A | abstain（薄包装无可判边界） | 支持 | abstain（HELP_LOCK 文案未细审） |

---

## 下一步

1. plan 回填 **v1.2**（本表 E-01..E-16；P\* 选项只改描述与边界声明，不改建议默认）。
2. 对 v1.2 跑**一轮**多模型 fan-out（`scripts/run/run_multi_ai_review.py`）；有新 🔴 改 plan 再开一轮，无则止——不重复扫同一文本。
3. **人裁 P1–P5** → plan 头部改 ✅ 已人裁 GO（hash）→ 才可开 `feat/ashare-engine-refactor` 交 Codex。合 docs PR ≠ 实施 GO。
