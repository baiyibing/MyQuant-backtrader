# Parquet + DuckDB 双模式股票数据读取方案

**文档编号**: PLAN-2026-0515-001  
**日期**: 2026-05-15  
**状态**: ✅ 已实现（2026-05-15）  
**关联**: `duckdb_scheme_a_vs_b_benchmark_plan.md`（benchmark 方案与结果）  
**实现**: `backtest/stock_data_reader.py` | 配置: `config/reader.yaml` | CLI: `python backtest/stock_data_reader.py --build`

---

## 1. 现状与问题

### 1.1 当前数据存储

- **存储格式**：Parquet + Snappy 压缩
- **目录结构**：`stock_data/period={period}/dividend_type={adjust}/symbol={code}/data.parquet`（下划线命名，如 `symbol=000001_SZ`）
- **总量**：5,525 只股票 × 3 种复权 × 日线（front 834 MB / back 838 MB / none 837 MB，合计 ~2.5 GB）+ 2,122 只 × 分钟线 none（~4.9 GB），共 ~12 GB
- **每文件 schema**：`time`(int64 ms), `open`, `high`, `low`, `close`, `volume`(int64), `amount`（7 列，所有文件一致）

### 1.2 当前读取模式

数据读取集中在 `backtest/` 目录，主要用于回测。典型读取方式：

**单只股票读取**（`qmt_utils_adv.py:get_stock_data`）：
```python
file_path = base_dir / f"period={period}" / f"dividend_type={adjust}" / f"symbol={code}" / "data.parquet"
df = pd.read_parquet(file_path, engine='pyarrow')
```

**全市场遍历**（`filter_chip_stocks.py`、`chip_backtest.py` 等）：
```python
for code in all_codes:           # ~5,500 只
    path = ... / f"symbol={code}" / "data.parquet"
    df = pd.read_parquet(path)   # 每次都要打开文件、解析 metadata、读取数据
    # 计算因子...
```

### 1.3 性能瓶颈

| 场景 | 当前做法 | 问题 |
|------|---------|------|
| 单只股票回测 | `pd.read_parquet(path)` | 可接受 |
| 全市场因子计算 | Python for-loop 逐个打开 5,500 个 parquet 文件 | **极慢** — 每次都要重复解析文件头、建立文件句柄 |
| 多日期截面筛选 | 遍历所有 symbol 目录，每个文件内再按日期过滤 | **双重慢** — 磁盘随机 I/O + Python 循环开销 |

> DuckDB 已安装（v1.5.2），但当前代码未使用。

---

## 2. 目标与假设

### 2.1 目标

1. **下载不变**：`qmt_utils_adv.py` 继续将数据写入 parquet 文件。
2. **读取可切换**：提供一个统一读取层，支持 `parquet`（原生）和 `duckdb` 两种模式。
3. **性能提升**：全市场遍历场景下，DuckDB 模式比原生 for-loop 显著提速。实测（`benchmark/duckdb_benchmark.py`）全市场 1 天截面 **3.52×**、1 年历史 **2.86×**、聚合 **11.47×**、单股点查 **357×**（详见 §9.2）。
4. **低侵入切换**：底层读取入口统一拦截，业务脚本不直接散落 `pd.read_parquet()` 调用；已有脚本逐步收敛到统一入口，而非逐文件硬改。
5. **可回归一致**：日线场景下，两种模式读取同一只股票、同一时间窗，返回的 DataFrame 在**行数、索引、关键列值、时间边界**上必须逐项等价。

### 2.2 假设

1. **默认安全回退优先于最大性能**：默认模式仍为 `parquet`，DuckDB 需显式开启；切换后系统行为可观测、可回退。
2. **分钟线语义不变**：分钟线强制 `adjust_type='none'` 的现有业务语义必须保留，新方案不做任何复权口径变更。
3. **schema 一致性**：所有 parquet 文件由同一套下载脚本生成，列名、类型、顺序一致。

---

## 3. 推荐方案：统一读取层 + 双模式 DuckDB 后端

### 3.1 核心思路

新建 `backtest/stock_data_reader.py`，封装三种读取后端：

- **`parquet` 模式**（默认）：保持现有行为，`pd.read_parquet()` 逐文件读取，兼容回退。
- **`duckdb` 模式**：DuckDB `:memory:` 连接 + `read_parquet(glob)` 直接扫描 parquet 目录，一条 SQL 完成全市场读取。
- **`duckdb_persistent` 模式**（补充）：DuckDB 连接本地 `.duckdb` 持久化文件 + 查表，已通过 benchmark 验证（详见 §9），适合高频全市场查询和单股点查。

DuckDB 两种模式都比 Python for-loop 逐个 `pd.read_parquet()` 快得多，因为：
- DuckDB 是 C++ 实现，文件 I/O 和列过滤在底层完成
- 支持**谓词下推**（predicate pushdown）：只读取满足 `WHERE` 条件的行
- 支持**投影下推**（projection pushdown）：只读取需要的列
- 可以**并行读取**多个 parquet 文件
- `duckdb_persistent` 额外享有**索引加速**和**zone map**，单股点查可达 350× 以上

### 3.2 文件架构

```
backtest/
  stock_data_reader.py   # 新增：统一读取层（必选）
  qmt_utils_adv.py       # 保持下载职责，不接入 reader（读取入口收敛到 StockDataReader）
  filter_chip_stocks.py  # 必选修改：全市场遍历必须改用 reader.scan_stocks()
  ...
```

### 3.3 接口设计

```python
# backtest/stock_data_reader.py

class StockDataReader:
    """
    统一股票数据读取层，支持 parquet 原生和 DuckDB 两种模式。

    用法：
        reader = StockDataReader(mode="duckdb", base_dir="stock_data")
        # 单只股票
        df = reader.read_stock("000001.SZ", period="1d", adjust="front",
                               start_time="20240101", end_time="20241231")
        # 全市场批量读取（DuckDB 优势场景）
        df = reader.scan_stocks(period="1d", adjust="front",
                                start_time="20240101", end_time="20241231")
        # df 包含所有股票的合并数据，建议通过 code/symbol 列区分
    """

    def __init__(self, base_dir: str = "stock_data", mode: str = "parquet",
                 db_path: str = None):
        """
        mode: "parquet" | "duckdb" | "duckdb_persistent"
        db_path: duckdb_persistent 模式下的 .duckdb 文件路径，默认 base_dir/../stock_data.duckdb
        """
        ...

    def read_stock(self, stock_code: str, period: str = "1d",
                   adjust_type: str = "front",
                   start_time: str = None, end_time: str = None,
                   columns: List[str] = None) -> Optional[pd.DataFrame]:
        """读取单只股票数据。duckdb_persistent 模式走索引查表。"""
        ...

    def scan_stocks(self, stock_codes: List[str] = None,
                    period: str = "1d", adjust_type: str = "front",
                    start_time: str = None, end_time: str = None,
                    columns: List[str] = None,
                    chunk_size: int = None) -> Optional[pd.DataFrame]:
        """
        批量读取多只股票数据。
        当 stock_codes 为 None 时，扫描全市场所有股票。
        duckdb 模式：read_parquet(glob) 批量扫描。
        duckdb_persistent 模式：查持久化表（~3× 快于 duckdb 模式）。
        parquet 模式：内部逐只 concat。
        返回的 DataFrame 包含 symbol 列用于区分不同股票。
        """
        ...

    @staticmethod
    def build_persistent_db(base_dir: str, db_path: str = None,
                            period: str = "1d", adjust_type: str = "front"):
        """
        构建 duckdb_persistent 所需的 .duckdb 文件。
        应在下载脚本完成后调用，或手动执行。
        预计耗时 ~46s，产出 ~1.0–1.7 GB 文件。
        """
        ...
```

### 3.4 三种模式实现对比

| 功能 | parquet（默认） | duckdb（:memory: + glob） | duckdb_persistent（.duckdb 文件） |
|------|----------------|--------------------------|----------------------------------|
| `read_stock` 单只 | `pd.read_parquet(path)` + 时间过滤 | 同 parquet（单文件无收益） | 索引查表 `WHERE symbol=? AND time BETWEEN ?` |
| `scan_stocks` 全市场 | for-loop + `pd.concat()` | `read_parquet(glob)` + SQL | 查持久化表 + SQL |
| 全市场性能（vs parquet） | 基线 1× | **2.5–3.5×** | **2.9–11.5×**（实测） |
| 单股点查性能 | 基线 1× | 同 parquet | **~357×**（索引 + zone map） |
| 数据同步 | 实时（直接读 parquet） | 实时（直接读 parquet） | 需重建 DB（~46s），下载后触发 |
| 额外磁盘占用 | 无 | 无 | ~1.0–1.7 GB（膨胀 1.2–2.0×） |
| 依赖 | pyarrow | duckdb | duckdb |
| 启动开销 | 无 | 无（`:memory:` 每次新建） | 建库一次 ~46s，后续查询零开销 |

### 3.4.1 DuckDB 分区列解析约束（实现细节）

DuckDB 的 `read_parquet('.../*/data.parquet')` 默认支持 Hive 分区列解析，目录名如 `symbol=000001.SZ` 会自动映射为 DataFrame 中的 `symbol` 列。实现时必须确认：

> **注意**：仓库实际目录中的 symbol 值可能为 `000001_SZ`（下划线风格）或 `000001.SZ`（点号风格），DuckDB 按实际目录名解析出 `symbol` 列；`scan_stocks()` 返回前必须将 symbol 统一规范化为点号格式（`000001.SZ`），与下游代码一致。

1. **DuckDB 版本 >= 0.8.0**（已满足，当前 v1.5.2）
2. **查询中显式包含 `symbol` 列**：`SELECT symbol, time, close, ... FROM read_parquet(...)`
3. **若 DuckDB 未自动解析分区列**，需在 `read_parquet` 中显式开启 `hive_partitioning=1`：
   ```sql
   SELECT * FROM read_parquet('.../*/data.parquet', hive_partitioning=1)
   ```
4. **下游分组依赖**：`scan_stocks()` 返回的 DataFrame 必须包含 `symbol` 列，否则全市场聚合/分组逻辑会失败；该列为验收清单的隐含项。

---

### 3.5 透明切换设计（核心）

用户核心诉求：**通过开关在 parquet / DuckDB 之间切换**，业务脚本尽可能少改动。

**关键约束：避免"部分 DuckDB、部分 Parquet"的混合状态**

评审意见指出：若只改一部分入口、另一部分脚本继续直接 `pd.read_parquet(path)`，系统会进入混合状态，结果一致性和性能都不可预期。

**因此，切换策略收敛为：StockDataReader 作为唯一读取入口，分两级迁移**

1. **`StockDataReader` 作为唯一读取入口**
   - `DataDownloader` 保持下载职责不变（从 QMT 拉数据写入 parquet），**不做读取路由**
   - 所有读取逻辑集中到 `StockDataReader`，避免下载器初始化依赖 QMT session 导致纯回测场景无法使用
   - 环境变量 `STOCK_DATA_READER_MODE` 由 `StockDataReader` 读取，不侵入下载器

2. **分两级迁移策略**
   - **一级（Phase 1 必须）**：全市场遍历脚本（`filter_chip_stocks.py`、`chip_backtest.py` 等）→ **必须迁移到 `scan_stocks()`**
   - **二级（Phase 2 逐步）**：单只股票读取脚本（回测、验证等）→ 可保留 `pd.read_parquet()`，逐步迁移到 `StockDataReader.read_stock()`，**不阻塞合入**

**开关设计（推荐环境变量）**：

| 方式 | 用法 | 推荐度 |
|------|------|--------|
| **环境变量** | `set STOCK_DATA_READER_MODE=duckdb` | ⭐⭐⭐ 最透明，只需改 StockDataReader |
| YAML 配置 | `runtime.yaml` 中增加 `data_reader: {mode: duckdb}` | ⭐⭐ 需读取配置 |
| 函数参数 | `StockDataReader(mode="duckdb")` | ⭐ 需逐处传递，不推荐 |

**环境变量 + 全局默认**

```python
# backtest/stock_data_reader.py 顶部
import os
DEFAULT_READER_MODE = os.environ.get("STOCK_DATA_READER_MODE", "parquet")
# 取值: "parquet"（默认） | "duckdb"（read_parquet 直读） | "duckdb_persistent"（.duckdb 查表）
```
`duckdb_persistent` 模式需预建 `.duckdb` 文件（通过 `StockDataReader.build_persistent_db()` 或 `benchmark/duckdb_benchmark.py`），否则回退到 `duckdb` 模式。

脚本侧收敛示例：
```python
# filter_chip_stocks.py 修改前（散落直读）
for code in all_codes:
    path = os.path.join(DAILY_DIR, f"symbol={code}", "data.parquet")
    df = pd.read_parquet(path)   # ❌ 直接读文件，绕过统一入口

# filter_chip_stocks.py 修改后（全市场扫描：走批量接口）
reader = StockDataReader(mode=DEFAULT_READER_MODE, base_dir=REPO + "/stock_data")
df_all = reader.scan_stocks(period="1d", adjust_type="front",
                            start_time="20200101", end_time="20250101")
# ✅ duckdb 模式：read_parquet(glob) 一条 SQL 扫描全市场
# ✅ duckdb_persistent 模式：查持久化表，额外 2–3× 提升
# ✅ parquet 模式：内部逐只读取后 concat（兼容回退）
# 返回的 DataFrame 包含 symbol 列用于区分股票
```

**读取路径决策树**：

| 场景 | 推荐接口 | 迁移要求 | 说明 |
|------|---------|---------|------|
| 单只股票回测/验证 | `reader.read_stock(code, ...)` | Phase 2 逐步，不阻塞 | 两种模式底层都是 `pd.read_parquet()`，零额外开销 |
| 全市场因子计算/截面筛选 | **`reader.scan_stocks(...)`** | **Phase 1 必须** | DuckDB 批量扫描是性能核心；parquet 模式下内部逐只 concat |
| 自定义股票列表（如 500 只成分股） | `reader.scan_stocks(stock_codes=[...])` | Phase 1 必须 | 批量接口支持指定列表 |

### 3.6 对现有代码的改动点

**改动 1：新增 `backtest/stock_data_reader.py`**
- 实现 `StockDataReader` 类，封装两种模式
- `mode="parquet"` 时行为与现有代码完全一致
- `mode="duckdb"` 时建立内存 DuckDB 连接，用 SQL 查询 parquet

**改动 2：`backtest/qmt_utils_adv.py` / `qmt_utils_new.py` 的 `get_stock_data()` 保持不变**
- `DataDownloader` 仅负责下载，不介入读取路由
- 避免下载器初始化依赖 QMT session 导致纯回测场景不可用

**改动 3（Phase 1 必选）：收敛全市场遍历脚本**
- `filter_chip_stocks.py`、`chip_backtest.py` 等所有**全市场遍历**脚本
- 将 for-loop 直读替换为 `StockDataReader.scan_stocks()`
- 未收敛的全市场脚本不得合入主干

**改动 4（Phase 2 逐步）：单只读取脚本可选迁移**
- 回测、验证等单只股票读取场景可保留 `pd.read_parquet()` 或逐步迁移到 `StockDataReader.read_stock()`
- 不阻塞合入

### 3.7 切换方式（推荐环境变量）

**方式 1：环境变量（最透明，推荐）**

```bash
# Windows CMD
set STOCK_DATA_READER_MODE=duckdb               # read_parquet(glob) 直读
set STOCK_DATA_READER_MODE=duckdb_persistent    # .duckdb 持久化表（需先建库）
set STOCK_DATA_READER_MODE=parquet              # 默认，pd.read_parquet() 逐文件

python backtest/filter_chip_stocks.py
```

代码侧只需在底层读取函数顶部读取该变量：
```python
# backtest/stock_data_reader.py 顶部
import os
DEFAULT_READER_MODE = os.environ.get("STOCK_DATA_READER_MODE", "parquet")
```

**方式 2：代码显式切换（开发调试用）**
```python
from backtest.stock_data_reader import StockDataReader
reader = StockDataReader(mode="duckdb")
```

**方式 3：YAML 配置（可选扩展）**
```yaml
# runtime.yaml 中增加
data_reader:
  mode: duckdb   # parquet | duckdb
```

---

## 4. 性能数据

已通过 `benchmark/duckdb_benchmark.py` 实测（warmup=3, timed=5, SSD, DuckDB 1.5.2, 5,525 只日线 front）。

### 4.1 方案 A（duckdb: read_parquet 直读）vs parquet 原生

| 场景 | parquet 原生 (for-loop) | duckdb (read_parquet glob) | 加速比 |
|------|------------------------|---------------------------|--------|
| 单只股票 1 年数据（日线） | ~50 ms | ~50 ms | 持平 |
| 全市场 1 天截面（~5.5K 行） | ~10s（逐文件） | — | **3.5×**（vs duckdb_persistent） |
| 全市场 1 年历史（~1.4M 行） | ~60–120s | — | 见 §4.2 |
| 全市场聚合（GROUP BY） | ~5s | — | 见 §4.2 |

> 注：parquet 原生全市场遍历耗时基于 5,525 文件 for-loop 估算，实际会因磁盘缓存波动。

### 4.2 方案 B（duckdb_persistent: .duckdb 持久化表）vs duckdb 直读

实测数据（E2E Cold，单位秒）：

| 场景 | duckdb (A) | duckdb_persistent (B) | B/A 加速比 |
|------|-----------|----------------------|-----------|
| 全市场 1 天截面 | 9.98s | **2.84s** | **3.52×** |
| 全市场 1 年历史 | 14.28s | **5.00s** | **2.86×** |
| 单股 10 年历史 | 5.83s | **0.016s** | **357×** |
| 全市场聚合 | 4.94s | **0.43s** | **11.47×** |

**DB 开销**：1,057 MB（膨胀 1.27×），建库 46s。

完整 benchmark 报告见 `duckdb_scheme_a_vs_b_benchmark_plan.md`。

---

## 5. 风险与缓解

| 风险 | 等级 | 说明 | 缓解 |
|------|------|------|------|
| DuckDB 内存占用 | 中 | `:memory:` 连接加载大量数据时可能占用较多内存 | scan_stocks 返回 DataFrame 后立即使用，不长期持有；大查询可分页 |
| `.duckdb` 与 parquet 源不同步 | 中 | 下载新数据后，持久化 DB 包含旧数据 | 下载脚本末尾触发 `build_persistent_db()` 重建（~46s）；或在 `StockDataReader` 初始化时校验 parquet 最新 mtime |
| `.duckdb` 磁盘膨胀 | 低 | 实测 1.27×（1,057 MB vs 834 MB），可接受 | 若未来超过 2× 阈值，检查 DuckDB 版本或手动 VACUUM |
| parquet 文件更新后 DuckDB metadata 缓存不一致 | 低 | `duckdb` 模式在同 session 内可能缓存 parquet metadata | **连接生命周期绑定到 StockDataReader 实例**：脚本内复用同一个 reader；仅在已知 parquet 变更时重建连接 |
| 列名/类型不一致 | 低 | 不同股票的 parquet 文件列名相同，但 DuckDB 对 schema 变化较敏感 | 所有 parquet 由同一脚本生成，schema 一致 |
| 新增依赖 | 低 | 依赖 duckdb 包 | 已安装（v1.5.2），无需新增 |
| 回退兼容性 | 低 | `mode="parquet"` 与现有行为完全一致 | 默认 mode 设为 `"parquet"`，DuckDB 为显式开启 |

---

## 6. 实施步骤

| 步骤 | 内容 | 预估工作量 | 状态 |
|------|------|-----------|------|
| 0 | Benchmark 验证：`benchmark/duckdb_benchmark.py` 对比方案 A/B 性能（详见 `duckdb_scheme_a_vs_b_benchmark_plan.md`） | 0.5 天 | ✅ 已完成 |
| 1 | 编写 `backtest/stock_data_reader.py`（含 parquet / duckdb / duckdb_persistent 三种模式 + 单只/批量接口 + build_persistent_db + CLI + YAML 配置） | 2–3 小时 | ✅ 已完成 |
| 2 | 单元测试 + 回归测试：三模式等价性（行数/时间边界/symbol/逐行 allclose）+ `filter_chip_stocks.py` / `chip_backtest.py` 端到端输出一致 | 30 分钟 | ✅ 已完成 |
| 3 | 基准回归：日线 + 分钟线 benchmark（`--period 1d|1m`），分钟线全市场场景 ≥ 2.0×，已纳入方案 B | 30 分钟 | ✅ 已完成 |
| 4 | 收敛 11 个直读脚本 + 多进程安全性验证（8 进程 PASS）+ 下载流程 `.duckdb` 自动重建集成 | 1–2 小时 | ✅ 已完成 |

---

## 7. 行为等价性验收清单

两种模式读取同一只股票、同一时间窗、同一复权类型时，返回的 DataFrame 必须在以下维度逐项等价：

| 验收项 | 验收标准 | 验证方法 |
|--------|---------|---------|
| **行数** | `len(df_parquet) == len(df_duckdb)` | 直接比对 |
| **索引** | `df_parquet.index.equals(df_duckdb.index)` | 索引值和类型一致 |
| **关键列值** | `df_parquet[['open','high','low','close','volume','amount']].equals(df_duckdb[...])` | 浮点列允许 `np.allclose` 容差 |
| **time 列** | `df_parquet['time'].values.tolist() == df_duckdb['time'].values.tolist()` | 毫秒时间戳精确匹配 |
| **分钟线复权语义** | `period='1m'` 时两种模式均强制 `adjust_type='none'` | 断言分钟线返回的 adjust 参数为 none |
| **时间边界** | `min(index) >= start_dt` 且 `max(index) <= end_dt` | 边界包含关系一致（`[start, end]` 闭区间） |
| **空结果处理** | 无数据时统一返回 `None`（与现有 `qmt_utils_adv.py` 行为一致） | 两种模式均返回 `None`，不允许返回空 DataFrame |
| **symbol 格式统一** | `scan_stocks()` 返回的 `symbol` 列统一为点号格式（`000001.SZ`），无论目录名是下划线还是点号风格 | 断言所有 symbol 值含 `.` 不含 `_` |
| **列类型** | `df_parquet.dtypes.equals(df_duckdb.dtypes)` | 类型一致 |

> **未达标即阻塞上线**：任一项不一致，必须定位根因并修复后方可合并。

---

## 8. 性能基准规范

> 本基准已通过 `benchmark/duckdb_benchmark.py` 完成，详细方案与结果见 `duckdb_scheme_a_vs_b_benchmark_plan.md`。实测数据见 §4 和 §9.2。以下规范保留作为未来扩展（如分钟线、其他复权类型）的参考。

| 维度 | 规范 |
|------|------|
| **测试样本** | 500 只 / 2,000 只 / 5,500 只（三档） |
| **时间窗** | 1 年（~250 交易日）/ 10 年（~2,500 交易日） |
| **复权类型** | front（日线） |
| **机器规格** | 记录 CPU、内存、磁盘类型（SSD/HDD） |
| **冷热缓存** | 每种组合跑 **冷启动**（系统缓存清空后）和 **热启动**（重复跑一次）各 5 次 |
| **统计方法** | 记录中位数和 P95，剔除异常值（>3σ） |
| **失败阈值** | 按场景分阈值：<br>• 全市场扫描：DuckDB 加速比 **< 2×** 时判定不达标<br>• 单只股票：DuckDB 耗时落在 parquet **0.8× ~ 1.2×** 之外时判定不达标 |
| **报告格式** | 表格：样本数 × 时间窗 × 冷/热 × parquet 中位数/P95 × DuckDB 中位数/P95 × 加速比 |

---

## 9. 补充模式：DuckDB 本地持久化数据库

### 9.1 概述

将全量 parquet 数据导入一个本地 `.duckdb` 文件，作为方案 A（`read_parquet` 直读）的**补充模式**，面向高频全市场查询和单股点查场景。

2026-05-15 已通过 benchmark 验证（详见 `duckdb_scheme_a_vs_b_benchmark_plan.md`）。

### 9.2 Benchmark 结论

| 场景 | 方案 A (read_parquet) | 方案 B (.duckdb) | B/A 加速比 | 判定 |
|------|----------------------|-------------------|-----------|------|
| 全市场 1 天截面（~5.5K 行） | 9.98s | **2.84s** | **3.52×** | ≥2.0× |
| 全市场 1 年历史（~1.4M 行） | 14.28s | **5.00s** | **2.86×** | ≥2.0× |
| 单股 10 年历史（~2.5K 行） | 5.83s | **0.016s** | **357×** | 索引优势 |
| 全市场聚合（AVG GROUP BY） | 4.94s | **0.43s** | **11.47×** | ≥2.0× |

**DB 开销**：1,057 MB（parquet 源 834 MB，膨胀 1.27×），建库 46 秒（5,525 只/日线 front）。

**正确性**：4/4 场景通过（行数 / 时间边界 / symbol / 逐行 allclose）。

### 9.3 双模式定位

| 对比 | 方案 A（默认） | 方案 B（补充模式） |
|------|--------------|------------------|
| 数据源 | parquet 文件（权威） | `.duckdb` 文件（副本） |
| 同步机制 | 实时（直接读 parquet） | 下载后重建 DB（~46s） |
| 写入改动 | 无 | 下载流程末尾触发 rebuild |
| 全市场扫描性能 | 基线 | **2.9×~3.5×** 快于 A |
| 单股点查性能 | 基线 | **350×** 快于 A（索引 + zone map） |
| 聚合查询性能 | 基线 | **11×** 快于 A |
| 维护成本 | 低 | 中（增量同步策略待定） |

### 9.4 启用方式

方案 B 作为补充模式，与环境变量 `STOCK_DATA_READER_MODE` 并行：

| 模式 | 环境变量值 | 说明 |
|------|-----------|------|
| 方案 A（默认） | `parquet` | 直接读 parquet，零额外依赖 |
| 方案 B（补充） | `duckdb_persistent` | 读 `.duckdb` 持久化表，需先建库 |

> 方案 A 为默认，方案 B 需显式开启。两者通过统一 `StockDataReader` 接口切换，业务脚本无感知。

---

## 10. 开放问题（全部已关闭 ✅）

1. **分钟线是否纳入 DuckDB 切换？** ✅ 已纳入  
   分钟线（v2.0, 2026-05-28）：已从持久化 `.duckdb` 切换为 `:memory:` + `read_parquet(glob)` 视图。`StockDataReader.duckdb_persistent` 模式下首次查询自动创建内存视图（启动 ~1s，431M 行），进程生命周期内复用。不再维护 `stock_data_minute.duckdb` 文件，不再执行 rebuild。详见 `docs/backtest/data/minute_backfill_optimization_plan.md` §3.4。

2. **多进程/多线程并发读取** ✅ 已验证  
   `tests/test_stock_data_reader_multiprocess.py`：8 进程 × 20 查询，三种模式全部 PASS。`duckdb_persistent`（`read_only=True`）多进程共享无冲突（38 q/s，最快）。`:memory:` 天然隔离。

3. **`.duckdb` 增量同步策略** ✅ 全量重建  
   日线 46s / 分钟线 546s，下载后自动触发（`backfill_daily_data.py`）。增量同步无明确瓶颈，暂不实施。若未来符号数 >10,000 或下载频率升至小时级再评估。
