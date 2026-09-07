import backtrader as bt
import numpy as np
import pandas as pd

from backtest.chip_indicator import ChipDistribution, TurnoverChipFactor


class _ChipPandasData(bt.feeds.PandasData):
    lines = ("turnover_rate",)
    params = (("turnover_rate", -1),)


def _build_ohlcv_df(n: int = 60) -> pd.DataFrame:
    close = np.linspace(10.0, 12.0, n)
    df = pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1_000_000.0),
            "turnover_rate": np.full(n, 0.015),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )
    return df


class _CaptureChipDistribution(bt.Strategy):
    params = (("period", 20),)

    def __init__(self):
        self.ind = ChipDistribution(self.datas[0], period=self.p.period, data_freq="1d", stock_code="000001.SZ")
        self.samples = []

    def prenext(self):
        self._capture()

    def next(self):
        self._capture()

    def _capture(self):
        self.samples.append(
            (
                len(self.data),
                (
                    float(self.ind.cyqk_c[0]),
                    float(self.ind.asr[0]),
                    float(self.ind.ckdw[0]),
                    float(self.ind.prp[0]),
                ),
            )
        )


class _CaptureTurnoverChip(bt.Strategy):
    params = (("period", 10),)

    def __init__(self):
        self.ind = TurnoverChipFactor(self.datas[0], period=self.p.period, stock_code="000001.SZ")
        self.samples = []

    def prenext(self):
        self._capture()

    def next(self):
        self._capture()

    def _capture(self):
        self.samples.append(
            (
                len(self.data),
                (
                    float(self.ind.arc[0]),
                    float(self.ind.vrc[0]),
                    float(self.ind.src[0]),
                    float(self.ind.krc[0]),
                ),
            )
        )


def _run(strategy_cls):
    cerebro = bt.Cerebro(stdstats=False)  # type: ignore[reportCallIssue]
    data = _ChipPandasData(dataname=_build_ohlcv_df())  # type: ignore[reportCallIssue]
    cerebro.adddata(data)
    cerebro.addstrategy(strategy_cls)
    result = cerebro.run()
    return result[0]


def test_chip_distribution_warmup_uses_nan_not_zero():
    strat = _run(_CaptureChipDistribution)
    warmup = [vals for bar, vals in strat.samples if bar < strat.p.period]
    ready = [vals for bar, vals in strat.samples if bar >= strat.p.period]

    assert warmup
    assert all(all(np.isnan(v) for v in vals) for vals in warmup)
    assert ready
    assert any(all(np.isfinite(v) for v in vals) for vals in ready)


def test_turnover_chip_warmup_uses_nan_not_zero():
    strat = _run(_CaptureTurnoverChip)
    warmup = [vals for bar, vals in strat.samples if bar < strat.p.period]
    ready = [vals for bar, vals in strat.samples if bar >= strat.p.period]

    assert warmup
    assert all(all(np.isnan(v) for v in vals) for vals in warmup)
    assert ready
    assert any(all(np.isfinite(v) for v in vals) for vals in ready)
