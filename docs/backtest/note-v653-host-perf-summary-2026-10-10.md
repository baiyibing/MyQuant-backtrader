# 6.53 分钟宿主性能：给下一刀 agent 的总结（2026-10-10）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-10（Asia/Shanghai） |
| 基线 HEAD | `96927c5`（`master` = `github/master`） |
| 配方 | `--strategy version6_53 --start 20251023 --end 20260909 --cash-total 27000000 --name-budget 10000 --rule-profile industry` |
| 性质 | 扫描与装载加速。卖点未改，未开新版本号。6.53 仍在 `PENDING_BOOK_NAMES` |
| 过程日记 | [note-independent-ladder-numba-2026-10-09.md](note-independent-ladder-numba-2026-10-09.md) |

成交核与档位见 [engine-ashare-correctness.md](engine-ashare-correctness.md)。分钟成交假设见 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

本文只收 **git 日志里的性能提交** 和 **2026-10-10 尚未提交的重新进核**。同周的策略 6.17–6.53 规则书、行业档费率、v7 折叠是别的账，不要当成加速结果去比净值。

---

## 1. 给接手的人

目标是缩短 **产品 `run()`** 的 6.53 全窗。比较用模拟分相（`profile_sim.json`），不要用冷缓存墙钟和热缓存墙钟直接比。

下一刀做模拟，仍在 CPU：把「每根动作 bar 重新进一次 Numba」的 Python 包装做轻。数组和加仓成本不要每次重造。验收是同一配方下成交键与 `daily_equity.csv` 不变，`held_scan` 下降，`post_group` 不再比 0.4s 的基线更慢。

单次新进程的墙钟里，更大的一块是分钟缓存装载（热文件 14.9s）。那是另一刀，见 §5。

---

## 2. 已提交的性能刀（2026-10-09）

`master` 上按时间顺序。数字来自过程日记里的全窗，**都不是锁定比分**。

| 提交 | 说明 | 全窗上看到的变化 |
|---|---|---|
| `89d917e` | 分钟宿主默认埋点。`OSKH_PROFILE_SIM=0` 关掉。不改成交 | 之后才能把装载和 `held_scan` 分开 |
| `dec3a0b` | 除权图按列下推；日线/分钟把 exdiv、指数闸计入分相 | 去掉未计时的 `adj_factor` 扫描。热点落到持仓扫描 |
| `c8d3021` | 6.x 独立持仓梯子进 Numba。安静 bar 跳过已放弃（成交漂移） | 相对不跳：墙钟 380.6s → 145.9s，模拟 329.9s → 100.2s，`held_scan` 256.9s → 46.4s。净值随跳过/前缀路径变过，不能当成绩 |
| `7c1f71f` | 停泊/红股锁改对象身份；`day_spans` sidecar；日线文件缓存；进程内 `bar_store` | 开核全窗净值 44,594,778.35（+65.17%），成交 9662，同进程三次短窗对齐。短窗墙钟 77.1s → 53.5s，省的是解码 |
| `79de799` | `DayBuyQuotes`；买侧 ST 闸；开盘跌停不再让 Numba 丢掉收盘计数 | 模拟 101.6s → 66.4s。`pool_buy` 21.6s → 9.7s。`day_spans` 26.3s → 0。净值 44,341,528.00（+64.23%），成交 9621，`skip_st=5`。墙钟 199.9s 是日线 cache miss 加分钟解码 91.2s |

`c8d3021` 的核只返回第一根必须交给 Python 的 bar，以及这根之前的峰值。账本、T+1、跌停、费用留在原来的 Python 成交路径。`sell_gate` / `exit_plan` / 自定义 `fill_config` 整段回 Python。关核：`OSKH_INDEPENDENT_NUMBA=0`。

`7c1f71f` 之后，同一进程第二次 `run()` 走 `bar_store`（`OSKH_BAR_MEM=0` 关掉）。跨进程仍读文件缓存。当时写明未做 mmap / Redis。

---

## 3. 尚未提交（2026-10-10 工作区）

相对 `96927c5` 的本地改动：

- `backtest/research/csv_minute_backtest.py`：`_drive_independent_window`。动作 bar 结算后按新的峰值 / `scale_steps` / 加仓成本再进同一核
- `tests/test_independent_numba_ladder.py`
- 过程日记补了 §2.8

回退：`OSKH_INDEPENDENT_RESUME=0`（一次前缀 + Python 尾巴）。游标已经尝试过离场（`first_exit_attempted`）、pending、`side_pending` 时整段留在 Python，避免把后面的高点写进已冻结的峰值。

本机两次全窗，`PYTHONHASHSEED=0`，产品 `run()`：

| 项 | `industry_baseline_h0`（冷缓存，算法同 §2 末行） | `industry_resume_h0`（文件缓存命中） |
|---|---:|---:|
| 模拟 | 46.1s | 16.6s |
| held_scan | 30.4s（62%） | 8.8s（49%） |
| post_group | 0.4s | 0.9s |
| pool_buy | 6.7s | 3.4s |
| 分钟装载 | 725.7s（写缓存） | 14.9s |
| 墙钟 | 786.8s | 36.1s |
| Python 评估 bar | 542,018 | 16,270 |
| Numba 重新覆盖的 bar | 0 | 525,763 |
| 净值 / 成交 | 44,341,528.00 / 9621 | 相同 |

`trades.csv`、`daily_equity.csv`、`pending_sells.csv` 与基线逐字节相同。`pool_buy` 变快来自缓存热度，不是这刀。`post_group` 变慢是下午重新进核的 Python 包装。

产物目录：`backtest_output/csv_minute_v6_53_20251023_20260909_industry_baseline_h0/` 与 `..._industry_resume_h0/`。

当前分钟文件缓存：`backtest_output/bar_cache/minute_none_20251013_20260909_61efabfabb98.parquet`，1.67 GB，125,781,274 行。过程日记里的 `afda45b21c12` 是更早的指纹。

---

## 4. 已经看过、先不要再开

| 方向 | 结论 |
|---|---|
| 安静 bar 启发式跳过 | `c8d3021` 已删。全窗成交漂移，人裁不再跳 |
| 把账本或 `execute_buy` 编进 Numba | 不做。`pool_buy` 热缓存下 3.4s |
| GPU / 4090 | 用不上。剩下的 16,270 根是有现金顺序的 Python 成交；52 万根安静 bar 已经在 CPU Numba 里 |
| 把现有 parquet 改 mmap | 用不上这 14.9s。mmap 压缩块省不掉解码。未压缩 OHLC+hm+ymd 约 5.2 GB，还得改日循环不再 `to_numpy` 拷一份。Mode B 的 mmap 包没有 high/low |
| 「改用 Arrow 就比 DataFrame 快」 | 读路径已经是 `pq.ParquetFile.read_row_group`。14.9s 里包含随后的 `to_pandas()` 和每只股票的 `DatetimeIndex`（`ashare_bars.read_minute_cache`）。模拟热路径用的是当天 numpy 列 |

---

## 5. 下一刀怎么选

**模拟时间的第一刀已按脑暴 P0 落地（仍在本分支）：** 每个持仓窗口只绑定一次 OHLC/`hm` 数组和梯子常数；lot 成本、均价锚和峰值仍每次刷新。有序 `hm` 的安静段用 `searchsorted` 做下标差，不再为计数逐根走 Python。日线「严格早于当日」在单调索引上走 `searchsorted`。没有 `sell_gate` 的书不再把全部昨收收成 list。成交路径没改。

**若目标是新进程墙钟：** 装载。可以从 Arrow 列直接取出 `open/high/low/close/hm` 的 numpy，跳过 `to_pandas()`。这只削 14.9s 的一部分。parquet 仍是跨进程真源。同一进程第二次 `run()` 已经走 `bar_store`，不要为这一刀再做 mmap。

两刀不要混在一次改动里。

---

## 6. 复跑

```text
set PYTHONHASHSEED=0
D:\anaconda3\envs\vanna312\python.exe -u backtest/research/csv_minute_backtest.py ^
  --strategy version6_53 --start 20251023 --end 20260909 ^
  --cash-total 27000000 --name-budget 10000 --rule-profile industry ^
  --out-dir backtest_output\csv_minute_v6_53_20251023_20260909_industry_<stamp>
```

已有目录会拒绝覆盖。分相在该目录的 `profile_sim.json`。

未授权：开新策略版本、改 6.53 卖点、把跳过接回宿主、把账本编进 Numba、用这些净值覆盖 `_opt` / `_prof`、把 6.53 锁成 golden、打开默认经济除权。

`master` 的 pytest 从 #450 起是红的。黄金已按当前引擎改过，仍不给 6.51–6.53 录 off-byte：账本默认带 `skip_st=0`；version1 同日卖出按代码序；6.47 / 6.48 / 6.50 的合成基线改到现行停泊字段。6.51–6.53 继续 pending。

---

## 7. 分钟布局四选一（2026-10-10 下午）

两套开关，互不绑定。默认仍是变长 DataFrame，成交路径和 parquet 缓存都不变。

| 开关 | 环境变量 | 命令行 | 默认 |
|---|---|---|---|
| 长度 | `OSKH_MINUTE_LENGTH` | `--minute-length variable\|fixed` | `variable` |
| 存储 | `OSKH_MINUTE_STORE` | `--minute-store frame\|array` | `frame` |

`fixed` 是每个有盘中分钟的交易日 242 槽（09:30–11:30 与 13:00–15:00）。缺的分钟留在原位，价格是 NaN，`hm` 仍是这根的时钟。空槽不成交。同一 `hm` 多行时后面的覆盖前面的。没有盘中分钟的日期不补成一天。布局在读入缓存之后才套上，不改 parquet，也不复用变长的日切片下标。

同一配方、四个新进程、缓存都是 `hit`。`PYTHONHASHSEED=0`。产物在 `backtest_output/csv_minute_v6_53_20251023_20260909_layout_<length>_<store>/`。

| 组合 | 进程墙钟 | 分相墙钟 | 分钟装载 | 模拟 | 持仓扫描 |
|---|---:|---:|---:|---:|---:|
| 变长 + DataFrame | **34.1s** | **31.1s** | 12.8s | 13.8s | 6.9s |
| 变长 + 数组 | 41.7s | 37.7s | 12.8s | **10.5s** | **4.1s** |
| 固定 242 + DataFrame | 85.6s | 81.3s | 12.1s | 33.7s | 11.5s |
| 固定 242 + 数组 | 124.1s | 119.6s | 22.3s | 14.1s | 4.7s |

四组 `trades.csv` 哈希相同：`aada3859339b91ee04da5542ac9bb5bfaf849be640298aa20fbe3743dfae111d`。期末净值都是 44,341,528.00 / 27,000,000，9621 笔。固定布局多看了 14 根空槽（持仓评估 16284 对 16270），没有改成交。

Numba 核按当天数组的长度往下扫，时间看 `hm`，不看槽位下标。变长只含真有的 bar。定长把空槽也放进循环，还要跳过 NaN。持仓扫描因此是变长数组 4.1s、定长数组 4.7s。定长没有让 Numba 更快。定长的大头是进核之前把全市场铺成 242 槽；固定 DataFrame 还在对象列上重建日切片（这一段 8.3s）。

变长数组的扫描最快，整次却不是最快。分钟缓存仍是 DataFrame。数组模式在模拟前对 2323 只、约 1.26 亿行做 `to_numpy` 并重建行号，大约 10 秒，比模拟省下的 3.3 秒多。默认路径只在真正扫到的那一天抽列。数组要在整次上也赢，得在读缓存时就直接得到列，而不是每次从 DataFrame 再包一遍。

上表就是实验记录，不是新的默认。本地过程文件不入库。

同一开关又跑了策略 9 原书的分钟入口，用来看顺序是否还在。原书日线没有这四个开关。池、窗口、资金和费率与 2026-10-10 的日线原书相同：`version9`，`exports/s9_bvot_20260101_20260909`，`20260101–20260909`，`--cash-total 21000000`，`--rule-profile industry`。先跑一次变长 DataFrame 把分钟缓存写入，下面四次都是 `cache=hit`。日线原书净值 20,512,623.31、54 笔，和分钟不是同一成交时钟，不要拿来对布局。

| 组合 | 进程墙钟 | 分相墙钟 | 分钟装载 | 模拟 | 持仓扫描 |
|---|---:|---:|---:|---:|---:|
| 变长 + DataFrame | 3.74s | 2.63s | 0.14s | 2.32s | 1.02s |
| 变长 + 数组 | 3.78s | **2.59s** | 0.14s | **2.19s** | **0.97s** |
| 固定 242 + 数组 | 4.11s | 2.95s | 0.14s | 2.33s | 1.12s |
| 固定 242 + DataFrame | 4.17s | 3.02s | 0.14s | 2.47s | 1.20s |

四组分钟 `trades.csv` 哈希相同：`8799feb6b5af40b0cce241c3d3a4a203be5fc3a72bbd0a2eb7ef2ff83dfe17d4`。期末净值都是 20,629,515.04 / 21,000,000，58 笔。

20 只股票上，变长数组和变长 DataFrame 的整次差在 0.05 秒里，分不出来。变长数组的持仓扫描仍是最短的。固定 242 两边都更慢，只是池子小，铺槽不再吃掉几十秒。6.53 上「变长数组扫描最快、变长 DataFrame 整次最快」在这本小书上仍然成立；整次差距会随股票数变小。产物目录是 `backtest_output/csv_minute_v9_20260101_20260909_layout_<length>_<store>/`，不入库。
