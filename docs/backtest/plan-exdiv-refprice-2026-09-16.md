# Plan：除权日参考价修正片（scoped；E-R6 落地 + E-R5 收窄）

> **落盘**：2026-09-16。**v1.1**（2026-09-16 两路评审修订，见 changelog §10）。
> **状态**：📄 **v1.1 · 已评审，待人裁 GO（PX-1–PX-7，见 §3）**。评审记录：[zcode-facts](../architecture/reviews/2026-09-16/plan-exdiv-refprice/zcode-facts.md) / [zcode-arch](../architecture/reviews/2026-09-16/plan-exdiv-refprice/zcode-arch.md) / [merge-consensus](../architecture/reviews/2026-09-16/plan-exdiv-refprice/merge-consensus.md)。
> **风险档**：**L2**（正确性行为变更：v1–v6、v8–v10 在除权日的 limit/止损/trail/买侧涨停拦截判定变化；成交价与净值估值语义不变）。
> **工作流**：走 [Codex 交接工作流](workflow-codex-handoff.md)。
> **裁决源**：[er5-recheck-5e8-note](er5-recheck-5e8-note-2026-09-16.md)（人裁 2026-09-16 选 B）；[survey-exdiv-adj-data-prep](survey-exdiv-adj-data-prep-2026-09-16.md) **C2 设计锁（主源层级，本 v1.1 已改回遵守）**。
> **顺序锁**：v8 规则 v2 的**切片 D 挂本片合入后**；与 v2 的 A/B/C **同文件不同区域冲突**（两引擎文件双片同改），后合者 rebase。

---

## 0. 一句话

在**持仓期内的除权日**（事件判定：`ex_date_index` 为主源 ∪ 因子跳变 >1e-2 兜底；比例 k 恒取因子行比 `cum[D-1]/cum[D]`，**禁用 dr 数值**），把该码当日全部 open lot 的 `cost`/`peak` 与**全部 prev_close→档位换算点**按 k 一次性缩放到 D 日价域——成交价、净值估值、整条 none 价格链不动；除权假跳空止损与假跌停成交从源头消失。

## 1. 机制与边界（v1.1 按评审定稿）

### 1.1 修正动作（除权日 D、该码、有 K 的首个事件日）

```
k = cum[prev_row] / cum[D_row]        # 行到行 LAG（禁日历 D-1：停牌跨度）；k<1
对每个 open lot：pos.cost ×= k；pos.peak ×= k   # ledger 纯函数 rescale_position(pos,k)
该码当日全部 prev_close 消费点：prev_close_ref = prev_close × k
```

**prev_close→档位换算点共 5 处**（X-R3 全集，评审钉锚）：

| 触点 | 锚点 |
|------|------|
| 日线持仓环 | `csv_daily_backtest.py:260-261`（closes[-1]→_named_limits；缩放+映射须在 :266 lot 环前） |
| 分钟持仓环 | `csv_minute_backtest.py:859-867`（缩放须在 :875 `scan_held_day` 调用前；**绝不**插在 :875 与 :902-903 peak 回写之间） |
| 共享 chase | `csv_simulate_loop.py:129-131`（closes[-1]→_named_limits→chase_decision） |
| **共享 pool 买**（v1.1 补） | `csv_simulate_loop.py:195-202`（closes[-1]→_named_limits→hit_limit_up→涨停挂 chase）——不映射则除权日**系统性漏挂 chase + 涨停不拦截** |
| 实现形态 | 单一 helper（如 `mapped_prev_close(code, ds, raw_prev)`），引擎侧替换传入值 |

### 1.2 事件判定（v1.1 改回 survey C2 层级）

- **主源 = `ex_date_index.parquet`**（窗口内事件枚举；检测可用）；**兜底 = 因子行跳变 |Δcum/cum| > 1e-2 且该日无 ex 事件行**（防 ex 缺行漏检，survey G4）；
- **k 恒取 adj_factor 行比**（`LAG` 型 prev 行；ε=5e-3 以下噪声带**不修正**，PX-2）；跳变记在除权前一日的 1 起错位由「ex 主源」天然规避；
- NaN/缺因子行：跳过 + `exdiv_skipped_no_factor` 计数，不抛异常。

### 1.3 已声明的残留（E-R6 三句，评审 🔴-2 定稿）

1. **跨除权 lot 的 trades pnl/净值含 (1−k) 结构性失真**：送转不增股、现金分红不入账、估值 raw close——本片只修触发参考，**不回收历史假止损的已实现亏损**（5 笔 -196 万的回收上界仅 +35~125 万 ≈ 0.01–0.025pp，切片 D 预写防误读）；
2. **v4 SMA 门（buy_gate/sell_gate 的 closes 序列）除权日不换域**（假 ma_signal/假拒，历史行为保留，另开微片再裁——PX-5）；
3. **噪声带 ≤0.5% 不修正**：止损触发距离/止盈地板偏移 ≤0.5pp，低价股档位边缘可差 1 分。

### 1.4 边界 case 语义（评审逐案核证，全部自洽）

买入日除权的新 lot **结构性无双重缩放**（日环顺序：缩放 pass 先于 pool 买 append）；pending_exit 是 reason 非价格（无需处理）；chase 的 per_ch 是金额不受 k；同 lot 跨多事件复合 ×k1×k2；停牌跨除权：跳变落复牌首成交行=引擎可见 bar 日（adj_factor outer-merge+ffill 构建口径相容，宿主实测项保留）；除权日恰逢 pending_exit 执行/chase 到期：成交价为 D 域市价，档位用映射参考 ✓；**假跌停成交也随修正消失**（同日除权+跌停：修正前会以现实不可能的价格撮合，修正后正确 defer）。

## 2. 现锁（X-R\*）

| # | 规则 |
|---|------|
| **X-R1** | **只修参考量**：open lot 的 cost/peak（除权事件日一次性 ×k，经 `csv_ledger.rescale_position(pos,k)` 纯函数）与当日 5 处 prev_close 档位参考；**成交价、净值估值、shares、佣金、整百股、T+1、chase 判定逻辑全部不动；现金红利不入账**。 |
| **X-R2** | 数据层：`backtest/research/exdiv_map.py`（`load_exdiv_ratios(codes, start, end) -> dict[code, dict[ymd, k]]`）；**事件=ex_date_index 主源 ∪ 跳变>1e-2 兜底；k=因子行比（LAG 型，含停牌跨度）；读窗含 warmup（start−10d）**；`resolve_source_parquet('adj_factor.parquet')` 不检查存在性——模块内 `is_file()` 守卫 + try/except → **缺失/读失败 = 空 map + 一次性 stderr**（范本 `l2_analytics/ref_data.py:30-34`）；pyarrow 下推过滤只读三列。 |
| **X-R3** | 引擎接入=§1.1 的 5 触点 + 缩放顺序约束（日线 :266 前、分钟 :875 前）；**布线锁（评审 🔴 定稿）：`simulate(..., exdiv: Optional[dict] = None)` 显式参数，缺省 None=空 map；仅 `run()` 负责加载**——防宿主 golden 变湖数据依赖。 |
| **X-R4** | 行为范围 = **v1–v6、v8–v10**（v7 独立引擎独立账本，不接，明示）；golden v1/v6（注入合成 bars 无除权）必须仍绿（由 X-R3 布线保证）；新增合成除权 fixture 单测（向量表见交接 §B）。 |
| **X-R5** | 统计：`exdiv_adjusted_lots`、`exdiv_prev_close_mapped`、`exdiv_skipped_no_factor` 入 stats；summary 行**条件打印**（仅非零时输出，防 `test_np3_layering.py` 全文 golden 红）。 |
| **X-R6** | 文档：`engine-ashare-correctness.md` 落 **E-R6「除权日参考价修正」**（含 §1.3 三句残留声明）；**E-R5 收窄**（措辞按评审 §4 定稿：非除权日/噪声带近似 + 历史数字标注「修正前口径」）；两引擎 HELP_LOCK 各一行；README 一句。 |
| **X-R7** | 不做：全链复权/front 喂核；调 shares/入账红利/修 v4 SMA 域（各自另裁）；改 `ex_date_index`/湖数据；改任何 `*_rules.py`（v2 片领地）；非事件日任何调整。 |

## 3. 人裁点（PX-1–3 维持默认；PX-4–7 新增）

| # | 问题 | 建议 |
|---|------|------|
| PX-1 | 修正作用于 v1–v6、v8–v10（正确性修复非 v8 专属；v7 不接） | 是 |
| PX-2 | 噪声带 ≤0.5% 不修正（E-R5 收窄声明） | 是 |
| PX-3 | 买入日除权的新 lot 不调整（结构性保证） | 是 |
| **PX-4** | **检测门改回 survey C2**：ex_date_index 主 ∪ 跳变>1e-2 兜底；k 恒因子比 | **是**（否则 145 个噪声日错误缩放，违 X-R7） |
| **PX-5** | v4 SMA 门除权日换域：本片只声明残留，另开微片 | 是（默认声明；并入则扩爆炸半径） |
| **PX-6** | E-R6 残留三句 + 切片 D 预写回收上界 +35~125 万 + 已交付文档加「修正前口径」脚注 | 是 |
| **PX-7** | X-R4 措辞（v7 不接）+ 切片 B 增「假成交消失」断言 | 是 |

## 4. 切片

从当时 master 开 `feat/exdiv-refprice`。A/B 分 commit。

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · 数据层** | `exdiv_map.py`（事件门 ∪ 兜底、LAG 行比、warmup 窗、缺失空 map）+ 单测（复用 `test_exdiv_hold_hits.py:137-163` 合成 parquet 模式；日期列双兼容 str/datetime 经 `normalize_date`） | data-free pytest 绿；CI 零影响 |
| **B · 引擎接入** | 5 触点 + `rescale_position`（csv_ledger 纯函数）+ `simulate(exdiv=)` 布线 + 三个 stats 条件打印 + 合成除权 fixture 单测（**评审向量 T1–T16**，必收 T1/T3/T4/T5/T8/T9/T11/T14/T15） | 全量 pytest 绿（含 np3_layering golden）；v1/v6 golden 绿；空 map 下 fixture 窗 trades 与 master 逐字节一致 |
| **C · 文档** | E-R6 + E-R5 收窄（评审措辞）+ HELP_LOCK×2 + README 一句 + **三份历史文档加「修正前口径」脚注**（er5-recheck / np2-host-note / 资金短记）+ 本 plan 回写 | review |
| **D · 宿主验证**（非合入门） | v1 规则重跑 5 亿分钟：预期止损 149→**~120–144**（下界 144=5 笔假止损消失；混合带部分转持有）、总亏损回收**上界 +35~125 万（≈0.01–0.025pp）**——短记预写防「12% 回收」误读；对照 research_false_stops 前后 | 短记落 docs；完成后**放行 v2 切片 D** |

## 5. 验证命令

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
# 无湖对照（真实旋钮是参数注入或 OSKH_SOURCE_PARQUET_ROOT，不存在 OSKH_ADJ_FACTOR env）：
#   simulate(..., exdiv=None) fixture 窗 trades 与 master 基线逐字节一致（测试内断言）
```

## 6. 代码落点

| 文件 | 动作 |
|------|------|
| `backtest/research/exdiv_map.py` | **新建** |
| `backtest/research/csv_ledger.py` | **仅新增纯函数 `rescale_position(pos, k)`**（不改既有签名；评审定稿） |
| `backtest/research/csv_daily_backtest.py` / `csv_minute_backtest.py` | 5 触点接入 + simulate 布线 + stats + HELP_LOCK |
| `backtest/research/csv_simulate_loop.py` | chase/pool 买侧的 prev_close 映射（经 helper 传入，不动判定逻辑） |
| `tests/test_exdiv_map.py`、`tests/test_exdiv_refprice_engines.py` | **新建**（T1–T16） |
| `docs/backtest/engine-ashare-correctness.md`、`README.md`、三份历史脚注 | 文档 |

禁止改：任何 `*_rules.py`、成交核 E-R1–E-R4 语义、v7、湖数据。

## 7. 风险（v1.1 收敛后）

- 与 v2 片同文件不同区域：后合者 rebase；v2 plan 中的 `csv_daily_backtest.py:590-598` 行号已因 NP3 过期（summarize 现在 csv_artifacts），rebase 时对语境。
- 停牌跨除权的宿主实测项保留（facts §3：(a) 占位行 (b) front 连续性 (c) 28 起无因子行码）——切片 D 顺带跑最小验证脚本。
- `_warn_authority_env_missing` 的 stderr 与本片一次性提示叠加：测试 capsys 预留。
- 除权日净值视觉跳变仍存在（估值 raw close，真实低估非仅视觉）——E-R6 声明 ① 覆盖。

## 8. 修订程序

改 X-R\*/事件门/k 定义须改本文并回写。全链复权永不进本片。

## 9. Changelog

- **v1.1**（2026-09-16，两路评审）：检测门改回 survey C2（ex_date_index 主 ∪ 跳变>1e-2 兜底，PX-4）；补 pool 买侧档位映射（第 5 触点，T9）；simulate 布线锁 `exdiv=None` 参数（防 golden 湖依赖）；k 改行到行 LAG（停牌跨度）；读窗含 warmup；cost/peak 落点定稿 ledger 纯函数 `rescale_position`；E-R6 残留三句 + 回收上界预写（PX-6）；v7 不接（PX-7）+ 假成交消失断言；stats 三键条件打印；验证命令修正（OSKH_SOURCE_PARQUET_ROOT）；v2 冲突面措辞改「同文件不同区域」。
- **v1.0**（2026-09-16）：初稿。
