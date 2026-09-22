# backtest/ 回测专题

本仓研究入口是**向量化**，不是 LEBS，也不是 Cerebro。

**研究问题总入口**（三份主名单 × 人工改书 / 机器网格 / 分数轮换；策略 1–12、Mode A/B、TopK 怎么挂）：**[research-backtest-entry.md](research-backtest-entry.md)**。下面是命令与 SSOT 表。

三件成交引擎（本仓向量化 / 1.3 LEBS / 1.3 MockQMT）怎么分工：见 **[engine-positioning-ssot.md](engine-positioning-ssot.md)**。Qlib `PortAnaRecord` 停用；Cerebro / Rolling 已退场（2026-09-16）。本仓没有 `backtest/lebs/`。

## 本仓研究入口（向量化）

除权参考价 SSOT：[engine-ashare-correctness §2.1](engine-ashare-correctness.md#21-p3-δ2-除权参考价契约human-go-aaaaa)；[P3 δ2 plan / data-free 验收 §8](plan-industry-align-p3-d2-exdiv-2026-09-19.md)。Human GO A/A/A/A/A 仅收口契约与 pins，送转不增股、现金红利不入账、NAV 经济残留继续 deferred。

ST 名称时间合同：[engine-ashare-correctness §2.2](engine-ashare-correctness.md#22-p3-δ3-st-name-as-of--v7-flatten-forkhuman-go-aaa)；[P3 δ3 plan / data-free pins 与冻结证明](plan-industry-align-p3-d3-st-pit-2026-09-19.md)。Human GO A/A/A 保留书侧日期 as-of / v7 窗口末名平铺分叉，生产不变；决策时刻可得性 PIT 仍未证。

`limits=None` 合同：[engine-ashare-correctness §2.3](engine-ashare-correctness.md#23-p3-δ4-v7-limitsnone-contracthuman-go-cba)；[P3 δ4 plan / data-free pins 与冻结证明](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md)。Human GO **C/B/A 的 production fail-closed 已落地**：v7 held stop/add/timer 无有效档位均拒绝交易尝试，复用无昨收/未知板块 skip reason；首开与书侧拒绝保持。peak/mark/参考价缩放仍可更新，无 policy 开关；δ5 production cap 见下；δ6 production economics 见下。

成交量参与率生产合同：[engine-ashare-correctness §2.4](engine-ashare-correctness.md#24-p3-δ5-volume-participation-cap-productionhuman-go-caaa)；[P3 δ5 plan / 生产验收与冻结证明](plan-industry-align-p3-d5-volume-cap-2026-09-19.md)。Human GO **C/A/A/A production volume-cap 已落地**：分钟书 `simulate` / `simulate_v7` 显式传 `participation_rate` 与带单位/`available_at` 的桶容量即可启用；默认 None 保持基线。共享买卖预算、partial与不可用拒绝已有生产测试；same-bar整桶为完成bar容量近似，开盘不借未来/EOD量。日线容量、loader/CLI均未接；无数据迁移，revert即可回滚。δ6 production economics 已基于 #130 独立落地，见下。

除权经济生产合同：[engine-ashare-correctness §2.5](engine-ashare-correctness.md#25-p3-δ6-ex-div-economics-productionhuman-go-cabba)；[P3 δ6 plan / 生产验收与冻结证明](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md)。Human GO **C/A/B/B/A production economics 已落地**：daily/minute `simulate` 与 `simulate_v7` 显式传 `exdiv_economics` lookup，ex 日按既有持仓逐 lot 增 `floor(q*b)` 股并开 `q*c` 应收，pay 日转现金，NAV 含应收；零碎舍弃，新股 list/ex 日起受 T+1 限售。默认 None 保留旧残留；不从 k 猜 b/c、不 shares/=k、不收公司行动佣金、不耗 volume、不改 trades schema。无湖/CLI 接线，无迁移，revert 可回滚；Mode B 独立冻结。

> **🔴 CLI 价格域风险：日线 `--qlib-data-root` 跳过 E-R6，不等于分钟 `--qlib-day-root` 跳过。** minute/v7 的 `daily=qlib_day` 仍加载并传递除权 map；这是已记录的危险组合。`qlib_day` 后复权与 `qlib_1min` none 是不同约定，读取器不认证真实 dump 域。δ2 保持现状，不新增跳过或拒绝逻辑；`--qlib-cost` 只管费率。

名单：`YYYYMMDD.csv`，首列裸六位码，`parse_pool_csv` 补交易所后缀。缺日 / 空文件 = 当日不买。6/8 默认读本仓 **可变** `stock_pool/`（不是快照）；实验/冻结跑用 `exports/` + `--pool-dir`；7 / **9** / **10** 必须 `--pool-dir`，9/10 拒绝 `stock_pool/`。生命周期 SSOT：[pool-csv-contract.md](pool-csv-contract.md)#lifecycle-ssot-stock_pool-vs-exports。

```text
# 策略 1 / 2 / 3 / 4 / 5 / 6 / 8 / 9 / 10：共用引擎，策略书换卖点与加仓。必须 --strategy，无缺省。
# 日线近似（收盘成交；分钟湖短于窗口时用这个接到今天）
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version6 --start 20251023 --end 20260909 ^
  --pool-dir D:\path\to\version6_pool
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version8 --start 20251023 --end 20260909 --cash-total 500000000

# 分钟（14:55 买入；湖 time 为中国交易时钟标成 UTC）
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py ^
  --strategy version6 --start 20251023 --end 20251104 ^
  --pool-dir D:\path\to\version6_pool
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py ^
  --strategy version8 --start 20251023 --end 20260909 --cash-total 500000000

# R5：MyQuant pred 当日 TopN；仅检查管道，不要使用 holdings 口径的 exports/r0_*
D:\anaconda3\envs\vanna312\python.exe my_scripts/export_daily_pool.py --pred my_scripts\预测结果.csv --topk 10 --asof pred_minus_one --out-dir exports/r2_pred_topn_20260302_20260323
D:\anaconda3\envs\vanna312\python.exe -c "from pathlib import Path; from backtest.research.csv_pool import validate_pool_dir; err=validate_pool_dir(Path(r'<r2 out>')); assert err == [], err"
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version6 --pool-dir <r2 out> --start <first filename stem> --end <last filename stem>

# 策略 9 底量超顶量（共用引擎；名单必须由导出器写，禁止 stock_pool/）
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_strategy9_pool.py --start 20260303 --end 20260908
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version9 --pool-dir exports/s9_bvot_20260303_20260908 --start 20260303 --end 20260908

# 策略 10 / 源 B（export_ta_pool.py；湖当日有 K；禁止 stock_pool/；不做 TopK）
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_ta_pool.py --start 20260303 --end 20260908
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version10 --pool-dir exports/src_b_tr_bb1000_20260303_20260908 --start 20260303 --end 20260908

# 策略 7 金榕元仓位机（独立，不进 1–6/8/9/10 策略书）。只吃海龟池。
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest_v7.py ^
  --start 20260804 --end 20260909 ^
  --pool-dir E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle

# topk_app_dropout（新策略，不改策略 7）：app ∩ qlib Top50 才开新仓
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest_topk_app_dropout.py ^
  --start 20260106 --end 20260909 --cash-total 500000000 ^
  --app-pool-dir <app YYYYMMDD.csv dir> --pred <MyQuant pred.csv> --topk 50

# 统一卖出规则网格 · 模式 A（前复权日线；名义现金池 11 亿；宿主真数据见 host-runbook）
D:\anaconda3\envs\vanna312\python.exe scripts/research/run_unified_exit_modea.py ^
  --pool-dir stock_pool --start 20251023 --end 20260909

# 统一卖出规则网格 · 模式 B（分钟触发；默认 P1=A 窄网格；独立输出目录）
D:\anaconda3\envs\vanna312\python.exe scripts/research/run_unified_exit_modeb.py --pool-dir stock_pool --start 20251023 --end 20260909
# docs/backtest/plan-unified-exit-modeb-2026-09-17.md
# Q39 E 短记：unified-exit-modeb-host-note-2026-09-17.md
# 甲/乙利弗莫尔：livermore-jia-yi-host-note-2026-09-17.md
```

R5 的 `--start/--end` 必须跟导出的首末文件名走：H0 / `pred_minus_one` 常没有 `20260302.csv`，最后一个 pred 日不写文件。无名称的 ST 按代码前缀使用 10% / 20% / 30% 档，不按 5%；该例只验管道，NAV / 涨跌停桶不是模型结论。细则见 [R2/R5 计划](_archive/plans/plan-pool-pipeline-r2r5-2026-09-12.md)与[名单 CSV 契约](pool-csv-contract.md)。

落盘：`backtest_output/csv_daily_{book}_{start}_{end}/`、`csv_minute_{book}_{start}_{end}/`、`csv_minute_v7_{start}_{end}/`、`csv_minute_topk_app_dropout_{start}_{end}/`（`summary.txt`、`daily_equity.csv`、`trades.csv`）。日线可用 `--out-dir` 改目录（M5 三列必须显式指定，见 [m5-list-attribution-2026-03.md](m5-list-attribution-2026-03.md)）。

**策略 6（list-add-tp-t1-stop2-dd70-50）**：`daily_quota` 日额度均分。已持再进当日名单加一笔（输家也加，独立 lot）。止损 2%（T+1 起）。T+1 起评止盈：峰值涨幅 &lt;6% 回撤 70%，≥6% 回撤 50%。峰差 15 分钟。计划：[plan-v6-stop2-2026-09-18.md](plan-v6-stop2-2026-09-18.md)。归档勿覆盖 `_v6_list_add_t1_dd70_50` / `_v6_list_add_tp_t1_dd70_50`。

**策略 8（stop10-max101-80-gap15-reserve-stale8）**：默认 `per_name`，每股票 100 万整笔（`--name-budget` 可覆盖）。已持再现当日名单加一个 100 万（输家也加，独立 lot）。相对第一笔成本每满 +20% 再加一个独立台阶。止损 10%（T+1 起）。T+1 起峰值≥买价×1.01 后，离场线 = max(买价×1.01, 买价+涨幅×80%)，现价≤该线 → `trail:max101_80`。峰值判定延时 15 分钟。遇涨停保留至开板（策略 3 同一分钟窗 09:30–09:40；开板按该分钟收盘卖）。满 8 日仍持有 → `force_sell:stale`（止盈先于僵持）。上证十日线两日下方停开新仓、已持可加。无六档、无 giveback、无未武装快切。现金不足支付整笔股款与佣金时记 `skip_cash`，按名单行序先到先得、不缩量。小预算不足 100 股时仍补足 100 股，现金不足则跳过。策略 1–6/9/10 保持 `daily_quota` 日额度均分。计划：[plan-v8-stop10-max101-80-gap15-reserve-stale8-2026-09-19.md](plan-v8-stop10-max101-80-gap15-reserve-stale8-2026-09-19.md)。归档勿覆盖 `_stop10` / `_v8_3` / `_v8_livermore` / `_v8_3_hold5` / `_v8_3_hold5_stale8` / `_v8_stop10_t4` / `_v8_t4_stop30_add` / `_v8_t4_stop30_add20` / `_v8_t4_stop10_add20` / `_v8_t4_stop30_last12_keep20` / `_v8_stop10_b78` / `_v8_stop10_b78_split` / `_v8_stop10_b78_split_last12` / `_v8_stop6_list_or_last12` / `_v8_blend_stop10_keep20_dead3` / `_v8_blend_list_step20_ride` / `_v8_list_nostep_cap10` / `_v8_t4_list_step20_ind_stale30` / `_v8_stop10_bands6` / `_v8_bands6_addall_step20_stale30_stop20` / `_v8_stop10_tp10_reserve` / `_v8_stop10_tp10_firstonly` / `_v8_stop20_tp10_floor102_cyb_defer` / `_v8_stop10_keep50_floor110_defer` / `_v8_stop10_gap15_floors_stale30_defer` / `_v8_stop2_gap30_floor102_stale30_defer` / `_v8_stop6_gap30_floor102_stale30_defer` / `_v8_stop30_gap30_max110_max120_stale30_defer` / `_v8_stop30_unarmed10_stale6_max120_defer` / `_v8_stop10_stale20_unarmed6_max120_defer` / `_v8_stop30_stale8_unarmed6_max120_defer` / `_v8_stop20_unarmed10_stale8_max120_defer` / `_v8_stop10_tp2_reserve_stale8` / `_v8_stop10_tp2_reserve_stale8_sseopen`。

**v8 对照顺序（M-R8③）**：首次宿主烟测先重跑同窗 daily v8，确认其 `summary.txt` 为 `sizing=per_name` 且预算相同，再运行分钟版。旧 daily_quota 工件先保存 commit/日期与池来源；跨 sizing 仅比较 lot 收益分布、胜率及单码敞口，不用 NAV 排名。日线收盘确认、次日开盘止盈，分钟逐 bar 判断成交；跨引擎结论以分钟版为准。

规则与闸：策略 7 见 [plan-strategy7-turtle-csv-minute-2026-09-11.md](_archive/plans/plan-strategy7-turtle-csv-minute-2026-09-11.md)。6/8 口径写在各自 CLI 的 help lock。成交核（档位 / 全卖因跌停 / Decimal 涨跌停价 / 停牌净值）见 [engine-ashare-correctness.md](engine-ashare-correctness.md)。名单 as-of 与 ST 名称列见 [pool-csv-contract.md](pool-csv-contract.md)。

数据：只读已设定的湖（`OSKH_SOURCE_PARQUET_ROOT`；未设定或文件缺失即报错，不猜 E/F）。申万一级只读 `vendor_wind_sw_l1/`（`oskh_data/industry_sw_l1.py`），采集写湖在 1.3。细则见根 `AGENTS.md`。

**CI contract gates（无 F 湖 / repo-only）：** `.github/workflows/python-tests.yml` 在 `pip` 前跑 `verify_oskh_data_contract.py`、`verify_data_path_ssot.py`（扫 `oskh_data` / `oskh_factors` / `scripts` / `common`）、`verify_no_hardcoded_machine_paths.py`、`verify_tr_bridge_import_ssot.py`（H12）。chip / TR / L2 等需湖门禁不进 CI。清单见 [plan-h10-ci-path-gates-2026-09-15.md](plan-h10-ci-path-gates-2026-09-15.md) · [plan-h12-ci-tr-bridge-gate-2026-09-15.md](plan-h12-ci-tr-bridge-gate-2026-09-15.md)。

**宿主湖门禁（9 个，host-only）：** purpose、跑法、数据要求与退出语义见 [host-lake-gates-cookbook-2026-09-16.md](host-lake-gates-cookbook-2026-09-16.md)；权威入口为 `scripts/gates/`。

## 1.3：LEBS 与 MockQMT（不在本仓跑）

要和 Paper 同源的扫描、真栈验收，去 **OSkhQuant1.3**（本仓没有 `backtest/lebs/`）：

- 研究扫描：`python -m backtest.lebs`（`--strategy turtle` 吃 `stock_pool_turtle/`，与 Paper 同源决策核；或 `csv_v1..csv_v5` 旧 CSV 轨，**不是**本仓 1–10 / 策略 7）
- 验收：`run_mock_turtle_stack_scenario.py` + `--parity`（真栈；**不用 LEBS 净值代替签字**）
- SSOT：1.3 `docs/backtest/backtest-architecture-ssot.md`（只管辖 1.3，不描述本仓向量化）
- 四件怎么选、LEBS ≠ 真栈：本仓 [plan-ashare-engine-refactor-2026-09-18.md](plan-ashare-engine-refactor-2026-09-18.md) §0.3

本仓不复刻 LEBS / MockQMT，也不承诺和它们净值对齐。策略 7（金榕元）≠ LEBS turtle ≠ Paper 海龟。

## Cerebro（已退场，2026-09-16）

Cerebro / Rolling 已退场（2026-09-16）；chip / ma_chip 对照产物为静态档案，代码路径已删。保留 `backtest_output/`、历史对照报告和测试 fixtures，以及纯筹码计算、Rust TR 和 CSV 策略规则。ma_chip 默认归档；需要可跑研究时另开 version11 CSV 移植计划，重裁次日开盘与现行 CSV 成交时点语义。**Cerebro 已退场，禁止复活。**

## SSOT

| 主题 | 文档 |
|------|------|
| **★ 研究问题总入口（名单 × 搜法 × 策略号）** | [research-backtest-entry.md](research-backtest-entry.md) |
| **★ 三件引擎定位（本仓 + 1.3）** | [engine-positioning-ssot.md](engine-positioning-ssot.md) |
| **★ 向量化成交核（A 股档位 / 跌停 / 停牌）** | [engine-ashare-correctness.md](engine-ashare-correctness.md) |
| **联合仓库 TopK 回测（讨论中，未编码 GO）** | [topk-joint-research-tracker-2026-09-22.md](topk-joint-research-tracker-2026-09-22.md) · [#164](https://github.com/baiyibing/MyQuant-backtrader/issues/164) · overlay 默认已冻结：[plan-topk-dropout-overlay-2026-09-16.md](plan-topk-dropout-overlay-2026-09-16.md) |
| **joint-return-v1（Grok Bot/4090 意图回放；≠ topk_dropout）** | [joint-return-frozen-explicit-price.md](joint-return-frozen-explicit-price.md) · 交接 [handoff-joint-return-qlib-to-bt-2026-09-22.md](handoff-joint-return-qlib-to-bt-2026-09-22.md) · 归类 [research-backtest-entry.md](research-backtest-entry.md) §5 |
| **P3 δ1 研究费率合同（docs/tests；生产冻结）** | [plan-industry-align-p3-fees-2026-09-19.md](plan-industry-align-p3-fees-2026-09-19.md) · correctness §1.1 · `tests/test_ashare_fee_wiring.py` · r1 [merge-consensus](../architecture/reviews/2026-09-19/plan-industry-align-p3-fees-r1/merge-consensus.md) |
| **向量化撮合核收口（⏳ 待人裁 GO — 见 plan，勿编码）** | [plan-ashare-engine-refactor-2026-09-18.md](plan-ashare-engine-refactor-2026-09-18.md) · [handoff](handoff-ashare-engine-refactor-codex-impl-2026-09-18.md) |
| 名单 CSV 契约（as-of = 买入日 T；H9/H16 list-quality CLI，双目录严格校验） | [pool-csv-contract.md](pool-csv-contract.md#list-quality-reporter-h9--h16) |
| **NP1 资金配给探针（只读；A 探针 / B `--ration` 待 GO）** | [plan-capital-ration-2026-09-16.md](plan-capital-ration-2026-09-16.md) · `scripts/research/report_capital_ration.py --trades <trades.csv> --pool-dir <pool>` |
| **NP2 除权持仓命中（只读；主源 ex_date_index；裁决人裁）** | [plan-exdiv-hold-hits-np2-2026-09-16.md](plan-exdiv-hold-hits-np2-2026-09-16.md) · [host runbook](exdiv-hold-hits-np2-host-runbook-2026-09-16.md) · `scripts/research/report_exdiv_hold_hits.py` |
| **统一卖出网格 · 模式 B（分钟；A–D 已合 #95，宿主 E 待跑）** | [plan-unified-exit-modeb-2026-09-17.md](plan-unified-exit-modeb-2026-09-17.md) · [handoff](handoff-unified-exit-modeb-codex-impl-2026-09-17.md) · [分钟就绪 smoke](host-runbook-unified-exit-modeb-smoke-2026-09-17.md) · [E 业务 runbook](host-runbook-unified-exit-modeb-2026-09-17.md) |
| **CI path-SSOT / contract gates（H10；无湖）** | [plan-h10-ci-path-gates-2026-09-15.md](plan-h10-ci-path-gates-2026-09-15.md) · workflow `python-tests.yml` |
| **CI TR bridge import gate（H12；无湖）** | [plan-h12-ci-tr-bridge-gate-2026-09-15.md](plan-h12-ci-tr-bridge-gate-2026-09-15.md) · `verify_tr_bridge_import_ssot.py` |
| **宿主湖门禁 cookbook（WP2；9 个 host-only）** | [host-lake-gates-cookbook-2026-09-16.md](host-lake-gates-cookbook-2026-09-16.md) |
| **Chip / TR slow-path inventory（H11；Theme D 软）** | [chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md) · [plan-h11-chip-slowpath-inventory-2026-09-15.md](plan-h11-chip-slowpath-inventory-2026-09-15.md) |
| **CYQ / TR 产品边界（H13）** | [plan-h13-cyq-tr-boundary-2026-09-15.md](plan-h13-cyq-tr-boundary-2026-09-15.md) · inventory §E：MyQuant numba `winner_ratio` feeder ≠ 本仓 Rust TR Store |
| **D1 minute/hybrid chip profile（H14）** | [plan-h14-d1-minute-chip-profile-2026-09-15.md](plan-h14-d1-minute-chip-profile-2026-09-15.md) · [chip/h14-d1-minute-chip-profile-results-2026-09-15.md](chip/h14-d1-minute-chip-profile-results-2026-09-15.md) · `bench_minute_chip_hotpath.py` |
| **D2 minute chip numba（H15）** | [plan-h15-d2-minute-chip-numba-2026-09-15.md](plan-h15-d2-minute-chip-numba-2026-09-15.md) · `MINUTE_CHIP_BACKEND` / `use_numba` · `tests/test_minute_chip_numba_parity.py` |
| **Minute `simulate()` real-path profile** | [minute-simulate-profile-results-2026-09-15.md](minute-simulate-profile-results-2026-09-15.md) · `bench_minute_simulate_hotpath.py` |
| **头脑风暴总览（A–F · H1–H16）** | [brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md) |
| **本仓对照分析（vs brainstorm · 2026-09-15）** | [repo-analysis-vs-brainstorm-2026-09-15.md](repo-analysis-vs-brainstorm-2026-09-15.md) |
| **Next heavy brainstorm** | [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md) |
| 名单管道 R0/R1（持仓胶水；已合 #21） | [plan-pool-pipeline-r0r1-2026-09-12.md](_archive/plans/plan-pool-pipeline-r0r1-2026-09-12.md) |
| **名单管道 R2/R5（pred TopN 闭环）** | [plan-pool-pipeline-r2r5-2026-09-12.md](_archive/plans/plan-pool-pipeline-r2r5-2026-09-12.md) |
| **Qlib 训练厂 R3（processors + filter；不做 M5）** | [plan-qlib-train-r3-2026-09-12.md](_archive/plans/plan-qlib-train-r3-2026-09-12.md) |
| **M5 名单归因（首轮 2026-03）** | [plan-m5-list-attribution-2026-09-13.md](_archive/plans/plan-m5-list-attribution-2026-09-13.md) · [2026-03 报告](m5-list-attribution-2026-03.md) |
| **M5 二轮（2026-03–09 三源）** | [plan-m5-round2-2026-09-13.md](_archive/plans/plan-m5-round2-2026-09-13.md) · [报告](m5-list-attribution-2026-03-09.md) |
| **策略 9 / 10 宿主烟测（2026-09-13）** | [s9-s10-host-smoke-2026-09-13.md](s9-s10-host-smoke-2026-09-13.md) |
| **MyQuant 中期同步（2026-09-13）** | [myquant-progress-sync-2026-09-13.md](myquant-progress-sync-2026-09-13.md) |
| 策略 1–8 书契约（U-R\*；撮合句以 E-R\* 为准） | [plan-unify-csv-strategies-1-8-2026-09-12.md](_archive/plans/plan-unify-csv-strategies-1-8-2026-09-12.md) |
| **策略 9 底量超顶量（买点 CSV + v9 卖点）** | [plan-strategy9-bottom-vol-2026-09-13.md](_archive/plans/plan-strategy9-bottom-vol-2026-09-13.md) |
| **策略 10 换手阻力 / 源 B（CSV + v6 卖点）** | [plan-strategy10-tr-pool-2026-09-13.md](_archive/plans/plan-strategy10-tr-pool-2026-09-13.md) |
| **名单源 B（TR → 契约 CSV；B-R*）** | [plan-source-b-ta-pool-2026-09-13.md](_archive/plans/plan-source-b-ta-pool-2026-09-13.md) |
| **策略 7 金榕元 CSV 分钟（A–D 已合；E 本机）** | [plan-strategy7-turtle-csv-minute-2026-09-11.md](_archive/plans/plan-strategy7-turtle-csv-minute-2026-09-11.md) |
| 日线复权增量 | [data/daily-adjusted-update-ssot.md](data/daily-adjusted-update-ssot.md) |
| ma + 筹码边（静态档案；代码已于 2026-09-16 退场） | [plan-ma-chip-edge-strategy-2026-09-07.md](_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md) |
| **★ 向量化热路径 offload（进行中）** | [plan-vectorized-hotpath-offload-2026-09-15.md](plan-vectorized-hotpath-offload-2026-09-15.md) |
| 1.3 presets 契约快照（防漂移） | `tests/test_presets_cross_repo_snapshot.py`（sibling `OSkhQuant1.3`） |
| 已完成 plan 归档 | [_archive/plans/](_archive/plans/) |


**Hygiene / future work:** 战略分析（tip `5ba97e4`）[strategic-analysis-opus5-next-2026-09-16.md](strategic-analysis-opus5-next-2026-09-16.md)；对照分析 [repo-analysis-vs-brainstorm-2026-09-15.md](repo-analysis-vs-brainstorm-2026-09-15.md)；总览 [brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md)；backlog [plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)（H1–H16 ✓）；next heavy → [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)（队列头 run-manifest hard **仍延期**）。引擎地图（NP3）：**双入口** `csv_daily_backtest` / `csv_minute_backtest` + **共享核** `csv_common` / `csv_ledger` / `csv_strategy_books` / `csv_pool` / `market_layer` / `csv_simulate_loop` / `csv_artifacts` / `csv_daily_loader`；chase / pool / equity-mark skeleton 在 `csv_simulate_loop.py`；sell loops remain split on purpose (daily bar rules vs `scan_held_day`; unify A–E locked sell books later — do not big-bang merge). Cerebro / Rolling 已退场（2026-09-16），禁止复活；chip / ma_chip 仅保留静态对照档案。 L2 (`l2_analytics/` / `run_l2_*`) stays offline ETL/aggregates — do not expand into trading or strategy books.

下列链到本仓不存在的 1.3 迁仓文件，不要当本仓入口：`backtest-architecture-ssot.md`、`../handoff/mockqmt-lebs-homology-review-handoff-2026-08-27.md`、`../engineering/plan-lightweight-event-backtest-shell-2026-08-25.md`。

## 子目录

| 目录 | 说明 |
|------|------|
| [chip/](chip/) | Chip 因子与 cost-migration；**H11 inventory** → [chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md)（含 **H13** 边界 + **H14/D1** profile + **H15/D2** numba minute） |
| [_archive/plans/](_archive/plans/) | 已完成 plan-*.md（状态 已合/已实施） |
| [_archive/fossils/](_archive/fossils/README.md) | 观察退役的 Backtrader 框架考古 |
| [code-reviews/](code-reviews/) | 历史 Backtrader 代码审查（考古） |
| [data/](data/) | 回测数据方案（含 unified-daily-bars-plan） |

## 文件（考古）

| 文件 | 说明 |
|------|------|
| [backtrader-order-types.md](_archive/fossils/backtrader-order-types.md) | 历史 Backtrader 订单类型 |
| [结合本系统讨论 Backtrader 订单的创建与执行流程.md](<_archive/fossils/结合本系统讨论 Backtrader 订单的创建与执行流程.md>) | 历史订单创建与执行流程 |
| [部分成交处理逻辑分析.md](_archive/fossils/部分成交处理逻辑分析.md) | 部分成交 |
| [订单生命周期详解.md](_archive/fossils/订单生命周期详解.md) | 历史 Backtrader 订单生命周期 |
| [延期买入误检查.md](_archive/fossils/延期买入误检查.md) | 历史分析（A6b 已拆除） |
| [资金管理实现逻辑（含回滚机制）.md](_archive/fossils/资金管理实现逻辑（含回滚机制）.md) | 资金管理（延期段 A6b 已拆除） |
