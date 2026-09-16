# NP2 除权持仓命中 · 宿主计数短记（E-R5 vs 复权片 裁决输入）

> **日期**：2026-09-16。**执行**：宿主本机 agent（zcode）；master `b528f3a`（#74 探针已合）。
> **对象**：[handoff-exdiv-adj-data-prep-intro](handoff-exdiv-adj-data-prep-intro-2026-09-16.md) §7 / [survey](survey-exdiv-adj-data-prep-2026-09-16.md) §3 设计锁的正式 NP2 计数。
> **命令**：`report_exdiv_hold_hits.py --trades <BUY/SELL 过滤后的 trades> --ex-date-index F:/stock_data/ex_date_index.parquet [--adj-factor ...]`。
> **探针缺口记录**：真实 trades.csv 含 `EOD_MARK` 行，#74 探针报 `unknown side 'EOD_MARK'`——本次宿主侧以 `grep -E ',(BUY|SELL),'` 过滤绕过；**建议探针小修**（跳过或显式支持非 BUY/SELL 行），不阻塞裁决。

## 1. 计数结果（D 烟测同窗 20251023–20260909，主源 ex_date_index）

| 口径 | daily（272 lots） | minute（864 lots） |
|------|------------------:|-------------------:|
| 持仓期命中除权的 lots（T+1 起） | **22（8.1%）** | **17（2.0%）**（事件 18） |
| 其中 `stop_loss:gap_open` | **0** | **2**（000686.SZ、002242.SZ） |
| 其中 defer_limit_down | 0 | 0 |
| 其中 band_trail（`trail:band:*`） | 10 | 4 |
| 其他（多为 `stop_loss:touch`） | 8 | 8 |
| 期末仍持仓（open lot） | 4 | 3 |
| parity（ε=5e-3） | 22 命中中 19 有因子跳变；1 起跳变被 ex index 漏（traded hold） | — |

## 2. 幅度富化（daily 22 起，join adj_factor 跳变 + 退出距除权天数）

**「可信假触发带」= 因子跳变 >1% 且 退出距除权 ≤2 天：4 笔 / 272 lots = 1.5%**（外加 1 笔边界：000686.SZ 当日 trail:band:15、+0.94%）：

| code | ex_date | 退出 | 退出-ex | reason | 因子跳变 |
|------|---------|------|--------:|--------|---------:|
| 000715.SZ | 20260610 | 20260611 | +1 | stop_loss:touch | +1.33% |
| 300335.SZ | 20260521 | 20260521 | 0 | stop_loss:touch | +1.52% |
| 000685.SZ | 20260715 | 20260717 | +2 | trail:band:2 | +3.57% |
| 002142.SZ | 20260716 | 20260716 | 0 | trail:band:2 | +2.85% |

其余命中：9 起幅度 ≤1%（小额分红/噪声带，非假触发主嫌疑）、多起退出距除权 70–113 天（与除权基本无关）、4 起期末持仓。G4 差集（ex−adj=4 / adj−ex=1,852）与 survey 预期一致（1,852 为舍入噪声群）。

## 3. 裁决建议：**E-R5「不复权链的已知边界」**（暂不开复权实施片）

依据：

1. **量级**：可信假触发 ≤ 4–6 笔 / 两引擎合计 1,136 lots（**≤0.5%**；daily 口径 1.5–2.2%）；D2 最担心的 `gap_open` 全窗仅 **2 起**（分钟）、`defer_limit_down` **0 起**。
2. **成本不对称**：复权修正 cost/peak/limit = 改写全部历史 NAV + 全部 golden + 跨日线/分钟双引擎语义裁决（引子 §5 硬锁：必须独立成片）；对 ≤0.5% lots 的修正收益不成比例。
3. **可观测**：探针已可随时重跑；E-R5 落 `engine-ashare-correctness.md` 后，该边界从「无声污染」变为「已登记、可复测的已知近似」。

**E-R5 建议内容**：csv 日线/分钟链全程 `dividend_type=none`，cost/peak/limit 参考价不按除权调整；宿主实测（20251023–20260909、v8 per_name）持仓期除权命中 daily 8.1%/minute 2.0%，其中可信假触发 ≤6 笔（幅度 1–4%）；两引擎 HELP_LOCK 各加一行点名。数字证据：本短记 + survey。

**重开条件（触发即重跑探针再裁）**：①止损档收紧至 <10% 或 trail 地板整体上调；②名单池切换到高分红/高送转风格；③分钟链成为主研究面（gap_open 集中地）；④任何 NAV 对比结论差距落在 <1% 量级时。

## 4. 待办（不阻塞裁决）

- #74 探针小修：支持/跳过 `EOD_MARK` 行（本短记头部已记复现绕法）。
- 分钟 17 起命中的幅度富化未做（daily 已足够支撑裁决；如需对称可后补）。
