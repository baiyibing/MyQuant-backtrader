"""qlib_cost — 筹码分布纯算法包。

核心算法仅依赖 numpy/pandas/numba，无可视化/外部依赖。
用法::

    from qlib_cost import ChipFactor, calc_dist_chips, calc_cumpdf, calc_curpdf
    from qlib_cost import calc_distribution_of_chips, calc_rc, calc_roll_cyq
"""

from .cyq import ChipFactor, calc_curpdf, calc_cumpdf, calc_dist_chips
from .distribution_of_chips import calc_adj_turnover, calc_triang_pdf, calc_uniform_pdf
from .turnover_coefficient_ops import (
    calc_distribution_of_chips,
    calc_rc,
    calc_roll_cyq,
)
from .utils import rolling_frame, rolling_windows
