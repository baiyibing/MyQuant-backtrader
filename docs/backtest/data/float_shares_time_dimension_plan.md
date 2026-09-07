# 流通股本 / 自由流通股本 时间维度化方案 v2

**文档编号**: PLAN-2026-0515-003
**日期**: 2026-05-15（原始） | 2026-05-30（v2 重写：miniQMT Capital 表替代 akshare 反推）
**状态**: v2 已落地（`free_float_shares.parquet` 385,130 行 / 5,522 只 / 2001~2026）
**关联**: `oskh_data/free_float_shares.py`, `backtest/chip_algorithm.py`, `stock_data/float_shares.parquet`, `stock_data/free_float_shares.parquet`

> **v2 核心变更**：原方案假设 miniQMT 无法提供历史股本数据，依赖 akshare 从 turnover 反推。2026-05-30 实测发现 miniQMT 的 `Capital` 财务表原生提供 `freeFloatCapital`（自由流通股本）和 `circulating_capital`（流通股本）的历史季度数据，精度远超反推方案。本方案切换为 miniQMT 直读。

---

## 问题定义

换手阻力计算需要两类股本：

| 指标 | 含义 | 来源 |
|------|------|------|
| **自由流通股本** (`freeFloatCapital`) | 剔除持股 5%+ 股东、董监高、国有持股后的实际可交易股数 | miniQMT `Capital` 表 |
| **流通股本** (`circulating_capital`) | 已上市流通 A 股总股数（含限售已解禁） | miniQMT `Capital` 表 |

`turnover_rate = volume / 股本`。用"今天的股本"算"历史的 turnover_rate"会产生系统性偏差——送转股、增发、限售解禁都会改变股本。回测需要用历史时点的股本，不能用当前快照。

miniQMT `get_instrument_detail()` 只返回当前 `FloatVolume`，不支持历史查询。但 `get_financial_data(table_list=['Capital'])` 提供**季度历史**：每只股票每个报告期一行，包含上述所有字段。

---

## 数据源

### 主数据源：miniQMT Capital 财务表

```python
from xtquant import xtdata

# 下载（首次或增量）
xtdata.download_financial_data2(
    stock_list, table_list=['Capital'],
    start_time='20200101', end_time='20260530',
)

# 查询
data = xtdata.get_financial_data(
    ['000001.SZ'], table_list=['Capital'],
    start_time='20200101', end_time='20260530',
    report_type='report_time',
)
df = data['000001.SZ']['Capital']
```

**可用字段**（miniQMT 原始字段名）：

| 字段 | 类型 | 含义 |
|------|------|------|
| `m_timetag` | timestamp | 报告截止日（主键，如 2024-12-31） |
| `m_anntime` | timestamp | 公告日 |
| `freeFloatCapital` | float | **自由流通股本**（股） |
| `circulating_capital` | float | 流通股本（股） |
| `restrict_circulating_capital` | float | 限售流通股份（股） |
| `total_capital` | float | 总股本（股） |

**粒度**：季度（每只股票每年 4 行）。部分股票有半年报、季报的中间时点（如 2024-09-30、2025-03-31）。

**覆盖范围**：全市场 A 股（实际测试 000001.SZ 有 22 行，覆盖 2020Q1 ~ 2026Q1）。

### 辅助数据源：miniQMT get_instrument_detail

```python
xtdata.get_instrument_detail('000001.SZ')
# → FloatVolume, TotalVolume  # 仅当前值
```

用于补充最新时点的实时值（财务报告有滞后，最新报告截止日可能是上季度）。

---

## 存储设计

### 主文件：`stock_data/free_float_shares.parquet`

```
columns: stock_code, m_timetag, freeFloatCapital, circulating_capital, restrict_circulating_capital, total_capital
key: (stock_code, m_timetag)
sorted by: stock_code, m_timetag
granularity: 季度（每只股票每季度一行）
volume: ~5,500 只 × 4 季/年 × 10 年 ≈ 220K 行, Parquet ~5MB
```

### 静态快照：`stock_data/float_shares.parquet`

```
columns: stock_code, FloatVolume, TotalVolume, name, updated_at
key: stock_code
source: get_instrument_detail()
granularity: 单日快照（仅当前值）
volume: ~5,500 行, Parquet ~500KB
```

由 `oskh_data/float_shares.py` 维护（`get_instrument_detail()` 当前值）。

### 命名约定

所有 parquet 列名**直接使用 miniQMT 原始字段名**，不做 snake_case 转换：

| 来源 | miniQMT 字段名 | parquet 列名 |
|------|---------------|-------------|
| `get_instrument_detail()` | `FloatVolume` | `FloatVolume` |
| `get_instrument_detail()` | `TotalVolume` | `TotalVolume` |
| `Capital` 财务表 | `m_timetag` | `m_timetag` |
| `Capital` 财务表 | `freeFloatCapital` | `freeFloatCapital` |
| `Capital` 财务表 | `circulating_capital` | `circulating_capital` |
| `Capital` 财务表 | `restrict_circulating_capital` | `restrict_circulating_capital` |
| `Capital` 财务表 | `total_capital` | `total_capital` |

**两个文件的使用场景**：

```
回测 (date='2023-06-15'):
  _get_float_shares('000001.SZ', date='2023-06-15')
    → free_float_shares.parquet → circulating_capital
  _get_free_float_shares('000001.SZ', date='2023-06-15')
    → free_float_shares.parquet → freeFloatCapital
  float_shares.parquet 不参与回测

实时 (date=None):
  _get_float_shares('000001.SZ')
    → float_shares.parquet → FloatVolume（兜底：QMT 挂了至少还有上一天缓存）
  _get_free_float_shares('000001.SZ')
    → 抛错（freeFloatCapital 无实时来源，get_instrument_detail 不返回）
```

两个指标独立使用，不做 fallback——freeFloatCapital 查不到直接抛错，不回退 FloatVolume（194 亿 vs 86 亿，不同口径）。

**实际数据**（2026-05-30 跑完全量）：
- `free_float_shares.parquet`: 385,130 行 / 5,522 只 / 2001-01-05 ~ 2026-05-30
- 数据覆盖逐年增长：2001 年 213 只 → 2025 年 5,463 只

### 生成与更新

```bash
# 全量初始化（首次）
python -m oskh_data.free_float_shares --update --start 20200101

# 收盘后增量更新（定期）
python -m oskh_data.free_float_shares --update --start 20260501
```

实现：`oskh_data/free_float_shares.py`
1. `download_financial_data2(table_list=['Capital'])` 下载到 QMT 本地缓存
2. `get_financial_data(table_list=['Capital'])` 读取
3. 按 `(stock_code, m_timetag)` 去重合并
4. 输出 parquet

---

## 查询接口

两个独立函数，各司其职：

```python
# 流通股本（FloatVolume / circulating_capital）
def _get_float_shares(stock_code=None, date=None) -> float:
    """
    1. date is not None → 查 free_float_shares.parquet
       → merge_asof: date <= target_date 的最新行
    2. date is None → 查 float_shares.parquet（最新快照）
    """

# 自由流通股本（freeFloatCapital）
def _get_free_float_shares(stock_code=None, date=None) -> float:
    """
    1. date is not None → 查 free_float_shares.parquet
       → merge_asof: m_timetag <= target_date 的最新行
       → gap > 90 天：warning + 继续用旧值
       （自由流通股本年级别才变一次，旧值远比换口径可靠）
    2. NOT fallback 到 FloatVolume
       （194 亿 vs 86 亿是不同的指标，fallback 会产生换手率跳变）
    """
```

**调用方式**：

```python
# 流通股本换手阻力
arr = adapt_columns(df, stock_code, as_of_date=date, use_free_float=False)
resistance_circ = turnover_chip_factors(arr)

# 自由流通股本换手阻力
arr = adapt_columns(df, stock_code, as_of_date=date, use_free_float=True)
resistance_free = turnover_chip_factors(arr)
```

---

## 实施步骤（v2 修订）

| # | 任务 | 状态 |
|---|------|:--:|
| 1 | `oskh_data/free_float_shares.py` 脚本 | ✅ |
| 2 | miniQMT `Capital` 表验证 | ✅ |
| 3 | 全量历史回填 | ✅ 385,130 行/5,522 只/2001~2026 |
| 4 | `_get_free_float_shares` + `adapt_columns(use_free_float=)` | ✅ |
| 5 | `float_shares_history.parquet` 废弃，代码和文档清理 | ✅ |
| 6 | 芯片/换手阻力调用方接入 `freeFloatCapital` | ⬜ |
| 7 | 验证：对比流通股本 vs 自由流通股本的 turnover_rate 偏差 | ⬜ |

---

## 相对 v1 的变更摘要

| 维度 | v1（旧） | v2（新） |
|------|---------|---------|
| 历史数据源 | akshare 从 turnover 反推 | miniQMT `Capital` 表直读 |
| 精度 | 反推（元级舍入 + 前视偏差） | 原生（财报公告值） |
| 指标 | 仅 `float_shares` | `freeFloatCapital` + `circulating_capital` |
| 粒度 | 每日（从 snapshot 铺平） | 季度（自然报告期） |
| 查询方式 | 精确匹配 `date` | `merge_asof`（`<= target_date` 最近） |
| 外部依赖 | akshare（限流/封IP风险） | 无需，全走 miniQMT |
| 存储体积 | ~300MB | ~5MB |

---

## 验收基线

1. **数据完整性**：`free_float_shares.parquet` 覆盖全部 ~5500 只 A 股，每只至少 4 季/年
2. **一致性**：最新一期 `freeFloatCapital` 与 `float_shares.parquet` 的 `FloatVolume` 交叉校验，偏差 < 5%
3. **回测基线**：同一标的同一区间，对比 静态股本 vs 时序股本 的 `turnover_rate` 偏差分布（P50/P95/Max）
4. **兼容性**：`_get_float_shares(stock_code)` 不传 `date` 时行为不变
