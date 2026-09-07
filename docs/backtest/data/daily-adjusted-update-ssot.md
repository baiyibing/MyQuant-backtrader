# SSOT：A 股日线复权增量更新

> **本叉不再下载行情。** QMT / `update_adjusted_daily` / `oskh_data.backfill` 以原仓库为准；此处只读 path-SSOT parquet。下文是历史运维口径，命令在本仓库已删除。
>
> 单一事实源。本文件记录日线复权数据（front / none / back）的增量更新策略、QMT 复权接口可行性结论、`scripts/data/update_adjusted_daily.py` 的用法与运维口径。
> 关联：[`docs/backtest/data/daily_data_backfill_summary.md`](daily_data_backfill_summary.md)、[`docs/prompts/prompt-stock-data-backfill-export-workflow.md`](../../prompts/prompt-stock-data-backfill-export-workflow.md)、[`scripts/data/update_adjusted_daily.py`](../../../scripts/data/update_adjusted_daily.py)、[`docs/engineering/proposal-daily-adjusted-fast-path.md`](../../engineering/proposal-daily-adjusted-fast-path.md)（快路径编排）、[`docs/engineering/daily-adjusted-update-performance-review-2026-07-04.md`](../../engineering/daily-adjusted-update-performance-review-2026-07-04.md)（性能瓶颈评审与实测汇总）。
> **数据卫生**：front/back 历史 pre-2020 周末伪交易日行清洗 → [`daily-weekend-contamination-cleanup-2026-06-23.md`](daily-weekend-contamination-cleanup-2026-06-23.md)（调休合法周末日 ≠ 污染，清洗锚 `none` 日期集）。

---

## 1. 核心结论

| 项目 | 结论 |
|------|------|
| 股票范围 | **全市场 A 股**，QMT sector 为 `沪深京A股`，约 **5548 只**（含沪深主板+创业板+科创板+北交所）。 |
| QMT `front` 复权 | **Ground truth**：从 QMT `get_market_data_ex(dividend_type='front')` 下载落盘。**禁止**再用 `back/none` 本地推导 front（会注入 ~0.5–1.5% back 噪声）。 |
| QMT `none` 复权 | **日常必下**；路径 B 与 `adj_factor` 分母。 |
| QMT `back` 复权 | **日常默认暂不下**（`--download-back` 可选恢复）。`adj_factor_back` 可含日际噪声，**不得**再驱动 front 重写；无当日 back 时该列可为 NULL。 |
| `back` 数据用途 | 后复权分析 / 可选观测；**不再**用于推导 front。 |
| QMT `get_divid_factors` | **检测可用 / 推导禁用**：用于 `detect_ex_date_changes.py` 发现新除权日；`dr` 不得用于推导 front 价格或因子数值。 |
| 前复权因子 | **只能计算、不能下载**：`cumulative_adj_factor[t] = close_front[t] / close_none[t]`（干净累计因子；无除权窗口内恒定）。 |
| 增量更新策略 | **唯一流水线**：`detect` → `update_adjusted_daily`（只下载）→ `finish_adj_factor_duckdb`（只算因子）→ rebuild。日常增量 `none`；除权股 delete+全历史 front；非除权路径 B。周日/`--force-refresh-front`/`--full` 全市场 front 重下。**已删除**本脚本内自算 adj 的慢路径。 |
| 1d 落盘写模式（2026-07-17） | none「写入文件」+ mirror/路径 B → `oskh_data/daily_parquet_write.py`；默认 `OSKH_DAILY_PARQUET_WRITE_MODE=batch`（别名 `duckdb`；可选 `parallel`/`legacy`）。**禁止**全历史 time-unify。见 prompt §4b / 教训 33–34。 |
| **指数/ETF** | **与 A 股分轨**（2026-07-15）：主轨宇宙仅 `沪深京A股`；主 hive 基准名单见 `config/market_data_etf_index_universe.txt` + `scripts/data/update_etf_index_daily.py`；全量 ETF 隔离目录见 `oskh_data.etf_backfill` → `stock_data/etf/`。**禁止**把指数/ETF 塞进 `_get_all_a_stock_codes()`。 |

---

## 2. 数据文件与格式

- **日线 parquet**：`stock_data/period=1d/dividend_type={front,none,back}/symbol={CODE}/data.parquet`
- **复权因子表**：`stock_data/adj_factor.parquet`（**计算产物**，不是 QMT 下载物）
  - 列：`date`, `stock_code`, `close_front`, `close_none`, `cumulative_adj_factor`, `adj_factor_back`
  - `cumulative_adj_factor`：前复权因子 = `close_front / close_none`
  - `adj_factor_back`：观测列 = `close_back / close_none`（日常不下 back 时可为 NULL）
- **ETF 隔离树**（全量 ETF，非主轨）：`stock_data/etf/` + `stock_data_etf_none.duckdb`（`oskh_data.etf_backfill`）
- **主 hive 指数/ETF 基准名单**：`config/market_data_etf_index_universe.txt`（仅故意放进 `period=1d` 的基准，由副轨脚本维护）

### ETF front/none isolation (2026-08-02 Phase 1)

- Parquet tree: ``stock_data/etf/period=1d/dividend_type={none,front}/symbol=XXX_YY/data.parquet``
- DuckDB: ``stock_data/stock_data_etf_none.duckdb`` and ``stock_data/stock_data_etf_front.duckdb``
- Backfill: ``python -m oskh_data.etf_backfill --core-pool-only --adjust both --rebuild-duckdb``
- Reader: ``StockDataReader(asset_type='etf')`` routes via ``_adjust_db_path`` (front->etf_front, else etf_none)
- Gate: ``scripts/gates/verify_duckdb_symbol_format.py`` covers ETF DuckDB files


### 2.1 A 股主轨 vs 指数/ETF 副轨（2026-07-15）

| 轨 | 宇宙 | 命令 | 落盘 |
|----|------|------|------|
| **主轨** | QMT `沪深京A股` | `run_daily_adjusted_fast.py` / `update_adjusted_daily.py` | `stock_data/period=1d` none+front |
| **副轨（主 hive 基准）** | `config/market_data_etf_index_universe.txt` | `scripts/data/update_etf_index_daily.py --end YYYYMMDD` | 同一 `period=1d`（仅名单） |
| **ETF 全量隔离** | QMT `沪深ETF` + 白名单 | `python -m oskh_data.etf_backfill` | `stock_data/etf/` |

P2-4 `verify_oskh_data_daily_alignment`（front⊆none）与 `verify_p2_4_symbol_coverage` 扫**主 hive**。若指数/ETF 混装导致红：先跑副轨补 none，或删除不打算维护的分区——**不要**全市场 none 重下。事故记录：[`docs/run-records/2026-07-15-p2-4-none-front-alignment-etf-index-track.md`](../../run-records/2026-07-15-p2-4-none-front-alignment-etf-index-track.md)。
- **兼容性**：`backtest/chip_algorithm.get_adj_factor` / `oskh_factors` 读取 `cumulative_adj_factor` 列，本方案保持该列语义不变。
- **同步更新**：`oskh_data/adj_factor.py` 与 `finish_adj_factor_duckdb.py` 均从已落盘 front/none 计算因子，**禁止** back/none→front。

### 2.1 `front` 数据是持久化落盘（QMT GT）

- `dividend_type=front` 目录下的 parquet **由 QMT front 下载 + 路径 B 写回本地**，与 `none` 一样持久保存。
- 日常增量：下载 **`none`**（默认跳过 `back`）；除权列表股 delete 后全历史重下 front；其余股路径 B 追加当日 `front=none`。
- `finish_adj_factor_duckdb.py` **只写** `adj_factor.parquet`，**禁止**再写 front/back 分区。
- 下游读取方式（`oskh_data.reader.StockDataReader`、`backtest` 等）不变；front 来源为 QMT GT。

---

## 3. 更新流程

### 3.1 首次初始化 / front 全量重下

```bash
# 旧 --init（本地 back/none 推导 front）已硬失败；请用：
D:\anaconda3\envs\vanna311\python.exe scripts/data/update_adjusted_daily.py --init-front-download --end YYYYMMDD
```

- 访问 QMT：全市场 **delete** 各股 front parquet 后 `download_data(adjust_type="front", incrementally=False)`。
- 随后跑 `finish_adj_factor_duckdb.py` 仅从已落盘 front/none 重建 `adj_factor.parquet`。
- 适用于：首次建立 QMT-GT front、历史 front 被旧推导污染、月度/周日 force 兜底。

### 3.2 日常增量更新

> **唯一推荐入口**：`scripts/data/run_daily_adjusted_fast.py`。

```bash
D:\anaconda3\envs\vanna311\python.exe scripts/data/run_daily_adjusted_fast.py --end YYYYMMDD
```

步骤：

1. **`detect_ex_date_changes.py`**：用 `get_divid_factors` 发现新除权日（检测可用 / 推导禁用）。
2. **`update_adjusted_daily.py --download-only --ex-date-changed-file ...`**（**只下载，不写 adj_factor**）：
   - 增量下载 **`none`**（默认**跳过 `back`**；需后复权时加 `--download-back`）；
   - 除权股：**delete + 全历史重下 QMT front**；
   - 非除权股：**路径 B** `front_today = none_today`。
3. **`finish_adj_factor_duckdb.py`**：**只计算并写出** `adj_factor.parquet`（`cumulative_adj_factor = front/none`）；**禁止**写 front/back 分区。
4. **`oskh_data.backfill rebuild --period 1d`** → 可选 export / 7z。

`--full` / 每月 1 号：步骤 2 加 `--force-refresh-front`，仍由步骤 3 算因子（**无第二套慢路径**）。

### 3.3 常用参数

```bash
# 日常快路径（推荐）
D:\anaconda3\envs\vanna311\python.exe scripts/data/run_daily_adjusted_fast.py --end 20260709

# 只下载 none+front（路径 B / 除权全历史），不算 adj_factor
D:\anaconda3\envs\vanna311\python.exe scripts/data/update_adjusted_daily.py \
    --download-only --ex-date-changed-file stock_data/.ex_date_changed_20260709.txt --end 20260709

# 仅缺 adj_factor 时本地计算（front/none 已落盘）
D:\anaconda3\envs\vanna311\python.exe scripts/data/finish_adj_factor_duckdb.py --end 20260709

# 需要后复权时
D:\anaconda3\envs\vanna311\python.exe scripts/data/update_adjusted_daily.py \
    --download-only --download-back --end 20260709
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--base-dir` | 数据根目录 | `./stock_data` |
| `--start` | 历史起始日期 | `19900101` |
| `--end` | 目标日期 | 今天 |
| `--batch` | 每批下载数量 | `100` |
| `--codes` | 股票列表文件（**会替换全市场**；日常除权列表勿用此参数） | 全市场 A 股 |
| `--download-only` | 兼容保留（本脚本默认即只下载） | `False` |
| `--download-back` | 同时增量下载后复权 back（默认跳过） | `False` |
| `--init` | **硬失败**（旧本地推导） | — |
| `--init-front-download` | 全市场 front delete+QMT 全历史下载 | `False` |
| `--ex-date-changed-file` | 仅驱动 front 全历史重下的股票列表 | 无 |
| `--force-refresh-front` | 全市场 front 全历史重下 | `False` |
| `--rebuild-duckdb` | 完成后重建 duckdb | `False` |
| `--recompute-all` | 兼容别名：等同 `--force-refresh-front`（不写 adj_factor） | `False` |

**性能说明**：
- 增量下载前用 pyarrow 元数据判断最新日期；日常默认不下 back，省去约一轮全市场下载。
- 因子由 `finish_adj_factor_duckdb` 批量计算（通常 1–3 分钟）；本脚本内逐只 adj 慢路径**已删除**。

### 3.4 QMT 断开后的回退（禁本地推导 front）

`none`/`front` 已落盘但收尾中断时：

1. **禁止**再用 `finish_adj_factor_duckdb` / `finish_adj_factor_only` 从 back/none **推导 front**。
2. front 缺失/除权未刷：QMT 恢复后重跑 `--ex-date-changed-file` 或 `--force-refresh-front` / `--init-front-download`。
3. 仅缺 `adj_factor.parquet`：跑 `finish_adj_factor_duckdb.py`（**只读**已落盘 front/none，**只写**因子表）。

```bash
D:\anaconda3\envs\vanna311\python.exe scripts/data/finish_adj_factor_duckdb.py --end YYYYMMDD
```

---

## 4. 与现有 `oskh_data.backfill` 的关系

- `oskh_data.backfill download --period 1d`：通用数据获取层（可下多种复权）；**日常收盘工作流不再依赖它下 front/back**。
- `scripts/data/update_adjusted_daily.py`：日常权威下载入口（none + front GT / 路径 B）；`--download-only` 后由 `finish_adj_factor_duckdb` 算因子。
- 推荐收盘后工作流：
  1. `scripts/data/run_daily_adjusted_fast.py --end YYYYMMDD`（含 detect / download-only / adj_factor / rebuild / 可选 export）
  2. 或手拆：`update_adjusted_daily --download-only` → `finish_adj_factor_duckdb` → `oskh_data.backfill rebuild --period 1d`

---

## 5. 注意事项与限制

1. **`adj_factor` 只能计算**：数值源是已落盘 QMT front ÷ none；**不要**从 QMT「下载因子」，也不要用 `dr`/back 推导因子数值。
2. **日常默认不下 `back`**：需要后复权分析时加 `--download-back`；`adj_factor_back` 可为 NULL，不作为完成失败条件。back DuckDB rebuild 失败（non-fatal）不判整次失败。
3. **QMT `back` 超长历史下载可能丢数据**：从 `19900101` 全量请求时，部分股票会丢失早期行。日常增量不受此影响。
4. **`back` 角色**：可选观测；**不得**再驱动 front 重写。除权后 front 须 delete+全历史重下。
5. **断更保护**：`max_stale_days=7`，若某股票 adj_factor 断更超过 7 天，首次恢复时视为首次记录，避免误判。
6. **旧 `--init` / `finish_adj_factor_only.py`**：硬失败；迁移见 `plan-front-adj-factor-dr-based-2026-07-09.md`。
7. **股票代码必须规范**：仅 `^\d{6}\.(SH|SZ|BJ)$`（`is_canonical_symbol`）。禁止 `000001,平安银行` 类脏分区进入 detect / 除权列表 / QMT 下载；`to_canonical_symbol` **不会**清洗逗号名。
8. **首次建 `ex_date_index`**：`known_pairs=0` 时 changed≈全市场 → 全历史 front 重下（预期）。`--resume` 且当日 `.ex_date_changed_*.txt` 已存在时**不重跑 detect**，避免列表缩水。
9. **front 全历史请求区间**：脚本传 `19900101–end`；落盘实际为各股上市首日→end（与 none 起止对齐为验收口径）。

---

## 6. 验证命令

```bash
# 检查 adj_factor（cumulative 应合理；adj_factor_back 日常可为 NaN）
D:\anaconda3\envs\vanna311\python.exe -c "
import pandas as pd
df = pd.read_parquet('stock_data/adj_factor.parquet')
sub = df[df.stock_code == '000002.SZ'].set_index('date').sort_index()
print(sub[['cumulative_adj_factor', 'adj_factor_back']].describe())
"

# 检查 front/none 最新日期（日常不要求 back）
D:\anaconda3\envs\vanna311\python.exe -c "
import pandas as pd
from pathlib import Path
for dt in ['front', 'none']:
    p = Path(f'stock_data/period=1d/dividend_type={dt}/symbol=000001_SZ/data.parquet')
    d = pd.read_parquet(p)
    print(f'{dt}: {len(d)} rows, latest={d.index.max()}')
"

# 检查 adj_factor.parquet stock_code 未被 Windows 路径污染
D:\anaconda3\envs\vanna311\python.exe -c "
import pandas as pd
df = pd.read_parquet('stock_data/adj_factor.parquet')
bad = df['stock_code'].astype(str).str.contains(r'[\\\\/]|data_parquet|data\\.parquet', regex=True, na=False)
print(f'stock_code 污染行数: {bad.sum()}')
print(f'股票数: {df[\"stock_code\"].nunique()}, 行数: {len(df)}')
"
```

---

## 7. 股票范围历史说明

早期版本（含 `oskh_data.backfill.py` 及 `scripts/data/update_adjusted_daily.py` 初稿）采用防御性 sector 列表：

```python
['沪深A股', '上海A股', '深圳A股', '北京A股', '科创板', '创业板', '北交所']
```

原意是“QMT 板块名称可能因版本而异，多试几个常见名称”。但实测在当前 QMT 版本中，除 `沪深A股` 外其余 sector 均返回 0，导致实际只拿到 **5208 只**，漏掉北交所。

本 SSOT 明确：**不再使用防御性 sector 列表**。`scripts/data/update_adjusted_daily.py` 统一使用 QMT `沪深京A股` sector 获取全市场 A 股代码（~5548 只）。如未来 QMT 该 sector 不可用，再更新本 SSOT，而不是在代码里罗列候选 sector。

---

## 8. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-06-17 | 初稿。确认 QMT front 不可靠，改为从 back 推导 front；实现 `scripts/data/update_adjusted_daily.py`；本文件作为 SSOT。 |
| 2026-06-18 | 修正 front 复权结论：QMT front 实测可用，选择本地推导是因为维护成本更低；明确 `back` 数据唯一用途是推导 `front`；股票范围统一为 `沪深京A股`（~5548 只），不再使用防御性 sector 列表。 |
| 2026-06-24 | 新增 DuckDB 本地回退路径 `scripts/data/finish_adj_factor_duckdb.py`；修正 Windows 下 DuckDB `PARTITION_BY` 目录名被编码为 `%5Cdata_parquet` 的问题；新增 `adj_factor.parquet` stock_code 污染校验命令；`update_adjusted_daily.py` 增加 `download_data` 返回值检查，QMT 下载失败时快速失败而非继续空跑；新增当日跳过列表（daily skip-list），避免 QMT 无数据股票被反复下载。详见事故记录 [`docs/run-records/2026-06-24-update-adjusted-daily-repeated-download-incident.md`](../../run-records/2026-06-24-update-adjusted-daily-repeated-download-incident.md)。 |
| 2026-06-26 | 性能优化：`DataDownloader._filter_incremental` 改用 pyarrow 元数据快速判断最新日期；`update_adjusted_daily.py` 主循环新增快速通道与 parquet 读取缓存，无变化日 `--dry-run` 从数分钟降到约 25–45 秒；`finish_adj_factor_duckdb.py` 新增 `--only-changed` 与 DuckDB 校验；`export_stock_pool_daily.py` 新增 `--use-duckdb` 批量导出。 |
| 2026-07-09 | **front 改 QMT GT 下载**：放弃 back/none 本地推导；`--init-front-download` / `--ex-date-changed-file` / 路径 B；`finish_adj_factor_duckdb` 只写 adj_factor；见 [`plan-front-adj-factor-dr-based-2026-07-09.md`](../../engineering/plan-front-adj-factor-dr-based-2026-07-09.md)。 |
| 2026-07-09（晚） | **日常默认不下 back**（`--download-back` 可选）；`adj_factor` 明确为计算产物（front/none）；SSOT §3.2/§4/§5/§6 与 prompt 工作流对齐；验收以 front+none 为准。 |
| 2026-07-09（夜） | **删除** `update_adjusted_daily` 内自算/写 adj_factor 的慢路径；`--full`/`--recompute-all` 仅强制 front 重下，因子一律 `finish_adj_factor_duckdb`。 |
| 2026-07-10 | **脏代码防护**：`is_canonical_symbol`；detect/除权列表/本地 none 跳过非规范代码。**resume**：front 未完成时保留 `.ex_date_changed_*.txt`、不重跑 detect。front 全历史进度约 10 分钟汇总；大列表 WARNING。详见 prompt 教训 23–26。 |
| 2026-07-15 | **`download_history_data2` 线程看门狗**：SDK 阻塞挂起时旧 post-call 超时无效；改为 daemon 线程 + 主线程 start/stall/total。Agent：`Connection reset`/零进度 → 重启 miniQMT 再 `--resume`；进度看 stdout 日志非 persist STEP 文件。详见 prompt 教训 31。 |
| 2026-07-15 | **指数/ETF 副轨**：主 hive 基准名单 `config/market_data_etf_index_universe.txt` + `scripts/data/update_etf_index_daily.py`（与沪深京A股主轨分离）。全量 ETF 仍走 `oskh_data.etf_backfill` → `stock_data/etf/`。事故与验收：[`../../run-records/2026-07-15-p2-4-none-front-alignment-etf-index-track.md`](../../run-records/2026-07-15-p2-4-none-front-alignment-etf-index-track.md)。 |
| 2026-07-17 | **P2-4 A′**：detect 宇宙过滤 + fail-fast；`ex_changed ∩ all_codes`。**1d 落盘**：`daily_parquet_write`（默认 `batch`）覆盖 none「写入文件」与 mirror/路径 B。**禁止**全历史 `+8h` UTC-midnight unify（双行事故）。prompt §4b / 教训 33–34。 |
| 2026-07-17 | **禁止全历史 time-unify**：勿把 QMT/\	ime\ 批量改成 UTC midnight 再与 CST 历史按毫秒去重（会叠成约 2x）。path B 仅写今天一行可保留。07-17 keep=CST；**2026-07-24 终态 none->UTC + shanghai-day collapse**（\scripts/data/_repair_daily_none_cst_to_utc.py\）。见 [\../../run-records/2026-07-24-none-cst-to-utc-apply.md\](../../run-records/2026-07-24-none-cst-to-utc-apply.md)。 |
