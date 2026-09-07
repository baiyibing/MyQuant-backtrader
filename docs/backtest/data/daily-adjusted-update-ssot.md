# SSOT：A 股日线复权增量更新

> 单一事实源。本文件记录日线复权数据（front / none / back）的增量更新策略、QMT 复权接口可行性结论、`scripts/update_adjusted_daily.py` 的用法与运维口径。
> 关联：[`docs/backtest/data/daily_data_backfill_summary.md`](daily_data_backfill_summary.md)、[`docs/prompts/prompt-stock-data-backfill-export-workflow.md`](../../prompts/prompt-stock-data-backfill-export-workflow.md)、[`scripts/update_adjusted_daily.py`](../../../scripts/update_adjusted_daily.py)。

---

## 1. 核心结论

| 项目 | 结论 |
|------|------|
| QMT `front` 复权 | **不可靠**。`xtdata.get_market_data_ex(dividend_type='front')` 返回的收盘价与 `none` 完全相同，未做真正复权。 |
| QMT `back` 复权 | **可靠**。`close_back / close_none` 可稳定得到累积复权因子，且随时间变化。 |
| QMT `get_divid_factors` | **不推荐直接用于推导复权因子**。`dr` 字段与 `close_front/close_none` 不是简单数学关系，不如直接用 back/none 价格比。 |
| 前复权推导 | `cumulative_adj_factor[t] = adj_factor_back[t] / adj_factor_back[latest]`，`close_front[t] = close_none[t] * cumulative_adj_factor[t]`。 |
| 增量更新策略 | 日常只下载 `none` + `back`，`front` 完全本地由 `back/none` 推导；检测到 `adj_factor_back` 突变时本地缩放历史 front/back。 |

---

## 2. 数据文件与格式

- **日线 parquet**：`stock_data/period=1d/dividend_type={front,none,back}/symbol={CODE}/data.parquet`
- **复权因子表**：`stock_data/adj_factor.parquet`
  - 列：`date`, `stock_code`, `close_front`, `close_none`, `cumulative_adj_factor`, `adj_factor_back`
  - `cumulative_adj_factor`：前复权因子（以最新日期为基准 1）
  - `adj_factor_back`：后复权累积因子（`close_back / close_none`）
- **兼容性**：`backtest/chip_algorithm.get_adj_factor` 读取 `cumulative_adj_factor` 列，本方案保持该列语义不变。
- **同步更新**：`oskh_data/adj_factor.py`（原 `backtest/build_adj_factor_table.py` 的底层实现）已同步改为从 `back/none` 推导，与 `scripts/update_adjusted_daily.py` 逻辑一致、输出格式相同。

### 2.1 `front` 数据是持久化落盘，不是每次现算

- `dividend_type=front` 目录下的 parquet **由脚本生成并写回本地**，与 `none`/`back` 一样持久保存。
- 日常增量：仅下载 `none` + `back`，然后根据最新复权因子推导/修正 `front`，再写回 `dividend_type=front/symbol=XXX/data.parquet`。
- 下游读取方式（`oskh_data.reader.StockDataReader`、`backtest` 等）**完全不变**，只是 `front` 的来源从"QMT 下载"变为"本地由 back 推导"。

---

## 3. 更新流程

### 3.1 首次初始化 / 断更后重建

```bash
D:\anaconda3\envs\vanna311\python.exe scripts/update_adjusted_daily.py --init
```

- 不访问 QMT，直接从本地 `back/none` parquet 重建：
  1. 计算完整 `adj_factor` 历史；
  2. 由 `adj_factor` 历史重写 `front/back` parquet；
  3. 保存 `adj_factor.parquet`。
- 适用于：首次生成 `adj_factor.parquet`、历史 `front` 数据被污染、断更后需要重新对齐。

### 3.2 日常增量更新

```bash
D:\anaconda3\envs\vanna311\python.exe scripts/update_adjusted_daily.py
```

步骤：

1. **增量下载** `none` 和 `back`（`front` 不再从 QMT 下载）。
2. **计算今日因子**：`adj_factor_back_today = close_back_today / close_none_today`，`cumulative_adj_factor_today = 1.0`。
3. **检测除权**：与昨日 `adj_factor_back` 比较，相对变化超过 `--threshold`（默认 0.5%）则认为发生除权。
4. **本地缩放历史价格**：对触发股票，仅缩放 `< target_date` 的历史 `front/back` OHLC/close，缩放比例 `scale = adj_factor_back_today / adj_factor_back_yesterday`。`target_date` 当天价格保持 QMT 最新值不变。
5. **重建 adj_factor 历史**：基于新的 `front/back` 重建该股票完整 `adj_factor`，保证 `adj_factor.parquet` 与 parquet 自洽。
6. 保存 `adj_factor.parquet`。

### 3.3 常用参数

```bash
# 指定日期与股票
D:\anaconda3\envs\vanna311\python.exe scripts/update_adjusted_daily.py --end 20260616 --codes codes.txt

# 只检测不执行
D:\anaconda3\envs\vanna311\python.exe scripts/update_adjusted_daily.py --dry-run

# 强制从 QMT 重下近 N 年修正 OHLC（可选，慎用）
D:\anaconda3\envs\vanna311\python.exe scripts/update_adjusted_daily.py \
    --rebuild-mode download --rebuild-window-years 5
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--base-dir` | 数据根目录 | `./stock_data` |
| `--start` | 历史起始日期 | `19900101` |
| `--end` | 目标日期 | 今天 |
| `--threshold` | 除权检测阈值 | `0.005`（0.5%） |
| `--batch` | 每批下载数量 | `100` |
| `--codes` | 股票列表文件 | 全市场 A 股 |
| `--rebuild-mode` | `local` / `download` / `both` | `local` |
| `--rebuild-window-years` | `download` 模式下只重下最近 N 年 | `0`（全部） |
| `--init` | 重建完整 adj_factor 历史 | `False` |
| `--rebuild-duckdb` | 完成后重建 duckdb | `False` |

---

## 4. 与现有 `oskh_data.backfill` 的关系

- `oskh_data.backfill download --period 1d`：全量/增量下载 QMT 三种复权，是**数据获取层**。
- `scripts/update_adjusted_daily.py`：在 `backfill` 已下载 `none/back` 的基础上，做**复权一致性维护**，解决 front 数据不可靠、除权后历史价格需更新的问题。
- 推荐收盘后工作流：
  1. `oskh_data.backfill download --period 1d --end YYYYMMDD`（获取最新 none/back）
  2. `scripts/update_adjusted_daily.py --end YYYYMMDD`（推导 front、维护 adj_factor）
  3. `oskh_data.backfill rebuild --period 1d`（同步 DuckDB）

---

## 5. 注意事项与限制

1. **QMT `back` 超长历史下载可能丢数据**：从 `19900101` 全量请求时，部分股票会丢失早期行（如 `600000.SH` 实测丢约 2200 行）。日常增量只补最新一天，不受此影响；首次全量下完后用 `--init` 重建即可。
2. **丢失的多为非交易日**：实测缺失日期多为周日，对交易日回测影响有限。
3. **OHLC 本地重算是近似**：用同一因子缩放 OHLC，与 QMT 真实复权可能存在微小误差。若对 OHLC 精度要求极高，可每月跑一次 `--rebuild-mode download --rebuild-window-years N` 做深刷新。
4. **不要直接依赖 QMT `front`**：本方案已改为本地推导，避免 front=none 的数据问题。
5. **断更保护**：`max_stale_days=7`，若某股票 adj_factor 断更超过 7 天，首次恢复时视为首次记录，避免误判。

---

## 6. 验证命令

```bash
# 检查 adj_factor 是否正常变化（不应全为 1.0 或常数）
D:\anaconda3\envs\vanna311\python.exe -c "
import pandas as pd
df = pd.read_parquet('stock_data/adj_factor.parquet')
sub = df[df.stock_code == '000002.SZ'].set_index('date').sort_index()
print(sub[['cumulative_adj_factor', 'adj_factor_back']].describe())
"

# 检查 front/none/back 最新日期是否一致
D:\anaconda3\envs\vanna311\python.exe -c "
import pandas as pd
from pathlib import Path
for dt in ['front', 'none', 'back']:
    p = Path(f'stock_data/period=1d/dividend_type={dt}/symbol=000001_SZ/data.parquet')
    d = pd.read_parquet(p)
    print(f'{dt}: {len(d)} rows, latest={d.index.max()}')
"
```

---

## 7. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-06-17 | 初稿。确认 QMT front 不可靠，改为从 back 推导 front；实现 `scripts/update_adjusted_daily.py`；本文件作为 SSOT。 |
