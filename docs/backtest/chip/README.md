# 筹码 / TR 文档索引

2026-11-09 当前归属：公共数值核与 Rust 源码先归 MyQuant `myquant_factors`，
BT 的旧数值模块只做兼容转发；数据与 Store IO 调用 infra。回测专用条件组合、
策略名单生成及成交/费用/持仓规则继续归 BT。公共计算不在各消费仓复制实现。

## 当前入口

| 文档 | 用途 |
| --- | --- |
| [因子迁移与保留职责](../../engineering/factor-owner-migration-20261109.md) | 公共因子接口、迁出清单与保留 BT 的回测名单 |
| [MyQuant 接收 PR #139](https://github.com/baiyibing/MyQuant/pull/139) | 数值源码、研究入口、Rust 构建说明及接收侧验证 |
| [研究回测入口](../research-backtest-entry.md) | BT 策略书、名单输入与回测命令 |

Rust 源码在 MyQuant `myquant_factors/rust/turnover-resist` 内构建。产物通过
`TURNOVER_RESIST_EXE` 或 `CARGO_TARGET_DIR` 显式配置；BT 不再提供本地 crate，
不要求固定盘符或机器缓存路径。

## 历史设计与算法说明

以下文档保留当时的公式、对照和实现沿革，旧目录或本地构建命令不代表当前源码归属。

| 文档 | 说明 |
| --- | --- |
| [H11 / H13 盘点](chip-slowpath-inventory-2026-09-15.md) | 历史 Rust / research / Cerebro 清点；CYQ 数据 feeder 与 TR 的产品区分 |
| [CYQ / TR 边界](../plan-h13-cyq-tr-boundary-2026-09-15.md) | 历史 H13 裁定及后续归属指针 |
| [分钟筹码 profile](h14-d1-minute-chip-profile-results-2026-09-15.md) | 历史合成 profile 记录 |
| [Numba 对拍](../plan-h15-d2-minute-chip-numba-2026-09-15.md) | Python 参考实现 / 加速后端的对拍约定 |
| [换手阻力总索引](turnover_resistance.md) | 公式与运行手册 |
| [算法说明](turnover_resistance_algorithm.md) | 公式、数据口径、历史调用链与列名对照 |
| [运行手册](turnover_resistance_runbook.md) | 历史框架与研究命令；当前策略入口见研究回测入口 |
| [Rust 设计](turnover_resistance_rust.md) | 历史 Rust 实现设计；当前构建见 MyQuant 接收文档 |

## 工程约定

1. 数值公共入口为 `myquant_factors.chip.core`、`myquant_factors.cyq` 等；BT 的
   `oskh_factors`、`qlib_cost` 为薄转发，不再是算法修改位置。
2. 对拍 T / T-1 截面时，先对齐输入价格域、窗口、股本时间点及换手率分母。
3. 股本与复权沿用公共 API 的缺失/异常合同，不在 BT 增加默认数据兜底。
4. Python 与 Rust/Numba 后端归同一共享组件；差异须通过数值对拍和显式口径说明处理。
5. 历史列名 `turnover_resistance` / `turnover_resist` / `resist` 的转换遵循各入口
   既有 CSV 合同，不因为迁移更改回测输入字段。

## 历史验证记录

2026-05-15，samples=19，window=80：turnover 19/19、resist 19/19 对齐。
当时产物名为 `backtest_output/verify_turnover_resist_align_20260515.csv`。
此为历史记录，本次未读取真实行情或重跑该样本；当前迁移验证见接收记录与 PR CI。
