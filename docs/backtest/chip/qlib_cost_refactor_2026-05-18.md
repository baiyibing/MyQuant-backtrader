# qlib_cost 包结构重构

> 日期：2026-05-18
> 状态：已完成

## 背景

`backtest/chip_algorithm.py` 有 60 行 `importlib` 黑魔法，手工注册 `sys.modules` 中的 namespace package 和伪造依赖，仅为了绕过 `qlib_cost/scr/__init__.py` 中对 `empyrical`/`statsmodels`/`scipy` 的硬依赖。

核心算法（`cyq.py`、`distribution_of_chips.py`、`utils.py`、`turnover_coefficient_ops.py`）只依赖 `numpy`/`pandas`/`numba`，不需要任何可视化库。

## 变更

### 1. `qlib_cost/scr/__init__.py`

**之前**（1 行）：
```python
from .plotting import plot_dist_chips,model_performance_graph,plot_score_ic,...
```
→ 导入 `plotting.py` → 导入 `empyrical` → 整个链失败

**之后**：纯算法导出
```python
from .cyq import ChipFactor, calc_curpdf, calc_cumpdf, calc_dist_chips
from .distribution_of_chips import calc_adj_turnover, calc_triang_pdf, calc_uniform_pdf
from .utils import rolling_frame, rolling_windows
```

### 2. `qlib_cost/scr/turnover_coefficient_ops.py`

**之前**：`from qlib.data.ops import PairRolling` — 外部 qlib 依赖

**之后**：try/except 空实现
```python
try:
    from qlib.data.ops import PairRolling
except ImportError:
    class PairRolling:
        def __init__(self, *args, **kwargs): ...
```

### 3. `qlib_cost/__init__.py`（新增）

顶层导出，外部只需 `from qlib_cost import ...`：
```python
from .scr.cyq import ChipFactor, calc_curpdf, calc_cumpdf, calc_dist_chips
from .scr.distribution_of_chips import calc_adj_turnover, calc_triang_pdf, calc_uniform_pdf
from .scr.turnover_coefficient_ops import calc_distribution_of_chips, calc_rc, calc_roll_cyq
from .scr.utils import rolling_frame, rolling_windows
```

### 4. `backtest/chip_algorithm.py`

**之前**：60 行 importlib 黑魔法（手动注册 namespace、伪造 qlib.data.ops.PairRolling）

**之后**：3 行
```python
from qlib_cost import (
    ChipFactor, calc_curpdf, calc_cumpdf, calc_dist_chips,
    ...
)
from qlib_cost import cyq
from qlib_cost import turnover_coefficient_ops as tco
```

### 5. `qlib_cost/plotting.py`（原 `qlib_cost/scr/plotting.py`）

保留为可选模块，需手动 `from qlib_cost.plotting import ...`。`scr/` 目录已删除。

## 包结构（重构后，扁平化）

```
qlib_cost/
  __init__.py              ← 顶层导出（纯算法 API）
  cyq.py                   ← ChipFactor, calc_dist_chips, calc_curpdf, calc_cumpdf
  distribution_of_chips.py ← calc_adj_turnover, calc_triang_pdf, calc_uniform_pdf
  utils.py                 ← rolling_frame, rolling_windows
  turnover_coefficient_ops.py ← calc_distribution_of_chips, calc_rc, calc_roll_cyq
  plotting.py              ← 可选绘图（依赖 empyrical/statsmodels/scipy，需手动导入）
  factor_analyze.py        ← 因子分析（未改动）
  factor_expr.py           ← 因子表达式（未改动）
  qlib_workflow.py         ← Qlib 工作流（未改动）
  cyq_ops.py               ← 筹码分布算子（未改动）
```

## 依赖

| 模块 | 依赖 |
|------|------|
| 核心算法（cyq, distribution_of_chips, utils, turnover_coefficient_ops） | numpy, pandas, numba |
| plotting.py | empyrical, matplotlib, scipy, statsmodels |

## 验证

```bash
python -c "from qlib_cost import ChipFactor, calc_dist_chips, calc_cumpdf; print('OK')"
python -m pytest tests/test_market_data_plane.py -q  # 21 passed
```
