# Plan: version11 ma_chip CSV 移植（2026-09-21）

> **Status**: **v1.0 · ✅ 已人裁 GO（2026-09-21，Asia/Shanghai）**——用户裁定 P0–P7 + V2/V9 **全按共识建议**：P0=a 框架移植先行（--help 印「非已验证多头」，全市场统计并行挂 strategy12 后）、P1=a/b 双跑分钟 09:30 为准（日线保持契约收盘）、P2=日线 pending_exit 原样、P3=独立导出器禁读 store cyqk_t、P4=seed-30 parity 主交付+消融轴对照、P5/P6/P7=沿归档、V2=契约日 T 该股首根 bar ≤4 自然日、V9=全市场滤 ST 排 688。
> **实施进度（2026-09-21）**：A/B 已实现并有 data-free pins（稳定化门禁 106 passed）；C 开盘 volume 分叉已按显式人裁 **A / 严格可得性** 解阻，待注册和引擎回归；D 未跑。见 [handoff 续作状态](handoff-version11-codex-impl-2026-09-21.md) 与 [人裁确认](https://github.com/baiyibing/MyQuant-backtrader/pull/152#issuecomment-5756590614)。本行不代表整项已实施。
> **评审链**：主笔对抗层（F1–F8）→ 四稿 fan-out（codex/kimi/cursor/claude 全 rc=0，5 组实验）→ [merge-consensus V1–V17](../architecture/reviews/2026-09-21/plan-version11-machip-csv/merge-consensus.md)（分歧记录：宽派被严派反对，采严派全修）。实施走 [Codex 交接工作流](workflow-codex-handoff.md)（门槛：ma_infra PR #150 已合入）。
> **业务源**：[归档 plan-ma-chip-edge-strategy-2026-09-07.md](_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md) §2 锁定口径（Cerebro 原实现已随 2026-09-16 Cerebro 退场删除；对照产物为静态档案）；用户 2026-09-21 指示「把 ma_chip 移植也做完」。
> **Main ship / 单行范围**：把 ma_chip_edge（均线+盈筹率边缘买入）移植到 CSV 向量化引擎为 `version11`：信号池导出器 + 卖点书 + 成交时点语义重裁；不复活 Cerebro。
> **前序**：[workflow-codex-handoff.md](workflow-codex-handoff.md)、[engine-ashare-correctness.md](engine-ashare-correctness.md)、[plan-ma-infra-shared-2026-09-21.md](plan-ma-infra-shared-2026-09-21.md)（**前置：共享均线基础设施，本 plan 实施时直接消费**）、[strategy12 plan](plan-strategy12-jinrongyuan-2026-09-21.md)（同日另一书，互不依赖）。

---

## 0) One-line scope

### 2026-09-21 续作覆盖（binding；docs-first）

1. **契约日覆盖 V2 / §1 / 切片 B**：D 为原信号日，T 为该股**严格晚于 D** 的首个有 bar 交易日；任何 on/after D 解释均作废。D→T ≤4 自然日；stale 从原 D 起算，超限无池行，`rejected.csv` 保留 `skip_buy(stale)` 和原 D。导出器只用 ≤T−1 数据计算，写 T 文件。
2. **周线覆盖 R8 / P7 / 切片 A、B**：逐 D 采用 A / prefix-equivalent，即先截 ≤D 再重算（含末端未完成周）。`ma_infra` 新增显式 opt-in；现有默认 series 全历史 backward alignment **不变**。导出器调用显式 prefix series，不在默认 API 内隐藏逐日 asof。data-free 测试必须 pin 默认不变及 opt-in 与 truncate-then-call 等价。
3. **R9 不变**：`apply()` 返回 dict 必须显式含 `limit_up_chase=False`；flag=False、chase pending 为空两项回归必过。
4. **volume / 09:30 = A**：保留 P3 δ5 严格可得性，开盘 `attempt_at=hm-1`、`bucket <= at`；09:30 桶未完成则买 skip / pending 卖 defer。否决 v11 同分钟完成量仍按开盘价成交例外；既有书与生产 cap 默认不变，新增 data-free skip/defer pin。

此节与 [更新 handoff](handoff-version11-codex-impl-2026-09-21.md) 优先于下方历史措辞；先独立提交文档，再写代码。

`version11` = ma_chip_edge 移植：`export_strategy11_pool.py` 按「T-1 四条件边缘 + 盈筹率>0.70」写契约日池 CSV（9/10 导出器先例），引擎按名单买；卖点书实现「买入日收阴→次日开盘卖 / 收阳→破 SMA5 次日开盘卖」；D+1 开盘成交语义在 CSV 时钟上重裁（P1）。

## 1) 规则转录（归档 plan §2，已锁定口径）

| 项 | 口径（源：§2 锁定表） |
|---|---|
| 买入信号（D 收盘评估） | `cond[D]`：D 收盘 > SMA20 日线 且 > 20 周均线（W-FRI+last_day=max，只 backward）且 > SMA60 日线 且 D `high` > 布林上轨（SMA20+2σ，σ=std ddof=1，含 D）；盈筹率 `cyqk_c[D] > 0.70`（含 D 的 200 日 OHLC 窗、窗内每日 asof 流通股本，优先 Rust `compute_cyqk_series`）。**边缘** = `cond[D]` 真且 `cond[D-1]` 假，**两边都必须有限**（NaN≠边缘）。**契约日口径（V2 裁决）：T = 该股 D 后首根有 bar 的交易日，且 D→T ≤4 自然日（超限不写池，manifest 计 `skip_buy(stale)` 并记原信号日 D）；导出器按 ≤T-1 计算写入 T**（export9 先例是「≤T 计算写 T」买即用语义，勿照搬） |
| **价格（V1 补行，归档 §2:31）** | **信号计算价格 = `dividend_type=front`**（归档锁定；QMT ground truth）；执行/涨跌停/T+1 = 引擎现行（none + `mapped_prev_close`）；manifest 记 adjust_type。R4 的「除权」限定执行侧 |
| **抽样/板块/股本（V9 补行，归档 §2:44/45/35）** | seed=`20240907`、hive front ∩ `float_shares`、每板 10（沪主板 60 排 688 / 深主板 000-003 / 创业板 300-301）；股本=`free_float_shares.parquet.circulating_capital` 逐日 backward asof，**禁用 D 日一条股本铺整窗**（`date=None` 快照=前视）。全市场模式滤 ST+排 688（无名称列时 ST 按前缀错走 10% 档）；seed-30 沿归档不做 ST |
| 买入成交 | 信号 D 的次一交易日开盘（原 Cerebro `cheat_on_open` + `next_open`；**本仓须重裁**，见 P1） |
| 卖出 | 买入日 T 收盘 ≤ T-1 收盘 → T+1 开盘卖（fail-closed 含等号）；T 收盘 > T-1 收盘 → 持有至首个收盘 < SMA5（含 T 当日评）的次日开盘卖。买入日禁止任何卖单 |
| skip FSM | 涨停买/跌停卖/volume=0 不成交不进净值，记 events；skip_sell 保留 pending_sell 下一日再试；skip_buy 消耗信号。信号后 >4 自然日无 bar → `skip_buy(stale)` 并消耗 |
| 仓位 | 单票 1 笔；已持忽略新开；卖出日不重入 |
| 原费用/涨跌停 | 自写 CommInfo（万 0.5/最低 5/印花 0.05%）+ front 昨收阈值 → **移植后一律用 CSV 引擎现行**（P4 已对齐的行业口径，优于原实现） |

## 2) Verified as-built anchors（HEAD `599a894`）

| 合同项 | 当前事实 | 锚点 |
|---|---|---|
| 池导出器先例 | `export_strategy9_pool.py` / `export_strategy10_pool.py`（源 B）写契约日 CSV；书侧「买点不在本模块」 | `scripts/data/export_strategy9_pool.py`、`:62-63` 拒绝 `stock_pool/`（`is_repo_stock_pool` + SystemExit） |
| 卖点书先例 | `strategyN_rules` 纯函数 + `pending_exit`（收盘评估次日开盘离场）——**仅日线引擎消费（开盘价成交、跌停 defer）；分钟引擎零消费** | `backtest/research/csv_ledger.py:79`；日线消费 `csv_daily_backtest.py:344-350`；分钟侧 `csv_minute_backtest.py:338` 无该参数 |
| 开盘成交先例 | 引擎买钟：日线近似=收盘成交、分钟=14:55 / chase 9:45；**无「次日开盘买」** | `csv_simulate_loop.py` `run_pool_buys_day`；`README.md` 引擎入口说明 |
| chip 计算 SSOT | Rust pyd 模块 `turnover_resist` 实测导出 `compute_cyqk_series`（vanna312 经 site-packages cp312 加载；repo 内 cp311 `.pyd` 为 ABI 不匹配残留件，manifest 须记 `__file__`+版本）。**两层失败契约（V5 实验）**：窗内坏日→**仅含该日的窗** NaN；数组长度不等→**抛 `PyValueError`**（安装件实测，与仓内源码分歧以安装件为准）→ 按码捕获 skip+计数。**无网格上限（V6）**：导出器须自加 `窗口内 (max(high)-min(low))/step` 预检 + 250k 量级上限（妖股宽幅可 ~200k 网格×320MB×线程）。asof 股本（V7）：`oskh_factors/chip/shares.py:60 _get_float_shares` 私有，须在 bridge 加 public 薄壳，**禁 `date=None` 快照（前视）** | `turnover-resist/src/lib.rs:97-115`、`src/algorithm.rs:436-473`；`oskh_factors/chip/shares.py:60`；TR store 刷新链（PR #146/#147/#148） |
| 周线换算先例 | `oskh_factors.weekly_macd_divergence._daily_to_weekly`（W-FRI + last_day=max） | 归档 plan §2 明示同构引用 |
| 编号预留 | AGENTS.md「ma_chip 默认归档；version11 CSV 移植须另开计划并重裁成交时点语义」——即本文件 | `AGENTS.md` Research entries 节 |
| 静态档案 | Cerebro 对照产物 `backtest_output/ma_chip_edge_*` 为静态档案，不参与 CI | AGENTS.md「chip / ma_chip 对照产物为静态档案」 |

## 3) 移植缺口

1. **成交时点**：原 D+1 开盘买 / 卖次日开盘，CSV 引擎无「次日开盘买」买钟（P1 重裁）。
2. **信号数据装载**：200 日筹码窗 + 每日 asof 股本 + 周线 MA——导出器需装载与缓存（TR store 生态可复用，P3）。
3. **skip FSM 映射**：原 events.csv 语义 → CSV 引擎 skip reason 体系（**对抗层证伪「已有对应物」**：`limit_up_chase` 默认 True 会 T+2 追买违反「skip_buy 消耗」；「>4 自然日 stale」无对应物——池 `skip_no_bar` 当日即消耗 `csv_simulate_loop.py:262`、chase pending 永不过期 `:146`）。
4. **买入日收盘评估（对抗层新增）**：「T 收盘评估 → T+1 开盘卖」在两引擎均无既有落点——`t1_sellable`（`ashare_session.py:39-41`）+ 日循环先卖后买结构性挡住；分钟引擎 pending_exit 零消费 → 需新 EOD 评估钩子。

## 4) R\* hard locks

| ID | 硬锁 |
|---|---|
| **R1** | 不复活 Cerebro/Rolling；不 import 已删路径；静态档案只读对照。 |
| **R2** | 策略 1–10/8.x/12 书零变更；全量 pytest 绿不放宽。 |
| **R3** | **（C9/V3 落地）**chip 一律 `turnover_resist.compute_cyqk_series`（两层失败契约见 §2）；**周线一律走 `ma_infra`**（与 R8 同源，消解旧「复用 oskh_factors 周线」的互斥锁）；不改 `oskh_factors` / `turnover_resist` / `qlib_cost` 公共 API（V7 的 asof 股本 public 薄壳除外）；`_daily_to_weekly` 保持私有、MA200 不迁不删。 |
| **R4** | 费用/涨跌停/除权/T+1 一律用 CSV 引擎现行口径（P1–P4 industry-align 成果），不自写费率。 |
| **R5** | 池导出器拒绝默认 `stock_pool/`（9/10 先例）；数据走 resolvers，禁写死盘符。 |
| **R6** | 时间因果：信号只含截至 D 的数据（PIT）；D-1 NaN ≠ 边缘，等号 fail-closed 沿用。 |
| **R7** | UTF-8 无 BOM、NUL=0；新文件 ruff 零告警。 |
| **R8** | MA/布林/周线一律消费共享基础设施 [ma_infra](plan-ma-infra-shared-2026-09-21.md)（`sma_asof`/`sma_series`/`bb_asof`/`weekly_sma_asof`）；导出器与书内不自写均线；周线防泄漏（调用方先截 ≤D、末端未完成周可参与）在 ma_infra 测试 pin。 |
| **R9** | `limit_up_chase` 本书 pin **False**（引擎默认 True 的 T+2 追买违反「skip_buy 消耗信号」FSM）。 |
| **R10** | **（V5/V8 改述）**单一算法来源 = 可复现 + 避免两套数值并存：Rust 两层失败（逐窗 NaN→该日该码 skip；`PyValueError`→按码捕获 skip+计数），**不切换算法**（归档 §2 的「回退 Python canonical chip」被本条**显式改口径**，登记于页眉）；统计窗前 edge 置假在导出器层；导出器前置剔 volume==0 bar（V14，export9 `:126` 先例）。 |

## 5) P\* 人裁点（评审重点；各附建议）

| ID | 问题 | 建议 |
|---|---|---|
| **P0 cyqk 语义（对抗层新增，必答）** | 归档 plan §3.3 自认「cyqk_c>0.70 在仓内文档是抛压区，本轮只验证框架」；2026-09-07 consensus 只裁映射未裁语义方向。把疑似抛压阈值当多头入场是否成立？ | 选项 a：按归档口径**框架移植先行**（定位=框架验证，非策略有效性），全市场信号统计并行另出；选项 b：**统计先行**，0.70 上/下分组前瞻收益仲裁后再写引擎。建议 a（7 份静态档案在、可比性强），人裁。 |
| **P1 成交时点重裁** | D+1 开盘买怎么落 CSV 时钟： 买钟加「次日开盘」事件；日线近似=信号次日收盘成交（偏差入 HELP_LOCK）。| 建议 a/b 双跑对照，以分钟 b 为准（v8 跨引擎先例）；**对抗层修正：09:30 新钟须带涨停/一字板/volume=0 拦截测试（domain-safety）**。 |
| **P2 卖出时点** | 次日开盘卖可直接用 `pending_exit`（现成）？分钟引擎是否也开盘卖？ | 日线 `pending_exit` 原样；分钟书在 09:30 首根按开盘价评 pending 卖（与买钟对称）。 |
| **P3 导出器形态** | 独立 `export_strategy11_pool.py`（9/10 先例）还是引擎内信号？ | 独立导出器：契约日 CSV、可审计；**复用 TR store 生态的装载/股本解析/bridge 件；cyqk 一律 `compute_cyqk_series(window=200)` 现算，禁读 store `cyqk_t` 与 store 布林（window=1000 世界）**（V10）；`--start/--end/--sample/--universe`。 |
| **P4 抽样 vs 全市场** | 保留原 30 只 seed 抽样，还是全市场池？（对抗层重开：7 份静态档案在，seed parity 可判读） | 导出器两种模式都留：`--sample seed=20240907`（对照静态档案）与全市场；**主交付建议改为 seed-30 parity + 全市场敏感性**（对抗层反题，人裁）。 |
| **P5 统计窗与预热** | 加载从 2022-07-01 起覆盖 200 日窗+20 周线；统计窗 2024-01-01 起，窗前 edge 置假。 | 沿用归档口径；导出器 manifest 记录窗与预热深度。 |
| **P6 对照验收** | 与 Cerebro 静态档案怎么比？ | 不求 byte parity（引擎/费用/档位已换）；出差异清单（成交价差、费差、skip 语义差）**+ sanity bounds（同 universe 信号数、成交笔数数量级一致性校验，防清单不可判读）**入 reviews；30 只 seed 模式跑同 universe 对照。 |
| **P7 布林/周线细节漂移** | std ddof=1、周线 asof 只 backward、末端未完成周可参与——沿用？ | 逐条沿用（归档 plan 对抗评审已锁），不重开。 |

## 6) 非目标

- 不做分钟级 chip、实盘、LEBS 接线。
- 不改 `oskh_factors` / `turnover_resist` / `qlib_cost` 公共 API。
- 不重跑 classic 对抗（归档 r1/r2 已锁口径；本 plan 评审走现行 fan-out）。
- 不求与静态档案数值一致（P6 差异清单即可）。

## 7) 切片（各一 commit，带完成定义）

| 刀 | 内容 | 完成定义（DoD） |
|---|---|---|
| **A** | `backtest/research/strategy11_rules.py` 纯函数：**前置=ma_infra 代码已合并（今 v1.0 GO、PR #150）**；消费其 `sma_series`/`bb_series`/`weekly_sma_series`（**序列件，禁逐日 `*_asof`**）；`edge_condition(...)`、`exit_signal(t_close, prev_close, sma5)`（SMA5 含/不含 T 收盘二选一 pin，V16/对抗 Y6）+ **hold_mode 两段 FSM pin**；record/HELP_LOCK（印 P0 定位「cyqk>0.70 抛压区、框架验证非已验证多头」+「D-1 NaN≠边缘/等号 fail-closed/买入日禁卖」三条原文）；`tests/test_strategy11_rules.py` | 无引擎/chip import；归档 §2 逐条有 pin |
| **B** | `scripts/data/export_strategy11_pool.py`：front 价装载（V1）+ 周线/cyqk 200 日窗（`compute_cyqk_series`，**网格预检+250k 上限 skip 计数**、两层失败按码捕获）+ asof 股本 public 薄壳（V7）+ **契约日 T=该股首根 bar 且 ≤4 自然日**（V2）+ **统计窗前 edge 置假** + **`rejected.csv`（date,symbol,reason）+ manifest 计数**（stale/grid/skip）+ 前置剔 volume==0（V14）+ 全市场滤 ST 排 688（V9）+ `--sample/--universe` | data-free 单测（合成 OHLC+股本）；拒绝 `stock_pool/`；池 CSV 契约 pin（裸六位无表头 LF、`validate_pool_dir` 冒烟）；manifest 记 adjust_type/pyd `__file__`+版本/耗时基线；`--help` 带 §2 要点与契约日口径 |
| **C** | 引擎接线：买钟按 P1（**a=日线保持契约收盘不造新钟；b=分钟 09:30 开盘**，涨停/一字/volume=0 拦截与计数器挂 b）+ **买入日 EOD 评估钩子（V4：在当日买循环之后、T 收盘写 pending_exit；卖走既有 `t1_sellable` 次日开盘，无旁路）** + 分钟侧 pending_exit 消费（**09:30 成交、跌停 defer 留 pending 次日再评**）+ **sold-today 集合买侧过滤**（V11）+ `apply()` 必返 `take_profit/record_params/limit_up_chase=False` 三键（V12）+ 卖书注册 `version11`（别名 `11/v11/version11`，`FORBIDDEN_DEFAULT_STOCK_POOL` 增项，tag `v11`）+ AGENTS.md 增行改预留句 | 引擎级测试：D+1 成交、skip FSM 映射（含 **chase pending 为空**回归 pin，V15）、卖出日不重入（sold-today）、买入日禁卖（t1_sellable 天然挡 + pin）、**EOD 时序**（T 买入当日评估产生 pending_exit、T+1 开盘成交，V16）；`--strategy 11 --help` 冒烟（日线+分钟双 CLI） |
| **D** | 对照冒烟：seed=20240907 30 只同 universe vs 静态档案差异清单 + 全市场池一跑；结果记 reviews（数字不入库） | 差异清单三分类（成交价/费用/skip 语义）成文 |

## 8) 验证命令

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
D:\anaconda3\envs\vanna312\python.exe -m ruff check backtest/research/strategy11_rules.py scripts/data/export_strategy11_pool.py tests/test_strategy11*.py
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_strategy11_pool.py --help
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py --strategy 11 --help
```

## 9) 代码落点

- 新：`backtest/research/strategy11_rules.py`、`scripts/data/export_strategy11_pool.py`、`tests/test_strategy11_rules.py`、`tests/test_export_strategy11_pool.py`、（C）`tests/test_strategy11_engine.py`
- 改：`csv_strategy_books.py`（注册 + FORBIDDEN 清单）、（按 P1）`csv_minute_backtest.py` 买钟、`tests/test_csv_strategy_books.py`（清单 pin）、`AGENTS.md`（Research entries + 预留句回写）

## 10) 修订程序

v0.x 草稿 → 主笔侧对抗层（✅ 2026-09-21）→ 四稿 fan-out + merge-consensus（✅ 2026-09-21，V1–V17）→ **P0–P7 + V2 契约日确认 + V9 ST/688 处置** 逐条人裁 → 修订到 vN、状态改「✅ 已人裁 GO（commit hash）」→ 走 [Codex 交接工作流](workflow-codex-handoff.md)（**门槛：ma_infra（PR #150）已合入；实施 PR 交 grok bot VM codex**）。

> 与 strategy12 plan 的顺序建议：两书互不依赖可并行评审；实施建议 12 先（引擎部分减仓能力独立）或 11 先（导出器复用 PR #146 TR store 刚落地的刷新链）皆可，人裁时定。
