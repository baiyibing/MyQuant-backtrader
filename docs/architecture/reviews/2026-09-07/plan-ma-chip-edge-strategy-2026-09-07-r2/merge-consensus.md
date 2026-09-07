# merge-consensus r2：plan-ma-chip-edge-strategy-2026-09-07

> **主持裁**：cursor-desktop  
> **产物**：本目录  
> **阵容**：codex + **Cursor Kimi**（`kimi-k3-high`，替代已用尽额度的独立 kimi-code）+ cursor:auto + claude（用户已换 LLM）

## 1. 票源

| 来源 | rc | 是否计入 |
|------|----|----------|
| cursor:kimi-k3-high | 0，716s，有实验 | **计入**（kimi 席位） |
| claude | 0，1420s，复现 kimi R1 并交叉 | **计入** |
| codex | 0，1267s | **计入** |
| cursor:auto | r2 首跑 plan 空壳；ask 重跑 rc=0 / 366s 有正文 | **计入**（ask 补票） |
| cursor-desktop | host | 本文件 |

r1 只有 cursor:auto（plan）有效票。r2 首跑三票 + auto 空壳；改默认 **ask** 后 auto 补票，**四票有效**。

## 2. 裁决

### 吸收并已改代码

**kimi R1 / claude R1（停牌缺口 stale 买）**  
`pending_buy` 仅信号日后 **≤4 个自然日** 的下一根 bar 有效，否则 `skip_buy(reason=stale)`。pending_sell 不对称过期。单测 `test_pending_buy_stale_across_halt_gap`。

**codex R1（买入日收阳但仍 < SMA5）**  
按口头规则：T 收盘 > T-1 后「直到收盘 < 5 日均线」。买入日切到 `ma5` 后 **同日** 再评 SMA5。单测 `test_first_day_up_but_below_sma5_sells_next_open`。

### 吸收进 plan 字面

- 周均线：末端未完成周若 `_last_day<=D` 可参与（kimi R2 / codex Y1）
- 抽样：禁止裸写盘符，不点名不存在的 `oskh_data.float_shares` 模块（kimi R3；claude 降为 🟢 合理）
- 卖日不重入（claude Y1，锁当前实现）
- events 按 `stats_start` 过滤（kimi R4）

### 不升 🔴 / 本轮不做

- **codex R2**（把 cyqk 链做成 `oskh_factors` 公共 API）：降 🟢。研究层走 `adapt_columns` + `daily_chip_distribution` 已可跑；§5 不改 oskh_factors。
- cond 级合成单测、逐 bar 股本换手、14 日 warmup：仍属后续。

## 3. 总评

classic fan-out 现可在独立 kimi 没额度时用 Cursor Kimi 顶席位。本轮新 🔴 已回补实现。`summary.md` 仍不得写因子有效。
