# -*- coding: utf-8 -*-
"""Mode A exit evaluator — hand-calculated expectation vectors (≥12).

All fixtures synthetic (tmp_path / in-memory); no F lake.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.research import unified_exit_modea as m


SESSIONS = [
    "20251103",  # 0 buy
    "20251104",  # 1 N=1
    "20251105",  # 2 N=2
    "20251106",  # 3 N=3
    "20251107",  # 4 N=4
    "20251110",  # 5 N=5
]


def _frame(dates: list[str], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
        },
        index=pd.to_datetime(dates),
    ).astype(np.float64)


def _inst(buy: float = 10.0, ymd: str = "20251103", code: str = "600000.SH") -> m.Instance:
    return m.Instance(code, "SYN", ymd, buy, True, None)


def _ret(buy: float, sell: float, *, trade: bool) -> float:
    _, _, r = m._price_return(buy, sell, is_trade=trade)
    return r


def test_grid_counts():
    specs = m.iter_grid()
    assert len(specs) == 8 + 252 + 20  # 280
    assert len(m.iter_grid(include_anchor_hold_end=True)) == 281
    labels = [s.label() for s in specs]
    assert labels.count("r1_n1") == 1
    assert "r2_xinf_yinf_n3" in labels
    assert "r3_y5_n10" in labels


def test_v01_n1_equals_rule2_n1_regardless_of_tp_sl():
    """N=1 equivalence: rule1 N=1 ≡ any rule2 with N=1 (same close/date)."""
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05"],
        [10.0, 10.50, 9.0],
    )}
    inst = _inst(10.0)
    r1 = m.evaluate_exit(inst, m.StrategySpec(1, 1), bars, SESSIONS, end="20251110")
    r2 = m.evaluate_exit(
        inst, m.StrategySpec(2, 1, x=2.0, y=2.0), bars, SESSIONS, end="20251110"
    )
    assert r1.sell_date == r2.sell_date == "20251104"
    assert r1.sell_price == r2.sell_price == pytest.approx(10.50)
    assert r1.reason == "n_expire"
    # rule2 also hits TP (+5% >= 2%) on same day — reason may be take_profit
    assert r2.reason == "take_profit"
    assert r1.return_pct == pytest.approx(r2.return_pct)


def test_v02_rule1_n3_fixed_hold():
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"],
        [10.0, 10.1, 10.2, 10.3],
    )}
    got = m.evaluate_exit(_inst(), m.StrategySpec(1, 3), bars, SESSIONS, end="20251110")
    assert got.sell_date == "20251106"
    assert got.sell_price == pytest.approx(10.3)
    assert got.reason == "n_expire"
    assert got.hold_sessions == 3
    assert got.return_pct == pytest.approx(_ret(10.0, 10.3, trade=True))


def test_v03_limit_down_postpones_n_expire():
    """N=1 day is limit-down (−9.9% vs prior) → postpone to next session."""
    # buy 10 on 11/03; 11/04 close 9.01 vs prev 10 → −9.9% limit-down; 11/05 = 9.5
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05"],
        [10.0, 9.01, 9.50],
    )}
    got = m.evaluate_exit(_inst(), m.StrategySpec(1, 1), bars, SESSIONS, end="20251110")
    assert got.sell_date == "20251105"
    assert got.sell_price == pytest.approx(9.50)
    assert got.reason == "n_expire"
    assert got.hold_sessions == 2


def test_v04_suspension_postpones_n_expire():
    """N=2 target day 11/05 has no K → postpone to 11/06 first bar."""
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-06"],
        [10.0, 10.1, 10.4],
    )}
    got = m.evaluate_exit(_inst(), m.StrategySpec(1, 2), bars, SESSIONS, end="20251110")
    assert got.sell_date == "20251106"
    assert got.sell_price == pytest.approx(10.4)
    assert got.reason == "n_expire"
    assert got.hold_sessions == 3  # market sessions buy→sell


def test_v05_take_profit_before_n():
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05"],
        [10.0, 10.25, 10.0],  # +2.5% on T+1
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(2, 5, x=2.0, y=5.0), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "take_profit"
    assert got.sell_date == "20251104"
    assert got.sell_price == pytest.approx(10.25)


def test_v06_stop_loss_before_n():
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05"],
        [10.0, 9.70, 10.0],  # −3%
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(2, 5, x=10.0, y=2.0), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "stop_loss"
    assert got.sell_date == "20251104"
    assert got.sell_price == pytest.approx(9.70)


def test_v07_trailing_buy_day_peak_no_trigger():
    """Buy-day high lifts peak; T+1 mild dip vs buy but not vs peak → no trail yet."""
    # buy close 10; peak seeds 10. On 11/04 close 10.5 → peak=10.5; 10.5 < 10.5*0.95? no
    # On 11/05 close 9.9 → peak stays 10.5; 9.9 < 10.5*0.95=9.975 → trail
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05"],
        [10.0, 10.5, 9.9],
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(3, 10, y=5.0), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "trailing"
    assert got.sell_date == "20251105"
    assert got.sell_price == pytest.approx(9.9)


def test_v08_trailing_does_not_fire_on_new_high_day():
    """Same-day new high cannot trail (peak updated first)."""
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"],
        [10.0, 11.0, 12.0, 11.5],
    )}
    # Y=5%: 11.5 < 12*0.95=11.4? 11.5 > 11.4 → no trail on 11/06
    # N=5 → continue to mark or later
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(3, 5, y=5.0), bars, SESSIONS, end="20251110"
    )
    # 11/10 is N=5; need bar — add via frame extending... sessions N=5 is 20251110
    # frame has no 11/10 → mark at 11/06
    assert got.reason == "mark_end"
    assert got.sell_date == "20251106"
    assert got.is_trade is False


def test_v09_trailing_n_expire_with_bars():
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07", "2025-11-10"],
        [10.0, 10.2, 10.3, 10.4, 10.5, 10.6],
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(3, 5, y=15.0), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "n_expire"
    assert got.sell_date == "20251110"
    assert got.hold_sessions == 5


def test_v10_early_bar_stop_marks_last_close():
    """Bars end before window end → freeze at last close (Q33), no trade."""
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04"],
        [10.0, 10.2],
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(1, 20), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "mark_end"
    assert got.sell_date == "20251104"
    assert got.is_trade is False
    assert got.return_pct == pytest.approx(_ret(10.0, 10.2, trade=False))


def test_v11_anchor_hold_end_marks_without_trade():
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-10"],
        [10.0, 11.0, 12.0],
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(0, None), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "mark_end"
    assert got.sell_date == "20251110"
    assert got.sell_price == pytest.approx(12.0)
    assert got.is_trade is False


def test_v12_tp_and_n_same_day_prefers_tp():
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04"],
        [10.0, 10.30],  # +3%
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(2, 1, x=2.0, y=5.0), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "take_profit"
    assert got.sell_date == "20251104"


def test_v13_limit_down_blocks_take_profit():
    """Would-be TP day is limit-down vs prior bar → postpone; next day sells on N."""
    # 11/03 buy 10; 11/04 close 9.01 limit-down (also would be SL); 11/05 = 10.5
    # Use wide TP/SL so only N=2 fires on 11/05... actually on 11/04 SL would trigger
    # but limit-down blocks. On 11/05 +5% TP triggers.
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05"],
        [10.0, 9.01, 10.50],
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(2, 5, x=2.0, y=2.0), bars, SESSIONS, end="20251110"
    )
    assert got.sell_date == "20251105"
    assert got.reason == "take_profit"
    assert got.sell_price == pytest.approx(10.50)


def test_v14_commission_roundtrip_hand_calc():
    """shares=100000 at buy=10; sell=11; ret = (11*0.999)/(10*1.001) - 1."""
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04"],
        [10.0, 11.0],
    )}
    got = m.evaluate_exit(_inst(10.0), m.StrategySpec(1, 1), bars, SESSIONS, end="20251110")
    shares = 100_000
    buy_cost = shares * 10.0 * 1.001
    proceeds = shares * 11.0 * 0.999
    expect = (proceeds - buy_cost) / buy_cost
    assert got.shares == shares
    assert got.return_pct == pytest.approx(expect)
    assert got.pnl == pytest.approx(proceeds - buy_cost)


def test_v15_halt_freezes_trailing_peak():
    """Halt day advances N but peak stays; resume day trails vs pre-halt peak."""
    # 11/03 buy 10; 11/04 close 11 peak=11; 11/05 no bar; 11/06 close 10.4
    # 10.4 < 11*0.95=10.45 → trail
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-06"],
        [10.0, 11.0, 10.4],
    )}
    got = m.evaluate_exit(
        _inst(), m.StrategySpec(3, 10, y=5.0), bars, SESSIONS, end="20251110"
    )
    assert got.reason == "trailing"
    assert got.sell_date == "20251106"
    assert got.sell_price == pytest.approx(10.4)


def test_matrix_shape():
    bars = {"600000.SH": _frame(
        ["2025-11-03", "2025-11-04", "2025-11-05"],
        [10.0, 10.2, 10.1],
    )}
    insts = [_inst(), m.Instance("600000.SH", "SYN", "20251103", 10.0, False, "limit_up")]
    specs = [m.StrategySpec(1, 1), m.StrategySpec(1, 2)]
    mat = m.evaluate_matrix(insts, specs, bars, SESSIONS, end="20251110")
    assert set(mat) == {"r1_n1", "r1_n2"}
    assert list(mat["r1_n1"]) == ["600000.SH|20251103"]
