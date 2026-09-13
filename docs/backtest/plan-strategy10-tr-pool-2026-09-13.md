# Plan：策略 10 换手阻力（名单源 B）

> **落盘**：2026-09-13。
> **状态**：已编码（夹具）。
> **风险档**：L1。不改账本公式、不第四台引擎、不写 `stock_pool/`、不 `import qlib`。
> **上游**：源 B 计划口径；本片把编号落成 **version10**。

## 0. 一句话

把已有 `resist_tr_bb_1000` 写成契约日 CSV。卖点复用策略 6。验收管道，不验收「比 pred 好」。

```text
注入截面 或 宿主 TurnoverResistanceStore.load_cross_section(T, 1000, bands)
        ↓  apply_turnover_resistance_filter(..., rule=resist_tr_bb_1000)
        ↓  裸六位、LF、无 BOM
exports/s10_tr_bb1000_{start}_{end}/
        ↓
csv_daily --strategy version10 --pool-dir <s10>
```

## 1. 现锁

| ID | 锁 |
|----|----|
| **S10-R1** | 共用引擎。`strategy10_rules` 卖点 = version6。`register(version10)`。禁止新引擎。 |
| **S10-R2** | 文件名 = 买入日 T。截面 `trade_date<=T`；出现 T 之后的行立即失败。不是 Qlib `pred_minus_one`。 |
| **S10-R3** | v0 唯一规则 `resist_tr_bb_1000` / `window=1000`。不改阈值。 |
| **S10-R4** | 默认宇宙 = 湖 `period=1d` 当日有 K 的代码（B-R4）。`--universe-file` 注入。注入截面时必须同时给宇宙。禁止默认 `stock_pool/` / pred。 |
| **S10-R5** | `load_cross_section` 可注入。合入门只跑 fixture。空表 / 缺行 fail-closed。 |
| **S10-R6** | 不做 TopK。空日不写文件。`validate_pool_dir=[]`。 |
| **S10-R7** | 必须 `--pool-dir`；拒绝 `stock_pool/`。 |
| **S10-R8** | 完成 = 夹具绿。宿主 Store 实跑不是合入门。禁止用该窗 NAV 宣称规则有效。 |

## 2. 命令

```text
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_ta_pool.py --start 20260303 --end 20260908
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version10 --pool-dir exports/src_b_tr_bb1000_20260303_20260908 --start 20260303 --end 20260908 --out-dir backtest_output/s10_tr
```
