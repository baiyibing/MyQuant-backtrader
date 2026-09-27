# 计划 v2：分钟止损 H/L 触发 + E-R6 残留补丁（2026-09-26）

> **状态**：v2 重写（按 Kimi 评审 #213 修正），待人裁。
> **v1 → v2 变化**：撤掉与 E-R6 重复的 `--exdiv-limit-ref` 全量开关，改为瞄准 E-R6 声明的残留缺口；补齐 v1 漏掉的第二套止损代码（`minute_cash_order.py`）和 v7 入口；补齐止盈方向；补齐跌停锁定 bar 不可成交规则；补齐开关兼容矩阵。
> **依据**：调研 v2 [note-minute-bar-industry-practices-2026-09-26.md](note-minute-bar-industry-practices-2026-09-26.md)。E-R6 已落地事实见 `plan-exdiv-refprice-2026-09-16.md`（人裁 PX-1…PX-7）。

## 1. 修复一：分钟止损/止盈触发用 H/L（X-09，覆盖全部止损位）

### 现状（三处止损代码）

| # | 位置 | 触发条件 | 活跃路径 |
|---|------|---------|---------|
| S1 | `csv_minute_backtest.py:341` | `close ≤ stop` | 主引擎（默认） |
| S2 | `minute_cash_order.py:139-142` | `close ≤ stop` | `--fix-minute-cash-order`（X-02） |
| S3 | `csv_minute_backtest_v7.py` 各会话扫描 | 自有实现 | v7 独立入口 |

### 方案

新旗标 `--minute-stop-trigger hl|close`（默认 `close` = 现状，零回归）：

| 项 | close（现状） | **hl（行业标准）** |
|----|-------------|-------------------|
| 止损触发 | `close ≤ stop` | **`low ≤ stop`** |
| 止盈触发 | `close ≥ tp` | **`high ≥ tp`** |
| 成交价（bar 内触及） | close | **止损价/止盈价**（挂单假设） |
| 成交价（跳空穿越） | open（已有） | 不变 |
| **跌停锁定 bar** | 不查（现只在 bar open 查跌停） | **low 触及止损但 bar 跌停封死 → 不可成交，顺延到下一可交易 bar** |
| **止损 vs 止盈同 bar** | 顺序取决于扫描顺序 | **止损先于止盈**（保守） |
| T+1 | 扫描跳过 T+0 | 不变 |

### 覆盖范围

| 止损位 | 处理 |
|--------|------|
| S1（主引擎） | 改 |
| S2（`minute_cash_order.py`） | 同步改 |
| S3（v7） | **不接此旗标**（v7 有独立入口，在 HELP 显式拒绝，与 E-R6 "v7 不接"先例一致） |

### 与现有修复开关的兼容矩阵

| 开关组合 | 允许 | 说明 |
|---------|------|------|
| `--minute-stop-trigger hl` 单独 | ✓ | 仅 S1+S2 改触发 |
| `+ --fix-s12-price-domain` | ✓ | 正交（价格域换算不碰触发时机） |
| `+ --fix-s11-exit-domain` | 拒绝 | version11 独占，topk 无此旗 |
| `+ --fix-minute-cash-order` | ✓ | S2 同步改 |
| `+ version12` | 拒绝 | version12 有自己的分钟止损扫描，不共用此旗标 |
| `+ v7 入口` | 拒绝 | v7 独立，不接 |

### 验收锚

1. `--minute-stop-trigger close` 不传 = **逐字节复现**现有全部书。
2. `hl` 合成测试：low 触止损 close 反弹 → 止损价成交；high 触止盈 → 止盈价成交；跳空 → open；跌停封死 low 触 → 不成交顺延。
3. 真实数据 A/B：s12 分钟 + s8 分钟，close vs hl 对照。

## 2. 修复二：E-R6 残留补丁（参考价到分 + 噪声带取消 + exdiv=None 路径）

### 现状（E-R6 已覆盖的部分不重做）

`mapped_prev_close`（`exdiv_map.py:77`）已用日线因子比 k 缩放昨收 → 涨跌停基准，主路径已落地。

### 残留缺口 → 补丁

| 缺口 | 补丁 | 开关 |
|------|------|------|
| **R1 参考价未到分** | `mapped_prev_close` 返回后 quantize 到 0.01（HALF_UP），再算涨跌停 | `--exdiv-ref-fen`（默认关） |
| **R2 噪声带 ≤0.5% 不修正** | `--exdiv-ref-fen` 开时同时取消噪声带（改为任何幅度的除权事件都修正） | 同上 |
| **R3 配股价缺项** | 暂不做（配股事件在本仓数据中极罕见；如果真湖出现再单开） | — |
| **R4 exdiv=None 路径** | version12 / `--dividend-type front` 不走 E-R6——**声明不做**（这两条路径有自己的除权语义） | — |

### 实现位置

- `exdiv_map.py` `mapped_prev_close()` 加可选参数 `fen_round=True`：返回前 `Decimal.quantize(Decimal("0.01"), ROUND_HALF_UP)`
- 噪声带逻辑（`:28,302-304`）：新旗标控制下 `threshold = 0`（任何幅度都修正）
- 调用方（`csv_minute_backtest.py:803-812`）传参

### 验收锚

1. 不传 `--exdiv-ref-fen` = 零回归。
2. 合成测试：10 送 10，昨收 10.00 → k=0.5 → raw 5.003 → 到分后 5.00 → 涨停 5.50 / 跌停 4.50。不做 fen_round 会算 5.503→涨停 5.55（差半分钱）。
3. 微额分红（k=0.999，噪声带内）：开旗标后修正生效。

## 3. 不做

- **E-R6 主路径不重做**（已落地，v1 的 `--exdiv-limit-ref` 全量开关撤回——与现有 `mapped_prev_close` 重复）
- **v7 不接止损旗标**（独立入口，与 E-R6 "v7 不接"先例一致）
- **R3 配股价公式**（数据中极罕见，出现再单开）
- **R4 exdiv=None 路径**（version12 / front 有自己的除权语义）
- **无涨跌幅日**（新股首日等——`limit_prices` 无此概念，非本刀范围）
- **不改日线引擎**（日线止损 EOD close 语义自成体系；旗标仅在分钟入口注册，不进 `add_csv_backtest_common_args`）

## 4. 切片

| 片 | 内容 | 依赖 |
|----|------|------|
| P1 | `--minute-stop-trigger hl`：S1 主引擎 + S2 时序现金引擎 + 合成测试 + close 模式回归锚 + 兼容矩阵 | 无 |
| P2 | `--exdiv-ref-fen`：fen_round + 噪声带取消 + 合成测试 | 无 |
| P3 | 真实数据 A/B：s12/s8 分钟 × {close,hl} × {fen off,on} 四格 + 跌停顺延检查 | P1+P2 |

## 5. 维护

- 起草：zcode（4090 机）· 2026-09-26 · v2 按 Kimi 评审 #213 全面重写。
