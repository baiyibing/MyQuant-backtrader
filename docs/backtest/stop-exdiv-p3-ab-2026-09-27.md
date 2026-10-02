# 分钟止损 / 除权参考价 P3 真湖 A/B 记录（20260927e）

日期：2026-09-27（Asia/Shanghai；PASS 于 2026-09-28 凌晨交付）。本页归档
4090 物理湖 Human-GO / re-GO 的 4090bot PASS 回报，对应 [#214](https://github.com/baiyibing/MyQuant-backtrader/issues/214)
血缘的 [计划 §4](plan-minute-stop-and-exdiv-fix-2026-09-26.md#4-切片)。实现边界见
[P1 止损触发](minute-stop-trigger-hl-p1-2026-09-27.md) 与
[P2 参考价到分](exdiv-ref-fen-p2-2026-09-27.md)。本次仅整理已提供的结果及宿主产物指针，未重跑真湖。

## 1. 共享常量与 PASS / SKIP 矩阵

| 项目 | 固定值 |
|---|---|
| 代码 tip | **`8a6d6c3`（#229 P2 + #228 P1）** |
| 宿主 / 湖 | 4090 物理湖 |
| stamp | **`20260927e`** |
| 资金 | **`5e8`（Human re-GO）** |
| 最终 PASS 窗口 | **`20251023–20260909`，s8 / s12 相同** |
| s8 | `s8_minute` / `version8` |
| s12 | `s12_minute` / `version12`，fix-on + 既有 transform |
| 格间变量 | `--minute-stop-trigger {close,hl}` × `--exdiv-ref-fen` off / on |

| 策略 | close × fen off | close × fen on | hl × fen off | hl × fen on |
|---|---|---|---|---|
| s8 | PASS | PASS | PASS | PASS |
| s12 | PASS | PASS | **SKIP（P1 拒绝 version12 + hl）** | **SKIP（同左）** |

共六个 PASS 格；s12 仅 close，不补造 hl 数字。结束日取 pool tip `20260909`，没有 `20260914.csv`。

## 2. s8 四格 PASS

| cell | NAV | ret | maxDD | buys/sells | stop/trail/force | wall_s |
|---|---:|---:|---:|---:|---:|---:|
| close_fen_off | 497,131,155.96 | −0.57% | −1.42% | 3155/3150 | 334/2543/252 | 499 |
| close_fen_on | 497,123,453.67 | −0.58% | −1.42% | 3155/3150 | 334/2543/252 | 506 |
| hl_fen_off | 496,817,555.16 | −0.64% | −1.42% | 3155/3150 | 348/2536/245 | 502 |
| hl_fen_on | 496,809,852.87 | −0.64% | −1.42% | 3155/3150 | 348/2536/245 | 505 |

## 3. s12 两格 PASS（close only）

| cell | NAV | ret | maxDD | buys/sells | wall_s |
|---|---:|---:|---:|---:|---:|
| close_fen_off | 437,706,433.22 | −12.46% | −25.25% | 64189/113495 | 4887 |
| close_fen_on | 437,706,433.22 | −12.46% | −25.25% | 64189/113495 | 4875 |

`wall_s` 为宿主回报耗时（秒），不作为性能保证。

## 4. 跨格事实与边界

- **s8 fen on**：buys/sells 相同；同一 trigger 内 stop/trail/force 相同。
  close 与 hl 的 NAV 相对各自 fen off 均减少 **7,702.29（约 −7.7k）**，相对 `5e8` 资金很小。
- **s8 hl vs close**：stop 从 **334→348**，trail 从 **2543→2536**，force 从 **252→245**；
  ret 略差（**−0.64% vs −0.57% / −0.58%**），maxDD 同为 **−1.42%**。
- **跌停顺延**：`s8_hl_fen_off=1`、`s8_hl_fen_on=1`；仅记录 hl 格，close 格未提供此计数。
- **s12 fen off ≡ fen on**：按宿主回报，本窗口 NAV 字节一致；`--exdiv-ref-fen` 在此
  version12 路径 **无可见效果**，与 R4 / version12 自有除权语义一致（P2 旗标作用于分钟 E-R6 路径）。
  此结论限定于本窗 NAV，不据此声称完整产物字节一致或其他窗口必然无差异。
- **不是默认切换 GO**：`--minute-stop-trigger` 默认仍为 **close**；`--exdiv-ref-fen` 默认仍为 **OFF**。
  仅归档 Human GO A/B，不改代码、测试、fixtures、默认值或 CLI，不合并。
- 范围外：R3 配股、R4 `exdiv=None` / version12-front 重写、#135 classic P1/P2/P4。

## 5. 首次 FAIL 与 re-GO caveat

封存 recipe 的 `21e6` **未成功**：首次 s8 起日约 `20260106`，在 #212 的资金不足 raise
语义下，于 `20260106/300163.SZ` 抛 `InsufficientCashError`。随后 Human re-GO 将资金改为 **`5e8`**。

首次 s12 单独取 `start=20260106` 抛 `PriceDomainError`：既有 transform cert 对应
**2322 codes @ 20251023**，而该起日对应 **1845 @ 20260106**。为复用既有 transform，
s12 必须采用 X01 封存全窗口；最终 s8 / s12 均用 **`20251023–20260909`**。
上表全部为 re-GO 后的 PASS 数字，不混入首次 FAIL，不代表 `21e6` recipe 通过。

## 6. 4090 宿主产物指针

相对仓库路径；原始产物不随本文入库，逐格完整目录以 RECEIPT 为准：

- RECEIPT：`backtest_output/RECEIPT_STOP_EXDIV_P3_8a6d6c3_20260927e.md`
- out-dir 模式：`backtest_output/stop_exdiv_p3_{s8_*,s12_*}_8a6d6c3_20251023_20260909_20260927e`
  （六格：s8 的 close/hl × fen off/on，s12 的 close × fen off/on）。
