# resist_tr_bb_1000 选股过滤 — 最小标定说明（M-004）

> **状态**：M-004 初版标定备忘（非 IC 全量回测）  
> **父文档**：[`RFC-003-m1-tr-selector-interface.md`](../../engineering/RFC-003-m1-tr-selector-interface.md)

## 规则定义

`strategies.tr_filter.apply_turnover_resistance_filter(..., rule="resist_tr_bb_1000")` 与
[`rfc-turnover-resistance-bands.md`](rfc-turnover-resistance-bands.md) Step 5 伪代码对齐：

| 条件 | 阈值 | 数据源 |
|------|------|--------|
| \|换手阻力\| | > 20 | `cross_section.turnover_resistance` |
| 价格 BB 位置 | ≥ 0.5（中轨上方） | `cross_section.bb_position` |
| TR BB 位置 | > 0.5 | `cross_section.tr_bb_position` |
| BB 就绪 | `bands_computed_at` / `tr_bb_middle` 非空 | store `require_bands=True` |

**窗口**：生产恒 `window=1000`（`CANONICAL_TR_WINDOW`）。legacy `resist_bb`（80 日 TR + 价格 BB）**未改**。

## 与 legacy resist_bb 差异

| 项 | legacy `resist_bb` | `resist_tr_bb_1000` |
|----|-------------------|---------------------|
| TR 窗口 | 80 日 inline 计算 | store `window=1000` |
| BB 类型 | 价格 BB only | 价格 BB **且** TR BB |
| 默认开关 | 研究脚本内硬编码 | `SELECTOR_TR_FILTER_ENABLED=false` |

## 启用前检查

1. 盘后 pipeline：`compute_turnover_resistance_bands.py` + `TurnoverResistanceStore.compute_and_update_bands`
2. 策略插件：`load_cross_section(trade_date, window=1000, require_bands=True)` → `apply_turnover_resistance_filter`
3. paper 调试可设 `SELECTOR_TR_FAIL_CLOSED=0`；live 保持 fail-closed

## 后续标定（Phase 2）

- IC / 多轮回测接入 `backtest/chip_factor_analysis.py` 新规则分支（不改 `resist_bb` 默认）
- 阈值敏感性：`scripts/data/chip_window_sensitivity.py` 对照 TR_1000 vs TR_80
