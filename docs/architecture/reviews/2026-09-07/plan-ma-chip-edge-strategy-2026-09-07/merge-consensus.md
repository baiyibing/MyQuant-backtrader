# merge-consensus：plan-ma-chip-edge-strategy-2026-09-07

> **主持裁**：cursor-desktop（本对话）  
> **plan**：`docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md`  
> **fan-out**：classic（2026-09-07），产物本目录  
> **对抗层**：`review-by-cursor.md`（不计独立票，已回填 v2）

## 1. 票源与有效性

| 来源 | 结果 | 是否计入事实裁决 |
|------|------|------------------|
| 对抗三路（Task） | 已吸收为 v2 | 取舍已定，本轮不再重开 |
| cursor:auto | rc=0，完整评审 | **计入** |
| kimi | rc=1，周额度 403 | 不计入（无意见本体） |
| claude | rc=1，周/月额度 429 | 不计入 |
| codex | rc=124 超时；落盘多为提示词回声 | 不计入（无独立 🔴） |
| cursor-desktop 空槽 | 指向对抗综合，不重复打分 | host |

本轮 **有效独立票 = 1**（cursor:auto）。未再开 classic 第二轮：三家 CLI 额度/超时，重跑不会补票。v3 吸收其 🔴 后直接落地。

## 2. 必查盲区（事实，以代码为准）

| 盲区 | 裁决 | 证据 |
|------|------|------|
| T+1 | D 收盘确认边缘 → D+1 开盘买；买入日不挂卖；卖出下一根开盘 | plan v2 §2；本仓 `bt.Order` **无** `Open` |
| 复权 | 日线 `period=1d` `adjust_type=front`；禁止 `load_single_stock_data` | `oskh_data` reader 默认 front；筹码 hybrid 亦 front |
| `cyqk_c` | **0–1**，阈值 **0.70** | `qlib_cost/cyq.py` `get_cyqk_c` → `get_winner` |
| 20 周均线 | `W-FRI` + `_last_day` backward asof，非 100 日 | 同构 `weekly_macd_divergence._daily_to_weekly` |
| 包边界 | CLI+Strategy 仅 `backtest/research/`；算法走 `chip_algorithm` → `oskh_factors` / `qlib_cost` | README / AGENTS |

## 3. cursor:auto 条目裁决

### 🔴 必须修 → 已写入 plan v3 并改代码

**R1. 禁止 `buy(exectype=Open)`**  
本环境 `hasattr(bt.Order, "Open") is False`。锁定：`pending_*` + 成交日 `buy()`/`sell()`（默认 Market）+ `set_coo(True)`，使委托在**当前 bar 开盘**成交。可测行为是「次日开盘成交或 skip」，不把 COO 文档字符串当 SSOT。

**R2. skip_sell 后必须保留退出状态机**  
跌停/停牌不成交时 **保留** `pending_sell` 与 `hold_mode`，下一交易日再试。成功卖出才清空。禁止 skip 后把多头留成永不退出。单测覆盖。

**R3. §1 等号与 §2 对齐**  
买入日收盘 **≤** T-1 收盘 → 次日开盘卖（fail-closed）。§1 口头「小于 / 大于」改为与 §2 同一口径。

### 🟡 应修

| ID | 裁决 |
|----|------|
| Y1 统计窗 | **吸收**。`edge` 在「统计窗前最后一个交易日」之前一律置假；成交与净值统计均从 `--start` 起。 |
| Y2 ST 5% / none 昨收 | **降入 §5**。本仓无 ST 列表 SSOT。本轮主板 10%、创业板 20%；昨收用 front，summary 声明偏差。 |
| Y3 报表 / `--help` | **吸收**。`--help` 附锁定口径；summary 含触发数、单票收益、回撤、skip 分类。 |
| Y4 COO | **部分吸收**。COO 是本状态机的实现细节，契约是次日开盘成交；不引用官方 COO docstring。 |
| Y5 S-F2 表述 | **吸收**。对抗旧句「均线只用 [-1]」已由 v2 重述：在 D 的 next 评 `cond[D]` 时 `sma` 含 D 合法。 |

### 未让步（对对抗 dissent）

用户本轮要 30 只框架试验。不改为全市场扫描，不改 `ChipDistribution` / `oskh_factors` / `qlib_cost`，不并入 rolling。

## 4. 总评

口径在复权、盈筹率单位、周均线、避开 Indicator 窗口、包边界上已对齐。吸收 R1–R3 与 Y1/Y3 后 **按 plan v3 实施**。`summary.md` 不得写因子有效。
