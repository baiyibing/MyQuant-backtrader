# 宿主湖门禁 cookbook（WP2 · 2026-09-16）

`scripts/gates/` 共 **13 个 `verify_*`**：CI 跑 **4 个 data-free**，其余 **9 个宿主 only**。本文补齐 #57 的 WP2 清单；宿主门禁需要真实数据才能提供验收证据，**CI 必须保持无湖**。`.github/workflows/python-tests.yml` 及其 “Do NOT add lake-backed…” 注释保持不变。

## 运行约定与数据位置

以下命令均在**仓库根目录**执行。`python` 表示仓库约定的研究环境解释器，不是隐式系统 Python；按 `OSKH_MERGE_PYTHON` → `VANNA312_PYTHON` → `VANNA311_PYTHON` → Windows vanna312 默认路径解析。本 workspace 可将命令中的 `python` 替换为 `/workspace/vanna312/bin/python`。

- 股票日线 / 分钟树：`resolve_period_root("1d" / "1m")`；复权与股本散表：`resolve_source_parquet(...)`；容器：`resolve_parquet_container()`。沿用宿主 F 湖 authority / resolver 配置，不使用 cwd 下的 `stock_data/` 冒充湖。本仓只读行情，外部下载、供应商合并由 1.3 完成。
- DuckDB / 实验工作区走 `resolve_e_stock_data_container()` / `OSKH_DATA_ROOT`，与 F Parquet 湖分开。`StockDataReader` 消费相应湖数据，环境须具备脚本依赖。
- 示例日期、代码必须落在宿主已有覆盖范围；带 CLI 的脚本可按下表调整。无 CLI 的脚本使用其现有固定样本，本文不改脚本。
- 留存命令、样本窗口、stdout、退出码及脚本生成的报告；检查有效样本数。部分门禁是报告型脚本，**exit 0 不保证有有效样本或指标达标**，具体见各项。

## CI 四门（对照，非本 cookbook 主跑）

这四项不需要 F 湖，在 workflow 的 pip 安装前运行；契约见 [H10](plan-h10-ci-path-gates-2026-09-15.md) / [H12](plan-h12-ci-tr-bridge-gate-2026-09-15.md)。

```bash
python scripts/gates/verify_oskh_data_contract.py
python scripts/gates/verify_data_path_ssot.py
python scripts/gates/verify_no_hardcoded_machine_paths.py
python scripts/gates/verify_tr_bridge_import_ssot.py
```

## 9 个宿主 only

### 1. verify_turnover_resistance_alignment

目的：Python canonical vs research-ops TR 对齐，核对换手与阻力两项。

```bash
python scripts/gates/verify_turnover_resistance_alignment.py --date 20260515 --samples 20
```

数据：需湖中前复权日线、`resolve_source_parquet("float_shares.parquet")`，以及 `StockDataReader(mode="duckdb_persistent")` 所需 DuckDB 环境；样本须满足窗口与 freshness 校验。可用 `--window`、`--seed`、`--tol-turnover`、`--tol-resist` 控制验证。

退出语义（#55）：**0 = 非空有效样本且两项全过；1 = 输入问题 / 零有效样本；2 = 任一项不对齐**。输入或依赖异常仍可能直接报错退出，不能只看终端最后一条指标。

### 2. verify_single_stock_turnover_resist

目的：单票换手阻力分步验算，输出中间量及可用 CSV 对照。

```bash
python scripts/gates/verify_single_stock_turnover_resist.py --code 003816.SZ --date 20260515 --window 1000
```

数据：需湖 + DuckDB，包含前复权日线、`free_float_shares.parquet` / `float_shares.parquet` 股本数据；既有对照 CSV 可选，缺失时提示未找到。散表走 `resolve_source_parquet`。

退出语义：报告型；正常结束为 0，没有把数值不一致映射为专用失败码。缺数据也可能提前返回，须看数据量、中间量与对照输出。

### 3. verify_chip_pool_enhancement

目的：比较原始池与 chip 过滤池的前向收益增量。

```bash
python scripts/gates/verify_chip_pool_enhancement.py --rule trend --horizon 10 --max-dates 20
```

数据：需湖中因子窗口及后续收益窗口的日线 + 仓库根 `stock_pool/` 历史名单；可用 `--start-date YYYYMMDD --end-date YYYYMMDD` 限定池日期。

退出语义：报告型；正常结束为 0，收益无增量不自动返回非零。无池日期、筛选后无日期或无有效结果均可能正常返回，须核对报告覆盖与收益统计。

### 4. verify_chip_factor_consistency

目的：日线 vs 分钟筹码因子交叉验证，报告相关性与误差。

```bash
python scripts/gates/verify_chip_factor_consistency.py --stocks 100 --dates 5 --start 2026-03-10 --end 2026-05-14
```

数据：需湖中前复权日线、未复权分钟线及 `float_shares.parquet`；日线 / 分钟路径分别走 `resolve_period_root`，股本走 `resolve_source_parquet`，需覆盖所选日期的历史窗口。

退出语义：报告型；正常结束为 0，打印的 `BELOW 0.80` / 数据不足不自动转失败码。检查有效配对数、各因子判定及生成的 `chip_cross_validation.csv`。

### 5. verify_minute_chip

目的：验证分钟 COST 筹码分布及日线对照。

```bash
python scripts/gates/verify_minute_chip.py
```

数据：需湖；固定 `000001.SZ`，日线最近 80 日及对应未复权分钟窗口，经 `StockDataReader` 读取，股本适配沿用因子层数据依赖。此脚本没有样本 CLI。

退出语义：到达汇总时，`failed == 0` 返回 0，否则 1；但缺数据分支的 `return 1` 未由入口 `main()` 转为进程退出码，可能 **exit 0 且未验证**。必须确认出现完整 `RESULTS` 与有效数据输出；本文仅记录现状。

### 6. verify_adj_minute_chip

目的：复权校正分钟筹码 vs 日线，比较未校正 / 校正两方案的相关性和 MAE。

```bash
python scripts/gates/verify_adj_minute_chip.py
```

数据：需湖中前复权日线、未复权分钟及 `resolve_source_parquet("adj_factor.parquet")`，并满足股本适配依赖。脚本固定截面 `2026-05-13`、80 日窗口，从复权因子偏离较大的标的选样；无 CLI。

退出语义：报告型；正常结束为 0，方案 B 未改善不自动返回失败码；有效标的少于 3 时打印“数据不足”后正常返回。须看有效标的数及比较结果。

### 7. verify_float_shares_time_dimension_baseline

目的：建立 float_shares 时间维兼容性、历史完整性及换手 / 因子差异基线。

```bash
python scripts/gates/verify_float_shares_time_dimension_baseline.py --sample-size 30 --bars 240
```

数据：必需 `resolve_source_parquet("float_shares.parquet")`；完整因子基线还需湖中前复权日线。`resolve_parquet_container() / "float_shares_history.parquet"` 为可选历史表，缺失会记录 `history_exists=False`。可用 `--codes`、`--start`、`--end` 限定样本。

退出语义：报告型；正常写出 JSON 为 0，无统一指标阈值失败码。检查历史表存在性、重复键、非空率与有效样本指标；缺必需输入可能异常退出。

### 8. verify_mvp_min

目的：COST MVP-min 多标的验收，检查筹码分布及因子。

```bash
python scripts/gates/verify_mvp_min.py --sample 20
```

数据：需湖中未复权日线（`resolve_period_root("1d") / "dividend_type=none"`）及股本适配数据；可用 `--stocks 000001.SZ,003816.SZ` 指定名单，或 `--all` 验证全部日线缓存标的。

退出语义：无待验名单或有真实失败为 1；`failed == 0` 为 0。低波动 / 数据不足可计为 SKIP，**全部 SKIP 仍可能 exit 0**，必须核对 passed / failed / skipped 数量。

### 9. verify_l2_manifest

目的：校验 L2 `_manifest.jsonl` 的 JSONL、必需字段、日期唯一性、Parquet 文件存在性与行数。

```bash
python scripts/gates/verify_l2_manifest.py --output-json
# 显式指定已有 L2 Parquet 根目录时：
python scripts/gates/verify_l2_manifest.py --parquet-root /path/to/l2_parquet --strict --output-json
```

数据：默认 `l2_analytics.db.default_parquet_root()`，支持 `OSKH_L2_PARQUET_ROOT` 或 `--parquet-root`；真正校验需要 manifest 及引用的 Parquet、DuckDB 计数依赖。`--strict` 虽已暴露为参数，但当前文件大小检查分支仍为 `pass`，不提供大小漂移校验。L2 仅离线研究分析。

退出语义：0 = 通过或 soft-skip（根目录不存在、无 manifest、空 manifest）；1 = 字段 / 日期 / 文件 / 行数等校验失败；2 = JSONL 解析失败。**无 manifest 时 soft-skip exit 0；有湖数据才是真校验**，须检查 JSON 的 `checks`，不能仅看 `ok` / 退出码。

## R12：权威入口与旧用法

同名副本存在于 `scripts/gates/`、`scripts/research/`、`backtest/research/` 之间；本文规定门禁的**权威入口 = `scripts/gates/`**，不物理合并、移动脚本。

若干 docstring 仍写 `python backtest/verify_*.py`（过期），包括 minute_chip / adj_minute_chip / chip_factor_consistency / chip_pool_enhancement / mvp_min / float_shares_time_dimension_baseline。正确跑法统一为 **`python scripts/gates/verify_*.py`**，以本文命令为准；本 PR 只改 Markdown，保留脚本原状。
