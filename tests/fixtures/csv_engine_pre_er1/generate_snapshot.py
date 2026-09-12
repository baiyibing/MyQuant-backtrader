# -*- coding: utf-8 -*-
"""Write 6/8 synthetic-window trades.csv from the current daily engine."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import backtest.research.csv_daily_backtest as sim

DAYS = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]
HERE = Path(__file__).resolve().parent


def _bars(rows: dict[str, list[tuple]]) -> dict:
    idx = pd.to_datetime(DAYS)
    out = {}
    for code, r in rows.items():
        pre = pd.Timestamp(DAYS[0]) - pd.Timedelta(days=2)
        out[code] = pd.DataFrame(
            {
                "open": [10.0] + [x[0] for x in r],
                "high": [10.0] + [x[1] for x in r],
                "low": [10.0] + [x[2] for x in r],
                "close": [10.0] + [x[3] for x in r],
            },
            index=pd.DatetimeIndex([pre]).append(idx),
        ).astype(np.float64)
    return out


def _run(strategy: str, rows: dict, pool: dict):
    return sim.simulate(
        _bars(rows), pool, "20251103", "20251107", strategy=strategy
    )


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    # Shared 6/8 window: buy D0, trail/stop paths on later days.
    rows6 = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.4, 10.6, 10.2, 10.45),
            (10.3, 10.5, 10.0, 10.05),
            (10.0, 10.1, 9.7, 9.8),
            (9.8, 9.9, 9.6, 9.7),
        ]
    }
    rows8 = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (12.0, 13.0, 11.8, 11.489),
            (11.80, 11.90, 11.70, 11.85),
            (11.8, 11.9, 11.6, 11.7),
            (11.7, 11.8, 11.5, 11.6),
        ]
    }
    pool = {"20251103": ["600000.SH"]}
    for book, rows in (("version6", rows6), ("version8", rows8)):
        st = _run(book, rows, pool)
        path = HERE / f"{book}_trades.csv"
        pd.DataFrame(st.trades).to_csv(path, index=False, encoding="utf-8")
        print(f"wrote {path} n={len(st.trades)}")


if __name__ == "__main__":
    main()
