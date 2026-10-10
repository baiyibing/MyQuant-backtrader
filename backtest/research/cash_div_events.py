# -*- coding: utf-8 -*-
"""Explicit cash-dividend events for 6.54 (overnight shares x cash per share).

600036 uses A-share implementation-notice cash. Other names reuse the 2026-10-08
overlay filter: lake ``ex_date_index`` dr in (1, 1.12] and implied cash/share
>= 0.30. Bonus ratio is 0. Pay date equals ex-date so overlay and engine match.
"""

from __future__ import annotations

from typing import Mapping

import pandas as pd
import pyarrow.parquet as pq

from backtest.research.ashare_bars import load_daily_ohlc
from backtest.research.ashare_exdiv_economics import ExDivEvent
from common.infra.data_root import resolve_source_parquet

PARK = "600036.SH"
CASH_DR_MAX = 1.12
CASH_PS_MIN = 0.30
# 巨潮 2026-01-10 / 1224927640 ；巨潮 2026-07-04 / 公告 2026-029
CMB_CASH_PS: dict[tuple[str, str], float] = {
    (PARK, "20260116"): 1.013,
    (PARK, "20260710"): 1.003,
}


def official_cmb_events() -> dict[tuple[str, str], ExDivEvent]:
    """Advertised 600036 cash events; no lake required."""
    out: dict[tuple[str, str], ExDivEvent] = {}
    for (code, ymd), cash_ps in CMB_CASH_PS.items():
        out[(code, ymd)] = ExDivEvent(
            event_id=f"{code}:{ymd}:cash",
            bonus_ratio=0,
            cash_div_per_share=cash_ps,
            ex_date=ymd,
            pay_date=ymd,
        )
    return out


def _close_map(bars: dict, code: str) -> dict[str, float]:
    out: dict[str, float] = {}
    df = bars.get(code)
    if df is None or len(df) == 0:
        return out
    for ts, row in df.iterrows():
        out[pd.Timestamp(ts).strftime("%Y%m%d")] = float(row["close"])
    return out


def _prev_close(closes: dict[str, float], ymd: str) -> float | None:
    keys = [k for k in closes if k < ymd]
    if not keys:
        return None
    return closes[max(keys)]


def load_cash_div_lookup(
    start: str,
    end: str,
    *,
    workers: int = 8,
    codes: set[str] | None = None,
    bars: dict | None = None,
) -> dict[tuple[str, str], ExDivEvent]:
    """Build (symbol, ex_ymd) -> cash-only ExDivEvent for [start, end].

    ``codes`` / ``bars`` come from the product ``run()`` lake load so the
    lookup does not pull the whole market. Official 600036 cash is always in.
    """
    start_ymd = "".join(ch for ch in str(start) if ch.isdigit())[:8]
    end_ymd = "".join(ch for ch in str(end) if ch.isdigit())[:8]
    out = {
        key: ev
        for key, ev in official_cmb_events().items()
        if start_ymd <= key[1] <= end_ymd
    }
    ex = pq.read_table(resolve_source_parquet("ex_date_index.parquet")).to_pandas()
    ex["stock_code"] = ex["stock_code"].astype(str)
    ex["ex_ymd"] = ex["ex_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    ex["dr"] = pd.to_numeric(ex["dr"], errors="coerce")
    ev = ex[
        (ex["ex_ymd"] >= start_ymd)
        & (ex["ex_ymd"] <= end_ymd)
        & ex["dr"].notna()
        & (ex["dr"] > 1.0)
        & (ex["dr"] <= CASH_DR_MAX)
        & (ex["stock_code"] != PARK)
    ].copy()
    if codes is not None:
        allowed = {str(c) for c in codes}
        ev = ev[ev["stock_code"].isin(allowed)]
    if ev.empty:
        return out
    need = sorted(set(ev["stock_code"].astype(str)))
    if bars is None:
        bars = load_daily_ohlc(need, start_ymd, end_ymd, source="lake", workers=workers)
    close_by = {c: _close_map(bars, c) for c in need}
    for row in ev.itertuples(index=False):
        code = str(row.stock_code)
        ex_ymd = str(row.ex_ymd)
        if (code, ex_ymd) in out:
            continue
        prev_px = _prev_close(close_by.get(code, {}), ex_ymd)
        if prev_px is None or prev_px <= 0:
            continue
        cash_ps = float(prev_px) * (1.0 - 1.0 / float(row.dr))
        if cash_ps < CASH_PS_MIN:
            continue
        out[(code, ex_ymd)] = ExDivEvent(
            event_id=f"{code}:{ex_ymd}:cash",
            bonus_ratio=0,
            cash_div_per_share=cash_ps,
            ex_date=ex_ymd,
            pay_date=ex_ymd,
        )
    return out


def bind_book_cash_div_economics(
    strategy: str,
    start: str,
    end: str,
    existing: Mapping | None,
    *,
    codes: set[str] | None = None,
    bars: dict | None = None,
    workers: int = 8,
) -> Mapping | None:
    """Product run() only: 6.54 gets the lake lookup when the caller omitted one."""
    if existing is not None:
        return existing
    from backtest.research.csv_strategy_books import normalize_csv_strategy

    if normalize_csv_strategy(strategy) != "version6_54":
        return None
    return load_cash_div_lookup(
        start, end, workers=workers, codes=codes, bars=bars
    )
