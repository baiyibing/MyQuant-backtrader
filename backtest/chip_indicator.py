# -*- coding: utf-8 -*-
"""
chip_indicator.py — COST 筹码分布 backtrader Indicator (Step 1 MVP-min)

将 chip_algorithm.py 封装为 backtrader.Indicator 子类，
在策略 next() 中可直接引用 self.chip.cyqk_c[0] 等。

用法示例（在 RollingInvestmentStrategy.__init__ 中）:

    from backtest.chip_indicator import ChipDistribution
    self.chip = ChipDistribution(
        self.datas[0], period=80, data_freq='1d'
    )

注意：MVP-min 使用固定流通股本占位 turnover_rate（不可用于生产）。
"""

import backtrader as bt
import numpy as np
import pandas as pd

from backtest.chip_algorithm import (  # noqa: E402
    adapt_columns,
    daily_chip_distribution,
    turnover_chip_factors,
    cyq,
)
from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

# P0-3 fix: 模块级 fault 计数器，用于策略检测计算异常
_CHIP_FAULT_COUNT: int = 0


def get_chip_fault_count() -> int:
    """返回自进程启动以来 chip indicator 的异常 fault 次数。

    策略可在 next() 中检查：若 fault_count > 0，应停止交易并告警。
    """
    return _CHIP_FAULT_COUNT


class ChipDistribution(bt.Indicator):
    """
    筹码分布因子 Indicator。

    输出 4 条 line：
    - cyqk_c：获利比例（筹码分布中价格低于当前收盘价的比例）
    - asr：活跃筹码比（收盘价 ±10% 范围内的筹码占比）
    - ckdw：筹码重心（成本分布中心偏离度）
    - prp：价格相对成本位置（收盘价 / 平均成本 - 1）

    参数：
    - period: 回看窗口（交易日数），默认 80
    - data_freq: 数据频率，'1d'（日线）或 '1m'（分钟线），默认 '1d'
    - dist_method: 日线模式下的分布假设，'triang'（三角分布）或 'uniform'（均匀分布），默认 'triang'
    - stock_code: 标的代码（如 '000001.SZ'），用于查找真实流通股本计算 turnover_rate
    """

    lines = ("cyqk_c", "asr", "ckdw", "prp")
    params = (
        ("period", 80),
        ("data_freq", "1d"),
        ("dist_method", "triang"),
        ("stock_code", ""),
    )

    plotinfo = dict(
        plot=True,
        subplot=True,
        plotname="Chip Distribution",
    )

    plotlines = dict(
        cyqk_c=dict(_name="CYQK_C", _method="line"),
        asr=dict(_name="ASR", _method="line"),
        ckdw=dict(_name="CKDW", _method="line"),
        prp=dict(_name="PRP", _method="line"),
    )

    def __init__(self):
        super(ChipDistribution, self).__init__()
        self.addminperiod(self.p.period)

    def _set_nan_lines(self):
        self.lines.cyqk_c[0] = float("nan")
        self.lines.asr[0] = float("nan")
        self.lines.ckdw[0] = float("nan")
        self.lines.prp[0] = float("nan")

    def prenext(self):
        # Warmup 阶段显式写 NaN，避免 backtrader line 默认值被误读为有效 0.0。
        self._set_nan_lines()

    def next(self):
        if len(self.data) < self.p.period:
            self._set_nan_lines()
            return

        # 收集窗口数据 → DataFrame
        window_data = {
            "close": np.array(
                [self.data.close[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
            "high": np.array(
                [self.data.high[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
            "low": np.array(
                [self.data.low[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
            "volume": np.array(
                [self.data.volume[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
        }
        df = pd.DataFrame(window_data)

        try:
            arr = adapt_columns(df, stock_code=self.p.stock_code or None)

            if self.p.data_freq == "1m":
                # P0-4 fix: 分钟线模式使用 hybrid 路径（日线 front 定框架 + 分钟线微调），
                # 代替纯分钟线筹码分布（QMT 分钟线不支持复权，除权日存在价格断裂）
                from backtest.chip_algorithm import hybrid_chip_distribution
                from oskh_data.reader import StockDataReader

                daily_reader = StockDataReader(mode="duckdb_persistent")
                end_date = self.data.datetime.date(0).strftime("%Y%m%d")
                start_date = (
                    pd.Timestamp(end_date) - pd.Timedelta(days=self.p.period * 2)
                ).strftime("%Y%m%d")
                daily_df = daily_reader.read_stock(
                    self.p.stock_code,
                    start_time=start_date,
                    end_time=end_date,
                    period="1d",
                    adjust_type="front",
                )
                daily_reader.close()

                if daily_df is None or len(daily_df) < self.p.period:
                    raise ValueError(
                        f"日线 front 数据不足: 需要 >= {self.p.period} 天，"
                        f"实际 {len(daily_df) if daily_df is not None else 0} 天"
                    )

                daily_df = daily_df.sort_index()
                daily_uniq = daily_df.index.normalize().unique()
                daily_mask = daily_df.index.normalize().isin(daily_uniq[-self.p.period:])
                daily_arr = adapt_columns(
                    daily_df.loc[daily_mask], stock_code=self.p.stock_code or None
                )
                dist = hybrid_chip_distribution(daily_arr, arr)
            else:
                dist = daily_chip_distribution(arr, method=self.p.dist_method)

            close_price = float(self.data.close[0])
            cf = cyq.ChipFactor(close_price, dist)

            self.lines.cyqk_c[0] = cf.get_cyqk_c()
            self.lines.asr[0] = cf.get_asr()
            self.lines.ckdw[0] = cf.get_ckdw()
            self.lines.prp[0] = cf.get_prp()

        except (ValueError, KeyError) as e:
            # 预期内：数据不足、停牌、列缺失、窗口不够等
            logger.warning(
                "ChipDistribution expected NaN",
                context={"stock": self.p.stock_code, "reason": str(e)},
            )
            self._set_nan_lines()
        except Exception as e:
            # P0-3 fix: 异常 NaN（计算错误、除零、数据损坏等）→ 记 fault
            global _CHIP_FAULT_COUNT
            _CHIP_FAULT_COUNT += 1
            logger.error(
                "ChipDistribution fault NaN",
                context={
                    "stock": self.p.stock_code,
                    "fault_count": _CHIP_FAULT_COUNT,
                    "exc": str(e),
                },
            )
            self._set_nan_lines()


class TurnoverChipFactor(bt.Indicator):
    """
    换手率半衰期筹码分布因子 Indicator（Phase 2）。

    输出 4 条 line：
    - arc：平均持仓盈亏（>0 盈利，<0 亏损）
    - vrc：筹码集中度（越大越分散，越小越集中）
    - src：盈亏分布偏度（>0 右偏，<0 左偏）
    - krc：盈亏分化度（越大分化越严重）

    参数：
    - period: 回看窗口（交易日数），默认 60
    - stock_code: 股票代码（用于查找真实流通股本）
    """

    lines = ("arc", "vrc", "src", "krc")
    params = (("period", 60), ("stock_code", ""))

    plotinfo = dict(plot=True, subplot=True, plotname="Turnover Chip")

    def __init__(self):
        self.addminperiod(self.p.period)

    def _set_nan_lines(self):
        self.lines.arc[0] = float("nan")
        self.lines.vrc[0] = float("nan")
        self.lines.src[0] = float("nan")
        self.lines.krc[0] = float("nan")

    def prenext(self):
        # warmup 阶段统一 NotReady 语义。
        self._set_nan_lines()

    def next(self):
        if len(self.data) < self.p.period:
            self._set_nan_lines()
            return
        try:
            tr = np.array(
                [self.data.turnover_rate[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            )
            cl = np.array(
                [self.data.close[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            )
            # 如果 turnover_rate line 不在数据中（NaN），用 volume 估算
            if np.isnan(tr).all():
                from backtest.chip_algorithm import _estimate_turnover, _get_float_shares
                vol = np.array(
                    [self.data.volume[i] for i in range(-self.p.period, 0)],
                    dtype=np.float64,
                )
                # P1-2 fix: 使用真实流通股本而非 100 亿默认值
                fs = _get_float_shares(self.p.stock_code) if self.p.stock_code else None
                if fs is not None and fs > 0:
                    tr = _estimate_turnover(vol, float_shares=fs)
                else:
                    # 无流通股本数据时使用默认值，但记录警告
                    logger.warning(
                        "TurnoverChipFactor using 100亿 default float_shares",
                        context={"stock": self.p.stock_code},
                    )
                    tr = _estimate_turnover(vol)

            result = turnover_chip_factors(tr, cl, window=self.p.period)
            self.lines.arc[0] = result["arc"]
            self.lines.vrc[0] = result["vrc"]
            self.lines.src[0] = result["src"]
            self.lines.krc[0] = result["krc"]
        except (ValueError, KeyError) as e:
            logger.warning(
                "TurnoverChipFactor expected NaN",
                context={"reason": str(e)},
            )
            self._set_nan_lines()
        except Exception as e:
            global _CHIP_FAULT_COUNT
            _CHIP_FAULT_COUNT += 1
            logger.error(
                "TurnoverChipFactor fault NaN",
                context={"fault_count": _CHIP_FAULT_COUNT, "exc": str(e)},
            )
            self._set_nan_lines()
