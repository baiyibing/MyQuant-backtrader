# MyQuant-backtrader 全面分析与下一步（local Opus 5 真跑 · tip `ad0c4ba`）

- **日期**：2026-09-15
- **状态**：**docs-only**。未改任何业务代码、未跑 F 湖回测、未跑 CloudAgent。落盘编辑：修正同目录相对链接；补全 §10 commit 清单；对 R11「零入链」措辞按 living vs 历史评审区分；**未发明性能数字**。
- **执行者鉴权与出处**：本机 `/home/box/.local/bin/cursor-agent -p` + `--model claude-opus-5-thinking-high`；已用 **User API Key（`CURSOR_API_KEY`）**，调用前 **已 `unset CURSOR_AUTH_TOKEN`**（Origin-scoped token 会让 Agent 端点返回 `permission_denied`）。**这是 local Opus 5 真跑，不是 CloudAgent，也不是先前鉴权失败后的替补稿**（先前替补稿见 §Appendix「稿系」）。
- **分析 tip**：工作树 `HEAD = ad0c4ba`（`docs/opus5-repo-analysis-next` 分支；parent1 = `36b7ffc` 先前替补稿 commit，parent2 = `origin/master = e06e1a9`）。相对先前稿的 `8793fd5`：master 已前进到 `e06e1a9`（本分支 ahead 5 = 4 个 master commit + 1 个 merge commit）。
- **SHA 取证方式（须知）**：Opus 本跑 shell 被环境策略拦截，未能执行 `git log`；SHA 读自 `.git` refs。落盘时由执行助手补全 `8793fd5..e06e1a9` 四条 commit（见 §10），并核对了行号 / gate 数 / R0/R1 双份文档。**分析对象 tip 仍为 `ad0c4ba`（= `36b7ffc` ⊕ `e06e1a9`）**；本文件落盘 commit 会更新 HEAD，但不改变分析基线。
- **Parents（本次实际 Read）**：[brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md) · [plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md) · [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md) · [repo-analysis-vs-brainstorm-2026-09-15.md](repo-analysis-vs-brainstorm-2026-09-15.md)（#52） · [repo-analysis-opus5-next-2026-09-15.md](repo-analysis-opus5-next-2026-09-15.md)（`8793fd5` 替补稿，WP1–WP5） · [minute-simulate-profile-results-2026-09-15.md](minute-simulate-profile-results-2026-09-15.md)（#54） · [plan-pool-pipeline-r0r1-2026-09-12.md](plan-pool-pipeline-r0r1-2026-09-12.md) · [engine-positioning-ssot.md](engine-positioning-ssot.md) · [pool-csv-contract.md](pool-csv-contract.md) · [chip/h14-d1-minute-chip-profile-results-2026-09-15.md](chip/h14-d1-minute-chip-profile-results-2026-09-15.md)

**G 禁区（继承，本文不挑战）**：改 6/8 卖点；重开 `--asof`；PortAna 定胜负；缺行 fail-closed→跳过；日线↔分钟卖环 big-bang 合并；物理删除 Cerebro；本仓复刻 MyQuant CYQ feeder；本仓复刻 LEBS / 真栈；CloudAgent 作为交付路径。

---

## 1. 现状一句话

软卫生 H1–H16 与 #51–#56 都已收口，本轮合入 master 的 `plan-pool-pipeline-r0r1` **其实是一份早已实现（PR #21）的旧计划**——树里 `validate_pool_dir` / `load_pool_names_by_day` / 加载侧丢 `volume==0` / `scripts/data/r0_positions_to_pool.py` 全部在位，所以它 **不构成新工作面**，只留下一个「root 与 `_archive/plans/` 双份、且 root 那份无人索引」的文档重复；真正还值得动的仍然只有 #54 那条证据（真实 `simulate()` 下卖环 ~75% 且现有 numba trail 进不去）。

---

## 2. 架构地图

### 2.1 向量化研究脸（真实路径，本跑逐个核对存在）

| 角色 | 路径 | 核对要点 |
|------|------|----------|
| 日线引擎 | `backtest/research/csv_daily_backtest.py` | `simulate` 收 `pool_names_by_day`（L301/L330）；`run` L492 调 `load_pool_names_by_day` |
| 分钟引擎 | `backtest/research/csv_minute_backtest.py` | `scan_held_day` 分派器 L603–644；`run` L991 同走 by_day |
| 策略 7 | `backtest/research/csv_minute_backtest_v7.py` | 独立仓位机，不在策略书 choices |
| 共用买/追/mark 骨架 | `backtest/research/csv_simulate_loop.py` | docstring 明写「Sell loops stay in each engine on purpose」 |
| 共用 CLI / 策略书 | `backtest/research/csv_strategy_books.py` | H2 `add_csv_backtest_common_args` |
| 成交核 / 账本 | `backtest/research/csv_ledger.py` | 档位 / defer / mark |
| 名单解析 | `backtest/research/csv_pool.py` | `parse_pool_csv` L71 · `validate_pool_dir` L88 · `load_pool_name_map` L133 · **`load_pool_names_by_day` L161** · `load_pool_day_map` L185 |
| 名单质量库 | `backtest/research/pool_list_quality.py` | H9/H16：`day_over_day_churn` L162 · `invalid_calendar_stems` L74 · `top_frequent_codes` L144 · JSON/md 双格式 L406/L410 |
| 源 B / TR 名单 | `backtest/research/source_b_tr_pool.py` | `assert_section_asof` L51 · `scan_tr_days` L94 · `write_tr_pool` L136 |

本仓 **无** `backtest/lebs/`（与 [engine-positioning-ssot.md](engine-positioning-ssot.md) 一致）。

### 2.2 simulate 骨架（#54 的实测对象）

```
simulate()
  ├─ prepare_strategy_hooks / init_sim_state        ← csv_simulate_loop.py
  ├─ per day:
  │    ├─ SELL（引擎本地，有意分家）
  │    │    daily : day_bar_and_prev_closes + 书规则 + _sell
  │    │    minute: scan_held_day(+可选 numba trail) + _sell + 跌停 defer
  │    ├─ run_chase_due_day(quotes_for=…)           ← 共用
  │    ├─ run_pool_buys_day(buy_quote_for=…)        ← 共用
  │    └─ append_equity_and_eod_marks(…)            ← 共用（H5 per-code mark 缓存）
  └─ summarize / write_run_artifacts
```

### 2.3 名单管道（R0/R1 已实现，本轮新增的只是文档）

本跑在树里确认 P-R2/P-R3/P-R4/P-R6 四条锁 **都已落地**：

| plan 锁 | 落地证据 |
|---------|----------|
| P-R2 名称 as-of（`ymd<=ds`，禁后日赢） | `csv_pool.load_pool_names_by_day` L161；日线 L492 / 分钟 L991 的 `run()` 都走 by_day；共用侧 `csv_common._pool_names_asof`（被 `csv_simulate_loop` import）；契约 [pool-csv-contract.md](pool-csv-contract.md) L10 写明 `name_asof(code, ds)` |
| P-R3 加载侧丢 `volume==0` | 日线 `csv_daily_backtest.py` L225–252（读 schema 判 `has_volume`，`out.loc[out["_volume"] != 0]`）；分钟 L165–207（**按日 `volume` 合计 ==0 整日丢行**，`groupby("ymd").transform("sum")`），与 P-R3「分钟按日合计」一致 |
| P-R4 R0 胶水在 `scripts/data/` | `scripts/data/r0_positions_to_pool.py` 存在；fixture `tests/fixtures/r0_position_analysis.txt` 存在；未落 `scripts/research/` |
| P-R6 契约补 as-of + 方言链 + 严格门 | `pool-csv-contract.md` L10（as-of 谓词）、L19（`SZ300190 → 300190 → 300190_SZ → 300190.SZ` 方言链）；`validate_pool_dir` L88 |

索引侧结论：`docs/backtest/README.md` L90 与 `docs/backtest/_archive/plans/README.md` L10 都写 **「R0/R1 已合 #21」并只链 `_archive/plans/` 那份**。

### 2.4 筹码 / TR 边界（H11–H15，不变）

| 桶 | 权威路径 | 状态 |
|----|----------|------|
| 生产 TR | `turnover-resist/`（Rust）→ `oskh_factors/bridge` → Store → 策略 10 / `tr_filter` / `export_ta_pool` | leave |
| 分钟筹码分布 | `oskh_factors/chip/core.py`：`minute_chip_distribution_python` L146 + `minute_chip_distribution` L228 | H15 可选 numba；**Python 仍默认** |
| hybrid / `calc_curpdf` | `hybrid_chip_distribution` / `qlib_cost/cyq.py` | later / leave |
| 全市场日频赢筹 CYQ | **sibling MyQuant** `build_winner_ratio.py`（numba） | **禁止本仓复刻**（H13 / G） |

### 2.5 CI（data-free；两条 workflow 均已核）

`.github/workflows/python-tests.yml`：Contract gates（**pip 之前**跑 `verify_oskh_data_contract.py` / `verify_data_path_ssot.py` / `verify_no_hardcoded_machine_paths.py` / `verify_tr_bridge_import_ssot.py`，L39–43）→ `pip install -r requirements.txt` → `python -c "import numba"` 断言（L52–53，H6 防 parity 静默 skip）→ `pytest -q -m "not production and not benchmark"`。workflow L35–37 有显式注释「**不要**把湖门禁加进来」。

`.github/workflows/turnover-resist-rust.yml`：路径触发 `turnover-resist/**`；`runs-on: ubuntu-latest`（注释说明 windows MSVC 14.51 下 duckdb bundled 编不过）；`RUSTC_WRAPPER: ""` 关掉本地 sccache；`cargo fmt --check` + `clippy --all-targets --all-features -D warnings` + `cargo test --all-targets`。

**门禁数量事实**：`scripts/gates/` 共 **13** 个 `verify_*`，CI 只跑 **4** 个 → **9 个为宿主 only**（`verify_turnover_resistance_alignment` / `verify_single_stock_turnover_resist` / `verify_chip_pool_enhancement` / `verify_chip_factor_consistency` / `verify_minute_chip` / `verify_adj_minute_chip` / `verify_float_shares_time_dimension_baseline` / `verify_mvp_min` / `verify_l2_manifest`），**这 9 个目前没有任何一处成文清单**（`docs/backtest/README.md` L57 只说「chip / TR / L2 等需湖门禁不进 CI」，未列名、未给跑法）。→ 这是 WP2 的实证缺口。

---

## 3. 主题 A–F 记分板

列「相对 #52」= `dd35fe9` 时代那份；列「相对 `8793fd5` 稿」= 先前 WP1–WP5 替补稿；列「本 tip 新增」= `8793fd5 → e06e1a9` 合入 + 本跑新查证。

| 主题 | 相对 #52 | 相对 `8793fd5` 稿 | 本 tip（`ad0c4ba`）新增 / 修正 | 残余 |
|------|----------|-------------------|--------------------------------|------|
| **A 性能** | H5 mark 缓存 · H8 `searchsorted` · #34 numba trail | #54 实测：卖环 ~75%，numba trail 被拒 | **代码级复核通过**（见 §5，行号已钉） | 编排级缓存 / 受限 compiled scan（WP1） |
| **B 入口 / 书** | H2 共用 argparse；两套卖引擎分家 | 无行为变更 | 无变更；`csv_simulate_loop` docstring 仍显式声明分家 | 继续分家（G） |
| **C 名单** | H7 生命周期 · H9/H16 list-quality | #53 `--other-dir` 双侧严格校验 | **新查证：R0/R1（PR #21）已实现**，本轮合入的是旧 plan 文档；并发现 **root 副本无人索引**（§7 R11） | golden fixture（WP3）；run-manifest 仍延期 |
| **D 筹码 / TR** | H11–H15 | 无新算法 | 无变更；D1 数字本跑第一手复读（§5.2） | hybrid/curpdf leave（WP4） |
| **E CI** | H6/H10/H12 | #55 TR alignment 双指标才 exit 0 · #56 presets 跨仓钉桩 | **新量化：13 gates 中 9 个宿主 only 且无清单**；Rust workflow 已核 | 宿主湖门禁 cookbook（WP2） |
| **F 工程脸** | H1/H3/H4 · #51/#52 索引 | 文档索引刷新 | **发现文档重复**：`plan-pool-pipeline-r0r1` root + `_archive/plans/` 双份 | de-dup（并入 WP4） |

**新合入的 pool-pipeline R0/R1 归属判定**：属主题 C，**但状态是「已交付、文档回潮」**，不是「新增待办」。理由见 §2.3 与 §8。

---

## 4. 热路径证据校验（只用已落盘数字）

### 4.1 #54：真实分钟 `simulate()`（唯一可用的编排级证据）

来源 [minute-simulate-profile-results-2026-09-15.md](minute-simulate-profile-results-2026-09-15.md)。场景：version8、30 交易日 × 16 码 × 240 分钟 bar、10 天有 pool buy（10 lots/码）、warm-up 后测 3 次；host `/workspace/vanna312/bin/python`；**合成、无 F 湖**。两跑收尾一致（160 live lots / 160 buys / 320 records 含 EOD mark）。

| 阶段 | 默认请求 | `CSV_SCAN_HELD_DAY_BACKEND=numba` 请求 |
|------|---------:|---------------------------------------:|
| `simulate()` / run | **1,218.48 ms** | **1,230.32 ms** |
| sell scan | **75.51 %** | 75.25 % |
| chase | 0.01 % | 0.01 % |
| pool buy | 4.99 % | 4.83 % |
| ledger / mark | 0.88 % | 0.89 % |
| orchestration remainder | 18.61 % | 19.02 % |
| nested day slice | 1.17 % | 1.22 % |
| nested previous-close prep | 4.76 % | 5.03 % |

nested 两行已含在 sell/chase/pool 里，**不得**与顶层百分比相加。设 numba 后没有加速（1,230 > 1,218，落在噪声内）。

### 4.2 #54 的「进不去」结论——本跑代码级复核通过

profile 文的解释（dispatcher 拒收 numba trail）在源码里逐条对上了：

```603:644:backtest/research/csv_minute_backtest.py
def scan_held_day(
    ...
    take_profit=None,
    ...
    reserve_state: Optional[dict] = None,
    ...
    is gated by ``use_numba=True`` or env ``CSV_SCAN_HELD_DAY_BACKEND=numba``.
    Callables (sell_gate / take_profit) and reserve_limit_up always use Python.
        and _NUMBA_SCAN_AVAILABLE
        and take_profit is None
        and reserve_state is None
```

而 `simulate()` 对每一手都造出非 `None` 的 `reserve_state`：

```851:881:backtest/research/csv_minute_backtest.py
                reserve_state = {"reserved": bool(pos.reserved)}
                ...
                    take_profit=take_profit,
                    ...
                    reserve_state=reserve_state,
                ...
                pos.reserved = bool(reserve_state["reserved"])
```

**结论（可引用）**：现有可选 numba trail 在真实 `simulate()` 编排下 **结构性不可达**——不是调参问题；version8 还额外提供 `take_profit` callable（L529/L591 是 Python 参考实现里的对应分支）。`scripts/research/bench_scan_held_day.py` 的独立加速比 **不能**代表真实编排。这一条推翻任何「设个环境变量就快了」的期待。

### 4.3 与 H14/D1 的关系（本跑第一手复读，未借 #52 转述）

来源 [chip/h14-d1-minute-chip-profile-results-2026-09-15.md](chip/h14-d1-minute-chip-profile-results-2026-09-15.md)（80 日 × 240 分钟，`step=0.01`，合成无湖）：

| Rank | Kernel | ms/call |
|------|--------|--------:|
| 1 | `minute_chip_distribution` | ~50.7 |
| 2 | `hybrid_chip_distribution` | ~1.01 |
| 3 | `calc_curpdf` × N | ~0.69 |
| 4 | `calc_cumpdf`（已 jit） | ~0.021 |

**正交性提醒**：分钟筹码直方图 offload（D2/H15）与分钟卖环 offload（主题 A）是两条路径，D2 的成功 **不是**卖环 offload 的许可证。H15 的「~58×」出自 `docs/architecture/reviews/2026-09-15/h15-d2-minute-chip-numba/grok.md`，本跑 **未重读该评审文**，故此处只标出处、不当本文证据。

### 4.4 明确「未实测」项

- 真实 F 湖窗口下的分钟 / 日线端到端耗时：**未实测**（CI 无湖，本跑无湖）。
- WP1 候选 1（prev-close / close-history 按 code/day 缓存）的收益上界：**未实测**；仅知 `nested previous-close prep` 在 #54 场景占 ~4.76%–5.03%，是「候选的量级参考」，不是预期加速比。
- 受限 compiled scan 的可行加速：**未实测**（尚无原型）。
- H5 / H8 的端到端日线净收益：**未实测**（#52 §3.1 已注明 H8 不主张 end-to-end）。

---

## 5. 跨仓边界（不变）

```
MyQuant                      MyQuant-backtrader（本仓）        OSkhQuant1.3
train / IC / 导出日 CSV      向量化 CSV 研究脸                 LEBS（MockQMT 撮合）
numba 全市场 CYQ feeder      Rust turnover-resist → Store      MockQMT 真栈（验收唯一入口）
run-manifest 写端            oskh_factors.chip（可选 numba）   trade_decision + capital
（PortAna 停用）             消费湖只读；Cerebro 观察退役      下载 / vendor 合并
```

硬篱笆：① 不复刻 `build_winner_ratio.py` / 全市场日频 CYQ；② 不克隆 LEBS / Redis / executor / live 包；③ 向量化 NAV ≠ Paper ≠ PortAna（三套对不上是预期，能比的是名单 / reason / 可卖股 / 涨跌停）；④ 6/8 卖点本仓锁死，presets 与 1.3 由 `tests/test_presets_cross_repo_snapshot.py` 钉；⑤ run-manifest **消费**默认延期。

---

## 6. 风险登记

沿用 #52 的 R1–R10 编号，本跑刷新状态并新增 R11–R12。

| ID | 风险 | 状态 / 缓解 |
|----|------|-------------|
| R1 | big-bang 合并日/分钟卖环带动 6/8 漂移 | 继续分家；`csv_simulate_loop` docstring 已成文；只许 golden+parity 微优化 |
| R2 | 误以为 `CSV_SCAN_HELD_DAY_BACKEND=numba` 已加速真实 simulate | **本跑已代码级证伪**（§4.2，L640–644 / L851）；WP1 前必读 profile 文 |
| R3 | 复刻 MyQuant CYQ feeder | H13 + inventory §E + CONTRIBUTING + AGENTS |
| R4 | 湖门禁被塞进 GitHub Actions | workflow L35–37 注释在位；**但 9 个宿主门禁仍无清单** → WP2 |
| R5 | 无产品点头硬接 run-manifest | 保持延期；H16 + R0/R1 已覆盖本地名单卫生 |
| R6 | Agent CLI 鉴权误当交付路径 | **本跑已解**：`CURSOR_API_KEY` + `unset CURSOR_AUTH_TOKEN` 可用 local Opus 5；交付仍走本机改 + Grok 核 + Actions |
| R7 | `stock_pool/`（可变）与 `exports/`（冻结）混用 | H7 SSOT；9/10 拒 `stock_pool/`；`is_repo_stock_pool` L76 在位 |
| R8 | 把合成 × 倍数当生产 SLA | 三份 profile 文都自写「research evidence, not SLA」；本文全部标场景 |
| R9 | 缺行 fail-closed→跳过（策略翻转） | G 禁区；P-R3 落地后零量占位日走 **既有缺行路径**（不评卖 / 追买不 pop / 不更新 peak / 净值走 `last_close_mark`） |
| R10 | 名称 as-of 断档失真 | 已知且成文（plan §6 双向失真：摘帽后旧 `*ST` → 5% 偏窄；断档无名 → 偏宽）。比「后日赢」安全；本轮不建 ST 履历库 |
| **R11**（新） | **文档双 SSOT**：`docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md`（root）与 `_archive/plans/` 同名文件并存，两 README 只链 `_archive/` 那份，living SSOT（`docs/backtest/README.md` / `_archive/plans/README.md`）**不链 root 副本**（历史 `docs/architecture/reviews/2026-09-12/...` 仍指向旧 root 路径）且缺 `_archive/` 版的「后续 → R2/R5」指针、相对链接也是旧的扁平写法。它是 32 个 `docs/backtest/*.md` 里 **唯一** 与 `_archive/plans/` 撞名的 plan | 低风险但会误导新人「R0/R1 还没做」（实际 PR #21 已合）→ 并入 WP4 一刀收 |
| **R12**（新） | **门禁脚本三处同名副本**：`verify_minute_chip` / `verify_chip_factor_consistency` / `verify_adj_minute_chip` / `verify_chip_pool_enhancement` / `verify_float_shares_time_dimension_baseline` / `verify_mvp_min` / `verify_single_stock_turnover_resist` / `verify_turnover_resistance_alignment` 在 `scripts/gates/`、`scripts/research/`、`backtest/research/` 之间同名存在，且非 shim（是整份拷贝）；`scripts/gates/verify_minute_chip.py` docstring 用法仍写 `python backtest/verify_minute_chip.py`（**过期路径**） | 与 #52 记的 `full_market_*_resist` 同类气味。WP2 顺手钉「哪份是权威、用法怎么写」，**不做**物理合并（改脚本布局非 docs-only 范围） |

---

## 7. 下一步改进方案 WP1–WP5

**编号说明**：保持与 `8793fd5` 稿 WP1–WP5 **完全连贯**，不改编号。唯一变动是 **WP4 扩容**（从「inventory later 再钉」扩为「docs SSOT 收口：inventory later + R0/R1 重复副本 de-dup」），理由：新合入的 `plan-pool-pipeline-r0r1` 在实现层已完成（PR #21，§2.3 四条锁均有代码证据），**没有任何实现工作可插**，只剩一个纯 docs 的重复项；为它单开 WP6 会把「一次 docs PR 能收的事」拆成两包，且会让「R0/R1 是新工作面」的误读固化。

**默认立场（不变）**：停止扩张 Hx 软卫生面；优先吃 #54 证据，否则做低风险 docs/fixture；**run-manifest hard 仍延期**（仍需产品点头）。

### WP1 — 主题 A：分钟 `simulate` 编排微优化（若痛点是分钟研究窗，则为下一刀）

| | |
|--|--|
| **意图** | 不碰卖点语义，落地 #54 两个候选之一或之二：(1) 按 `code/day` 缓存 prev-close 与 close-history，跨 lots 与 sell/chase/pool 报价路径复用；(2) **仅**对显式支持的内置书合同（含 reserve / take-profit 行为）做 **可选** compiled scan 原型，默认仍 Python，parity 锁死 |
| **为何现在** | sell scan 在真实编排占 **75.51%**；现有 numba trail 因 `reserve_state`/`take_profit` **结构性不可达**（§4.2 已钉行号），所以「便宜的那条路」已经证伪 |
| **明确不做** | 合并日线↔分钟卖环；改 6/8 理由码 / trail / gate；改默认后端；F 湖 NAV 验收；把 `reserve_state` 从 `simulate()` 里摘掉以「骗过」分派器 |
| **验收** | 新/扩 plan + `bench_minute_simulate_hotpath.py` 前后对比（同场景同 reps）；Python↔numba parity 绿；golden 分钟测试绿；Python 仍默认；Grok 核无有效 🔴 |
| **体量** | 中（软代码 + 文档）。建议先只做候选 (1) 单独一刀，候选 (2) 另评 |

### WP2 — 主题 E：host-only 湖门禁 cookbook（无性能痛点时的默认安全刀）

| | |
|--|--|
| **意图** | 一页清单：`scripts/gates/` 13 个 gate 里 **哪 4 个在 CI**、**哪 9 个宿主 only**、各自跑法（需要哪个湖 / 哪个 resolver / 期望 exit code）、以及为何不进 CI；顺带钉 R12 的「同名多副本谁是权威」与修 `verify_minute_chip.py` 的过期用法串 |
| **为何现在** | 本跑量化了缺口：README L57 只有一句「不进 CI」，9 个宿主门禁 **无处可查**；#55 之后 TR alignment 的「双指标才 exit 0」语义也值得写进跑法 |
| **明确不做** | 把湖门禁接进 `python-tests.yml`；物理移动/合并门禁脚本 |
| **验收** | 新人 ≤30s 找到宿主门禁清单；CI workflow 精神不变（注释块不动）；docs-only |
| **体量** | 小（docs；`verify_minute_chip.py` docstring 一行属最小例外，可选） |

### WP3 — 主题 C：list-quality golden fixture（软，**仍非** run-manifest）

| | |
|--|--|
| **意图** | 检入微型合成池目录 + pytest，锁住 H16 报表（day-over-day churn / invalid calendar stems / top-N / 空日 / #53 `--other-dir` 双侧严格校验），让回归在 data-free CI 里可见 |
| **本跑核实的缺口** | `tests/fixtures/` 现有 6 项（presets baseline、`csv_engine_pre_er1/` 三件、`r0_position_analysis.txt`），**没有** pool 目录 fixture → 该包仍成立 |
| **明确不做** | 消费 `myquant.run-manifest/1`；改 `simulate` / 卖环；改 `validate_pool_dir` 严格度（`run()` 有意不 SystemExit，见 P-R6） |
| **验收** | data-free CI 绿；`pool-csv-contract.md` 一行指针 |
| **体量** | 小–中 |

### WP4 — docs SSOT 收口：inventory「later」再钉 + R0/R1 重复副本 de-dup（**本轮扩容**）

| | |
|--|--|
| **意图（原）** | H15 之后显式写清 hybrid / `calc_curpdf` **leave until 产品吞吐需要**，附「何时重开」判据（可引 D1 的 ~1.01 ms / ~0.69 ms / ~0.021 ms） |
| **意图（新增）** | 收掉 R11：`docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md`（root）与 `_archive/plans/` 同名文件二选一——建议 **删 root 副本**（两 README 已只链 `_archive/`），或退一步把 root 改成一行指针；并在归档 README 补一句「R0/R1 的 P-R2/P-R3/P-R4/P-R6 已实现，代码落点见 `csv_pool.load_pool_names_by_day` / 日线 L225–252 · 分钟 L165–207 / `scripts/data/r0_positions_to_pool.py`」，防止再有人把它当待办 |
| **为何合并而非新开 WP6** | 两件都是纯 docs、同一份 PR 能收、且都属「把 later/已完成状态写清楚」这一件事；单开 WP6 会误示「R0/R1 是新工作面」 |
| **明确不做** | 新 numba / Rust 内核；迁 MyQuant feeder；改 `docs/architecture/reviews/**` 历史评审原文（考古，plan §2 禁改） |
| **验收** | 单个 docs PR；`rg plan-pool-pipeline-r0r1` 后无死链；无算法 / 无行为变更 |
| **体量** | 极小 |

### WP5 — 产品门：run-manifest hard（**仅点头后**）

| | |
|--|--|
| **意图** | 本仓消费 MyQuant `myquant.run-manifest/1`（训练 / 导出溯源） |
| **为何仍排后** | H16 + R0/R1 已覆盖本地名单卫生与名称 as-of；硬接跨仓契约无点头易脆；`engine-positioning-ssot.md` §5 也仍写「本仓暂不接」 |
| **明确不做** | 偷偷当默认必经路径；用 PortAna / NAV 当合入门 |
| **验收** | 另开任务书；schema 对齐 MyQuant `docs/run-manifest-spec.md`；fixture + 可选宿主烟测 |
| **体量** | 重（跨仓） |

---

## 8. 建议决策

**关于「pool-pipeline R0/R1 是否插新 WP」的回答**：**不插新 WP，不并入实现型 WP**。它在实现上已于 PR #21 落地（四条锁均有本跑核对的代码证据），本轮合入 master 的只是计划文档；剩余动作是 **一个纯 docs de-dup**，已并入 **WP4**。**run-manifest 仍延期**，本轮没有任何新证据支持提前（相反，R0/R1 已实现进一步削弱了「必须现在硬接」的理由）。

排序建议：

1. **想立刻有产出、且不想动代码** → **WP4**。它现在有一条本跑新查出的、可验证的具体缺陷（R11：唯一撞名 plan + 零入链），是全场最便宜的一刀。
2. **想补最实用的工程面** → **WP2**。缺口已量化（13 gates / 4 在 CI / 9 无清单），顺带清 R12 的过期用法串。
3. **分钟研究窗真的慢** → **WP1**，并且只从候选 (1)（prev-close / close-history 缓存）开始，单独一刀、单独 bench；候选 (2) 的 compiled scan 先出原型评估再决定是否成片。**不要**为了让 numba trail 生效而改 `simulate()` 传 `reserve_state` 的方式（那等于绕 6/8 语义锁）。
4. **想让 CI 看得见名单质量回归** → **WP3**。
5. **run-manifest** → 等明确点头再开 **WP5**；默认继续 defer。

**若你此刻没有性能痛点**：建议 **WP4 → WP2** 连做一个 docs PR 组，然后停在 master，别再开 offload 大片。这与 #52 / `8793fd5` 稿的默认立场一致。

---

## 9. Appendix A — 稿系（避免混淆三份自分析）

| 稿 | tip | 出处性质 |
|----|-----|----------|
| [repo-analysis-vs-brainstorm-2026-09-15.md](repo-analysis-vs-brainstorm-2026-09-15.md) | 分支切点 ≈ `dd35fe9`（#51 时代），PR #52 | 本机 backtrader 助手（Grok Bot executor）；**Opus Agent CLI 鉴权失败** |
| [repo-analysis-opus5-next-2026-09-15.md](repo-analysis-opus5-next-2026-09-15.md) | `8793fd5`（#56 merge） | **鉴权失败后的替补稿**，文首自述「不是 CloudAgent」；首次给出 WP1–WP5 |
| **本文** | `ad0c4ba`（= `36b7ffc` ⊕ `origin/master e06e1a9`） | **local Opus 5（`claude-opus-5-thinking-high`）真跑**，`CURSOR_API_KEY` 修复鉴权后；非 CloudAgent、非替补稿 |

## 10. Appendix B — #51–#56 与 master 后续速查

| PR | 作用 |
|----|------|
| [#51](https://github.com/baiyibing/MyQuant-backtrader/pull/51) | brainstorm overview A–F 索引 |
| [#52](https://github.com/baiyibing/MyQuant-backtrader/pull/52) | 旧 tip 自分析（WP1–WP5 的前身：WP1 分钟卖环 profile / WP2 inventory triage / WP3 host gate cookbook / WP4 golden fixture / WP5 fossil smoke） |
| [#53](https://github.com/baiyibing/MyQuant-backtrader/pull/53) | list-quality `--other-dir` 两侧都严格 `validate_pool_dir` |
| [#54](https://github.com/baiyibing/MyQuant-backtrader/pull/54) | 分钟 `simulate` 热路径 profile（本文 §4 与 WP1 的唯一编排级证据） |
| [#55](https://github.com/baiyibing/MyQuant-backtrader/pull/55) | TR alignment 两指标都过才 exit 0 |
| [#56](https://github.com/baiyibing/MyQuant-backtrader/pull/56) | presets 跨仓 baseline 钉进 CI（`tests/fixtures/presets_cross_repo_baseline.json`） |
| — | **`8793fd5 → e06e1a9`（4 commits，落盘时补全）**：`1e86014` docs: lock pool pipeline R0/R1 plan after multi-agent review；`7dd0fd3` docs: 锁定名单源 B 计划（TR 过滤写出契约日 CSV）；`b67772a` Merge branch `docs/plan-pool-pipeline-r0r1`（root 回潮 `plan-pool-pipeline-r0r1`，对应 R11）；`e06e1a9` Merge `docs/plan-source-b-ta-pool`：已被 #32 取代，保留归档更新副本 |

历史 PR：#34–#50（H1–H16）见 [brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md)；H1–H16 → 主题索引见 [repo-analysis-vs-brainstorm-2026-09-15.md](repo-analysis-vs-brainstorm-2026-09-15.md) Appendix；R0/R1 的 P-R\* 锁见 [_archive/plans/plan-pool-pipeline-r0r1-2026-09-12.md](_archive/plans/plan-pool-pipeline-r0r1-2026-09-12.md)（**权威副本**）。

