# 主笔侧对抗评审草案：plan-version11-machip-csv v0.2（2026-09-21）

- **评审人**：claude（主笔，本草案不计独立票）
- **方法**：3 路对抗子代理。**dissent-steelman 与 pattern-evidence 两路环境受阻**（子代理会话无文件读取工具，各自重试后仍无；两路均拒绝伪造证据）；domain-safety 完整取证。受阻两路按其条件式产出 + 主笔在主会话代核事实，独立性让渡给外部四稿复核。
- **原则**：证据优先于票数；主笔让步逐条记录；对抗草案不计票。

## §0 评审结论速览

| 维度 | 提案原立场 | 修正后立场 | 关键依据 |
|---|---|---|---|
| 策略前提 | 直接移植框架 | **新增 P0 必答**：cyqk>0.70 语义（抛压区疑虑）先仲裁 | 归档 plan §3.3 自认 + consensus 未裁 |
| 契约日口径 | 导出器按 ≤D 计算写 D | **按 ≤T-1 计算写入买日 T** | export9 先例是「≤T 计算写 T」（买即用）；v11 信号是 T-1 边缘，**勿照搬** |
| 涨停追买默认 | 未提 | **`limit_up_chase` 须 pin False**（否则 T+2 追买违反 skip_buy 消耗） | `csv_simulate_loop.py:280-287` 默认 True |
| stale 机制 | 「引擎有对应物」 | **无对应物**，须导出器/书侧新建 | 池 `skip_no_bar` 即消耗 `:262`；chase 永不过期 `:146` |
| 分钟卖出钟 | pending_exit「现成」 | 仅日线现成（`:344-350` 开盘价成交）；**分钟侧零消费，全新代码** | `csv_minute_backtest.py:338` 无该参数 |
| 买入日评估 | 「现成落点」 | **两引擎均被 t1_sellable 挡住**，需新 EOD 评估钩子 | `ashare_session.py:39-41` + 日循环先卖后买 |
| Rust cyqk 回退 | 「失败回退 Python」 | **失败即 skip**，不换算法（Python 侧为等权法，非等价） | `oskh_factors/chip/core.py:580` 等权；Rust NaN fail-closed ✓ |
| P4 默认全市场 | 全市场为主、seed 对照 | 重开：**seed-30 parity 或为主交付**（7 份静态档案在） | dissent 条件式反题 + 档案清单实证 |

一句话：移植可行性成立，但 §3「skip FSM 已有对应物」被证伪、契约日口径有一处危险照搬、策略前提（cyqk 语义）须升为 P0 必答。

## §1 关键发现（改变主笔立场）

- **F1【让步】cyqk>0.70 语义矛盾未裁**（dissent 条件式 + 主笔核实）：归档 plan §3.3 自认「cyqk_c>0.70 在仓内文档是抛压区，本轮只验证框架」；2026-09-07 consensus 只裁过映射（`qlib_cost/cyq.py get_cyqk_c → get_winner`，0–1，阈值 0.70），**未裁语义方向**。升为 P0。
- **F2【让步】「skip FSM 已有对应物」不成立**（domain-safety）：① `limit_up_chase` 默认 True → T+2 09:45 追买，与「skip_buy 消耗信号」直接冲突，须 pin False；② 「>4 自然日 stale」无引擎对应物（池 `skip_no_bar` 当日即消耗 `csv_simulate_loop.py:262`；chase pending 永不过期 `:146`；v8 `force_sell:stale` 是持仓僵持语义）→ 导出器层新建。
- **F3【让步】买入日收盘评估无既有落点**（domain-safety）：「T 收盘评估 → T+1 开盘卖」被 `t1_sellable`（`ashare_session.py:39-41`，buy_date<session）+ 日循环先卖后买（`csv_daily_backtest.py:310` vs `:460`）结构性挡住；分钟引擎完全无 pending_exit 消费（`csv_minute_backtest.py:338`）→ 两侧均为新代码，§3 缺口清单须扩。
- **F4【让步】契约日口径危险照搬**（domain-safety）：export9 先例 =「filename=买日 T、按 ≤T 计算」（`export_strategy9_pool.py:2-4`）；v11 信号是 T-1 边缘 → 导出器**按 ≤T-1 计算写入 T**，与先例差一天，勿照搬。
- **F5【让步】Rust cyqk 回退策略反转**（domain-safety）：`turnover-resist/src/algorithm.rs:436-473` 子窗异常全 NaN fail-closed ✓；Python 侧 `compute_equal_weight_cyqk` 是等权法**非等价**；失败应 skip 该日该码，不切换算法。另：repo 内 `.pyd`（cp311）是陈旧件，实际 import 走 site-packages（vanna312 实测含 `compute_cyqk_series`）。
- **F6【部分让步】统计窗前置假只能在导出器层**（domain-safety）：`build_calendar` 只裁日历、前置 bar 留预热（`csv_common.py:48-59`）；「统计窗前 edge 置假」引擎无机制（`skip_sma_warmup` 是另一物）。
- **F7【部分让步】周线防泄漏责任在未建的 ma_infra**（domain-safety）：`_daily_to_weekly` 全段 resample 无 asof 参数（`weekly_macd_divergence.py:86-104`），须调用方先截 ≤D；末端未完成周可参与的细节须在 ma_infra 测试 pin（回填 ma_infra 待其 fan-out 完成后）。
- **F8【认同 + 勘误】静态档案在**（主笔核实）：7 份 `backtest_output/ma_chip_edge_20240907_*`（含 cyqk80/nobb/nocyqk 等变体）——dissent 的「seed-30 parity 为主交付」反题有实证基础，P4 重开。

## §2 三方裁决对照

| 维度 | dissent-steelman（条件式） | domain-safety | pattern-evidence（主笔代核） | 主笔综合 |
|---|---|---|---|---|
| 移植与否 | 先归档 + 全市场统计仲裁语义 | 可行，补三处锁 | 锚点大体成立 | **P0 必答，人裁** |
| P1 双跑 | 先锁单口径再跑 | 双跑可行，09:30 新钟带涨停/一字/volume=0 测试 | 买钟全集确认无次日开盘买 | 双跑保留，先裁口径 |
| P4 | seed parity 为主 | 未裁 | 档案在 | 重开，外部裁决 |
| P6 差异清单 | 无一致性校验不可判读 | 未裁 | —— | 加 sanity bounds（笔数量级等） |

## §3 立场修正方案

- **α** = 原案。弃：F2/F3/F4 三处事实错误未被吸收。
- **β** = dissent 全量（先归档，全市场统计仲裁后再议）。弃：静态档案 + 共识链已允许框架移植；语义仲裁可并行不阻塞引擎面。
- **γ（推荐）**= 吸收式移植：① P0 升必答（框架验证定位 vs 全市场统计先行，人裁）；② 契约日改 ≤T-1 写 T；③ `limit_up_chase=False` + stale 导出器层新建；④ 买入日评估 EOD 钩子入 §3 缺口；⑤ Rust 失败即 skip；⑥ P4/P6 重开为外部必答。护栏：R1–R8 不变，新增 R9（limit_up_chase pin）、R10（cyqk 失败 skip 不换算法）。

## §4 留给外部四稿的必答题

1. P0：cyqk>0.70 作多头入场的语义矛盾——先全市场信号统计仲裁，还是按归档口径框架移植先行、统计并行？
2. P4：seed-30 parity 为主交付 + 全市场为敏感性，还是反之？
3. P1：D+1 开盘买在 CSV 时钟上，分钟 09:30 新钟 vs 日线收盘近似，单裁还是双跑？
4. 契约日 ≤T-1 写 T 的口径，是否与 9/10 先例形成需要文档化的「评估窗分类」（买即用 vs 边缘信号）？
5. stale「>4 自然日」是否保留原口径，还是简化为「次一交易日无 bar 即消耗」？

## §5 对提案稿的勘误（须回填）

| 位置 | 错误 | 修正 |
|---|---|---|
| §1 买入信号「盈筹率 cyqk_c[D]」 | 评估窗与契约日未分开 | 导出器按 ≤T-1 计算写入 T（F4） |
| §2 export9 锚点「:54 拒绝」 | 行号错 | `:62-63`（`is_repo_stock_pool` + SystemExit） |
| §2 pending_exit「csv_ledger.py:81」 | 行号漂移 | 字段 `:79`；日线消费 `csv_daily_backtest.py:344-350`（开盘价、跌停 defer）；分钟零消费 |
| §2「chip 计算 SSOT：turnover_resist.compute_cyqk_series」 | import 路径含糊 | Rust pyd `turnover_resist` 模块实测导出（vanna312 走 site-packages，repo cp311 .pyd 陈旧）；回退改 skip（F5） |
| §3 缺口清单 | 少 3 项 | EOD 评估钩子、分钟 pending_exit 全新、stale 无对应物 |
| §5 P6 | 无一致性校验 | 差异清单加 sanity bounds |
| R 表 | 缺 R9/R10 | 补 limit_up_chase pin、cyqk 失败 skip |

## §6 最终立场

投 γ：移植继续，但按 F2–F5 修正事实与口径，P0/P4 重开必答。请外部四稿重点裁决 §4 题 1/2/3。两路环境受阻的独立性缺口，请外部稿对本草案 §5 勘误逐条复核。
