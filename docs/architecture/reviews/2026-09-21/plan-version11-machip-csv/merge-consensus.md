# merge-consensus：plan-version11-machip-csv v0.3（2026-09-21）

四家独立评审（codex 330s / kimi 593s / cursor:auto 1235s 含一次空输出重试 / claude 746s，全 rc=0，含 5 组实验）。
证据裁决，不投票；cursor-desktop 席主持回避。**分歧记录**：claude 总评「修两处 🔴 可进实现」被 cursor 明确反对
（「R1 会在除权日系统性改信号、R2 让停牌票交易集分叉、R3 两把锁必破一把、R4 旁路会在买入日卖出」）——
采严格派：V1–V8 全修后待人裁。四家对 P0–P7 建议方向**一致**（P0=a 框架先行、P1 分钟为准、P4 seed parity 主交付）。

## 证据裁决表

| # | 面 | 裁决 | 证据（多路独立收敛） |
|---|---|---|---|
| **V1** | §1 转录**丢「价格」行**（归档 §2:31 `adjust_type=front`） | **成立（3/4）** | codex R3/claude R1/cursor R1：引擎与先例全是 none（`csv_daily_loader.py:108`、`ashare_bars.py:128`、`export_strategy9_pool.py:141`）→ 除权日假筹码簇/假收阴卖/假突破。**裁决：信号侧 front、执行侧引擎现行（none + `mapped_prev_close`），manifest 记 adjust_type；R4 的「除权」限定执行侧** |
| **V2** | 契约日 T 定义缺位 | **成立（2/4 但决定性）** | claude R2/cursor R2：池 `skip_no_bar` 当日即消耗（`csv_simulate_loop.py:260-263`）→ T=市场次日会静默丢停牌票。**裁决：T=该股 D 后首根有 bar 的交易日且 D→T ≤4 自然日；超限不写池，manifest 计 `skip_buy(stale)` 并记原信号日 D** |
| **V3** | R3/R8 周线归属互斥**仍未回写**（即 ma_infra 共识 C9，主笔当时押后） | 成立（cursor R3 独立重申） | v0.3 R3 仍写「复用 oskh_factors」。**裁决落地：R3 只锁 chip→`compute_cyqk_series`；周线一律 `ma_infra.weekly_sma_series/asof`；`_daily_to_weekly` 保持私有；切片 A 前置=ma_infra 代码已合并（今 v1.0 GO + PR #150）；全市场用序列件，禁逐日 `*_asof`（~3M 次 resample 级）** |
| **V4** | 切片 C「t1_sellable 旁路」措辞错误 | 成立（cursor R4） | P2 说的是 pending_exit 原样（次日开盘），不是旁路；旁路=买入日能卖，违反 §1「买入日禁卖」。**裁决：删「旁路」二字；EOD 钩子在当日买循环之后用 T 收盘写 pending_exit，卖走既有 `t1_sellable` 次日开盘（`csv_daily_backtest.py:344-349` 同因同价）；分钟侧 T 末根后写 pending、09:30 成交** |
| **V5** | cyqk 失败**两层契约**被压成一句「全 NaN」 | **成立（2 组实验）** | kimi E2/E3 + cursor Y5：① 窗内坏日→**仅含该日的窗** NaN（E2：shares[0]=0 只毒 out[199] 前后）；② 形状不等→**抛 `PyValueError`**（`lib.rs:109-112`；E3 实测，与仓内 `algorithm.rs:448-456` 源码分歧，以安装 pyd 为准）。**裁决：NaN→该日该码 skip；ValueError→按码捕获 skip+计数；不换算法；切片 B 两条 pin** |
| **V6** | `compute_cyqk_series` **无网格上限**（OOM 风险） | 成立（1/4 实验） | codex Exp2：无 `max_grid_points` 参数（`lib.rs:97-115`；同模块 `compute_turnover_resist` 有 250k 闸 `algorithm.rs:560`）；600 元跨度→60k 网格 1.19s/票，妖股 2000 元跨度→~200k 网格 ~320MB×线程。**裁决：导出器自加 `窗口内 (max(high)-min(low))/step` 预检 + 250k 量级上限，超限 skip+计数；性能基线（全市场 20–35 min）写进 plan** |
| **V7** | 200 日窗**逐日 asof 股本源**未 pin + 唯一访问器私有 | 成立（1/4） | codex R2：`_get_float_shares`（`oskh_factors/chip/shares.py:60`）私有；`date=None`→**当前快照=前视**（归档明令禁止铺整窗）；Rust CLI 读 FloatVolume 快照（`data.rs:66-73`）。**裁决：源=`free_float_shares.parquet.circulating_capital` backward asof；在 `oskh_factors.bridge.turnover_resist` 加 public 薄壳；与 store `cyqk_t`（window=1000）差异写 manifest** |
| **V8** | R10 论据引错函数 | 成立（2/4） | codex R4：归档回退指 canonical chip（`core.py:70 daily_chip_distribution` 族），非等权法对比件（`:580`）。**裁决：R10 改述「单一算法来源=可复现+避免两套数值并存」，页眉登记「本条是对归档 §2 的显式改口径」** |
| V9 | §1 又丢三行（抽样/板块/股本）+ ST 处置 | 成立（3/4） | claude Y1/cursor Y4/kimi Y1：板块（沪排 688、深 000-003、创 300/301）、抽样（seed、front∩float、每板 10）、股本（逐日 asof 禁铺整窗）；无名称列时 ST 按前缀走 10% 错阈值（`pool-csv-contract.md:19-21`）。**裁决：§1 补三行；全市场模式滤 ST+排 688（或写名称列），seed-30 沿归档可不做 ST** |
| V10 | 「复用 TR store 缓存」措辞误导 | 成立（2/4） | claude Y3/cursor Y3：store 是 window=1000 世界（`export_ta_pool.py:46`、bridge 默认 `:74`），列有 `cyqk_t`。**裁决：P3 改「复用装载/股本解析/bridge 件；cyqk 一律 `compute_cyqk_series(window=200)` 现算，禁读 store cyqk_t 与 store 布林」** |
| V11 | 卖出日不重入无闸 | 成立（2/4） | claude Y2/cursor Y2：买侧只查 positions（`csv_simulate_loop.py:252-255`），先卖后买当日可买回。**裁决：切片 C 显式 sold-today 集合 + 买侧过滤** |
| V12 | 注册面三键 | 成立（2/4） | cursor Y6/codex Y4：`apply()` 不返 `take_profit/record_params` 直接 RuntimeError（`csv_strategy_books.py:137-140`）；`limit_up_chase` 是 setdefault True（`:134`）→ **False 必须在 apply() 返回值**（topk 先例 `:811`） |
| V13 | P1 a/b 标签与日线口径 | 成立（2/4） | cursor Y1/claude：日线=池契约收盘（`csv_daily_backtest.py:458`），**不另造 09:30 钟**（除非改 pool-csv-contract As-of 句）；a/b 分别标注；涨停/一字/volume=0 测试挂 b |
| V14 | volume=0 可达性 | 成立（1/4 实验） | codex R6：分钟 loader 删整日 volume=0（`ashare_bars.py:369-371`）→ FSM 该项在分钟引擎不可达（表现为 skip_no_bar）；导出器前置剔 volume==0 bar（kimi G3，export9 `:126` 先例）；两引擎判定点/计数器名写死 |
| V15 | chase 危害更正 | 成立（1/4 实验） | kimi E5/Y4：pending **30 天不过期**（实测），比「T+2 追买」更重；切片 C 加回归 pin「涨停拦截后 pending_chase 为空」 |
| V16 | 09:30 跌停 defer / EOD 次序 / hold_mode | 成立（2/4） | kimi Y2（09:30 跌停 defer 留 pending 次日再评）、claude Y4（钩子在卖→买→EOD 次序，DoD 加时序测试）、cursor 🟢（`exit_signal` 盖不住两段 FSM，加 hold_mode pin） |
| V17 | 产物与验证细节 | 成立 | codex Y1（`rejected.csv`+manifest 计数）、Y2（池 CSV 契约：裸六位无表头 LF、`validate_pool_dir` 冒烟）、Y3（symbol SSOT=`oskh_data/symbol_format.py`，plan 勿引不存在的文件名）；cursor 🟢（CI 口径 `-m "not production and not benchmark"`、补日线 `--help`）；codex/cursor 🟢（`--help` 印 P0 定位「cyqk>0.70 抛压区、框架验证非已验证多头」）；kimi Y3（差异清单按 7 份档案的消融轴 cyqk80/90/nobb/nocyqk 对照，喂 P0）；kimi G4（manifest 记 pyd `__file__`+版本）；codex R5 注记（评审时 ma_infra 为 v0.1，今已 v1.0 GO） |

## 分歧与处置

- 可 GO 门槛宽严：claude（两处）vs cursor（四条+人裁+ma_infra 进树）→ **采严格派**（V1–V8 均一两段文字级修订，全修不贵）。
- pyd 与仓内源码在长度不匹配行为上分歧（NaN vs ValueError）：以安装件实测为准（kimi E3），manifest 记 pyd 版本（V17）。

## 人裁清单（v0.4 后）

P0（cyqk 语义：建议 a 框架先行+统计并行挂靠）、P1（a/b 双跑分钟为准）、P2（日线 pending_exit 原样）、
P3（改措辞后确认）、P4（seed-30 parity 为主+消融轴对照）、P5（预热/窗）、P6（sanity bounds+消融轴）、
P7（归档细节沿用）+ 新增 V2（契约日 T 定义确认）、V9（ST/688 处置）。

## 结论

修订 v0.4（V1–V17 落进 plan：§1 补四行、§2 改两层契约+股本源、R3 落 C9、删「旁路」、
切片 B 网格闸+rejected.csv+ST 处置、切片 C 三键+EOD 次序+sold-today+chase pin）后，
按上表 9 问人裁；GO 后走 Codex 交接（门槛：ma_infra 已合入）。
