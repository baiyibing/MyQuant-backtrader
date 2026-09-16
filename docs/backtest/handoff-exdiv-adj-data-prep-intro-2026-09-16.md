# 引子 · 复权 / adj_factor 数据准备调查（宿主本地 agent）

> 日期：2026-09-16（Asia/Shanghai）  
> 状态：**引子 / briefing only** — 供宿主本地 agent 调研「复权数据在湖里如何准备」；**不是** NP2 完整测量，**不是** 改引擎实现计划。  
> 父战略：[strategic-analysis-opus5-next-2026-09-16.md](strategic-analysis-opus5-next-2026-09-16.md) §3.2(1) D2 / §6 **NP2**  
> 数据 SSOT：[data/daily-adjusted-update-ssot.md](data/daily-adjusted-update-ssot.md)  
> 正确性锁：[engine-ashare-correctness.md](engine-ashare-correctness.md)（现有 E-R1–E-R4；NP2 裁决后可能落 **E-R5**）  
> 分支意图：`docs/handoff-exdiv-adj-intro` · Docs-only PR · **勿合入前改业务代码**

---

## 1. 为什么要这份交接（Why）

战略分析把 **D2「除权日语义未裁决」** 标为会污染现有 NAV 结论的正确性风险：研究链全程走 **不复权**（`dividend_type=none`），而涨跌停价、止损触发、trail 峰值全部建立在**原始价**上。除权日（送转/现金分红等）次日 open 相对「未调整的 prev_close / cost / peak」会出现结构性跳空，可能制造：

- 假 `defer_sell_limit_down`（算出的跌停档相对真实除权参考价偏高，open 被误判跌停）；
- 假 `stop_loss:gap_open` / `stop_loss:touch`（`cost` 仍是除权前买价）；
- band / trail 书（v6/v8/v10）假回撤触发（`peak` 从未按除权比例下调）。

上述机制是**从代码推演**的（见战略文 §3.2(1)），**频率与幅度尚未实测**——这正是 **NP2** 的存在理由。NP2 本意是「只读探针 → 裁决写 E-R5 或另开复权片」。

本引子把范围**收窄一层**：先让**宿主本地 agent**（能摸到 F 湖 / QMT 产物 / Windows 路径）把 **复权数据准备侧**摸清——字段、权威源、更新节奏、与 none 链回测的关系——再决定如何安全地做 NP2 只读计数。云端 box **没有**完整湖与 QMT，不适合直接跑 NP2 测量。

---

## 2. 当前回测引擎事实（BT 链 = none）

| 事实 | 位置 | 含义 |
|------|------|------|
| 日线加载根 | `backtest/research/csv_daily_backtest.py` `load_daily_bars` ≈ **L262** | `resolve_period_root("1d") / "dividend_type=none"`；docstring 写明「不复权日线（与分钟链 adjust_type='none' 对齐）」 |
| 分钟加载根 | `backtest/research/csv_minute_backtest.py` `_load_minute_from_lake` ≈ **L355** | `resolve_period_root("1m") / "dividend_type=none"` |
| 分钟 HELP | 同文件模块 docstring ≈ **L111–112** | 「复权：买卖价、涨跌停、净值全程 dividend_type=none（与日线对齐，不用 front 对照）」 |
| 涨跌停锚 | `csv_daily_backtest.py` ≈ **L352–353** | `prev_close = float(closes[-1])` → `_named_limits(code, prev_close, names)` = **原始** prev_close × (1±档) |
| 止损 | 同 ≈ **L371–372** | `trigger = pos.cost * (1.0 - stop_pct)`；`open`/`low` 与 **未调整 cost** 比 |
| 峰值 | 同 ≈ **L393** | `pos.peak = max(pos.peak, float(row["high"]))`；除权前高点不缩 |

战略登记 **D2** 同引：`csv_daily_backtest.py:262,352-353,371-372,393`；`csv_minute_backtest.py:355,111-112`。

**对照**：筹码 / 因子侧大量读 `adjust_type="front"` 或 `get_adj_factor`（如 `backtest/chip_algorithm.py`、若干 `scripts/data/full_market_*`），那是**研究因子域**，与 csv 成交核的 none 价域**刻意分离**。L2 分析层已有「除权日价域归一」雏形：`l2_analytics/ref_data.py` 用 `prev_close * cum_factor[D-1] / cum_factor[D]` 得到 D 日价域的 `prev_close_d_domain`（注释写明供涨跌停模板在除权日正确）——**成交核未接这条路径**。

---

## 3. 湖里 / SSOT 已有什么（front vs none、adj_factor、谁生产）

权威运维口径：[data/daily-adjusted-update-ssot.md](data/daily-adjusted-update-ssot.md)。注意文首：**本叉（MyQuant-backtrader）不再下载行情**；QMT / `update_adjusted_daily` / `oskh_data.backfill` 以 **原仓库（OSkhQuant / 1.3）** 为准；本仓只读 path-SSOT parquet。盒上若已有 `/workspace/OSkhQuant1.3/docs/backtest/data/daily-adjusted-update-ssot.md`，可作同文交叉核对（勿再 clone）。

### 3.1 分区与角色

| 产物 | 路径（相对湖 root / `stock_data`） | 角色 |
|------|--------------------------------------|------|
| 不复权日线 | `period=1d/dividend_type=none/symbol={CODE}/data.parquet` | **日常必下**；BT 研究链唯一价源；路径 B 与 adj 分母 |
| 前复权日线 | `period=1d/dividend_type=front/...` | **QMT ground truth**（`get_market_data_ex(dividend_type='front')`）；禁止用 back/none 本地推导 |
| 后复权日线 | `period=1d/dividend_type=back/...` | 日常默认**不下**；仅可选观测 |
| 复权因子表 | `adj_factor.parquet`（**计算产物，非 QMT 下载物**） | 列见下 |

### 3.2 `adj_factor.parquet` 字段（文档口径）

列：`date`, `stock_code`, `close_front`, `close_none`, `cumulative_adj_factor`, `adj_factor_back`

- `cumulative_adj_factor[t] = close_front[t] / close_none[t]`（干净累计前复权因子；**无除权窗口内应近似恒定**）
- `adj_factor_back[t] = close_back[t] / close_none[t]`（观测列；日常无 back 时可为 NULL）
- 代码侧同定义：`oskh_data/adj_factor.py` 模块头；`finish_adj_factor_duckdb` **只写**因子表、**禁止**再写 front/back 分区

### 3.3 谁生产 / 更新节奏（1.3 / QMT）

唯一流水线（SSOT §3.2）：

1. `detect_ex_date_changes.py` — QMT `get_divid_factors`：**检测可用 / 推导禁用**（`dr` 不得用来推 front 价或因子数值）
2. `update_adjusted_daily.py --download-only` — 增量 **none**；除权股 **delete + 全历史重下 QMT front**；非除权 **路径 B** `front_today = none_today`
3. `finish_adj_factor_duckdb.py` — 只算 `adj_factor.parquet`
4. `oskh_data.backfill rebuild --period 1d`

推荐入口：`scripts/data/run_daily_adjusted_fast.py --end YYYYMMDD`。周日 / `--force-refresh-front` / `--full` / 每月 1 号：全市场 front 重下后再算因子。

股票宇宙：QMT sector **`沪深京A股`**（约 5548）；指数/ETF **分轨**，禁止混进主 hive 全市场名单。

### 3.4 与 none 链回测的关系（预备结论，待宿主核实）

- **成交 / 涨跌停 / NAV 标记价**：现状 = none 原始价（§2）。
- **除权日定位（NP2 探针）**：对 `cumulative_adj_factor` 做**日际跳变**（或对照 detect 的除权列表）即可得到候选 `(code, date)`——战略称「免费可查」。
- **front 价**：适合因子 / 对照 / 筹码；**不能**未经裁决直接替换成交核价源（会改写全部历史 NAV 与 golden）。L2 的「D 日价域归一」思路是除权日涨跌停的**候选算法**之一，不是现成开关。
- 实盘涨跌停降级文档强调 prev_close 取自 **none**（[data/local-pre-close-for-limit-info-feasibility.md](data/local-pre-close-for-limit-info-feasibility.md) §4.2）；这与「除权日应用**除权参考价**定档」不矛盾——缺的是 **ex-div 日把 none prev_close 映射到交易所参考价** 这一步（因子跳变或 `get_divid_factors` / 交易所字段）。

---

## 4. 宿主 agent 调查清单（Investigation checklist）

请在宿主（湖 + 可选 QMT）上**只读**回答下列问题，产出 survey notes；数字可进 dated 短记，**不要**改 csv 引擎。

### A. Schema / 权威源

- [ ] **A1** 宿主湖上 `stock_data/adj_factor.parquet` 是否存在？列名是否与 SSOT 一致（`date`, `stock_code`, `close_front`, `close_none`, `cumulative_adj_factor`, `adj_factor_back`）？`stock_code` 格式是否规范 `^\d{6}\.(SH|SZ|BJ)$`（有无 Windows 路径污染）？
- [ ] **A2** `period=1d/dividend_type={none,front}` 最新交易日是否对齐？front⊆none（P2-4 口径）在烟测相关代码上是否成立？
- [ ] **A3** 权威生产者是本机仍跑的 `run_daily_adjusted_fast` / OSkhQuant1.3，还是只消费已落盘产物？本仓脚本是否已删、仅文档残留？

### B. 更新节奏与覆盖

- [ ] **B1** 日常增量：none 是否每个交易日更新？除权股 front 全历史重下的实际频率（detect 列表规模）？
- [ ] **B2** `adj_factor` 相对 front/none 的滞后（`max_stale_days=7` 等）在烟测窗内是否触发过？
- [ ] **B3** **相对 D 烟测窗 `20251023–20260909`**（见 [money-modes-v8-pername-smoke-2026-09-16.md](money-modes-v8-pername-smoke-2026-09-16.md)）：窗内有多少只代码出现 `cumulative_adj_factor` 跳变？跳变日分布？

### C. 累计因子定义与除权检测

- [ ] **C1** 确认计算式仅为 `close_front/close_none`（无 back 推导）；无除权段因子是否近似常数（噪声幅度）？
- [ ] **C2** 「跳变」阈值建议：相对变化阈值（如 `|Δf/f| > ε`）、是否需排除停牌/缺失日、是否与 `detect_ex_date_changes` / `get_divid_factors` 交叉验证？
- [ ] **C3** 跳变日是记在**除权当日**还是前一交易日？（对齐 NP2「持仓期内命中」计数）

### D. front 可用性边界

- [ ] **D1** front 是否适合作为「匹配对照价」：与 none 同窗对齐后，非除权日应近似相等（路径 B）；除权日后 front 历史被重写——对照实验要固定 **as-of 落盘日** 还是接受「最新 front」？
- [ ] **D2** 明确：**front 价直接喂成交核** vs **仅用因子修正 limit/cost/peak** vs **只做事后归因**——三者成本与 fixture 冲击差几个数量级；本阶段只调研，不选型落码。

### E. 语义陷阱（Pitfalls）

- [ ] **E1 T+1**：除权日落在买入日当日（`n_days==0`）时，止损/卖出本就不评；假止损主要威胁 **D+1 起仍持仓** 的除权日。计数时按持仓区间 ∩ 除权日。
- [ ] **E2 除权日涨跌停参考价**：交易所按**除权参考价**定档，不是简单 `prev_close_none × (1±pct)`。实盘有 `get_limit_info` / tick 上下限；BT 没有。评估「用 cum_factor 把 prev_close 映到 D 日价域」（参考 `l2_analytics/ref_data.py`）是否足够接近交易所档。
- [ ] **E3 送转 vs 现金分红**：因子跳变幅度与「假 -50% 止损」叙事的关系；小额现金分红是否在噪声带内可忽略。
- [ ] **E4 分钟链**：1m 亦为 `dividend_type=none`；若日线窗已证明影响可忽略，分钟是否还需单独数（战略默认先日线同窗）。
- [ ] **E5 与费率/配给债分离**：NP2 不要和 NP1（配给）或 COMMISSION 打包；避免一次 PR 改写多条正确性轴。

---

## 5. 明确非目标（Non-goals）

1. **不要**改 `csv_daily_backtest.py` / `csv_minute_backtest.py` 的 `dividend_type` 或 limit/stop/peak 语义。  
2. **不要**重算 / 重生成 `tests/fixtures/csv_engine_pre_er1/` 或其它 golden。  
3. **不要**开 GPU / 性能片 / CloudAgent；本工作为宿主本地只读调研。  
4. **不要**静默切换 front 成交或「顺手实现复权」——战略硬锁：复权会改写全部历史 NAV，必须**独立成片**。  
5. 交付物 = **survey notes**（可选 follow-on plan 草稿）→ 再喂正式 **NP2 只读计数**；不是本引子 PR 内完成 NP2 验收。

---

## 6. 建议粘贴的本地 agent 启动命令 / 提示词

仓库路径（Windows）：`E:\PycharmProjects\MyQuant-backtrader`  
（若用 cursor-agent Opus：`unset CURSOR_AUTH_TOKEN`；确保 `CURSOR_API_KEY` 已设；`--model claude-opus-5-thinking-high`。）

```text
你是宿主本地 agent。工作目录：E:\PycharmProjects\MyQuant-backtrader（先 git fetch && checkout master && pull）。

只读调研「复权 / adj_factor 数据准备」，服务战略 NP2 前置；不要改 csv 引擎、不要重生 fixture、不要开 GPU。

必读：
- docs/backtest/handoff-exdiv-adj-data-prep-intro-2026-09-16.md（本引子）
- docs/backtest/strategic-analysis-opus5-next-2026-09-16.md §3.2(1)、§5 D2、§6 NP2
- docs/backtest/data/daily-adjusted-update-ssot.md
- backtest/research/csv_daily_backtest.py（load_daily_bars≈262；simulate limit/stop/peak≈352-393）
- backtest/research/csv_minute_backtest.py（doc≈111-112；_load_minute_from_lake≈355）
- oskh_data/adj_factor.py；l2_analytics/ref_data.py（prev_close_d_domain 仅作参考）

湖上只读检查（路径以本机 stock_data / OSKH_* 环境为准）：
1) adj_factor.parquet schema、行数、date/code 范围、cumulative_adj_factor 描述统计
2) 在窗 20251023–20260909 内按股票检测 cumulative_adj_factor 日际跳变，输出候选除权 (code,date) 计数与样例
3) 对照 period=1d none/front 最新日与抽样对齐
4) 若有 detect_ex_date / get_divid_factors 产物，与跳变列表交叉

交付：在 docs/backtest/ 写一份 dated survey 短记（中文），逐条回答引子 §4 checklist；文末给出「能否直接开 NP2 只读计数」的 go/no-go 与缺口。不要开实现 PR。
```

可选 CLI 骨架（本机 Python / 湖路径自行替换）：

```bash
cd /d E:\PycharmProjects\MyQuant-backtrader
D:\anaconda3\envs\vanna312\python.exe -c "import pandas as pd; df=pd.read_parquet(r'F:\...\stock_data\adj_factor.parquet'); print(df.columns.tolist()); print(df.dtypes); print(df['date'].min(), df['date'].max())"
```

---

## 7. 指回战略 NP2 验收（读完 survey 之后）

正式 **NP2**（战略 §6）验收口径摘要——本引子**不替代**该片：

| 项 | 内容 |
|----|------|
| **意图** | 用 `adj_factor.parquet` 的 `cumulative_adj_factor` 跳变定位除权 `(code, date)`；在 D 烟测同窗 **20251023–20260909** 只读统计：① 持仓期内命中的除权日数；② 其中触发 `stop_loss:gap_open` / `defer_sell_limit_down` / band trail 的笔数；③ 对应 `trades.csv` 行 |
| **裁决** | 影响可忽略 → **E-R5「不复权链的已知边界」** 写入 [engine-ashare-correctness.md](engine-ashare-correctness.md)，并在日线/分钟 HELP_LOCK 点名；影响显著 → **另开**复权实施片（禁止在 NP2 内改 `dividend_type` / cost / peak） |
| **明确不做** | 改引擎语义；重算 fixture；探针进 CI（需稳定 F 湖门禁） |
| **交付** | dated 结果文档 + E-R5 **或** 独立复权 plan；只读、无业务代码变更 |

**建议顺序**：本引子 PR（docs）→ 宿主 survey notes → NP2 只读计数 PR（仍建议 docs + 可选只读脚本，默认不改成交核）→ 裁决落 E-R5 或开复权片。

**与 NP1 关系**：战略允许 NP2 + NP1(a) 合成只读片；若宿主带宽有限，**优先 NP2**（唯一可能正在无声制造假交易记录的项）。

---

## 8. 指针速查

| 文档 / 代码 | 用途 |
|-------------|------|
| [strategic-analysis-opus5-next-2026-09-16.md](strategic-analysis-opus5-next-2026-09-16.md) | D2 / NP2 定义与排序 |
| [data/daily-adjusted-update-ssot.md](data/daily-adjusted-update-ssot.md) | front/none/adj_factor 生产 SSOT |
| [data/local-pre-close-for-limit-info-feasibility.md](data/local-pre-close-for-limit-info-feasibility.md) | 涨跌停用 none prev_close 的实盘侧口径 |
| [money-modes-v8-pername-smoke-2026-09-16.md](money-modes-v8-pername-smoke-2026-09-16.md) | D 烟测窗与工件路径 |
| [engine-ashare-correctness.md](engine-ashare-correctness.md) | E-R\* 现锁；未来 E-R5 落点 |
| `backtest/research/csv_daily_backtest.py` | none 加载 + limit/stop/peak |
| `backtest/research/csv_minute_backtest.py` | none 分钟链声明与加载 |
| `oskh_data/adj_factor.py` | 因子计算公式 |
| `l2_analytics/ref_data.py` | 除权日价域归一参考（未接成交核） |
