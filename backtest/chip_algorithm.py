# -*- coding: utf-8 -*-
"""
chip_algorithm.py — COST 筹码分布算法适配层

将 qlib_cost/ 的纯算法层适配到 backtrader 数据契约：
- 列名映射：volume → vol
- turnover_rate 生成：按流通股本动态估算（优先 float_shares_history 按日查询，
  其次静态 float_shares.parquet；缺失时抛 ValueError，P0-18 fail-close）
- 分钟线量价累积（跳过三角/均匀 PDF）
- 日线三角/均匀 PDF fallback

依赖：qlib_cost/cyq.py + distribution_of_chips.py + utils.py + turnover_coefficient_ops.py（零 Qlib 依赖层）
"""

import json
import numpy as np
import pandas as pd
from typing import Optional

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 导入 qlib_cost 纯算法层
# ---------------------------------------------------------------------------
from qlib_cost.distribution_of_chips import make_price_grid
from qlib_cost import (
    ChipFactor, calc_curpdf, calc_cumpdf, calc_dist_chips,
    calc_adj_turnover, calc_triang_pdf, calc_uniform_pdf,
    calc_distribution_of_chips, calc_rc, calc_roll_cyq,
)

from qlib_cost import cyq
from qlib_cost import turnover_coefficient_ops as tco

# ---------------------------------------------------------------------------
# 流通股本数据
# ---------------------------------------------------------------------------
# 默认值：100 亿股（中大盘典型值）。仅在 _estimate_turnover(float_shares=None) 窄路径使用。
_FLOAT_SHARES_DEFAULT: int = 10_000_000_000

# 模块级缓存
_float_shares_cache: Optional[pd.DataFrame] = None
_free_float_shares_cache: Optional[pd.DataFrame] = None


def _load_float_shares_map(parquet_path: str = None) -> pd.DataFrame:
    """加载流通股本 Parquet（当前快照），缓存到模块级变量。"""
    global _float_shares_cache
    if _float_shares_cache is not None:
        return _float_shares_cache
    from pathlib import Path

    from common.infra.data_root import resolve_source_parquet

    path = Path(parquet_path) if parquet_path else resolve_source_parquet("float_shares.parquet")
    if path.exists():
        _float_shares_cache = pd.read_parquet(path)
    else:
        _float_shares_cache = pd.DataFrame()
    return _float_shares_cache


def _load_free_float_shares(parquet_path: str = None) -> pd.DataFrame:
    """加载自由流通股本 Parquet（miniQMT Capital 财务表），缓存到模块级变量。"""
    global _free_float_shares_cache
    if _free_float_shares_cache is not None:
        return _free_float_shares_cache
    from pathlib import Path

    from common.infra.data_root import resolve_source_parquet

    path = Path(parquet_path) if parquet_path else resolve_source_parquet("free_float_shares.parquet")
    if not path.exists():
        _free_float_shares_cache = pd.DataFrame()
        return _free_float_shares_cache
    df = pd.read_parquet(path)
    if not df.empty and "m_timetag" in df.columns:
        df = df.copy()
        df["m_timetag"] = pd.to_datetime(df["m_timetag"]).dt.normalize()
    _free_float_shares_cache = df
    return _free_float_shares_cache


def _get_float_shares(stock_code: str = None, date=None) -> float:
    """
    获取流通股本（circulating_capital / FloatVolume）。

    1. date is not None → free_float_shares.parquet → circulating_capital
    2. date is None     → float_shares.parquet → FloatVolume
    """
    if stock_code and date is not None:
        ffs = _load_free_float_shares()
        if not ffs.empty:
            target_date = pd.Timestamp(date).normalize()
            matches = ffs[
                (ffs["stock_code"] == stock_code) & (ffs["m_timetag"] <= target_date)
            ].sort_values("m_timetag")
            if len(matches) > 0:
                row = matches.iloc[-1]
                fs = row.get("circulating_capital")
                if fs is not None and fs > 0:
                    gap_days = int((target_date - pd.Timestamp(row["m_timetag"])).days)
                    if gap_days > 90:
                        logger.warning(
                            "circulating_capital history gap >90 days",
                            context={
                                "stock": stock_code,
                                "target_date": target_date.strftime("%Y-%m-%d"),
                                "found_date": pd.Timestamp(row["m_timetag"]).strftime("%Y-%m-%d"),
                                "gap_days": gap_days,
                            },
                        )
                    return float(fs)

    if stock_code:
        df = _load_float_shares_map()
        if not df.empty:
            row = df[df["stock_code"] == stock_code]
            if len(row) > 0:
                fs = row.iloc[0].get("FloatVolume") or row.iloc[0].get("float_shares")  # v2 compat
                if fs is not None and fs > 0:
                    return float(fs)
        # P0-18 FIX: 有 stock_code 但找不到数据时抛异常，禁止静默回退 100 亿默认值
        logger.error(
            "float_shares missing",
            context={"stock": stock_code, "date": str(date)},
        )
        raise ValueError(
            f"float_shares missing for {stock_code}"
            f"{f' (date={date})' if date else ''}; "
            f"chip calculation cannot proceed with default"
        )

    # P0-18 FIX: stock_code=None 也不允许静默回退 —— 没有股票代码就无法查流通股本，
    # 使用 100 亿默认值会产生严重失真的筹码分布。调用方必须提供 stock_code。
    logger.error(
        "float_shares unavailable: stock_code not provided",
        context={"stock": stock_code, "date": str(date)},
    )
    raise ValueError(
        "float_shares unavailable: stock_code is required "
        "for chip calculation; cannot use 100亿 default"
    )


def _get_free_float_shares(stock_code: str = None, date=None) -> float:
    """
    获取自由流通股本（freeFloatCapital）。

    查询逻辑：
    1. date is not None → 查 free_float_shares.parquet（Capital 财务表）
       → merge_asof: m_timetag <= target_date 的最新行
       → gap > 90 天：warning + 继续用旧值
    2. 查不到 → raise ValueError
       （不回退 FloatVolume：194 亿 vs 86 亿，不同口径）
    3. date is None → raise ValueError
       （get_instrument_detail 不返回 freeFloatCapital）
    """
    if stock_code and date is not None:
        ffs = _load_free_float_shares()
        if not ffs.empty:
            target_date = pd.Timestamp(date).normalize()
            matches = ffs[
                (ffs["stock_code"] == stock_code) & (ffs["m_timetag"] <= target_date)
            ].sort_values("m_timetag")
            if len(matches) > 0:
                row = matches.iloc[-1]
                ff = row.get("freeFloatCapital")
                if ff is not None and ff > 0:
                    gap_days = int((target_date - pd.Timestamp(row["m_timetag"])).days)
                    if gap_days > 90:
                        logger.warning(
                            "freeFloatCapital history gap >90 days; using stale value "
                            "(free-float changes rarely, stale is better than switching to FloatVolume)",
                            context={
                                "stock": stock_code,
                                "target_date": target_date.strftime("%Y-%m-%d"),
                                "found_date": pd.Timestamp(row["m_timetag"]).strftime("%Y-%m-%d"),
                                "gap_days": gap_days,
                            },
                        )
                    return float(ff)

    raise ValueError(
        f"freeFloatCapital missing for {stock_code}"
        f"{f' (date={date})' if date else ''}"
        f"; FloatVolume fallback intentionally NOT used "
        f"(different metric: FloatVolume={194}亿 vs freeFloatCapital={86}亿 for 000001.SZ)"
    )


def _estimate_turnover(volume: np.ndarray, float_shares: float = None) -> np.ndarray:
    """
    估算 turnover_rate。

    公式：turnover_rate = (volume * 100) / float_shares
    单位换算：volume（手） × 100 = 股 ÷ 流通股本（股）。

    Args:
        volume: 成交量数组（单位：手）
        float_shares: 流通股本（股）。为 None 时回退到 100 亿默认值。
                      P0-18 后主路径（adapt_columns→compute_chip_factors）已强制要求
                      stock_code 并 fail-close；None 分支仅服务于外部调用者
                      （chip_indicator TurnoverChipFactor 无 stock_code 时、chip_factor_analysis）。

    Returns:
        turnover_rate 数组（比例，0-1，非百分比）
    """
    if float_shares is None:
        logger.warning(
            "_estimate_turnover using 100亿 default float_shares; "
            "turnover_rate may be significantly distorted for small-cap stocks",
            context={},
        )
        fs = float(_FLOAT_SHARES_DEFAULT)
    else:
        fs = float_shares
    return (volume.astype(np.float64) * 100.0) / fs


# ---------------------------------------------------------------------------
# 列名适配器
# ---------------------------------------------------------------------------
def adapt_columns(
    df: pd.DataFrame,
    stock_code: str = None,
    as_of_date: Optional[pd.Timestamp] = None,
    use_free_float: bool = False,
) -> np.ndarray:
    """
    适配 backtrader DataFrame 列名到 cyq.py 期望的列名契约。

    cyq.py:100 要求 [\"close\", \"high\", \"low\", \"vol\", \"turnover_rate\"]
    现有数据：volume（非 vol），无 turnover_rate。
    传入 stock_code 时从 float_shares.parquet / history 获取流通股本计算 turnover_rate。

    Args:
        df: backtrader 风格的 DataFrame（columns: close, high, low, volume）
        stock_code: 标的代码（如 '000001.SZ'），用于查找真实流通股本
        as_of_date: 可选，按该日期查询历史股本（用于回测避免前视）
        use_free_float: True=自由流通股本（freeFloatCapital），False=流通股本（FloatVolume）

    Returns:
        np.ndarray with columns: close, high, low, vol, turnover_rate
    """
    df = df.rename(columns={"volume": "vol"})
    if "turnover_rate" not in df.columns:
        if use_free_float:
            float_shares = _get_free_float_shares(stock_code, date=as_of_date)
        else:
            float_shares = _get_float_shares(stock_code, date=as_of_date)
        df["turnover_rate"] = _estimate_turnover(df["vol"].values, float_shares)
    return df[["close", "high", "low", "vol", "turnover_rate"]].values


# ---------------------------------------------------------------------------
# 日线筹码分布（三角/均匀 PDF fallback）
# ---------------------------------------------------------------------------
def daily_chip_distribution(arr: np.ndarray, method: str = "triang") -> pd.Series:
    """
    日线筹码分布：使用三角/均匀 PDF 假设。

    直接委托给 qlib_cost 的 calc_dist_chips()。

    Args:
        arr: adapt_columns() 输出 (N, 5) 数组
        method: "triang" 或 "uniform"

    Returns:
        pd.Series, index=price, values=chip volume
    """
    return cyq.calc_dist_chips(arr, method=method)


# ---------------------------------------------------------------------------
# 分钟线筹码分布（实际量价累积，跳过 PDF 假设）
# ---------------------------------------------------------------------------
def minute_chip_distribution(
    arr: np.ndarray,
    step: float = 0.01,
    stock_code: str = "",
) -> pd.Series:
    """
    分钟线筹码分布：用每分钟的实际 (close, volume) 构建直方图。

    跳过三角/均匀 PDF 假设，直接用量价累积。
    但仍需假设分钟内成交价格代表值为 close。

    Args:
        arr: adapt_columns() 输出 (N, 5) 数组。
             N ≈ 80 天 × 240 分钟 = 19,200。
             columns: close, high, low, vol, turnover_rate
        step: 价格步长（元）
        stock_code: 标的代码（仅用于异常时的日志上下文）

    Returns:
        pd.Series, index=price（以 step 为步长）, values=累计 chip volume
    """
    close = arr[:, 0]   # 分钟 close
    vol = arr[:, 3]     # 分钟 volume
    turnover = arr[:, 4]  # 分钟 turnover_rate（从日线按 volume 占比分配后）

    min_p = float(np.nanmin(close))
    max_p = float(np.nanmax(close))
    if np.isnan(min_p) or np.isnan(max_p) or max_p <= min_p:
        # P1-5 fix: 记录原因（停牌/一字板/数据异常），不再静默返回空
        label = f"{stock_code} " if stock_code else ""
        reason = (
            f"{label}价格全部相同 (max={max_p} <= min={min_p})，"
            f"可能原因：停牌、一字板涨跌停、或数据异常"
        )
        logger.warning(reason)
        return pd.Series(dtype=float, name="cumpdf")

    price_bins = make_price_grid(min_p, max_p, step)
    cumpdf = np.zeros(len(price_bins), dtype=np.float64)

    # 按日期分组，每日内用 decay 模型累积
    # arr 按时间排序，每日的 decay 由该日的分钟 turnover_rate 计算
    decay = turnover.copy()
    diff = 1.0 - decay

    for i in range(len(close)):
        if np.isnan(close[i]) or vol[i] <= 0:
            continue
        # 找到该分钟的成交量归属的价格 bin
        idx = int((close[i] - min_p) / step)
        if idx < 0:
            idx = 0
        elif idx >= len(price_bins):
            idx = len(price_bins) - 1

        curpdf = np.zeros(len(price_bins), dtype=np.float64)
        curpdf[idx] = vol[i] * decay[i]

        if i == 0:
            cumpdf = curpdf
        else:
            cumpdf = cumpdf * diff[i] + curpdf

    # 归一化
    total = cumpdf.sum()
    if total > 0:
        cumpdf /= total

    return pd.Series(cumpdf, index=price_bins, name="cumpdf")


# ---------------------------------------------------------------------------
# 方案 A：日线定框架 + 分钟线做日内偏移（§10.4.2）
# ---------------------------------------------------------------------------
def hybrid_chip_distribution(
    daily_arr: np.ndarray,
    minute_today_arr: np.ndarray,
    step: float = 0.01,
) -> pd.Series:
    """
    混合筹码分布：历史日线三角PDF + 当日分钟线量价累积。

    §10.4.2 方案 A — 日线定框架，分钟线只做当日新开仓成本的微调。
    与 pure minute (80天×240分钟) 相比，大幅降低计算量。

    Args:
        daily_arr: adapt_columns() 输出 (N, 5)，N 天日线，最后一行为当日
        minute_today_arr: adapt_columns() 输出 (M, 5)，当日分钟线
        step: 价格步长（元）

    Returns:
        pd.Series, index=price, values=累计 chip volume
    """
    # 价格网格：覆盖日线 + 分钟线的完整范围
    max_p = max(float(np.nanmax(daily_arr[:, 1])),
                float(np.nanmax(minute_today_arr[:, 0])))
    min_p = min(float(np.nanmin(daily_arr[:, 2])),
                float(np.nanmin(minute_today_arr[:, 0])))
    if max_p <= min_p:
        # P1-5 fix
        logger.warning(
            f"hybrid_chip_distribution: 日线+分钟线价格范围为空 "
            f"(max={max_p} <= min={min_p})，可能停牌或数据异常"
        )
        return pd.Series(dtype=float, name="cumpdf")

    xs = make_price_grid(min_p, max_p, step)
    n_days = len(daily_arr)
    curpdfs = np.zeros((n_days, len(xs)), dtype=np.float64)

    # 历史日（0 到 n_days-2）：三角 PDF
    for i in range(n_days - 1):
        curpdfs[i] = cyq.calc_curpdf(
            float(daily_arr[i, 0]), float(daily_arr[i, 1]),
            float(daily_arr[i, 2]), float(daily_arr[i, 3]),
            min_p, max_p, step, method="triang",
        )

    # 当日（最后一"天"）：分钟线量价直方图
    today_close = minute_today_arr[:, 0]
    today_vol = minute_today_arr[:, 3]
    today_pdf = np.zeros(len(xs), dtype=np.float64)
    for j in range(len(today_close)):
        if np.isnan(today_close[j]) or today_vol[j] <= 0:
            continue
        idx = int((today_close[j] - min_p) / step)
        if 0 <= idx < len(xs):
            today_pdf[idx] += today_vol[j]
    if today_pdf.sum() > 0:
        today_pdf /= today_pdf.sum()
    curpdfs[n_days - 1] = today_pdf

    # 换手率：历史日用日线值，当日用日线值（分钟 turnover 之和应与日线一致）
    turnover = daily_arr[:, 4].copy()

    cum_vol = cyq.calc_cumpdf(curpdfs, turnover)
    return pd.Series(cum_vol, index=xs, name="cumpdf")


def adj_minute_chip_distribution(
    arr: np.ndarray,
    stock_code: str,
    date,
    step: float = 0.01,
) -> pd.Series:
    """
    方案 B：复权因子校正后的分钟线筹码分布（§10.4.2）。

    流程：
    1. 用 get_adj_factor() 查询该标的首日的累积复权乘数
    2. 对价格列（close/high/low）乘上复权因子，量列（vol/turnover_rate）不变
    3. 调用 minute_chip_distribution() 计算筹码分布

    Args:
        arr: adapt_columns() 输出 (N, 5)，未复权分钟线
        stock_code: 标的代码
        date: 截面日期（用于查询复权因子）
        step: 价格步长

    Returns:
        pd.Series, index=price（等效前复权）, values=chip volume
    """
    factor = get_adj_factor(stock_code, date, strict=True)
    # P1-2: NaN 保护 — 复权因子不可用时不应进入筹码计算
    if pd.isna(factor):
        raise ValueError(
            f"adj_minute_chip_distribution: factor is NaN for {stock_code} @ {date}"
        )
    if factor == 1.0:
        # 无复权差异，直接走原始路径
        return minute_chip_distribution(arr, step=step)

    arr_adj = arr.copy()
    arr_adj[:, 0] = arr[:, 0] * factor  # close
    arr_adj[:, 1] = arr[:, 1] * factor  # high
    arr_adj[:, 2] = arr[:, 2] * factor  # low
    # vol (col 3) 和 turnover_rate (col 4) 保持不变

    return minute_chip_distribution(arr_adj, step=step)


# ---------------------------------------------------------------------------
# 便捷函数：从 DataFrame 一步计算 ChipFactor
# ---------------------------------------------------------------------------
def compute_chip_factors(
    df: pd.DataFrame,
    method: str = "triang",
    data_freq: str = "1d",
    stock_code: str = None,
    daily_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    从 backtrader 风格的 DataFrame 计算 4 个筹码分布因子。

    Args:
        df: 包含 close, high, low, volume 列的 DataFrame（N 行窗口）
        method: 日线模式用 "triang" 或 "uniform"；分钟线模式忽略
        data_freq: "1d" 或 "1m"
        stock_code: 股票代码（如 "000001.SZ"），用于查找真实流通股本。
                    为 None 时抛 ValueError（P0-18 强制要求传入有效 stock_code）
        daily_df: 日线前复权 DataFrame（仅 data_freq="1m" 时需要）。
                  用于 hybrid_chip_distribution —— 历史日线定框架 + 当日分钟线微调，
                  解决 QMT 分钟线不支持复权导致的除权日筹码失真。

    Returns:
        dict with keys: cyqk_c, asr, ckdw, prp
    """
    as_of_date = None
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
        as_of_date = pd.Timestamp(df.index[-1]).normalize()
    arr = adapt_columns(df, stock_code=stock_code, as_of_date=as_of_date)

    if data_freq == "1m":
        # P0-4 fix: 分钟线模式使用 hybrid 路径，日线 front 定框架 + 分钟线 none 微调
        if daily_df is not None and len(daily_df) > 0:
            daily_as_of = None
            if isinstance(daily_df.index, pd.DatetimeIndex) and len(daily_df.index) > 0:
                daily_as_of = pd.Timestamp(daily_df.index[-1]).normalize()
            daily_arr = adapt_columns(
                daily_df,
                stock_code=stock_code,
                as_of_date=daily_as_of,
            )
            dist = hybrid_chip_distribution(daily_arr, arr)
        else:
            raise ValueError(
                "data_freq='1m' 需要 daily_df 参数（日线前复权数据）。"
                "纯分钟线筹码分布在除权日前后存在价格断裂，已弃用。"
                "请调用方通过 StockDataReader(adjust_type='front') 加载日线数据后传入。"
            )
    else:
        dist = daily_chip_distribution(arr, method=method)

    close_price = float(arr[-1, 0])  # 最新 bar 的 close
    cf = cyq.ChipFactor(close_price, dist)

    return {
        "cyqk_c": cf.get_cyqk_c(),
        "asr": cf.get_asr(),
        "ckdw": cf.get_ckdw(),
        "prp": cf.get_prp(),
    }


# ---------------------------------------------------------------------------
# Phase 2: 换手率半衰期筹码分布因子（ARC/VRC/SRC/KRC）
# ---------------------------------------------------------------------------
def turnover_chip_factors(
    turnover_rate: np.ndarray,
    close: np.ndarray,
    window: int = 60,
) -> dict:
    """
    计算换手率衰减筹码分布因子（ARC/VRC/SRC/KRC）。

    基于广发证券多因子 alpha 系列报告 #27 的换手率半衰期模型。
    不需要 OHLC 分布假设，仅需换手率和收盘价。

    Args:
        turnover_rate: 换手率序列（比例，0-1），长度 ≥ window
        close: 收盘价序列，长度 ≥ window
        window: 滚动窗口（默认 60）

    Returns:
        dict with keys: arc, vrc, src, krc
    """
    if len(turnover_rate) < window or len(close) < window:
        return {"arc": np.nan, "vrc": np.nan, "src": np.nan, "krc": np.nan}

    # 截取最后 window 个值
    tr = np.asarray(turnover_rate[-window:], dtype=np.float64).flatten()
    cl = np.asarray(close[-window:], dtype=np.float64).flatten()

    arc, vrc, src, krc = tco.calc_distribution_of_chips(tr, cl, window)
    return {
        "arc": float(arc),
        "vrc": float(vrc),
        "src": float(src),
        "krc": float(krc),
    }


# ---------------------------------------------------------------------------
# 复权因子表（§10.4.2 方案 B 前置基建）
# ---------------------------------------------------------------------------
_adj_factor_cache: Optional[pd.DataFrame] = None


def _load_adj_factor_table(parquet_path: str = None) -> pd.DataFrame:
    """加载复权因子表，缓存到模块级变量。"""
    global _adj_factor_cache
    if _adj_factor_cache is not None:
        return _adj_factor_cache
    from pathlib import Path

    from common.infra.data_root import resolve_source_parquet

    path = Path(parquet_path) if parquet_path else resolve_source_parquet("adj_factor.parquet")
    if path.exists():
        _adj_factor_cache = pd.read_parquet(path)
    else:
        _adj_factor_cache = pd.DataFrame()
    return _adj_factor_cache


def get_adj_factor(stock_code: str, date, *, strict: bool = True) -> float:
    """
    查询指定标的在指定日期的累积复权乘数因子。

    Args:
        stock_code: 如 '000001.SZ'
        date: 日期（str 'YYYY-MM-DD' 或 pd.Timestamp）

    Returns:
        cumulative_adj_factor = close_front / close_none。
        strict=True 且未找到时抛 ValueError，避免静默使用错误口径。
    """
    df = _load_adj_factor_table()
    if df.empty:
        if strict:
            raise ValueError("adj_factor table is empty; cannot compute adjusted minute prices safely")
        return 1.0
    if isinstance(date, str):
        date = pd.Timestamp(date)
    row = df[(df["stock_code"] == stock_code) & (df["date"] == date.normalize())]
    if len(row) > 0:
        factor = float(row.iloc[0]["cumulative_adj_factor"])
        # P1-2: NaN 校验 — adj_factor.py 对 ffill 无法填充的首行返回 NaN
        if pd.isna(factor):
            msg = (
                f"adj_factor is NaN for {stock_code} @ "
                f"{pd.Timestamp(date).strftime('%Y-%m-%d')} "
                f"(front/none data alignment issue at data boundary)"
            )
            if strict:
                raise ValueError(msg)
            return float("nan")
        return factor
    if strict:
        raise ValueError(
            f"adj_factor missing for {stock_code} @ {pd.Timestamp(date).strftime('%Y-%m-%d')}"
        )
    return 1.0


def adj_minute_prices(
    stock_code: str, date, minute_close: np.ndarray,
    minute_high: np.ndarray = None, minute_low: np.ndarray = None,
) -> dict:
    """
    将未复权分钟线价格校正为等效前复权价格（§10.4.2 方案 B）。

    公式：adj_price = unadj_price × cumulative_adj_factor_at_date

    Args:
        stock_code: 标的代码
        date: 日期
        minute_close: 未复权分钟收盘价数组
        minute_high: 未复权分钟最高价（可选）
        minute_low: 未复权分钟最低价（可选）

    Returns:
        dict with keys: close (, high, low)
    """
    factor = get_adj_factor(stock_code, date, strict=True)
    result = {"close": minute_close * factor}
    if minute_high is not None:
        result["high"] = minute_high * factor
    if minute_low is not None:
        result["low"] = minute_low * factor
    return result


# ---------------------------------------------------------------------------
# 跨日衍生 chip 因子
# ---------------------------------------------------------------------------
def derived_chip_factors(
    cyqk_today: float,
    cyqk_yesterday: float,
    turnover_today: float,
) -> dict:
    """
    跨日衍生 chip 因子。

    Args:
        cyqk_today: 当日获利筹码比例
        cyqk_yesterday: 上一日获利筹码比例
        turnover_today: 当日换手率（比例，0-1）

    Returns:
        dict with keys: profit_chip_diff, turnover_ratio, turnover_resistance
    """
    profit_chip_diff = cyqk_today - cyqk_yesterday
    if turnover_today > 0:
        turnover_resistance = profit_chip_diff / turnover_today
    else:
        turnover_resistance = 0.0

    return {
        "profit_chip_diff": round(profit_chip_diff, 6),
        "turnover_ratio": round(turnover_today, 6),
        "turnover_resistance": round(turnover_resistance, 4),
    }


def _fmt_cyqk(val: float):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    return round(float(val), 4)


def compute_crossday_turnover_resistance(
    df: pd.DataFrame,
    stock_code: str,
    window: int = 1000,
    method: str = "triang",
) -> dict:
    """
    截面日 T 的 canonical 换手阻力。

    今日窗口：最近 window 个交易日（含 T），默认 1000≈4 年；
    昨日窗口：再往前 window 日（含 T-1）。
    分母为今日窗口 adapt_columns 末行 turnover_rate（arr_t[-1, 4]），按 as_of_date 查股本。
    """
    if df is None or df.empty:
        raise ValueError("empty dataframe")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df index must be DatetimeIndex")

    df = df.sort_index()
    unique_dates = df.index.normalize().unique()
    if len(unique_dates) < window:
        raise ValueError(f"need {window} trading days, got {len(unique_dates)}")

    as_of_t = pd.Timestamp(unique_dates[-1]).normalize()
    mask_t = df.index.normalize().isin(unique_dates[-window:])
    df_t = df.loc[mask_t]

    arr_t = adapt_columns(df_t, stock_code=stock_code, as_of_date=as_of_t)
    dist_t = daily_chip_distribution(arr_t, method=method)
    cf_t = cyq.ChipFactor(float(arr_t[-1, 0]), dist_t)
    cyqk_today = cf_t.get_cyqk_c()
    turnover_today = float(arr_t[-1, 4])

    out = {
        "cyqk_c": _fmt_cyqk(cyqk_today),
        "cyqk_c_yesterday": "",
        "profit_chip_diff": "",
        "turnover_ratio": round(turnover_today, 6),
        "turnover_resistance": "",
    }

    if len(unique_dates) < window + 1:
        return out

    prev_dates = unique_dates[-(window + 1):-1]
    as_of_y = pd.Timestamp(prev_dates[-1]).normalize()
    mask_y = df.index.normalize().isin(prev_dates)
    df_y = df.loc[mask_y]
    arr_y = adapt_columns(df_y, stock_code=stock_code, as_of_date=as_of_y)
    dist_y = daily_chip_distribution(arr_y, method=method)
    cf_y = cyq.ChipFactor(float(arr_y[-1, 0]), dist_y)

    derived = derived_chip_factors(
        cyqk_today, cf_y.get_cyqk_c(), turnover_today,
    )
    out["cyqk_c_yesterday"] = _fmt_cyqk(cf_y.get_cyqk_c())
    out["profit_chip_diff"] = derived["profit_chip_diff"]
    out["turnover_ratio"] = derived["turnover_ratio"]
    out["turnover_resistance"] = derived["turnover_resistance"]
    return out


# ---------------------------------------------------------------------------
# 等权重筹码分布（市面常见指标对比实现）
# ---------------------------------------------------------------------------
def compute_equal_weight_cyqk(
    df: pd.DataFrame,
    stock_code: str,
    window: int = 1000,
    method: str = "triang",
) -> dict:
    """
    等权重筹码分布（无换手率衰减）—— 与市面常见筹码分布 APP 对齐的对比实现。

    与 canonical 路径 ``compute_crossday_turnover_resistance`` 的核心差异：
    1. **无衰减**：历史日筹码等权重累加，不使用 ``calc_cumpdf`` 的换手率衰减模型；
    2. **窗口**：默认 120 个交易日（市面常见指标通常用 100~130 日）；
    3. **无 turnover 估算**：本函数仅输出筹码分布因子，不计算换手率及阻力。

    Args:
        df: 日线 DataFrame（含 close/high/low/volume）
        stock_code: 标的代码
        window: 筹码分布窗口（交易日），默认 120
        method: PDF 方法，"triang" 或 "uniform"

    Returns:
        dict: cyqk_c, asr, ckdw, prp, cost_p05...cost_p95, close, window
    """
    if df is None or df.empty:
        raise ValueError("empty dataframe")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df index must be DatetimeIndex")

    df = df.sort_index()
    unique_dates = df.index.normalize().unique()
    if len(unique_dates) < window:
        raise ValueError(f"need {window} trading days, got {len(unique_dates)}")

    as_of = pd.Timestamp(unique_dates[-1]).normalize()
    win_dates = unique_dates[-window:]
    mask = df.index.normalize().isin(win_dates)
    df_w = df.loc[mask]

    arr = adapt_columns(df_w, stock_code=stock_code, as_of_date=as_of)
    close = float(arr[-1, 0])

    # 等权重累加：不用 calc_cumpdf，直接 sum(curpdf)
    max_p = float(np.nanmax(arr[:, 1]))
    min_p = float(np.nanmin(arr[:, 2]))
    step = 0.01
    if max_p <= min_p:
        return {
            "cyqk_c": float("nan"), "asr": float("nan"), "ckdw": float("nan"), "prp": float("nan"),
            "cost_p05": float("nan"), "cost_p10": float("nan"), "cost_p50": float("nan"),
            "cost_p90": float("nan"), "cost_p95": float("nan"),
            "close": close, "window": window, "method": method,
        }

    xs = make_price_grid(min_p, max_p, step)
    curpdfs = np.zeros((len(arr), len(xs)))
    for i in range(len(arr)):
        row = arr[i]
        pdf = calc_curpdf(row[0], row[1], row[2], row[3], min_p, max_p, step, method)
        curpdfs[i] = pdf

    cum_vol = np.sum(curpdfs, axis=0)
    dist = pd.Series(cum_vol, index=xs, name="cumpdf")

    cf = cyq.ChipFactor(close, dist)
    return {
        "cyqk_c": _fmt_cyqk(cf.get_cyqk_c()),
        "asr": _fmt_cyqk(cf.get_asr()),
        "ckdw": _fmt_cyqk(cf.get_ckdw()),
        "prp": _fmt_cyqk(cf.get_prp()),
        "cost_p05": round(float(cf.get_cost(0.05)), 2),
        "cost_p10": round(float(cf.get_cost(0.10)), 2),
        "cost_p50": round(float(cf.get_cost(0.50)), 2),
        "cost_p90": round(float(cf.get_cost(0.90)), 2),
        "cost_p95": round(float(cf.get_cost(0.95)), 2),
        "close": close,
        "window": window,
        "method": method,
    }


# ---------------------------------------------------------------------------
# 布林带位置（统一实现，供 filter_chip_stocks / chip_factor_analysis 复用）
# ---------------------------------------------------------------------------
def bb_position(close: np.ndarray, period: int = 20, nbdev: float = 2.0) -> float:
    """布林带位置：0=下轨, 0.5=中轨, 1=上轨。"""
    if len(close) < period:
        return 0.5
    ma = np.mean(close[-period:])
    std = np.std(close[-period:])
    upper = ma + nbdev * std
    lower = ma - nbdev * std
    band_width = upper - lower
    if band_width < 1e-8:
        return 0.5
    return float((close[-1] - lower) / band_width)
