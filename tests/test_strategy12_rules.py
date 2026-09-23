"""Human cuts latch=A / residual=2 and pure MA/lot boundaries."""

from types import SimpleNamespace

import pytest

from backtest.research import strategy12_rules as r


@pytest.mark.parametrize("count", range(5))
def test_ma5_warmup(count):
    assert r.de_risk_signal(9, [10] * count) is None
    assert r.reclaim_signal(10, [10] * count) is None


@pytest.mark.parametrize("count", range(10))
def test_ma10_warmup(count):
    assert r.reclaim_signal(10, [10] * count, channel="stopped") is None


@pytest.mark.parametrize("px", [0, -1, float("nan")])
def test_invalid_price(px):
    assert r.de_risk_signal(px, [10] * 10) is None
    assert r.reclaim_signal(px, [10] * 10) is None


def test_ma_boundaries_and_stop_priority():
    mem = r.CodeMemory()
    lots = [r.SellLot(0, 1000, 1000)]
    assert r.de_risk_signal(10, [10] * 10) is None
    assert r.reclaim_signal(10, [10] * 10) == r.RECLAIM5
    assert r.exit_plan("x", 9, None, [10] * 10, lots, memory=mem) == (r.REDUCE, 500)
    assert r.exit_plan("x", 8.99, None, [10] * 10, lots, memory=mem) == (r.STOP, 1000)


def test_t1_sellable_base_rounding_order_and_anchor():
    lots = [r.SellLot(0, 250, 250), r.SellLot(1, 300, 300),
            r.SellLot(2, 200, 200, True), r.SellLot(3, 900, 0)]
    assert r.exit_plan("x", 9.9, None, [10] * 10, lots, memory=r.CodeMemory()) == (r.REDUCE, 300)
    assert r.allocate_exit(lots, 300, keep_anchor=True) == [(2, 200), (1, 100)]
    assert r.allocate_exit(lots, 1000, keep_anchor=True) == [(2, 200), (1, 300), (0, 150)]
    assert r.exit_plan("x", 9.9, None, [10] * 10, [r.SellLot(0, 100, 100)], memory=r.CodeMemory()) is None


def test_clamp_exit_keeps_the_planned_lots_and_ignores_post_plan_adds():
    planned = r.allocate_exit([r.SellLot(0, 1000, 1000)], 500, keep_anchor=True)
    assert planned == [(0, 500)]
    later = [r.SellLot(0, 1000, 1000), r.SellLot(1, 1000, 1000), r.SellLot(2, 300, 300, True)]
    assert r.clamp_exit(later, planned, keep_anchor=True) == [(0, 500)]
    assert r.clamp_exit([r.SellLot(0, 200, 200)], planned, keep_anchor=True) == [(0, 100)]
    assert r.clamp_exit([r.SellLot(1, 1000, 1000)], planned, keep_anchor=True) == []
    mem = r.Memory()
    mem.sold(0)
    assert mem == r.Memory()


@pytest.mark.parametrize("lot_id,shares,sellable,keep_anchor,expected", [
    (0, 200, 200, True, [(0, 100)]),
    (0, 200, 50, True, [(0, 50)]),
    (0, 100, 100, True, []),
    (0, 50, 50, True, []),
    (0, 200, 200, False, [(0, 200)]),
    (1, 200, 200, True, [(1, 200)]),
])
def test_clamp_exit_reapplies_derisk_anchor_but_stop_and_other_lots_can_clear(
        lot_id, shares, sellable, keep_anchor, expected):
    assert r.clamp_exit([r.SellLot(lot_id, shares, sellable)], [(lot_id, 500)],
                        keep_anchor=keep_anchor) == expected


@pytest.mark.parametrize("channel", ["reduced", "stopped"])
def test_partial_buyback_preserves_residual_rearms_and_merges_next_round(channel):
    code = r.CodeMemory()
    mem = getattr(code, channel)
    mem.sold(150)
    assert mem.latched
    assert r.buyback_plan(10, [10] * 10, mem, channel=channel) == 100
    mem.reclaimed(100)
    assert (mem.shares, mem.latched) == (50, False)
    mem.sold(250)
    assert mem.shares == 300
    assert r.buyback_plan(10, [10] * 10, mem, channel=channel) == 300


@pytest.mark.parametrize("channel", ["reduced", "stopped"])
def test_sub100_no_buy_qualified_reclaim_preserves_and_rearms(channel):
    mem = r.Memory()
    mem.sold(50)
    assert r.reclaim_signal(10, [10] * 10, channel=channel)
    assert r.buyback_plan(10, [10] * 10, mem, channel=channel) == 0
    mem.reclaimed()
    assert (mem.shares, mem.latched) == (50, False)


def test_cycle_only_same_day_rederisk_and_partial_fill_stays_pending():
    mem = r.CodeMemory()
    mem.reduced.sold(500)
    lots = [r.SellLot(0, 500, 500), r.SellLot(1, 500, 0)]
    assert r.exit_plan("x", 9.9, "20251104", [10] * 10, lots, memory=mem) is None
    mem.reduced.reclaimed(200)
    assert mem.reduced.latched  # Still a whole-lot buyback outstanding.
    mem.reduced.reclaimed(300)
    assert r.exit_plan("x", 9.9, "20251104", [10] * 10, lots, memory=mem) == (r.REDUCE, 200)


def test_channels_independent_and_fresh_buy_clears_both():
    mem = r.CodeMemory(r.Memory(500, True), r.Memory(800, True), steps=2)
    mem.reduced.reclaimed(500)
    assert mem.stopped.shares == 800
    mem.fresh_buy()
    assert mem.reduced == mem.stopped == r.Memory()
    assert mem.steps == 2


def test_exdiv_explicit_rounding_and_cash_only_unchanged():
    mem = r.CodeMemory(r.Memory(150, True), r.Memory(250, True))
    assert r.scale_memory(mem, 1) == {}
    assert mem.reduced.shares == 150
    assert r.scale_memory(mem, "1.5") == {"reduced": 25, "stopped": 75}
    assert (mem.reduced.shares, mem.stopped.shares) == (200, 300)


def test_step_count_does_not_depend_on_surviving_step_lots():
    mem = r.CodeMemory(steps=1)
    lots = [SimpleNamespace(lot_id=0, cost=10)]
    assert not r.step_add_due(lots, 12, memory=mem)
    assert r.step_add_due(lots, 14, memory=mem)


def test_help_pins_human_cuts():
    for text in (
        "latch=A",
        "residual=2",
        "无每日锁",
        "memory<100",
        "reduced/stopped",
        "禁止等归零",
        "分钟成交域默认 none",
        "front",
        "禁止静默双重调整",
        "px==open",
        "5+",
        "最低佣金",
    ):
        assert text in r.HELP_LOCK
