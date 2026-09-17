# -*- coding: utf-8 -*-
"""Mode A assembly: limit-up skip / no-K skip / normal buy / prev_close across halt.

Synthetic tmp_path fixtures only — no F lake, no cwd stock_data/, no resolvers needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.research import unified_exit_modea as m
from oskh_data.symbol_format import to_partition_key


SESSIONS = ["20251103", "20251104", "20251105", "20251106", "20251107"]


def _ms(*dates: str) -> list[int]:
    return [int(pd.Timestamp(d, tz="UTC").timestamp() * 1000) for d in dates]


def _write_pool(pool_dir: Path, ymd: str, rows: list[tuple[str, str]]) -> None:
    pool_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"{bare},{name}" for bare, name in rows]
    (pool_dir / f"{ymd}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _frame(dates: list[str], closes: list[float]) -> pd.DataFrame:
    n = len(dates)
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
        },
        index=pd.to_datetime(dates),
    ).astype(np.float64)


def _write_front_lake(root: Path, code: str, dates: list[str], closes: list[float]) -> None:
    part = root / f"symbol={to_partition_key(code)}"
    part.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "time": _ms(*dates),
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
        }
    ).to_parquet(part / "data.parquet", index=False)


def test_session_calendar_injection_filters_window():
    got = m.load_session_calendar(
        "20251104",
        "20251106",
        sessions=["20251103", "20251104", "20251105", "20251106", "20251107"],
    )
    assert got == ["20251104", "20251105", "20251106"]


def test_limit_up_skip(tmp_path: Path):
    pool = tmp_path / "pool"
    # Main board 10%: +9.9% within tol of 10%-0.2% → skip
    _write_pool(pool, "20251104", [("600000", "SYN_A")])
    bars = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-04"],
            [10.0, 10.0 * 1.099],  # +9.9% >= 10%-0.2%
        )
    }
    inst = m.assemble_instances(pool, SESSIONS, bars)
    assert len(inst) == 1
    assert inst[0].opened is False
    assert inst[0].skip_reason == "limit_up"


def test_no_bar_skip(tmp_path: Path):
    pool = tmp_path / "pool"
    _write_pool(pool, "20251104", [("600000", "SYN_B")])
    # Bar exists on other days only — list day missing
    bars = {"600000.SH": _frame(["2025-11-03", "2025-11-05"], [10.0, 10.1])}
    inst = m.assemble_instances(pool, SESSIONS, bars)
    assert len(inst) == 1
    assert inst[0].opened is False
    assert inst[0].skip_reason == "no_bar"


def test_missing_code_no_bar(tmp_path: Path):
    pool = tmp_path / "pool"
    _write_pool(pool, "20251104", [("600000", "SYN_C")])
    inst = m.assemble_instances(pool, SESSIONS, bars={})
    assert inst[0].skip_reason == "no_bar"
    assert inst[0].opened is False


def test_normal_buy(tmp_path: Path):
    pool = tmp_path / "pool"
    _write_pool(pool, "20251104", [("600000", "SYN_D")])
    bars = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-04"],
            [10.0, 10.5],  # +5% < 9.8% band
        )
    }
    inst = m.assemble_instances(pool, SESSIONS, bars)
    assert len(inst) == 1
    assert inst[0].opened is True
    assert inst[0].buy_price == pytest.approx(10.5)
    assert inst[0].skip_reason is None
    assert m._lot_shares(10.5) == 95200


def test_prev_close_crosses_suspension(tmp_path: Path):
    """prev_close = prior bar in series, not calendar-previous session."""
    pool = tmp_path / "pool"
    # List on 20251106; stock halted 11/04–11/05 (no bars); prior close = 11/03
    _write_pool(pool, "20251106", [("600000", "SYN_E")])
    # From 10.0 → 10.99 = +9.9% vs prior bar → limit-up skip
    bars = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-06"],
            [10.0, 10.99],
        )
    }
    inst = m.assemble_instances(pool, SESSIONS, bars)
    assert inst[0].skip_reason == "limit_up"

    # Same gap but +5% vs prior bar → open
    bars2 = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-06"],
            [10.0, 10.50],
        )
    }
    inst2 = m.assemble_instances(pool, SESSIONS, bars2)
    assert inst2[0].opened is True
    assert inst2[0].buy_price == pytest.approx(10.50)


def test_missing_pool_file_is_silent(tmp_path: Path):
    """No CSV for a session → no buy that day, no error (Q: 20260525/20260605)."""
    pool = tmp_path / "pool"
    _write_pool(pool, "20251103", [("600000", "SYN_F")])
    # 20251104 file absent
    bars = {"600000.SH": _frame(["2025-11-03", "2025-11-04"], [10.0, 10.1])}
    inst = m.assemble_instances(pool, SESSIONS, bars)
    assert len(inst) == 1
    assert inst[0].list_date == "20251103"


def test_load_front_bars_from_synthetic_lake(tmp_path: Path):
    root = tmp_path / "front"
    _write_front_lake(
        root,
        "600000.SH",
        ["2025-11-03", "2025-11-04"],
        [10.0, 10.2],
    )
    got = m.load_front_bars(
        ["600000.SH"],
        "20251103",
        "20251104",
        front_root=root,
        workers=1,
    )
    assert "600000.SH" in got
    assert list(got["600000.SH"]["close"]) == pytest.approx([10.0, 10.2])


def test_chi_next_limit_band(tmp_path: Path):
    """创业板 20% band: +19.9% is limit-up; +15% is not."""
    pool = tmp_path / "pool"
    _write_pool(pool, "20251104", [("300001", "SYN_CHI")])
    bars_up = {
        "300001.SZ": _frame(["2025-11-03", "2025-11-04"], [10.0, 11.99]),
    }
    assert m.assemble_instances(pool, SESSIONS, bars_up)[0].skip_reason == "limit_up"
    bars_ok = {
        "300001.SZ": _frame(["2025-11-03", "2025-11-04"], [10.0, 11.50]),
    }
    assert m.assemble_instances(pool, SESSIONS, bars_ok)[0].opened is True
