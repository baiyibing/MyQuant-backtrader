# Chip / TR slow-path inventory（H11 · Theme D soft）

- 日期：2026-09-15
- 状态：SSOT 清点（inventory only；无算法 / 卖点变更）；**H13 补边界节**
- Plan：[../plan-h11-chip-slowpath-inventory-2026-09-15.md](../plan-h11-chip-slowpath-inventory-2026-09-15.md) · [../plan-h13-cyq-tr-boundary-2026-09-15.md](../plan-h13-cyq-tr-boundary-2026-09-15.md)
- 父队列：[../plan-hygiene-backlog-2026-09-15.md](../plan-hygiene-backlog-2026-09-15.md)

## 怎么读

| Recommendation | 含义 |
|----------------|------|
| **leave** | 保持现状；主路径或合理研究消费 |
| **later offload** | 仍热；日后可考虑 numba / Rust，**本切片不动** |
| **fossil** | Cerebro / Indicator 观察退役对照；**不物理删除** |

四桶互不排斥：同一模块可「研究消费者」+「含热循环」；表内以**主角色**归类，热循环另见表 D。

**生产 TR 规范路径（已落地）：**  
`turnover-resist` (Rust) → `oskh_factors.bridge.turnover_resist` →（可选）`oskh_core.turnover_resist_bridge` → `oskh_data.turnover_resistance_store` → 策略 10 / `export_ta_pool` / `tr_filter`。

Python `oskh_factors.chip` + `qlib_cost.cyq*` 仍是**研究 / 对照 / 短窗 chip 因子** SSOT；全市场 window=1000 canonical TR 以 Rust 为准（见 [turnover-resist-bridge-selection.md](turnover-resist-bridge-selection.md)、[turnover_resistance_rust.md](turnover_resistance_rust.md)）。

---

## A. Already Rust SSOT（turnover-resist）

| Path | Role | Recommendation |
|------|------|----------------|
| `turnover-resist/`（crate + `src/` + PyO3 cdylib） | Canonical TR + BB 高性能实现 | **leave** |
| `oskh_factors/bridge/turnover_resist.py` | PyO3 FFI 主通道 + CLI subprocess fallback | **leave** |
| `oskh_core/turnover_resist_bridge.py` | Compat re-export → `oskh_factors.bridge.turnover_resist` | **leave** |
| `scripts/tr/compute_turnover_resistance_bands.py` | 单日/批 TR bands：经 bridge 调 Rust | **leave** |
| `scripts/tr/backfill_turnover_resistance_bands.py` | 宿主回填 Store：经 bridge | **leave** |
| `scripts/tr/backfill_turnover_resistance_yearly.py` | 年批回填编排（subprocess / bridge 周边） | **leave** |
| `oskh_data/turnover_resistance_store.py` | TR 日频 parquet Store（吃 Rust 行 + Python TR-BB 列） | **leave** |
| `scripts/data/export_ta_pool.py` + `backtest/research/source_b_tr_pool.py` | 策略 10 / 源 B：读 Store 截面写契约 CSV（**不**现场算 PDF） | **leave** |
| `strategies/tr_filter.py` | 名单过滤：读已算好的 `turnover_resistance` | **leave** |
| `scripts/research/benchmark_turnover_resist_bridge.py` | Bridge 选型 benchmark | **leave** |
| `tests/test_turnover_resist_bridge.py` | Bridge mode / shim / prefer_ffi（无湖） | **leave** |
| `scripts/gates/verify_tr_bridge_import_ssot.py`（H11；**H12 进 CI**） | 静态：shim / 已知消费者仍指向 factors bridge | **leave** |

---

## B. Python research consumers

| Path | Role | Recommendation |
|------|------|----------------|
| `oskh_factors/chip/core.py` | Chip 分布 / 因子 / `compute_crossday_turnover_resistance` Python API | **leave**（热循环见 D） |
| `oskh_factors/chip/{adj_factor,bands,constants,paths,shares,window_guard}.py` | 复权、TR-BB helpers、股本、路径 | **leave**（`bands` 轻量） |
| `oskh_factors/chip/__init__.py` | 包导出 | **leave** |
| `qlib_cost/cyq.py` / `cyq_ops.py` / `distribution_of_chips.py` | 数学层（curpdf / cumpdf / ChipFactor / qlib ops） | **leave**（热循环见 D） |
| `backtest/chip_algorithm.py` | Cerebro-facing **re-export** of `oskh_factors.chip`（勿在此写算法） | **leave** |
| `scripts/data/full_market_canonical_resist.py` | 全市场 Python canonical（numba `batch` / `original` 对照） | **leave** research；生产全市场 → Rust |
| `scripts/research/full_market_canonical_resist.py` | 同上（research 树副本/并行入口） | **leave** research |
| `scripts/data/full_market_chip_resist.py` | 短窗 crossday + BB 扫描（`compute_crossday_*`） | **leave** research |
| `scripts/research/full_market_chip_resist.py` | 同上 | **leave** research |
| `scripts/data|research/full_market_equal_weight_resist*.py` | equal-weight cyqk 研究 | **leave** |
| `scripts/data|research/spot_check_chip_factors.py` | 抽样对照 | **leave** |
| `scripts/data|research/chip_window_sensitivity.py` | 窗长敏感度 | **leave** |
| `scripts/data/daily_chip_logger.py` | 日筹码日志研究 | **leave** |
| `backtest/research/chip/{evaluate_turnover_chip_factors,filter_chip_stocks,filter_stock_pool_by_chip,rolling_ic_chip_factors}.py` | 研究面 IC / 过滤（H4 face 可导入） | **leave** |
| `backtest/research/{evaluate_turnover_chip_factors,filter_chip_stocks,filter_stock_pool_by_chip,rolling_ic_chip_factors,chip_factor_analysis}.py` | 薄包装 / 历史入口 | **leave** |
| `backtest/research/verify_{mvp_min,minute_chip,adj_minute_chip,chip_factor_consistency,chip_pool_enhancement,float_shares_time_dimension_baseline}.py` | 需湖校验脚本 | **leave**（host；不进 CI） |
| `scripts/gates/verify_{mvp_min,minute_chip,adj_minute_chip,chip_factor_consistency,chip_pool_enhancement,float_shares_*,turnover_resistance_alignment,single_stock_turnover_resist}.py` | 需湖门禁 | **leave**（host-only；H10 已排除出 CI） |
| `scripts/research/verify_{turnover_resistance_alignment,single_stock_turnover_resist}.py` | 对齐 / 单票（research） | **leave** |
| `oskh_factors/chip/bands.py` + Store 内 TR-BB 列 | 对已算 TR 序列做滚动 BB（非 PDF 热核） | **leave** |
| `tests/test_turnover_resistance_store.py` / `tests/test_export_ta_pool.py` / `tests/test_strategy10_tr_pool.py` / `tests/test_selector_tr_filter.py` | 契约单测（无现场 Rust 重算） | **leave** |

---

## C. Cerebro Indicator fossils

| Path | Role | Recommendation |
|------|------|----------------|
| `backtest/chip_indicator.py` | `ChipDistribution` / `TurnoverChipFactor`（`bt.Indicator`） | **fossil** |
| `backtest/research/chip_backtest.py` | Cerebro chip 回测对照 | **fossil** |
| `backtest/research/ma_chip_edge_backtest.py` | ma + 筹码边 Cerebro；可选 `import turnover_resist` 加速 cyqk | **fossil** |
| `backtest/research/chip_selection_backtest.py` | 筹码选股 Cerebro 对照 | **fossil** |
| `backtest/research/verify_cerebro_chip.py` | Cerebro chip 冒烟 | **fossil** |
| `backtest/backtest_main_full.py` + `--allow-cerebro-fossil` | 主入口化石门（chip / ProfitStrategy 观察退役） | **fossil**（门禁留着） |
| `tests/test_chip_indicator_warmup_semantics.py` | Indicator warmup 语义锁（仍依赖 bt） | **leave**（锁化石语义，非新策略） |

> H4 / AGENTS：向量化 CSV 主路径不 import `backtrader`；上表对照**允许**继续依赖 bt。**禁止本切片物理删除。**

---

## D. Still-hot Python loops（日后 numba / Rust 候选）

| Path | Hot spot | Recommendation |
|------|----------|----------------|
| `qlib_cost/cyq.py` — `calc_curpdf` / `calc_cumpdf` / `calc_dist_chips` | 逐日三角 PDF + 衰减累积 | **later offload**（全市场已有 Rust；短窗研究可留 Python / 既有 numba batch） |
| `qlib_cost/distribution_of_chips.py` — `make_price_grid` 等 | 网格构建 | **later offload**（随 curpdf） |
| `oskh_factors/chip/core.py` — `minute_chip_distribution` / `hybrid_chip_distribution` | Python `for` 调 `cyq.calc_curpdf` | **later offload** |
| `oskh_factors/chip/core.py` — `compute_crossday_turnover_resistance` / `turnover_chip_factors` | 短窗对照路径（非 Rust window=1000 主路径） | **leave** research；大批量 → Rust bridge |
| `scripts/data|research/full_market_canonical_resist.py` | 已含 numba `_batch_triang_curpdf` / `_batch_cumpdf_4way` | **leave** 作 parity / 性能文案；**生产全市场 leave→Rust**（勿再扩 Python 主路径） |
| `docs/backtest/chip/性能优化-python.md` / `性能优化-rust.md` | 历史 profile 与定型判据 | **leave**（文档；非代码热路径） |
| [h14-d1-minute-chip-profile-results-2026-09-15.md](h14-d1-minute-chip-profile-results-2026-09-15.md) | **H14/D1** 合成 microbench：minute ~50.7ms、hybrid ~1.0ms、cumpdf已numba；**D2=numba minute** | **leave**（文档；代码仍 later offload 至 D2） |

**H14 注：** `minute_chip_distribution` / `hybrid` 行 recommendation 仍为 **later offload**，直至 D2 落地后再改。

**明确不在本表扩写：** 向量化成交核 `scan_held_day` / daily sell index（主题 A / H5–H8）——与 chip/TR 正交。

---

## E. MyQuant numba CYQ vs 本仓 Rust TR（H13 边界 · 2026-09-14/15）

**不要混：**

| | MyQuant CYQ / `winner_ratio` | 本仓 Rust `turnover-resist` |
|--|------------------------------|-----------------------------|
| **仓** | 兄弟仓 **MyQuant**（非本树） | **本仓** `turnover-resist/` |
| **入口** | `my_scripts/build_winner_ratio.py`（numba；不可用回落纯 Python） | PyO3 bridge → Store → 策略 10 / `export_ta_pool` / `tr_filter` |
| **产物** | 全市场日频 exact `winner_ratio` parquet（买过滤外置馈源） | Canonical TR / cyqk 行 + Store；审计与生产 TR 路径 |
| **算法 SSOT** | 对齐本仓 `qlib_cost.cyq`（同族；对拍见 MyQuant parity 文） | 注释复刻 Python SSOT；全市场 window=1000 以 Rust 为准 |
| **量级（用户确认）** | ~5569×166 日频，约 **~53s** 量级 | 既有 Rust 全市场 TR 路径（见 `turnover_resistance_rust.md`） |
| **证据** | 兄弟仓 `MyQuant/my_scripts/build_winner_ratio.py` · `MyQuant/docs/winner-ratio-cyq-parity-2026-09-14.md`（只读，不迁树） | 本 inventory §A + bridge selection |

**本仓不做：** 不把 MyQuant feeder 迁进本树；不在本仓再写一套全市场日频 CYQ/`winner_ratio` 构建器去「替代」MyQuant。  
**日后 offload（仍开放、仍在本仓）：** §D 的 minute/hybrid chip、`calc_curpdf` 短窗研究等 —— **不是**复刻 MyQuant 日频 feeder。

Plan：[../plan-h13-cyq-tr-boundary-2026-09-15.md](../plan-h13-cyq-tr-boundary-2026-09-15.md)

## F. 边界与非目标（H11 + H13）

| 项 | 本切片 |
|----|--------|
| 改 6/8 卖点 / simulate | ✗ |
| Full Rust rewrite / 新 PyO3 API | ✗ |
| 删 Cerebro / `chip_indicator` | ✗ |
| 扩 L2 → 交易/策略书 | ✗ |
| 需湖 chip/TR gate 进 CI | ✗（H10） |
| Bridge import 仍指向 `oskh_factors.bridge.turnover_resist` | ✓ data-free 断言 |
| 在本仓 reimplement MyQuant CYQ / `winner_ratio` feeder | ✗（H13；产品在 MyQuant） |
| 把 MyQuant 日频 feeder 与 Rust TR Store 路径混用为同一 SSOT | ✗（H13 边界） |

## 相关文档

- [turnover-resist-bridge-selection.md](turnover-resist-bridge-selection.md) — PyO3 vs CLI
- [turnover_resistance_rust.md](turnover_resistance_rust.md) / [turnover_resistance_algorithm.md](turnover_resistance_algorithm.md)
- [../plan-h10-ci-path-gates-2026-09-15.md](../plan-h10-ci-path-gates-2026-09-15.md) — 需湖 gates 清单
- [README.md](README.md) — chip 文档索引
- [../plan-h13-cyq-tr-boundary-2026-09-15.md](../plan-h13-cyq-tr-boundary-2026-09-15.md) — MyQuant CYQ vs Rust TR 边界
- 兄弟仓证据（只读）：`MyQuant/docs/winner-ratio-cyq-parity-2026-09-14.md`
