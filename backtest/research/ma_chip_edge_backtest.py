#!/usr/bin/env python3
"""均线 + 盈筹率边缘买入试验（plan v3）。

T = 信号日的下一根交易日：在日 D 收盘确认 cond[D] 且 cond[D-1] 有限为假，
于 D+1 开盘买入（pending + Market + set_coo；无 bt.Order.Open）。
买入日收盘 <= T-1 收盘则次日开盘卖；否则收到收盘 < SMA5 的次日开盘卖。
买入日不挂卖。涨跌停/停牌不成交；skip_sell 保留 pending，下一交易日再试。

用法：
    python backtest/research/ma_chip_edge_backtest.py --seed 20240907 --start 20240101
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

import backtrader as bt

from backtest.chip_algorithm import adapt_columns, daily_chip_distribution, cyq
from common.infra.data_root import resolve_index_daily_root, resolve_period_root, resolve_source_parquet
from oskh_data import StockDataReader
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key
from oskh_factors.chip.shares import (
    _load_float_shares_map,
    _load_free_float_shares,
)

CHIP_WINDOW = 200
WEEK_RULE = "W-FRI"
CYQK_TH = 0.70
BB_PERIOD = 20
BB_NBDEV = 2.0
BB_DDOF = 1
INDEX_MA_FAST = 5
INDEX_MA_SLOW = 10
BOARD_INDEX = {
    "sh_main": "000001.SH",  # 上证指数
    "sz_main": "399001.SZ",  # 深证成指
    "chinext": "399006.SZ",  # 创业板指
}
PENDING_BUY_MAX_GAP_DAYS = 4
LOAD_START = "20220701"
DEFAULT_SEED = 20240907
DEFAULT_CASH = 1_000_000.0
# 统计窗前预热：至少满 CHIP_WINDOW 根，再留一段给 D-1 finite。
CYQK_PRE_STATS_CAL_DAYS = max(200, int(CHIP_WINDOW * 1.6))
HELP_LOCK = """
锁定口径（plan v3 §2）：
  成交：Cerebro(cheat_on_open=True)+next_open 下 Market；禁止 bt.Order.Open
  买入：D 收盘条件全真且有限（三条均线 + 最高价>布林上轨 + 可选盈筹），D-1 有限但非全真 → D+1 开盘买
  等号：买入日收盘 <= T-1 收盘 → 次日开盘卖（fail-closed）
  否则：持有到收盘 < SMA5，再下一根开盘卖；买入日不挂卖
  skip：涨停买/跌停卖/停牌不成交；skip_sell 保留 pending 次日再试
  pending_buy：仅信号日后 <=4 个自然日内的下一根 bar 有效，更长缺口 skip_buy(stale)
  统计窗：--start 前最后一个交易日之前的 edge 置假；窗前成交不进净值
  盈筹率：get_cyqk_c 为 0-1，默认阈值 0.70（--cyqk-th 可改）；200 日窗口含 D，换手按窗内每日 asof 股本
  加速：cyqk 序列优先 turnover_resist.compute_cyqk_series（Rust）；失败回退 Python
  布林：上轨 = SMA20(close) + 2σ，σ 用 pandas rolling.std(ddof=1)；cond 要求 D 的 high > 上轨
  指数过滤：D 收盘时个股对应指数收盘 > 指数 MA5 且 > MA10（沪主板=上证 000001.SH·
    深主板=深成 399001.SZ·创业板=创业板指 399006.SZ；--no-index-ma 关闭）。
    指数均线只用指数自身历史（对齐到个股日历 ffill）；指数缺失 fail-closed 无信号。
  --no-bb：买入 cond 去掉布林上轨
  --no-cyqk：买入 cond 去掉盈筹；不计算 cyqk
  出报：trades_by_stock.txt / trade_pairs.csv（按票 BUY→下一笔 SELL）
"""


def board_of(code: str) -> Optional[str]:
    num, _, exch = code.partition(".")
    if exch == "SH" and num.startswith("688"):
        return None
    if exch == "SH" and num.startswith("60"):
        return "sh_main"
    if exch == "SZ" and num.startswith(("000", "001", "002", "003")):
        return "sz_main"
    if exch == "SZ" and num.startswith(("300", "301")):
        return "chinext"
    return None


def limit_pct(code: str) -> float:
    num = "".join(c for c in code if c.isdigit())
    if num.startswith(("300", "301", "688")):
        return 0.20
    return 0.10


def affordable_size(cash: float, price: float, commission: float = 0.00005, min_commission: float = 5.0) -> int:
    """向下取整到 100 股，并预留佣金，避免 Margin 拒单。"""
    if not np.isfinite(cash) or not np.isfinite(price) or price <= 0 or cash <= 0:
        return 0
    size = int(cash / price / 100.0) * 100
    while size >= 100:
        notional = size * price
        comm = max(notional * commission, min_commission)
        if notional + comm <= cash - 1.0:
            return size
        size -= 100
    return 0


def is_limit_open(code: str, open_px: float, prev_close: float, *, up: bool) -> bool:
    if not np.isfinite(open_px) or not np.isfinite(prev_close) or prev_close <= 0:
        return False
    pct = limit_pct(code)
    target = round(prev_close * (1 + pct if up else 1 - pct), 2)
    return abs(open_px - target) <= 0.01 + 1e-9


def week_ma20_asof(close: pd.Series) -> pd.Series:
    """20 周均线，asof 键为该周最后交易日（无未来价）。"""
    daily = pd.DataFrame({"close": close.to_numpy(), "_last_day": close.index}, index=close.index)
    weekly = daily.resample(WEEK_RULE).agg({"close": "last", "_last_day": "max"}).dropna()
    weekly["ma20"] = weekly["close"].rolling(20, min_periods=20).mean()
    w_last = weekly["_last_day"].tolist()
    w_ma = weekly["ma20"].to_numpy(dtype=np.float64)
    out = np.full(len(close), np.nan, dtype=np.float64)
    wi = 0
    for i, d in enumerate(close.index):
        while wi < len(w_last) and w_last[wi] <= d:
            wi += 1
        if wi > 0:
            out[i] = w_ma[wi - 1]
    return pd.Series(out, index=close.index)


def bb_upper_series(
    close: pd.Series,
    period: int = BB_PERIOD,
    nbdev: float = BB_NBDEV,
    ddof: int = BB_DDOF,
) -> pd.Series:
    """价格布林上轨：中轨 SMA(close, 20) + 2σ，σ 与 pandas / Rust ddof=1 对齐。"""
    mid = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std(ddof=ddof)
    return mid + nbdev * std


def load_index_close(index_code: str, start: str, end: str) -> Optional[pd.Series]:
    """指数日线收盘（index 树 none-only），epoch-ms time → UTC 午夜索引。"""
    root = resolve_index_daily_root()
    part = to_partition_key(to_canonical_symbol(index_code))
    path = root / "dividend_type=none" / f"symbol={part}" / "data.parquet"
    if not path.is_file():
        return None
    df = pd.read_parquet(path, columns=["time", "close"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df.set_index("time").sort_index()
    ts = pd.Timestamp(start) - pd.Timedelta(days=30)  # 均线预热余量
    te = pd.Timestamp(end)
    win = df.loc[(df.index >= ts) & (df.index <= te), "close"]
    if win.empty:
        return None
    return win.astype(np.float64)


def index_ma_frame(index_close: pd.Series, stock_index: pd.DatetimeIndex) -> pd.DataFrame:
    """指数收盘 + MA5/MA10 对齐到个股日历（ffill，仅用指数自身历史，无未来价）。

    fail-closed：个股日早于指数首根（NaN）或晚于指数末根（数据停更）→ NaN，
    对应 finite 为假、不产生信号——不得拿陈旧指数值继续放行过滤。
    """
    s = index_close.sort_index()
    ma = pd.DataFrame({"idx_close": s})
    ma["idx_sma5"] = s.rolling(INDEX_MA_FAST, min_periods=INDEX_MA_FAST).mean()
    ma["idx_sma10"] = s.rolling(INDEX_MA_SLOW, min_periods=INDEX_MA_SLOW).mean()
    target = pd.DatetimeIndex(stock_index).normalize()
    aligned = ma.reindex(target, method="ffill")
    aligned[target > s.index[-1]] = np.nan
    return aligned


def _code_keys(stock_code: str) -> list[str]:
    keys = [stock_code]
    alt = stock_code.replace(".", "_")
    if alt not in keys:
        keys.append(alt)
    try:
        canon = to_canonical_symbol(alt if "." not in stock_code else stock_code)
    except Exception:
        canon = stock_code
    if canon not in keys:
        keys.append(canon)
    return keys


def shares_asof_series(stock_code: str, index: pd.DatetimeIndex) -> np.ndarray:
    """每个交易日 asof 的流通股本（股）。一次 merge_asof，避免逐日扫表。"""
    days = pd.DataFrame({"d": pd.DatetimeIndex(index).normalize()})
    out = np.full(len(days), np.nan, dtype=np.float64)
    keys = _code_keys(stock_code)
    ffs = _load_free_float_shares()
    if ffs is not None and not ffs.empty and "stock_code" in ffs.columns:
        hist = ffs.loc[ffs["stock_code"].astype(str).isin(keys), ["m_timetag", "circulating_capital"]]
        if not hist.empty:
            hist = hist.dropna(subset=["circulating_capital"]).copy()
            hist["m_timetag"] = pd.to_datetime(hist["m_timetag"]).dt.normalize()
            hist = hist.sort_values("m_timetag").drop_duplicates("m_timetag", keep="last")
            order = np.argsort(days["d"].to_numpy())
            sorted_days = days.iloc[order]
            merged = pd.merge_asof(
                sorted_days,
                hist.rename(columns={"m_timetag": "d"}),
                on="d",
                direction="backward",
            )
            vals = merged["circulating_capital"].to_numpy(dtype=np.float64)
            restore = np.empty_like(order)
            restore[order] = np.arange(len(order))
            out = vals[restore]

    if not np.isfinite(out).any():
        snap = _load_float_shares_map()
        if snap is not None and not snap.empty and "stock_code" in snap.columns:
            row = snap.loc[snap["stock_code"].astype(str).isin(keys)]
            if not row.empty:
                fs = row.iloc[0].get("FloatVolume") or row.iloc[0].get("float_shares")
                if fs is not None and float(fs) > 0:
                    out[:] = float(fs)
    return out


def turnover_from_daily_shares(volume: np.ndarray, shares: np.ndarray) -> np.ndarray:
    """换手 = volume(手) * 100 / 当日 asof 流通股本（股）。按日对齐，禁止用单日股本铺整窗。"""
    vol = np.asarray(volume, dtype=np.float64)
    sh = np.asarray(shares, dtype=np.float64)
    if vol.shape != sh.shape:
        raise ValueError(f"volume/shares length mismatch: {vol.shape} vs {sh.shape}")
    out = np.full(vol.shape, np.nan, dtype=np.float64)
    ok = np.isfinite(vol) & np.isfinite(sh) & (sh > 0.0)
    out[ok] = vol[ok] * 100.0 / sh[ok]
    return out


def _cyqk_start_i(
    index: pd.Index,
    window: int,
    compute_from: Optional[pd.Timestamp],
) -> int:
    start_i = window - 1
    if compute_from is not None:
        hits = np.flatnonzero(index >= pd.Timestamp(compute_from))
        if len(hits):
            start_i = max(start_i, int(hits[0]))
    return start_i


def _try_cyqk_series_rust(
    df: pd.DataFrame,
    shares: np.ndarray,
    window: int,
    start_i: int,
    step: float = 0.01,
) -> Optional[pd.Series]:
    """调用已安装的 PyO3 `compute_cyqk_series`；符号不存在或失败则 None。"""
    try:
        import turnover_resist as tr  # type: ignore[import-not-found]
    except ImportError:
        return None
    fn = getattr(tr, "compute_cyqk_series", None)
    if fn is None:
        return None
    try:
        arr = fn(
            np.ascontiguousarray(df["close"], dtype=np.float64).tolist(),
            np.ascontiguousarray(df["high"], dtype=np.float64).tolist(),
            np.ascontiguousarray(df["low"], dtype=np.float64).tolist(),
            np.ascontiguousarray(df["volume"], dtype=np.float64).tolist(),
            np.ascontiguousarray(shares, dtype=np.float64).tolist(),
            int(window),
            int(start_i),
            float(step),
        )
    except Exception:
        return None
    if arr is None or len(arr) != len(df):
        return None
    return pd.Series(np.asarray(arr, dtype=np.float64), index=df.index)


def _cyqk_series_python(
    df: pd.DataFrame,
    stock_code: str,
    shares: np.ndarray,
    window: int,
    start_i: int,
) -> pd.Series:
    n = len(df)
    out = np.full(n, np.nan, dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    volume = df["volume"].to_numpy(dtype=np.float64)
    work = df[["close", "high", "low", "volume"]].copy()
    for i in range(start_i, n):
        lo = i - window + 1
        win_sh = shares[lo : i + 1]
        if win_sh.size != window or not np.isfinite(win_sh).all() or np.any(win_sh <= 0):
            continue
        sl = work.iloc[lo : i + 1].copy()
        sl["turnover_rate"] = turnover_from_daily_shares(volume[lo : i + 1], win_sh)
        as_of = pd.Timestamp(df.index[i])
        try:
            arr = adapt_columns(sl, stock_code=stock_code, as_of_date=as_of)
            dist = daily_chip_distribution(arr)
            out[i] = float(cyq.ChipFactor(float(closes[i]), dist).get_cyqk_c())
        except Exception:
            out[i] = np.nan
    return pd.Series(out, index=df.index)


def cyqk_series(
    df: pd.DataFrame,
    stock_code: str,
    window: int = CHIP_WINDOW,
    compute_from: Optional[pd.Timestamp] = None,
) -> pd.Series:
    """截至当日（含）的 200 日筹码盈筹率；窗内每一日换手用该日 asof 股本。

    优先 Rust PyO3（按日股本 + 每窗独立价格网格）；失败回退本文件 Python 循环。
    """
    shares = shares_asof_series(stock_code, pd.DatetimeIndex(df.index))
    start_i = _cyqk_start_i(df.index, window, compute_from)
    rust = _try_cyqk_series_rust(df, shares, window, start_i)
    if rust is not None:
        return rust
    return _cyqk_series_python(df, stock_code, shares, window, start_i)


def build_signal_frame(
    df: pd.DataFrame,
    stock_code: str,
    cyqk_from: Optional[pd.Timestamp] = None,
    *,
    use_cyqk: bool = True,
    cyqk_th: float = CYQK_TH,
    use_bb: bool = True,
    index_close: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """给日线 OHLCV 加上均线、盈筹率、finite、cond、edge。

    ``index_close`` 提供时（指数过滤开启）：D 收盘要求对应指数收盘 > 指数
    MA5 且 > MA10；指数值缺失 → finite 为假（fail-closed 无信号）。
    """
    out = df.copy()
    close = out["close"]
    out["sma5"] = close.rolling(5, min_periods=5).mean()
    out["sma20"] = close.rolling(20, min_periods=20).mean()
    out["sma60"] = close.rolling(60, min_periods=60).mean()
    out["week_ma20"] = week_ma20_asof(close)
    out["bb_upper"] = bb_upper_series(close)
    if use_cyqk:
        out["cyqk"] = cyqk_series(out, stock_code, compute_from=cyqk_from)
    else:
        out["cyqk"] = np.nan
    if index_close is not None:
        idx = index_ma_frame(index_close, out.index)
        out["idx_close"] = idx["idx_close"].to_numpy(dtype=np.float64)
        out["idx_sma5"] = idx["idx_sma5"].to_numpy(dtype=np.float64)
        out["idx_sma10"] = idx["idx_sma10"].to_numpy(dtype=np.float64)
    high_v = out["high"].to_numpy(dtype=np.float64)
    finite = (
        np.isfinite(out["sma20"].to_numpy(dtype=np.float64))
        & np.isfinite(out["sma60"].to_numpy(dtype=np.float64))
        & np.isfinite(out["week_ma20"].to_numpy(dtype=np.float64))
    )
    if use_bb:
        finite = (
            finite
            & np.isfinite(out["bb_upper"].to_numpy(dtype=np.float64))
            & np.isfinite(high_v)
        )
    if use_cyqk:
        finite = finite & np.isfinite(out["cyqk"].to_numpy(dtype=np.float64))
    if index_close is not None:
        finite = (
            finite
            & np.isfinite(out["idx_close"].to_numpy(dtype=np.float64))
            & np.isfinite(out["idx_sma5"].to_numpy(dtype=np.float64))
            & np.isfinite(out["idx_sma10"].to_numpy(dtype=np.float64))
        )
    close_v = close.to_numpy(dtype=np.float64)
    cond = (
        finite
        & (close_v > out["sma20"].to_numpy(dtype=np.float64))
        & (close_v > out["sma60"].to_numpy(dtype=np.float64))
        & (close_v > out["week_ma20"].to_numpy(dtype=np.float64))
    )
    if use_bb:
        cond = cond & (high_v > out["bb_upper"].to_numpy(dtype=np.float64))
    if use_cyqk:
        cond = cond & (out["cyqk"].to_numpy(dtype=np.float64) > float(cyqk_th))
    if index_close is not None:
        cond = (
            cond
            & (out["idx_close"].to_numpy(dtype=np.float64) > out["idx_sma5"].to_numpy(dtype=np.float64))
            & (out["idx_close"].to_numpy(dtype=np.float64) > out["idx_sma10"].to_numpy(dtype=np.float64))
        )
    edge = np.zeros(len(out), dtype=bool)
    edge[1:] = cond[1:] & (~cond[:-1]) & finite[:-1]
    out["finite"] = finite
    out["cond"] = cond
    out["edge"] = edge
    return out


def mask_pre_window_edges(sig: pd.DataFrame, stats_start: pd.Timestamp) -> pd.DataFrame:
    """统计窗前最后一个交易日之前的 edge 置假（该日边缘仍可在窗内首日买入）。"""
    out = sig.copy()
    pre = out.index[out.index < pd.Timestamp(stats_start)]
    if len(pre) == 0:
        return out
    last_pre = pre[-1]
    out.loc[out.index < last_pre, "edge"] = False
    return out


def max_drawdown(equity: list[tuple[date, float]], from_ts: pd.Timestamp) -> float:
    vals = [v for d, v in equity if pd.Timestamp(d) >= from_ts]
    if not vals:
        return float("nan")
    peak = vals[0]
    dd = 0.0
    for v in vals:
        peak = max(peak, v)
        if peak > 0:
            dd = min(dd, v / peak - 1.0)
    return dd


class SignalPandasData(bt.feeds.PandasData):
    lines = ("sma5", "edge")
    params = (
        ("datetime", None),
        ("open", -1),
        ("high", -1),
        ("low", -1),
        ("close", -1),
        ("volume", -1),
        ("sma5", -1),
        ("edge", -1),
    )


class AShareCommInfo(bt.CommInfoBase):
    params = (
        ("commission", 0.00005),
        ("min_commission", 5.0),
        ("stamp_tax", 0.0005),
        ("stocklike", True),
        ("commtype", bt.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )

    def _getcommission(self, size, price, pseudoexec):
        notional = abs(size) * price
        comm = max(notional * self.p.commission, self.p.min_commission)
        if size < 0:
            comm += notional * self.p.stamp_tax
        return comm


@dataclass
class RunResult:
    code: str
    board: str
    trades: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    equity_end: float = DEFAULT_CASH
    n_buys: int = 0
    max_dd: float = float("nan")
    skipped: bool = False
    skip_reason: str = ""


class MaChipEdgeStrategy(bt.Strategy):
    params = (("stock_code", ""),)

    def __init__(self):
        self.pending_buy = False
        self.pending_sell = False
        self.hold_mode: Optional[str] = None
        self.buy_ref_close: Optional[float] = None
        self.trades: list[dict] = []
        self.events: list[dict] = []
        self.equity_curve: list[tuple[date, float]] = []
        self._long = False
        self._pending_ref_close: Optional[float] = None
        self._sold_today = False
        self._buy_sig_date: Optional[date] = None

    def _dt(self) -> date:
        return self.data.datetime.date(0)

    def _pos_size(self) -> int:
        try:
            return abs(int(self.position.size))
        except Exception:
            return 0

    def notify_order(self, order):
        if order.status in (order.Margin, order.Rejected, order.Canceled):
            self.events.append(
                {
                    "date": self._dt().isoformat(),
                    "code": self.p.stock_code,
                    "event": f"order_{order.getstatusname().lower()}",
                    "open": float(self.data.open[0]),
                }
            )
            if order.isbuy():
                self._long = False
                self.hold_mode = None
                self.buy_ref_close = None
            return
        if order.status != order.Completed:
            return
        rec = {
            "date": self._dt().isoformat(),
            "code": self.p.stock_code,
            "side": "BUY" if order.isbuy() else "SELL",
            "price": float(order.executed.price),
            "size": abs(int(order.executed.size)),
        }
        self.trades.append(rec)
        if order.isbuy():
            self._long = True
            self.hold_mode = "first_day"
            self.buy_ref_close = self._pending_ref_close
        else:
            self._long = False
            self.hold_mode = None
            self.buy_ref_close = None
            self.pending_sell = False
            self._sold_today = True

    def next_open(self):
        """cheat_on_open：用当日开盘成交，再进入 next() 看收盘。"""
        code = self.p.stock_code
        o = float(self.data.open[0])
        vol = float(self.data.volume[0])
        prev_c = float(self.data.close[-1]) if len(self.data) > 1 else np.nan
        d = self._dt().isoformat()
        long_now = self._pos_size() > 0 or self._long

        if self.pending_sell and long_now:
            if vol <= 0 or is_limit_open(code, o, prev_c, up=False):
                self.events.append({"date": d, "code": code, "event": "skip_sell", "open": o})
                return
            size = self._pos_size()
            if size <= 0:
                self.events.append({"date": d, "code": code, "event": "skip_sell", "open": o})
                return
            self.sell(size=size)
            return

        if self.pending_buy and (not long_now):
            gap = (
                (self._dt() - self._buy_sig_date).days
                if self._buy_sig_date is not None
                else 10**9
            )
            if self._buy_sig_date is None or gap > PENDING_BUY_MAX_GAP_DAYS:
                self.events.append(
                    {"date": d, "code": code, "event": "skip_buy", "open": o, "reason": "stale"}
                )
            elif vol <= 0 or is_limit_open(code, o, prev_c, up=True):
                self.events.append({"date": d, "code": code, "event": "skip_buy", "open": o})
            else:
                size = affordable_size(float(self.broker.getcash()), o)
                if size >= 100:
                    self._pending_ref_close = prev_c
                    self.buy(size=size)
            self.pending_buy = False
            self._buy_sig_date = None

    def next(self):
        c = float(self.data.close[0])
        sma5 = float(self.data.sma5[0])
        long_now = self._pos_size() > 0 or self._long
        bought_today = self.hold_mode == "first_day" and long_now and (not self._sold_today)

        if not self.pending_sell:
            if self.hold_mode == "first_day" and long_now:
                if self.buy_ref_close is not None and c <= self.buy_ref_close:
                    self.pending_sell = True
                else:
                    self.hold_mode = "ma5"
                    if np.isfinite(sma5) and c < sma5:
                        self.pending_sell = True
            elif self.hold_mode == "ma5" and long_now:
                if np.isfinite(sma5) and c < sma5:
                    self.pending_sell = True

        if (
            len(self.data) >= 2
            and (not long_now)
            and (not self.pending_sell)
            and (not self._sold_today)
            and (not bought_today)
        ):
            if float(self.data.edge[0]) > 0.5:
                self.pending_buy = True
                self._buy_sig_date = self._dt()

        self.equity_curve.append((self._dt(), float(self.broker.getvalue())))
        self._sold_today = False


def _list_float_codes() -> set[str]:
    path = resolve_source_parquet("float_shares.parquet")
    if not path.is_file():
        return set()
    s = pd.read_parquet(path, columns=["stock_code"])["stock_code"].astype(str)
    return {to_canonical_symbol(x.replace(".", "_")) if "." not in x else x for x in s}


def _list_front_hive_codes() -> set[str]:
    root = resolve_period_root("1d") / "dividend_type=front"
    if not root.is_dir():
        return set()
    out: set[str] = set()
    for p in root.iterdir():
        if p.name.startswith("symbol=") and (p / "data.parquet").is_file():
            out.add(to_canonical_symbol(p.name[len("symbol=") :]))
    return out


def candidates_by_board(seed: int) -> dict[str, list[str]]:
    pool = _list_float_codes() & _list_front_hive_codes()
    rng = np.random.default_rng(seed)
    out: dict[str, list[str]] = {}
    for board in ("sz_main", "sh_main", "chinext"):
        cands = [c for c in pool if board_of(c) == board]
        cands.sort()
        rng.shuffle(cands)
        out[board] = cands
    return out


def load_front_daily(code: str, start: str, end: str) -> Optional[pd.DataFrame]:
    reader = StockDataReader(mode="parquet")
    try:
        df = reader.read_stock(
            code,
            start_time=start,
            end_time=end,
            period="1d",
            adjust_type="front",
        )
    finally:
        reader.close()
    if df is None or df.empty:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        if "time" in df.columns:
            df = df.set_index(pd.to_datetime(df["time"]))
        else:
            return None
    df = df.sort_index()
    need = {"open", "high", "low", "close", "volume"}
    if not need.issubset(df.columns):
        return None
    return df[list(need)].astype(np.float64)


def ready_for_stats(sig: pd.DataFrame, stats_start: pd.Timestamp) -> bool:
    pre = sig.loc[sig.index < stats_start]
    if pre.empty:
        return False
    return bool(pre["finite"].any())


def run_one(code: str, board: str, sig: pd.DataFrame, stats_start: pd.Timestamp, cash: float) -> RunResult:
    warmup_from = stats_start - pd.Timedelta(days=14)
    feed_df = mask_pre_window_edges(sig, stats_start)
    feed_df = feed_df.loc[feed_df.index >= warmup_from].copy()
    feed_df = feed_df.dropna(subset=["open", "close"])
    feed_df["edge"] = feed_df["edge"].astype(float)
    feed_df["sma5"] = feed_df["sma5"].astype(float)
    cerebro = bt.Cerebro(stdstats=False, cheat_on_open=True, runonce=False)
    cerebro.broker.setcash(cash)
    cerebro.broker.set_coo(True)
    cerebro.broker.addcommissioninfo(AShareCommInfo())
    data = SignalPandasData(dataname=feed_df)
    cerebro.adddata(data, name=code)
    cerebro.addstrategy(MaChipEdgeStrategy, stock_code=code)
    strat = cerebro.run()[0]
    trades = [t for t in strat.trades if pd.Timestamp(t["date"]) >= stats_start]
    events = [e for e in strat.events if pd.Timestamp(e["date"]) >= stats_start]
    return RunResult(
        code=code,
        board=board,
        trades=trades,
        events=events,
        equity_end=float(cerebro.broker.getvalue()),
        n_buys=sum(1 for t in trades if t["side"] == "BUY"),
        max_dd=max_drawdown(strat.equity_curve, stats_start),
    )


def _as_ymd(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def pair_round_trips(trades: Iterable[dict]) -> list[dict]:
    """同一票按时间 FIFO：BUY 配下一笔 SELL。连续两买则先一笔记 OPEN。"""
    by_code: dict[str, list[dict]] = {}
    for raw in trades:
        by_code.setdefault(str(raw["code"]), []).append(raw)

    def _sort_key(row: dict) -> tuple:
        side = str(row.get("side", "")).upper()
        return (pd.Timestamp(row["date"]), 0 if side == "BUY" else 1)

    out: list[dict] = []
    for code, rows in by_code.items():
        pending: Optional[dict] = None
        seq = 0
        for row in sorted(rows, key=_sort_key):
            side = str(row.get("side", "")).upper()
            if side == "BUY":
                if pending is not None:
                    seq += 1
                    out.append(_open_pair(code, seq, pending))
                pending = row
            elif side == "SELL":
                if pending is None:
                    seq += 1
                    out.append(_unmatched_sell(code, seq, row))
                else:
                    seq += 1
                    out.append(_closed_pair(code, seq, pending, row))
                    pending = None
        if pending is not None:
            seq += 1
            out.append(_open_pair(code, seq, pending))
    return out


def _trade_px(row: dict) -> float:
    return float(row["price"])


def _trade_sz(row: dict) -> int:
    return int(round(float(row["size"])))


def _closed_pair(code: str, seq: int, buy: dict, sell: dict) -> dict:
    buy_d = pd.Timestamp(buy["date"])
    sell_d = pd.Timestamp(sell["date"])
    buy_px = _trade_px(buy)
    sell_px = _trade_px(sell)
    ret = (sell_px / buy_px - 1.0) if buy_px > 0 else float("nan")
    return {
        "code": code,
        "seq": seq,
        "buy_date": _as_ymd(buy_d),
        "buy_price": buy_px,
        "buy_size": _trade_sz(buy),
        "sell_date": _as_ymd(sell_d),
        "sell_price": sell_px,
        "sell_size": _trade_sz(sell),
        "hold_days": int((sell_d.normalize() - buy_d.normalize()).days),
        "ret_pct": ret,
        "status": "closed",
    }


def _open_pair(code: str, seq: int, buy: dict) -> dict:
    return {
        "code": code,
        "seq": seq,
        "buy_date": _as_ymd(buy["date"]),
        "buy_price": _trade_px(buy),
        "buy_size": _trade_sz(buy),
        "sell_date": "",
        "sell_price": float("nan"),
        "sell_size": 0,
        "hold_days": 0,
        "ret_pct": float("nan"),
        "status": "open",
    }


def _unmatched_sell(code: str, seq: int, sell: dict) -> dict:
    return {
        "code": code,
        "seq": seq,
        "buy_date": "",
        "buy_price": float("nan"),
        "buy_size": 0,
        "sell_date": _as_ymd(sell["date"]),
        "sell_price": _trade_px(sell),
        "sell_size": _trade_sz(sell),
        "hold_days": 0,
        "ret_pct": float("nan"),
        "status": "unmatched_sell",
    }


def format_trades_by_stock(
    pairs: list[dict],
    stats: pd.DataFrame,
    universe: pd.DataFrame,
    events: Iterable[dict],
    *,
    title: str,
    cash: float = DEFAULT_CASH,
) -> str:
    """给人看的按票配对清单。size 必须用成交股数字段，禁止 Series.size。"""
    board = {}
    if len(universe) and "code" in universe.columns:
        board = dict(zip(universe["code"].astype(str), universe.get("board", pd.Series(dtype=str)).astype(str)))
    order: list[str] = []
    if len(universe) and "code" in universe.columns:
        order = [str(c) for c in universe["code"].tolist()]
    extra = [c for c in dict.fromkeys(str(p["code"]) for p in pairs) if c not in order]
    order.extend(extra)

    stats_map = {}
    if len(stats) and "code" in stats.columns:
        for rec in stats.to_dict("records"):
            stats_map[str(rec["code"])] = rec

    ev_map: dict[str, list[dict]] = {}
    for ev in events:
        name = str(ev.get("code", ""))
        if ev.get("event") in {"skip_buy", "skip_sell"}:
            ev_map.setdefault(name, []).append(ev)

    by_code: dict[str, list[dict]] = {}
    for p in pairs:
        by_code.setdefault(str(p["code"]), []).append(p)

    cash_txt = f"{cash:.0f}"
    lines = [
        f"# {title}" if title else "# ma_chip_edge trades_by_stock",
        "",
        f"每票独立现金 {cash_txt}，前复权开盘成交。配对 = 同一票 BUY 后第一笔 SELL。",
        "ret_pct = 卖价/买价-1（不含费用）。OPEN = 期末未平。hold = 日历日。",
        "",
    ]
    for code in order:
        st = stats_map.get(code, {})
        bd = board.get(code, st.get("board", ""))
        n_buys = int(st["n_buys"]) if "n_buys" in st and pd.notna(st["n_buys"]) else len(by_code.get(code, []))
        ret = st.get("ret", float("nan"))
        dd = st.get("max_dd", float("nan"))
        ret_s = f"{float(ret)*100:+.2f}%" if pd.notna(ret) else "nan"
        dd_s = f"{float(dd)*100:.2f}%" if pd.notna(dd) else "nan"
        lines.append(f"## {code}  {bd}  n_buys={n_buys}  ret={ret_s}  max_dd={dd_s}")
        for p in by_code.get(code, []):
            lines.append(_format_pair_line(p))
        for ev in ev_map.get(code, []):
            reason = ev.get("reason")
            if reason is None or (isinstance(reason, float) and pd.isna(reason)):
                reason = ""
            else:
                reason = str(reason).strip()
            if reason.lower() in {"", "nan", "none"}:
                reason = ""
            extra = f"  reason={reason}" if reason else ""
            open_px = ev.get("open", "")
            try:
                open_s = f"{float(open_px):.4f}"
            except (TypeError, ValueError):
                open_s = str(open_px)
            lines.append(f"    {ev.get('event')}  {_as_ymd(ev.get('date'))}  open={open_s}{extra}")
        lines.append("")
    return "\n".join(lines)


def _format_pair_line(pair: dict) -> str:
    seq = int(pair["seq"])
    status = str(pair.get("status", ""))
    if status == "closed":
        ret = float(pair["ret_pct"])
        return (
            f"{seq:3d} {_as_ymd(pair['buy_date'])} BUY  {float(pair['buy_price']):8.4f}  {int(pair['buy_size']):7d}"
            f"  ->  {_as_ymd(pair['sell_date'])} SELL {float(pair['sell_price']):8.4f}  {int(pair['sell_size']):7d}"
            f"  hold={int(pair['hold_days'])}d  {ret*100:+.2f}%"
        )
    if status == "open":
        return (
            f"{seq:3d} {_as_ymd(pair['buy_date'])} BUY  {float(pair['buy_price']):8.4f}  {int(pair['buy_size']):7d}"
            f"  ->  OPEN"
        )
    return (
        f"{seq:3d} ----           SELL {float(pair['sell_price']):8.4f}  {int(pair['sell_size']):7d}"
        f"  unmatched_sell {_as_ymd(pair['sell_date'])}"
    )


def write_paired_trade_listing(
    out_dir: Path,
    trades: list[dict],
    stats: pd.DataFrame,
    universe: pd.DataFrame,
    events: list[dict],
    *,
    title: str,
    cash: float = DEFAULT_CASH,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = pair_round_trips(trades)
    pd.DataFrame(pairs).to_csv(out_dir / "trade_pairs.csv", index=False, encoding="utf-8")
    text = format_trades_by_stock(
        pairs, stats, universe, events, title=title, cash=cash
    )
    path = out_dir / "trades_by_stock.txt"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def rebuild_paired_listing(
    out_dir: Path,
    *,
    title: str = "",
    cash: float = DEFAULT_CASH,
) -> Path:
    """从已有 trades.csv 重出配对清单，不重跑 Cerebro。"""
    def _read(name: str) -> pd.DataFrame:
        p = out_dir / name
        if not p.exists() or p.stat().st_size < 4:
            return pd.DataFrame()
        return pd.read_csv(p)

    trades_df = _read("trades.csv")
    stats = _read("per_stock_stats.csv")
    universe = _read("universe.csv")
    events_df = _read("events.csv")
    trades = trades_df.to_dict("records") if len(trades_df) else []
    events = events_df.to_dict("records") if len(events_df) else []
    head = title or out_dir.name
    return write_paired_trade_listing(
        out_dir, trades, stats, universe, events, title=head, cash=cash
    )


def _write_report(
    out_dir: Path,
    universe: pd.DataFrame,
    results: list[RunResult],
    stats: pd.DataFrame,
    *,
    title: str = "",
    cash: float = DEFAULT_CASH,
    use_cyqk: bool = True,
    cyqk_th: float = CYQK_TH,
    use_bb: bool = True,
    use_index_ma: bool = False,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    universe.to_csv(out_dir / "universe.csv", index=False, encoding="utf-8")
    trades = [t for r in results for t in r.trades]
    events = [e for r in results for e in r.events]
    pd.DataFrame(trades).to_csv(out_dir / "trades.csv", index=False, encoding="utf-8")
    pd.DataFrame(events).to_csv(out_dir / "events.csv", index=False, encoding="utf-8")
    stats.to_csv(out_dir / "per_stock_stats.csv", index=False, encoding="utf-8")
    n_trig = int((stats["n_buys"] > 0).sum()) if len(stats) else 0
    eq = float(stats["ret"].mean()) if len(stats) else float("nan")
    med = float(stats["ret"].median()) if len(stats) else float("nan")
    dd = float(stats["max_dd"].mean()) if len(stats) and "max_dd" in stats.columns else float("nan")
    ev = pd.DataFrame(events)
    n_skip_buy = int((ev["event"] == "skip_buy").sum()) if len(ev) and "event" in ev.columns else 0
    n_skip_sell = int((ev["event"] == "skip_sell").sum()) if len(ev) and "event" in ev.columns else 0
    n_open = 0
    if trades:
        td = pd.DataFrame(trades)
        n_open = int(
            (
                td.groupby("code")["side"].apply(lambda s: (s == "BUY").sum() - (s == "SELL").sum())
                > 0
            ).sum()
        )
    board_counts = (
        universe.groupby("board")["code"].count().to_dict() if len(universe) else {}
    )
    lines = [
        "# ma_chip_edge trial",
        "",
        "框架试验，不论证因子有效。涨跌停用 front 昨收，未套 ST 5%。",
        "",
        f"- cyqk_filter: {'on > ' + f'{cyqk_th:.2f}' if use_cyqk else 'off'}",
        f"- bb_break: {'D high > SMA20(close)+2σ (ddof=1)' if use_bb else 'off'}",
        f"- index_ma: "
        + (
            "D 收盘对应指数 > MA{} 且 > MA{}（{}）".format(
                INDEX_MA_FAST,
                INDEX_MA_SLOW,
                "·".join(f"{b}={BOARD_INDEX[b]}" for b in sorted(BOARD_INDEX)),
            )
            if use_index_ma
            else "off"
        ),
        f"- names: {len(stats)}",
        f"- per_board: {board_counts}",
        f"- names_with_buy: {n_trig}",
        f"- mean_single_name_return: {eq:.4f}" if np.isfinite(eq) else "- mean_single_name_return: nan",
        f"- median_single_name_return: {med:.4f}" if np.isfinite(med) else "- median_single_name_return: nan",
        f"- mean_max_drawdown: {dd:.4f}" if np.isfinite(dd) else "- mean_max_drawdown: nan",
        f"- names_still_open: {n_open}",
        f"- skip_buy: {n_skip_buy}",
        f"- skip_sell: {n_skip_sell}",
        "- paired_listing: trades_by_stock.txt / trade_pairs.csv",
        "",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    write_paired_trade_listing(
        out_dir,
        trades,
        stats,
        universe,
        events,
        title=title or out_dir.name,
        cash=cash,
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="MA + cyqk_c edge entry trial (plan v3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=HELP_LOCK,
    )
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--start", default="20240101", help="stats window start YYYYMMDD")
    ap.add_argument("--end", default="", help="YYYYMMDD, default today")
    ap.add_argument("--per-board", type=int, default=10)
    ap.add_argument("--cash", type=float, default=DEFAULT_CASH)
    ap.add_argument("--codes", default="", help="comma codes, skip random sample")
    ap.add_argument(
        "--from-dir",
        default="",
        help="rebuild trades_by_stock.txt from an existing output dir (no Cerebro)",
    )
    ap.add_argument(
        "--no-cyqk",
        action="store_true",
        help="drop cyqk from entry; MA+BB-upper edge (writes *_nocyqk dir)",
    )
    ap.add_argument(
        "--cyqk-th",
        type=float,
        default=CYQK_TH,
        help="cyqk threshold in 0-1 (default 0.70); ignored with --no-cyqk",
    )
    ap.add_argument(
        "--no-bb",
        action="store_true",
        help="drop high>bb_upper from entry (writes *_nobb dir)",
    )
    ap.add_argument(
        "--no-index-ma",
        action="store_true",
        help="drop the board-index MA5/MA10 filter from entry (writes *_noidx dir)",
    )
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.from_dir:
        out = Path(args.from_dir)
        if not out.is_absolute():
            out = Path(REPO) / out
        path = rebuild_paired_listing(out, title=out.name, cash=args.cash)
        print(f"wrote {path}")
        return 0

    end = args.end or date.today().strftime("%Y%m%d")
    stats_start = pd.Timestamp(args.start)
    use_cyqk = not args.no_cyqk
    use_bb = not args.no_bb
    use_index_ma = not args.no_index_ma
    cyqk_th = float(args.cyqk_th)
    if use_cyqk and (not np.isfinite(cyqk_th) or cyqk_th <= 0.0 or cyqk_th >= 1.0):
        raise SystemExit(f"--cyqk-th must be in (0, 1), got {cyqk_th}")
    cyqk_from = stats_start - pd.Timedelta(days=CYQK_PRE_STATS_CAL_DAYS)
    index_close_by_board: dict[str, pd.Series] = {}
    if use_index_ma:
        for board, idx_code in BOARD_INDEX.items():
            s = load_index_close(idx_code, LOAD_START, end)
            if s is None or s.empty:
                raise SystemExit(
                    f"index filter is on but {idx_code} ({board}) has no data at "
                    f"{resolve_index_daily_root()} (index tree, dividend_type=none)"
                )
            index_close_by_board[board] = s
        print(
            "[index] " + " ".join(f"{b}={BOARD_INDEX[b]}" for b in sorted(index_close_by_board)),
            flush=True,
        )
    results: list[RunResult] = []
    stat_rows = []
    used = []

    def _try_code(code: str, board: str, replaced: bool) -> Optional[RunResult]:
        raw = load_front_daily(code, LOAD_START, end)
        if raw is None or len(raw) < CHIP_WINDOW + 60:
            return None
        idx_series = index_close_by_board.get(board) if use_index_ma else None
        if use_index_ma and idx_series is None:
            print(f"[skip] {code}: board {board!r} has no mapped index for the filter", flush=True)
            return None
        sig = build_signal_frame(
            raw,
            code,
            cyqk_from=cyqk_from,
            use_cyqk=use_cyqk,
            cyqk_th=cyqk_th,
            use_bb=use_bb,
            index_close=idx_series,
        )
        if not ready_for_stats(sig, stats_start):
            return None
        print(f"[run] {board} {code}", flush=True)
        return run_one(code, board, sig, stats_start, args.cash), replaced

    if args.codes:
        for code in [c.strip() for c in args.codes.split(",") if c.strip()]:
            board = board_of(code) or "other"
            got = _try_code(code, board, False)
            if got is None:
                results.append(RunResult(code, board, skipped=True, skip_reason="unusable"))
                continue
            run, replaced = got
            results.append(run)
            used.append({"code": code, "board": board, "replaced": replaced})
            stat_rows.append(
                {
                    "code": code,
                    "board": board,
                    "n_buys": run.n_buys,
                    "n_trades": len(run.trades),
                    "n_skips": len(run.events),
                    "equity_end": run.equity_end,
                    "ret": run.equity_end / args.cash - 1.0,
                    "max_dd": run.max_dd,
                }
            )
    else:
        cands = candidates_by_board(args.seed)
        for board, codes in cands.items():
            got_n = 0
            skipped_before = 0
            for code in codes:
                if got_n >= args.per_board:
                    break
                got = _try_code(code, board, skipped_before > 0)
                if got is None:
                    skipped_before += 1
                    continue
                run, replaced = got
                results.append(run)
                used.append({"code": code, "board": board, "replaced": replaced})
                stat_rows.append(
                    {
                        "code": code,
                        "board": board,
                        "n_buys": run.n_buys,
                        "n_trades": len(run.trades),
                        "n_skips": len(run.events),
                        "equity_end": run.equity_end,
                        "ret": run.equity_end / args.cash - 1.0,
                        "max_dd": run.max_dd,
                    }
                )
                got_n += 1

    tag = f"ma_chip_edge_{args.seed}_{end}"
    if not use_cyqk:
        tag += "_nocyqk"
    elif abs(cyqk_th - CYQK_TH) > 1e-12:
        tag += f"_cyqk{int(round(cyqk_th * 100))}"
    if not use_bb:
        tag += "_nobb"
    if not use_index_ma:
        tag += "_noidx"
    out_dir = Path(REPO) / "backtest_output" / tag
    stats = pd.DataFrame(stat_rows)
    _write_report(
        out_dir,
        pd.DataFrame(used),
        results,
        stats,
        title=f"{tag} (seed={args.seed}, {args.start}..{end})",
        cash=args.cash,
        use_cyqk=use_cyqk,
        cyqk_th=cyqk_th,
        use_bb=use_bb,
        use_index_ma=use_index_ma,
    )
    print(f"wrote {out_dir}")
    print(stats.to_string(index=False) if len(stats) else "no names ran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
