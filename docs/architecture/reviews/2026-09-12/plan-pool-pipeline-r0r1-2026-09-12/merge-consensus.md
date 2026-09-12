# merge-consensus：plan-pool-pipeline-r0r1-2026-09-12

> **主持裁**：cursor-desktop（本对话）
> **plan**：`docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md` **v1.2**
> **fan-out**：classic 2026-09-12，四家 rc=0（codex 224s / kimi 677s / cursor:auto 147s / claude 446s）
> **对抗层**：`review-by-cursor.md`（不计票，已回填 v1.1）

## 1. 票源

| 来源 | 结果 | 计入 |
|------|------|------|
| 对抗三路 | 回填 v1.1（P-R1–P-R7 骨架） | 取舍已定 |
| claude | rc=0，完整 | **计入** |
| codex | rc=0，完整 + 湖探测 | **计入** |
| cursor:kimi-k3-high | rc=0，完整 + R0 窗全量 volume 实验 | **计入** |
| cursor:auto | rc=0，完整 | **计入** |
| cursor-desktop 空槽 | 综合，不重复打分 | host |

有效独立票 = 4。主持裁复现停牌占位：`F:\stock_data\stock\period=1d\dividend_type=none\symbol=000004_SZ\data.parquet` → `rows 8668 zero_vol 458`，尾部 OHLC 全 2.76 / volume 0。与 codex EXP7、kimi E1 同方向。无新的架构级互斥需要再开 classic。v1.2 吸收下方必修后 **可进人裁「按 plan 实施」**。

## 2. 必查盲区

| 盲区 | 裁决 |
|------|------|
| T+1 | 本 plan 不改卖核。买入日 `n_days=0` 不卖；止盈 `pending_exit` 次日开。C 丢零量行后停牌日计入日历但不成交。 |
| 复权 | 成交与均线同一 `none`。禁 chip / front。 |
| 盈筹率 | **不适用**。 |
| 涨跌停 / 停牌 | 档位 E-R2 不重开。名称 as-of = `last_seen` 且 `ymd<=ds`。停牌：加载丢 `volume==0` ≡ 缺 K。 |
| 包边界 | `backtest/research/` + `scripts/data/`；不改 `presets.py`；7 不进 BOOKS；胶水不是 Qlib 导出 SSOT。 |

## 3. 🔴 裁决（已写入 v1.2）

| 票 | 原 ID | host |
|----|-------|------|
| codex R1 / kimi K1 | C 默认降级前提被推翻 | **吸收**：C 默认落地。claude/auto「降级安全」只核了加载器不读 volume，未探湖 |
| auto R1 / claude R2 / kimi K4 | `max{name}` 字典序 | **吸收**：`last_seen` / `max ymd` |
| claude R1 / kimi K2 | P-R4 锁死日期来源 | **吸收**：最近 `日期:` 行 + 只认 list |
| 四方 | ≡缺 K 剔除点 | **吸收**：加载侧丢行 |
| auto Y1 等 | 双通道优先级 | **吸收** |
| claude Y2 / kimi K6 | 缺列 `return None` | **吸收** |
| kimi K5 | 分钟有 volume | **吸收**：按日合计==0 丢整日 |
| claude Y6 | `--src` | **吸收**：env 或 `../MyQuant/...` |
| kimi K9 | 持仓≠新买 | **吸收**：docstring |
| codex R2 | 旧名永久 5% | **降 🟡**：§6 双向；不加履历 |

## 4. 未吸收

- 不把 R0 转换器搬去 MyQuant（人裁本仓为主）。
- 不加 ST 名称 N 日失效开关（P-R7）。
- 不重写引擎、不改卖点、不改 `presets.py`、不做 R2/R3/R5。
- 不另开第二轮 classic：剩余 🔴 都是契约句，已落 v1.2。

## 5. 结论

v1.1 把 as-of 和包边界收干净了，但把 C 写成「湖省略停牌日」是假前提。湖写的是零量占位 K。v1.2 按 plan 自己的「探测到就落地」把 C 升为默认，剔除点钉在加载器。B/D/A 文字锁已够编码。

**可进人裁「按 plan 实施」。切片序 A → B → C → D → E，禁止 A–D 同 commit，B 与 C 不绑。**
