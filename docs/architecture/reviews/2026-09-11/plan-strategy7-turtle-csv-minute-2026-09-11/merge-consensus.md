# merge-consensus：plan-strategy7-turtle-csv-minute-2026-09-11

> **主持裁**：cursor-desktop（本对话）  
> **plan**：`docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md` **v1.2**  
> **fan-out**：classic 2026-09-11，四家 rc=0（codex 481s / kimi 329s / cursor:auto 264s / claude 699s）  
> **对抗层**：`review-by-cursor.md`（不计票，已回填 v1.1）

## 1. 票源

| 来源 | 结果 | 计入 |
|------|------|------|
| 对抗三路 | 回填 v1.1（H-R1–R16） | 取舍已定，不重开 |
| claude | rc=0，完整 | **计入** |
| codex | rc=0，完整 + 只读实验 | **计入** |
| cursor:kimi-k3-high | rc=0，完整 + 5 组实验 | **计入** |
| cursor:auto | rc=0，完整 | **计入** |
| cursor-desktop 空槽 | 综合，不重复打分 | host |

有效独立票 = 4。无 🔴 事实互斥到需要再开一轮。v1.2 吸收下方必修后 **可进切片 A**。

## 2. 必查盲区（本 plan）

| 盲区 | 裁决 |
|------|------|
| T+1 | lots `buy_date < today`；残留次日重评。禁止仓位级 `can_sell` |
| 复权 | 股票 1m/1d、指数 1d 全程 **none**。禁 chip / front |
| 盈筹率 / 周均线 | **不适用** |
| 包边界 | `backtest/research/` 新文件；不改 `presets.py`；禁 1.3 `stop.py` / `_eval_prototype_sell` |
| 000001 | 死锁 `000001.SH` → `index/period=1d`。裸码 / `.SZ` 失败 |

## 3. 🔴 裁决（已写入 v1.2 F-R*）

| 票 | 原 ID | host |
|----|-------|------|
| claude | 暖机 10 日不够算 `MA10[T-2]` | **吸收**：preload **11** 交易日；close≤0 只查 preload∪窗口 |
| codex | 加仓时钟写成 14:55 | **吸收**：新开 14:55，加仓盘中 close |
| codex | 股票昨收未预载 → 首日全 skip | **吸收**：日线与指数同一 preload |
| codex / auto | 交替档「已触发」吃掉 T+1 残量 | **吸收**：每档目标/已卖；`frac=1−Π(1−r)` |
| codex / auto / kimi | `load_pool_days(None)` 回落 `stock_pool/` | **吸收**：v7 先解析 path，禁 None |
| kimi | A1×0.96 高于 A×0.99，减试错后次分钟易 3b | **吸收 (a)**：写明数字后果 + 单测；不发明重新穿越 |
| auto | `write_run_artifacts` vs 禁 `SimState` | **吸收**：duck-type 或自写三件套 |

驳回 / 降级：

- 不把 3a 后无止损改回 Paper（对抗未让步，四家未要求推翻人裁数字）。
- 不改佣金、不加印花税（研究对齐策略 6）。
- 除权 guard / ST·北交断言：本窗实测 0 越界、名单无 ST/BJ → 🟢 实现时可加，不挡切片 A。

## 4. 🟡 已顺手锁进 v1.2

`simulate_v7` 注入、日历=指数日、jump_nine 优先、计时成交=开盘、B=当前目标名义、`stage=nine` 粘性、reason 补 skip/defer、多票现金=名单序、H-R10=股数为 0。

未写入正文、实现时注意：独立 `cache_dir`；index loader 时间归一化抄 `_read_one_daily`；`--end` 超 `MINUTE_LAKE_END` 应报错。

## 5. 结论

v1.1 骨架（T+1 lots、闸用 T-1、涨跌停方向、禁策略 6 撮合、H-R1 解开 §4.4 死路径）四家取证后站得住。卡住编码的是暖机天数、加仓时钟、止盈残量、池路径、3b 级联语义——均已写进 v1.2。

**按 v1.2 实施。从切片 A（`strategy7_rules.py` + 单测 1–6）开工。** 不另开 classic 第二轮。
