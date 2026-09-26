# 计划：分钟止损 H/L 触发 + 除权日涨跌停参考价（2026-09-26）

> **状态**：plan 起草，待人裁。批准后实现；不改默认（两项各挂显式开关）。
> **依据**：调研 [note-minute-bar-industry-practices-2026-09-26.md](note-minute-bar-industry-practices-2026-09-26.md)。行业标准 = 聚宽/米筐/VN.PY 的分钟引擎做法 + 交易所除权规则。
> **对应审查发现**：止损触发 = #200 X-09；除权参考价 = 新发现（调研产物）。

## 1. 修复一：分钟止损触发用 H/L，不用 close（X-09）

### 现状

`csv_minute_backtest.py:341`：止损触发条件为 `close ≤ stop_price`。行业标准为 `low ≤ stop_price`（止损）/ `high ≥ tp_price`（止盈）。后果：**漏触发**——bar 内曾触及止损但 close 反弹回来，实盘此时已离场，回测还在持有。

### 方案

| 项 | 现 | 改后 |
|----|-----|------|
| 触发判定 | `close ≤ stop` | **`low ≤ stop`**（止损）/ **`high ≥ tp`**（止盈） |
| 成交价（bar 内触及） | `close` | **止损价/止盈价**（挂单假设） |
| 成交价（跳空穿越） | `open`（已有） | 不变 |
| 开关 | — | `--minute-stop-trigger hl|close`（默认 `close` = 现状；`hl` = 行业标准） |

### 实现

- `csv_minute_backtest.py` 分钟止损扫描函数（`:341` 一带）：条件从 `close` 改为 `low`（或 `high`，方向对称），成交价从 `close` 改为 `stop_price`。
- 新旗标 `--minute-stop-trigger`，两引擎（`add_csv_backtest_common_args`）共享。
- HELP_LOCK 更新。

### 验收锚

1. `--minute-stop-trigger close` 不传 = **逐字节复现**现有所有书（默认关，零回归）。
2. `hl` 模式合成测试：bar 内 low 触及止损但 close 反弹 → 以止损价成交；high 触及止盈 → 以止盈价成交；跳空穿越 → open 成交。
3. 真实数据 A/B：s12 分钟版 close vs hl 对照（预期 hl 触发更频繁、回撤更小）。

## 2. 修复二：除权日涨跌停用参考价，不用昨收

### 现状

`market_layer.py:73-84` `limit_prices()` 用 `prev_close × (1±档)` 算涨跌停。除权日昨收 ≠ 参考价（交易所调整为除权除息价），涨跌停判定用错基准。

### 方案

| 项 | 现 | 改后 |
|----|-----|------|
| 涨跌停基准 | 昨收 | **除权参考价**（除权日）/ 昨收（非除权日） |
| 参考价来源 | — | `ashare_exdiv_economics.py` 已有除权事件数据，从中提取当日参考价 |
| 开关 | — | `--exdiv-limit-ref`（默认关 = 现状；开 = 行业标准） |

### 实现

- `market_layer.py` `limit_prices()` 加可选参数 `exdiv_ref_price: float | None`：非 None 时用之替代 `prev_close`。
- 调用方（`csv_ledger.py` / 分钟引擎的 bar 匹配路径）在除权日传入参考价，非除权日传 None。
- 参考价从 `ExDivEconomics` 事件对象获取（`ashare_exdiv_economics.py` 已有 factor / price 信息）。
- 新旗标 `--exdiv-limit-ref`，两引擎共享。

### 验收锚

1. `--exdiv-limit-ref` 不传 = **零回归**（默认关）。
2. 合成测试：10 送 10 的除权日，昨收 10.00 → 参考价 5.00 → 涨停 5.50 / 跌停 4.50。用 5.50 判定"不涨停"（而旧算法会算 11.00 误判涨停）。
3. 真实数据 A/B：含除权日的窗口，开/关对照涨跌停拦截数。

## 3. 不做

- 不改 X-01 的域换算路径（已在修复专题 X-01 刀中，另线推进）。
- 不做 intra-bar O→H→L→C 路径建模（保守假设止损先于止盈，已是标准）。
- 不改日线引擎（日线止损已有 EOD close 触发语义，自成体系）。

## 4. 切片

| 片 | 内容 | 依赖 |
|----|------|------|
| P1 | `--minute-stop-trigger hl` + 合成测试 + close 模式回归锚 | 无 |
| P2 | `--exdiv-limit-ref` + `limit_prices()` 接参 + ExDivEconomics 参考价提取 + 合成测试 | 无 |
| P3 | 真实数据 A/B（s12 分钟 close vs hl × exdiv on/off 四格） | P1+P2 |

## 5. 维护

- 起草：zcode（4090 机）· 2026-09-26 · 调研证据与行业标准见调研笔记。
