# stock_pool 日线/分钟线数据导出

**脚本**: `scripts/misc/export_stock_pool_daily.py`

**目的**: 从本地 `stock_data/` 中导出 `stock_pool/` 目录下所有 CSV 文件涉及的股票（自动去重）的日线或分钟线数据，保持原 Hive 分区结构写入 `stock_data/exp/`，供回测、策略验证或外部分析使用。

---

## 1. 输入与输出

### 输入

| 来源 | 说明 |
|------|------|
| `stock_pool/*.csv` | 每行格式 `"代码,名称"`，无表头；自动识别 6 位数字股票代码 |
| `stock_data/period={1d,1m}/dividend_type={front,none}/symbol=XXXXXX_XX/data.parquet` | 本地已下载的 Parquet 日线/分钟线数据 |

### 输出

| 路径 | 说明 |
|------|------|
| `stock_data/exp/period={1d,1m}/dividend_type=front/symbol=XXXXXX_XX/data.parquet` | 按时间范围过滤后的子集，保持原 Hive 分区结构（日线默认仅 front） |

---

## 2. 用法示例

### 2.1 导出日线（默认）

结束日期为昨天，起始日期默认 `2025-01-01`：

```bash
# 默认：逐文件读取本地 parquet
D:\anaconda3\envs\vanna311\python.exe scripts/misc/export_stock_pool_daily.py --end-date 2026-05-18

# 推荐：DuckDB 批量导出（需先 rebuild --period 1d，2227 只实测 ~30s vs ~45s）
D:\anaconda3\envs\vanna311\python.exe scripts/misc/export_stock_pool_daily.py --end-date 2026-05-18 --use-duckdb

# 如需同时导出 none
D:\anaconda3\envs\vanna311\python.exe scripts/misc/export_stock_pool_daily.py --end-date 2026-05-18 --use-duckdb --adjust-types front,none
```

### 2.2 仅列出待导出股票（不写文件）

```bash
D:\anaconda3\envs\vanna311\python.exe scripts/misc/export_stock_pool_daily.py --end-date 2026-05-18 --list
```

### 2.3 导出一分钟线

```bash
D:\anaconda3\envs\vanna311\python.exe scripts/misc/export_stock_pool_daily.py --end-date 2026-05-18 --period 1m
```

### 2.4 自定义时间范围

```bash
D:\anaconda3\envs\vanna311\python.exe scripts/misc/export_stock_pool_daily.py \
  --start-date 2024-01-01 --end-date 2026-05-18
```

---

## 3. 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--end-date` | **必填** | 结束日期 `YYYY-MM-DD` |
| `--start-date` | `2025-01-01` | 起始日期 `YYYY-MM-DD` |
| `--period` | `1d` | 周期：`1d`（日线）或 `1m`（分钟线） |
| `--pool-dir` | `stock_pool/` | stock_pool CSV 目录 |
| `--source-dir` | `stock_data/` | 源数据根目录 |
| `--export-dir` | `stock_data/exp/` | 导出根目录 |
| `--list` | `False` | 仅列出股票代码，不写文件 |
| `--use-duckdb` | `False` | 使用 DuckDB 批量导出（先执行 `oskh_data.backfill rebuild --period 1d`） |
| `--adjust-types` | `1d=front, 1m=none` | 复权类型，逗号分隔（如 `front,none`） |

> **注意**：日线（`1d`）默认仅导出 `front`（前复权）；如需 `none`（未复权），追加 `--adjust-types front,none`。分钟线（`1m`）默认仅导出 `none`。

---

## 4. 输出目录结构

```
stock_data/exp/
├── period=1d/
│   └── dividend_type=front/
│       ├── symbol=000001_SH/
│       │   └── data.parquet
│       ├── symbol=000002_SH/
│       │   └── data.parquet
│       └── ...
└── period=1m/
    └── dividend_type=none/
        └── ...
```

---

## 5. 典型使用场景

| 场景 | 命令示例 |
|------|---------|
| **回测前准备数据** | 按当前 stock_pool 提取子集，避免加载全市场 5,000+ 只股票 |
| **策略验证** | 导出特定时间段数据，配合回测框架快速验证 |
| **外部分析** | 保持 Hive 结构，可直接用 DuckDB / PyArrow / Pandas 读取 |
| **CSV 签字前快照** | 固定某一日的 stock_pool 成分，导出对应历史数据留档 |

---

## 6. 与全量 backfill 的关系

本脚本**不负责下载数据**，它依赖 `oskh_data.backfill` 或 `backtest/backfill_daily_data.py` 事先将数据下载到本地。两者配合使用：

1. **先补录**: `python -m oskh_data.backfill update --period 1d`（确保本地数据完整）
2. **后导出**: `python scripts/misc/export_stock_pool_daily.py --end-date YYYY-MM-DD`（按 stock_pool 提取子集）

---

*文档记录于 2026-05-19；2026-06-26 新增 `--use-duckdb` 批量导出。*
