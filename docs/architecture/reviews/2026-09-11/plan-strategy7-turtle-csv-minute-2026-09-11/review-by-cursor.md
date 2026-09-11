# cursor 对抗综合（host，不计独立票）

评审对象：`docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md` v1  
三路：dissent-steelman / domain-safety / pattern-evidence（2026-09-11）  
回填：plan **v1.1**

## 1. 主笔让步（立场修正）

1. **§4.3 与 §4.4 不能同时「普通 7 成 avg×0.99」+「必须碰到 A×0.99 才减试错」。** 加 3 成后 `avg×0.99` 约在 A×1.007，先于 A×0.99，§4.4 在连续下跌上是死路径。v1.1：试错 lot 仍在的 7 成 **只**走 A×0.99 减试错，禁用综合成本 ×0.99。
2. **删除 `ProfitStrategy.Strategy7`。** 接口装不下 lots / 分档卖；v1 不做 Cerebro。
3. **禁止 import 策略 6 撮合**（`execute_buy` / `_sell` / `SimState` / `Position` / `scan_held_day` / `_buy_px` / chase）。只借湖 I/O、涨跌停 HALF_UP、佣金数字、落盘。
4. **§4.8 涨跌停写反。** 改为：涨停禁买可卖；跌停禁卖（开盘跌停 defer，不成交）。
5. **T+1 按 lot.buy_date。** 禁止仓位级 `can_sell`。
6. **指数闸 `gate[T]=f(closes[≤T-1])`。** D 收盘只决定 D+1；禁止 `StockDataReader` / `load_daily_bars` 读上证。
7. **峰值 = 已走过的分钟 high running max。** 满 9 成后才评回撤；禁止日线 high。
8. **`--pool-dir` 必填或 `OSKH_TURTLE_POOL_DIR`。** 去掉写死 `E:\...\OSkhQuant1.3\...`。
9. **本仓无 `turtle/stop.py`。** 改为禁止 import 1.3 `stop.py`；止盈手写，禁止 `_eval_prototype_sell`。
10. **计时/止损清仓后当日禁止再新开该票。**
11. **缺 14:55 不开仓**，禁止抄 `_buy_px` 14:30 回退；湖时钟按 CST 钟点标 UTC 取 `hm`。

**未让步：**

- 人裁止损数字（试错 A×0.96、减试错 A×0.99、9 成均价 ×1.01）不改回 Paper ×1.01/×1.02。
- §4.4 减试错路径保留（解开与 avg×0.99 的互斥后）。
- 3a 后「无新止损档」保留为人裁研究偏离，必须加暴跌单测，不擅自加回综合成本 ×0.99。
- 不把策略 7 做成 LEBS/Paper 同源壳（本仓也没有 LEBS）。
- 不把池 CSV 拷进本仓。

## 2. 勘误表（已回填 v1.1）

| ID | 来源 | 动作 |
|----|------|------|
| D-F1 | 7 成 avg×0.99 杀死 §4.4 | 试错仍在时只走 A×0.99 减试错 |
| D-F2 | 3a 后裸奔 | 人裁保留无新档；补暴跌单测 + 偏离声明 |
| D-F3 / S-F1 | 同分钟 / 涨跌停 | 子序 + 一 bar 先止损再级联计时；跌停 defer |
| D-F4 / P-F1 | Strategy7 | 从 §3 删除 |
| D-F5 / S-F5 / P-F7 | 缺数 fail / 闸 / 指数读 | preload 10 交易日；`gate[T]=f(T-1)`；自写 index loader |
| D-F11 / P-F2 / P-F8 | 复用策略 6 | 白/黑名单 |
| S-F2 | 仓位级 T+1 | lots `buy_date < today` |
| S-F3 | 清仓再开 | 当日禁再新开该票 |
| S-F4 / S-F14 | 峰值 / OHLC | running max(minute high)；触线只用 close |
| S-F6 | 000001 | 死锁 `.SH`；裸码失败 |
| S-F7 | chip/front | v1 禁读 |
| S-F8 / S-F9 | 14:55 | 缺根 skip；禁时区二次转换 |
| S-F12 / D-F8 | 5 日计数 | 锚日=0；第 5 个交易日开盘起；chop 后下一档=3a |
| P-F3 | 池路径 | 必填 / env |
| P-F9 / P-F10 | sell/stop | 手写规则；禁 1.3 stop / 本仓 sell |
| P-F5 | LEBS | 不以过期 README 选型 |
| D-F12 | 缓存隔离 | 行情缓存可同窗；禁止「已含规则」假设 |

## 3. 对 §3 的 host 裁决

- §3.1 文件：`strategy7_rules.py` + `csv_minute_backtest_v7.py` + 两份测试 **必要**。
- §3.2 `ProfitStrategy.Strategy7` **不必要且有害**。
- §3.3 默认绝对池路径 **不必要**；必填或 env 即可。
