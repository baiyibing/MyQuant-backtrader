# 换手阻力（Turnover Resistance）完整技术文档

> 本文档为索引页。实质性内容已拆分为：
> - [`turnover_resistance_algorithm.md`](turnover_resistance_algorithm.md) — 算法核心（公式、调用链路、各层实现、附录 A/B）
> - [`turnover_resistance_runbook.md`](turnover_resistance_runbook.md) — 运行手册（回测框架、脚本 CLI、参数速查）
>
> 手算核对（填数样例）：[`turnover_resistance_handcheck_300834_20260327.md`](turnover_resistance_handcheck_300834_20260327.md)（300834.SZ / 20260327）

## 文档导航

| 文档 | 内容 | 面向读者 |
|------|------|----------|
| [`turnover_resistance_algorithm.md`](turnover_resistance_algorithm.md) | §1–§4：概述、核心公式、调用链路、数据准备层、筹码分布层、纯数学层（qlib_cost）、因子提取层、跨日衍生层、截面日定义、市面指标差异对比；附录 A/B（Indicator 详解） | 算法开发、因子研究、代码审计 |
| [`turnover_resistance_runbook.md`](turnover_resistance_runbook.md) | §5–§7：回测框架（选股规则、布林带、ChipSellStrategy、多轮回测、滚动 IC）、脚本使用指南（全市场计算 / Spot Check / 因子分析 / 每日截面日志 / 全市场筛选 / 双路径对齐验证 / 手算核对）、参数速查表 | 策略回测、运维执行、日常计算 |
| [`turnover_resistance_tr_bollinger.md`](turnover_resistance_tr_bollinger.md) | Canonical TR_1000 持久化 + TR 布林带 + 盘后流水线 | 因子研究、模拟柜台盘后任务 |
| [`../../engineering/qlib-cost-package-status-2026-08-19.md`](../../engineering/qlib-cost-package-status-2026-08-19.md) | `qlib_cost` 包级环境：numpy 2 / alphalens / pyqlib / #299/#300 | 装包、venv、研究壳还能不能跑 |

## 相关源码路径

- `oskh_factors/chip/core.py`
- `qlib_cost/cyq.py`
- `qlib_cost/distribution_of_chips.py`
- `backtest/chip_factor_analysis.py`
- `scripts/data/daily_chip_logger.py`
- `backtest/filter_chip_stocks.py`
- `scripts/data/full_market_chip_resist.py`
- `scripts/data/spot_check_chip_factors.py`
- `turnover-resist/` — Rust 高性能实现（`maturin build --profile release-fast` 构建 PyO3 wheel；`cargo build --release` 构建 CLI binary）。PyO3 FFI 桥接见 [`oskh_factors/bridge/turnover_resist.py`](../../oskh_factors/bridge/turnover_resist.py)（自动检测 `pyo3_ffi` / `cli_fallback`，一行 `compute_turnover_resist(date=...)` 调用）。桥接选型见 [`turnover-resist-bridge-selection.md`](turnover-resist-bridge-selection.md)（CLI 39ms vs PyO3 0.2μs，结论 PyO3）。
- `stock_data/float_shares.parquet`、`stock_data/free_float_shares.parquet`（流通股本）

## 8. 文件索引

| 文件 | 作用 |
|------|------|
| `oskh_factors/chip/core.py` | 适配层：`adapt_columns`、`derived_chip_factors`、`compute_crossday_turnover_resistance`、`compute_chip_factors`、`compute_equal_weight_cyqk` |
| `qlib_cost/cyq.py` | 筹码分布核心：`calc_dist_chips`、`ChipFactor` |
| `qlib_cost/distribution_of_chips.py` | PDF 数学：`triang_pdf`、`calc_triang_pdf`、`uniform_pdf` |
| `stock_data/float_shares.parquet` | 静态流通股本（全市场脚本读表） |
| `stock_data/free_float_shares.parquet` | 按日流通股本（`adapt_columns` + `as_of_date`） |
| `backtest/chip_factor_analysis.py` | 多轮回测 + 滚动 IC；`StockDataReader`（backtest） |
| `scripts/data/daily_chip_logger.py` | **Legacy TR_80 每日截面 CSV**：`derived_chip_factors` + ARC/VRC |
| `backtest/filter_chip_stocks.py` | 指定日截面：阻力 + BB 过滤（列名 `resist`） |
| `oskh_factors/bridge/turnover_resist.py` | **PyO3 FFI 桥接**（v1.0, 2026-06-07；`oskh_core/turnover_resist_bridge.py` shim 已删 2026-08-24 PR-4）：`compute_turnover_resist()` 主入口，自动选择 `pyo3_ffi` 或 `cli_fallback` |
| `turnover-resist/` Rust 子项目 | Rust Polars+Rayon 并行实现；`maturin build` → PyO3 wheel；`cargo build --release` → CLI exe |
| `turnover-resist/src/lib.rs` | PyO3 绑定：`compute_turnover_resist(date, window, step, data_dir, ...)` → JSON |
| `turnover-resist-bridge-selection.md` | 桥接选型（PyO3 vs CLI benchmark） |
| `backtest/chip_indicator.py` | backtrader `ChipDistribution`（lines: cyqk_c/asr/ckdw/prp） |
| `scripts/data/full_market_chip_resist.py` | 全市场 CSV（`turnover_resist` 等） |
| `scripts/data/spot_check_chip_factors.py` | 随机抽样 Spot Check |
| `scripts/gates/verify_turnover_resistance_alignment.py` | canonical vs 脚本路径换手率/阻力偏差验证 |
| `oskh_data/reader.py` | 运维脚本用 `StockDataReader`（DuckDB） |
| `oskh_data/turnover_resistance_store.py` | **Canonical TR_1000 Parquet 时序表** + TR BB 写回 |
| `oskh_factors/chip/bands.py` | TR 布林带 rolling 计算 |
| `scripts/data/compute_turnover_resistance_bands.py` | 盘后 TR + TR BB 单日流水线 |
| `scripts/data/backfill_turnover_resistance_bands.py` | 历史 TR 回填 + TR BB |
| `backtest/stock_data_reader.py` | 回测用 `StockDataReader` |

## 9. Python/Rust 精度对齐（v1.1, 2026-06-07）

| 项 | 状态 | 说明 |
|----|------|------|
| 网格构造 | ✅ 已修复 | Python `np.arange` 重复加法 → IEEE-754 误差累积 → 边界 bin 翻转。已改用 `make_price_grid`：`min_p + np.arange(n) * step`，与 Rust `min_p + i * step` 逐点一致 |
| `--free-float-policy` | ✅ 已对齐 | Python + Rust 均支持 `warn-zero`（默认）/ `skip` / `fail`。同等参数下跳过数量一致 |
| Rust capital 复用 | ✅ 已修复 | WarnZero 路径 `circ_cap_hist` 错误使用 `circ_cap_t`，已改为 `circ_cap_t1` |
| 双路径验证 | ✅ 通过 | `scripts/gates/verify_rust_python_alignment.py --date 20260525`：4595 只全 diff=0 |

验证命令：
```bash
D:/anaconda3/envs/vanna311/python.exe scripts/gates/verify_rust_python_alignment.py \
  --date YYYYMMDD --free-float-policy warn-zero
```

根因分析见 [`Rust-Python换手阻力精度差异—权威根因分析报告.md`](Rust-Python换手阻力精度差异—权威根因分析报告.md)。

---

*文档整理于 2026-05-24；2026-05-28 拆分为算法+运行手册+索引；2026-06-07 更新精度对齐 + PyO3 FFI 桥接 + free_float_policy 对齐。*
