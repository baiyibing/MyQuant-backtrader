"""Wind st_daily membership: positive rows exclude, missing rows pass."""

from __future__ import annotations

import pandas as pd

from backtest.research.st_status import drop_st_names, is_st_on, membership_from_frame


def _table():
    frame = pd.DataFrame(
        {
            "trade_date": ["2026-06-10", "2026-06-11"],
            "code": ["600180.SH", "000001.SZ"],
            "is_st": [True, False],
        }
    )
    return membership_from_frame(frame)


def test_positive_row_is_st_and_missing_row_is_not():
    table = _table()
    assert is_st_on("600180", "20260610", table) is True
    assert is_st_on("600180.SH", "2026-06-11", table) is False
    assert is_st_on("605499", "20260610", table) is False


def test_drop_st_names_keeps_days_that_still_have_a_name():
    table = _table()
    days = {"20260610": ["600180.SH", "605499.SH"], "20260611": ["000001.SZ"]}
    kept, dropped = drop_st_names(days, table)
    assert dropped == 1
    assert kept["20260610"] == ["605499.SH"]
    assert kept["20260611"] == ["000001.SZ"]
