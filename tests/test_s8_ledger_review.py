"""Review regressions for independent-position rejection diagnostics."""

from __future__ import annotations

import pytest

from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.csv_ledger import _sell, execute_buy, exit_positions
from tests.test_s8_independent_positions import BOOKS, CODE, DAYS, _ds, _pid, _state


@pytest.mark.parametrize("strategy", (*BOOKS, "version8_1", "version1"))
@pytest.mark.parametrize("side", ("BUY", "SELL"))
@pytest.mark.parametrize("missing_volume", (False, True))
def test_capacity_skip_identifies_only_target_book_positions(strategy, side, missing_volume):
    st, _, _ = _state(strategy)
    # The first group deliberately has the same code: a rejected second group
    # must identify its own source signal rather than whichever lot is oldest.
    assert execute_buy(st, CODE, 10., 1_000_000, 0, DAYS[0], position_id=_pid(0))
    if side == "SELL":
        assert execute_buy(st, CODE, 10., 1_000_000, 1, DAYS[1], position_id=_pid(1))
    volumes = {} if missing_volume else {
        (CODE, _ds(2), 895): BucketVolume(0, 895, "raw_shares_incremental"),
    }
    st.volume_cap = VolumeCap(1, volumes)
    if side == "BUY":
        assert not execute_buy(
            st, CODE, 10., 1_000_000, 2, DAYS[2], position_id=_pid(1), bucket_id=895,
        )
    else:
        pos = exit_positions(st, CODE, day_i=2)[1]
        assert _sell(st, CODE, pos, 10., DAYS[2], "stop_loss:test", day_i=2, bucket_id=895) == 0
    skip = st.trades[-1]
    expected = {
        "date": _ds(2), "code": CODE, "side": "SKIP", "price": 10.,
        "shares": 0, "notional": 0., "commission": 0.,
        "reason": (
            "skip_volume_unavailable:missing_or_untyped"
            if missing_volume else "skip_volume_cap:zero_or_exhausted"
        ),
        "bucket": 895, "session_phase": "", "price_rule": "",
    }
    if strategy in BOOKS:
        expected.update(position_id=_pid(1), entry_signal_date=_ds(1))
    assert skip == expected


@pytest.mark.parametrize("strategy", BOOKS)
@pytest.mark.parametrize("explicit_signal_date", (False, True))
def test_execute_buy_rejects_position_id_without_signal_separator(strategy, explicit_signal_date):
    st, _, _ = _state(strategy)
    before = st.cash
    kwargs = {"entry_signal_date": _ds(0)} if explicit_signal_date else {}
    with pytest.raises(ValueError) as exc:
        execute_buy(st, CODE, 10., 1_000_000, 0, DAYS[0], position_id=CODE, **kwargs)
    assert "position_id" in str(exc.value)
    assert "@" in str(exc.value)
    assert CODE in str(exc.value)
    assert st.cash == before
    assert not st.trades
    assert not st.positions

