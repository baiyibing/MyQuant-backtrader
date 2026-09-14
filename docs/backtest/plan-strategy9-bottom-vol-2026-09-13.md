# Plan：策略 9 底量超顶量

> **落盘**：2026-09-13。
> **状态**：已编码（夹具已合 [#32](https://github.com/baiyibing/MyQuant-backtrader/pull/32)）。宿主长窗烟测 2026-09-13，见 [s9-s10-host-smoke-2026-09-13.md](s9-s10-host-smoke-2026-09-13.md)。
> **风险档**：L1（新策略书 + 名单导出；不改账本公式、不第四台引擎、不写 `stock_pool/`、不 `import qlib`）。
> **范围**：本仓。策略 10 已另片落地，不进本计划正文。

## 0. 一句话

底量超顶量是**买点**。写成契约日 CSV，再用共用引擎 + `version9` 卖点（8% 止损、满 20 个交易日强平）。禁止默认 `stock_pool/`。

```text
湖日线宇宙（或注入 OHLCV）
        ↓  bottom_vol_over_top.scan_ohlcv   # 只用 date<=T
        ↓  裸六位、LF、无 BOM、无表头
exports/s9_bvot_{start}_{end}/
        ↓
csv_daily --strategy version9 --pool-dir <s9>
```

## 1. 现锁（S9-R*）

| ID | 锁 |
|----|----|
| **S9-R1** | 共用日线/分钟引擎。`strategy9_rules.py` + `register(version9)`。禁止 `simulate_v9` / Cerebro / 第四台引擎。 |
| **S9-R2** | 文件名 = 买入日 T。量能窗 `[center-3, center+3]` **裁到 `[0, T]`**，禁止通达信式读 T+1..T+3。 |
| **S9-R3** | 顶/底 = 最近 N=120 根（含 T）HHV(H)/LLV(L)，并列取最近一根。`top_ago > bottom_ago + 10`；`1 <= bottom_ago <= 15`（底当日不发）。底后 `min(low) > 底低`。`close[T] <= 底低 × 1.10`。底窗量 > 顶窗量 × 1.2。 |
| **S9-R4** | 宇宙默认主板+中小板（10% 档：600/601/603/605/000/001/002/003）。创科/北交/ST 名不进。上市不足 250 根不进。重大利空无公告表，本轮不做。 |
| **S9-R5** | 流通盘若完整：底窗最大换手 &lt; 10% 或顶窗最大换手 &lt; 2% 则丢掉。缺流通盘则跳过增强，不否决基础信号。 |
| **S9-R6** | 输出字节同 R2：`YYYYMMDD.csv`，utf-8 无 BOM，LF，无表头，裸六位。空日不写文件。`validate_pool_dir=[]`。`refuses_stock_pool`。 |
| **S9-R7** | 卖点：止损 8%；`n_days>=20` → `force_sell:max_hold`（日线次日开盘）。`allow_add=False`。不抄 version6 回撤。 |
| **S9-R8** | 完成 = 夹具绿 + 契约字节。全市场扫描与事件研究是宿主/旁路，不是合入门。禁止用一窗净值宣称规则有效。 |

## 2. 非目标

| 不做 | 原因 |
|------|------|
| 策略 10 / TR 源 B | 用户指定先 9 后 10 |
| 默认读 `stock_pool/` | 隔夜手工池，会续写 |
| 改 `csv_ledger` / `--asof` / 1–8 卖点 / v7 | 本片只加书与源 |
| 用 NAV 给模型加冕 | 与 M5 同一禁令 |

## 3. 命令

```text
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_strategy9_pool.py --start 20260303 --end 20260908
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version9 --pool-dir exports/s9_bvot_20260303_20260908 --start 20260303 --end 20260908 --out-dir backtest_output/s9_bvot
```

宿主长窗（2026-09-13）：131 文件、`validate=[]`、相对 pred 空日 0；同日 ∩ pred 仅 1 日 1 只，∩ 手工 / 手工 Top10 全空。禁止用该窗 NAV 宣称规则有效。
