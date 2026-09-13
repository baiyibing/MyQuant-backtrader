# PR #18 评审：A 股成交正确性 + csv_ledger 拆分（E-R1–E-R4）

- 日期：2026-09-12
- 评审人：OSkhQuant1.3 侧 agent（应三仓路线图跨仓对齐要求做交叉评审）
- 对象：PR [#18](https://github.com/baiyibing/MyQuant-backtrader/pull/18) `feat/engine-ashare-correctness`（+782/−319，26 文件；CI pytest-and-gates 绿，本地引擎套件 168 passed）
- 新 SSOT：[`docs/backtest/engine-ashare-correctness.md`](../engine-ashare-correctness.md)（E-R1–E-R4）

---

## 一、做了什么

### 结构面（两件拆解）

1. **新建 `backtest/research/csv_ledger.py`（253 行）**：`Position` / `SimState` / `execute_buy` / `_sell` / 追买桶从日线、分钟两个 simulate 循环抽出共享，模块 docstring 自锁 "must not import either engine"。两个引擎的账本重复消除，循环变薄——这是本 PR 最有长期价值的改动。
2. **`market_layer.py` 升级为市场规则叶子**：`board_limit_pct`（板块前缀识别）、`is_st_name`（名单名称列识别 ST/\*ST，注意 `(?<![A-Za-z])ST` 防 WEST 误命中）、`limit_prices`（Decimal HALF_UP 到分）、`round_fen`。v7 仓位机删除本地 float 实现，改 import 同一份 Decimal 逻辑。

### 行为面（E-R1–E-R4 重开旧 U-R 四条撮合锁）

| ID | 现行为 | 评价 |
|----|--------|------|
| E-R1 | 日线+分钟**任何卖因**成交前跌停 → defer（含 trail / profit_take / force_sell / ma_signal / open_board） | 拉平了旧锁「分钟仅 stop_loss defer」的不对称，方向正确：跌停无法卖出是物理事实，不该因卖因不同而异 |
| E-R2 | 板块档位 20%（300/301/302/688/689）/ 30%（920/430/83/87/88）/ 10%（主板）/ ST 5%；**未知板块 fail-closed skip，不默认 10%** | fail-closed 与 OSkhQuant1.3 设计原则⑤同向；档位表显式枚举优于粗前缀 |
| E-R3 | 涨跌停价统一 Decimal HALF_UP 到分，禁 `round()` 银行家舍入；1.65×10% 跌停钉 1.49 | 与柜台/交易所实际分档一致，与 1.3 侧 fee 定点化方向一致 |
| E-R4 | 停牌冻仓净值用最近有 K 的 close（不用成本）；追买日无 K 保留 pending 到下一有 K 日 | 修掉了「停牌按成本估值」和「追买 pop 作废」两个已知失真 |

### 工程姿势（值得肯定，建议保持）

- 承认行为变更（6/8 历史净值会因少卖而变），不假装没变：建 pre-E-R1 合成窗快照 fixtures（`tests/fixtures/csv_engine_pre_er1/`，v6/v8 trades.csv + 生成脚本），并明文「对照看 reason / 可卖 / 涨跌停，不是旧 daily_equity.csv」——与三仓路线图原则 3「对账只比名单/reason/可卖/涨跌停」逐字对齐。
- 先锁 SSOT 文档（E-R\*）再认行为变更，unify plan 旧撮合句显式标作废并指向新 SSOT，无双权威漂移。
- 边界克制：不动 presets.py、费率、7 进 BOOKS、Cerebro 删除——行为 PR 不夹带结构扩张。

## 二、方向评价

方向正确，且与两侧既有决策严格同向：

- **fail-closed**（未知板块 skip）同 1.3 原则⑤；
- **Decimal 定点**（HALF_UP 到分）同 1.3 G1 fee 定点方向；
- **共享层叶子化**（csv_ledger / market_layer 不反向 import 引擎）是健康的拆分方式，scale 虽小但形状正确；
- 「仓名还叫 backtrader、成交核已全面自造向量化」又进一步——`engine-positioning-ssot.md` 与本 PR 文档链已同步，仓名名不副实的问题留人裁（不在本评审范围）。

## 三、发现的问题：与 OSkhQuant1.3 涨跌停口径的方向性分歧（跨仓冻结面首案）

E-R2 与 1.3 `oskh_core/board_limit.py:15-28` 存在实质分歧（1.3 侧已记入 `docs/engineering/plan-repo-industry-alignment-refactor-2026-09-12.md` §9.6）：

| 点位 | 本仓 E-R2（PR #18 后） | 1.3 `board_limit_pct` |
|---|---|---|
| 未知板块 | **fail-closed：skip_unknown_board** | **默认 0.10**（fail-open 兜底） |
| 北交 30% | 显式 920/430/83/87/88 | 粗前缀 `8`/`4`/`9`（覆盖面更大：**900 沪 B 股会被误档 30%**） |
| ST 5% | 名单 CSV 名称列 | 不在该函数（1.3 走盘前 ST 名单缓存 `cache/pretrade/daily_st_*`，机制不同） |
| 20% 档（300/301/302/688/689） | ✅ | ✅ 一致 |

缓解事实：1.3 侧涨跌停真相源是 QMT LIMIT_INFO（其原则㉑：决策价格源唯二），`board_limit.py` 仅服务离线/SQL/研究读面；本仓 E-R2 服务成交核。两仓当前各用各的，无即时正确性事故。

**建议（须三仓会签裁决，任何一侧不单方改）**：

1. 短期：维持现状，把上表当已登记分歧（1.3 plan §9.6 + 本篇即双侧登记）。
2. 中期：F 湖/口径契约文档（三仓路线图承诺的两篇契约之一，归 1.3 写）落盘时，把「板块档位表 + 未知板块策略 + ST 识别机制」写成契约条目，两仓实现对齐契约。
3. 若裁决 1.3 兜底也向 fail-closed 对齐：成本极低（`board_limit_pct` 返回 Optional + SQL 分支），但须先盘点其全部读面（含 `BOARD_LIMIT_PCT_SQL` 的消费者）。
4. 顺带勘误候选：1.3 粗前缀 `9%` 含 900 沪 B 股误档 30%，裁决时一并处理。

## 四、结论

** approve 方向，合并无跨仓阻塞项**。E-R1–E-R4 锁住了该锁的（跌停不可卖、档位正确、分档舍入正确、停牌估值不失真），csv_ledger 拆分形状正确，对照基建（快照 + 对照货币声明）是行为变更的正确姿势。唯一跨仓事项是 §三 的涨跌停口径分歧，属登记-裁决类，不阻塞本 PR。
