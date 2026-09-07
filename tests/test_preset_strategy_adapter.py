# -*- coding: utf-8 -*-
"""P0-1 PR-A: preset sell adapter context parity, wiring smoke, cross-day scratch."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from backtest.preset_strategy_adapter import (
    PresetSellScratch,
    PresetStrategyAdapter,
    SellContextAtoms,
    build_live_wiring_equivalent_context,
    context_from_atoms,
    resolve_use_preset_sell_adapter,
    runtime_atoms_from_backtest,
)
from trade_decision.presets import SellPresetContext, evaluate_sell_preset


def _atoms(**overrides) -> SellContextAtoms:
    base = dict(
        stock_code="000001.SZ",
        cost_price=10.0,
        current_price=10.5,
        holding_high=11.0,
        hold_days=2,
        is_limit_up=False,
        now_local=datetime(2026, 6, 18, 10, 30, 0),
        indicators=None,
        reserved_for_limit_up=False,
        prev_close=9.8,
        open_price=10.1,
    )
    base.update(overrides)
    return SellContextAtoms(**base)


def test_adapter_context_parity_matches_live_wiring_equivalent() -> None:
    """Same mock atoms -> adapter canonical ctx == live wiring base-field ctx."""
    atoms = _atoms()
    adapter_ctx = context_from_atoms(atoms)
    wiring_ctx = build_live_wiring_equivalent_context(atoms)
    assert adapter_ctx == wiring_ctx


def test_adapter_context_parity_holding_high_tracks_price_like_wiring() -> None:
    atoms = _atoms(current_price=12.0, holding_high=11.0)
    wiring_ctx = build_live_wiring_equivalent_context(atoms)
    assert wiring_ctx.holding_high == 12.0


def test_runtime_atoms_use_scratch_not_status_mutation() -> None:
    scratch = PresetSellScratch()
    status = SimpleNamespace(
        stock_code="600000.SH",
        cost_price=10.0,
        holding_high=10.5,
        hold_days=1,
    )
    dt = datetime(2026, 6, 18, 9, 35, 0)
    atoms = runtime_atoms_from_backtest(
        status=status,
        current_datetime=dt,
        current_price=10.2,
        is_limit_up=True,
        indicators=None,
        scratch=scratch,
    )
    assert atoms.reserved_for_limit_up is False
    assert not hasattr(status, "_reserved_for_limit_up")


def test_cross_day_scratch_carries_reserved_then_clears_on_open_board() -> None:
    """reserved_for_limit_up carries from day1 to day2; cleared after open-board sell."""
    scratch = PresetSellScratch()
    stock = "000001.SZ"
    day2 = datetime(2026, 6, 19, 10, 0, 0)

    scratch.set(stock, True)
    assert scratch.get(stock) is True

    status = SimpleNamespace(
        stock_code=stock,
        cost_price=10.0,
        holding_high=11.0,
        hold_days=1,
    )
    atoms_day2 = runtime_atoms_from_backtest(
        status=status,
        current_datetime=day2,
        current_price=10.8,
        is_limit_up=False,
        indicators=None,
        scratch=scratch,
    )
    assert atoms_day2.reserved_for_limit_up is True

    adapter = PresetStrategyAdapter("version3")
    adapter._scratch = scratch
    sell, _ = adapter.should_sell(status, day2, 10.8, is_limit_up=False)
    assert sell is True
    assert scratch.get(stock) is False


def test_preset_adapter_wiring_smoke_version3_limit_up_reserve_cross_day() -> None:
    """Smoke: v3 reserve window sets scratch; next day starts clean; open board sells."""
    adapter = PresetStrategyAdapter("version3")
    status = SimpleNamespace(
        stock_code="000001.SZ",
        cost_price=10.0,
        holding_high=11.0,
        hold_days=1,
    )

    day1_reserve = datetime(2026, 6, 18, 9, 35, 0)
    sell1, reason1 = adapter.should_sell(status, day1_reserve, 11.0, is_limit_up=True)
    assert sell1 is False
    assert reason1 is None
    assert adapter._scratch.get("000001.SZ") is True

    day2_open_board = datetime(2026, 6, 19, 10, 0, 0)
    sell2, reason2 = adapter.should_sell(status, day2_open_board, 10.8, is_limit_up=False)
    assert sell2 is True
    assert reason2 is not None
    assert adapter._scratch.get("000001.SZ") is False


def test_preset_adapter_delegates_to_evaluate_sell_preset_version1_stop_loss() -> None:
    adapter = PresetStrategyAdapter("version1")
    status = SimpleNamespace(
        stock_code="000001.SZ",
        cost_price=10.0,
        holding_high=10.0,
        hold_days=1,
    )
    should_sell, reason = adapter.should_sell(
        status,
        datetime(2026, 6, 18, 10, 0, 0),
        9.7,
        is_limit_up=False,
    )
    assert should_sell is True
    assert reason is not None
    assert reason.startswith("stop_loss")

    ctx = SellPresetContext(
        cost_price=10.0,
        current_price=9.7,
        holding_high=10.0,
        hold_days=1,
        is_limit_up=False,
        now_local=datetime(2026, 6, 18, 10, 0, 0),
    )
    expected = evaluate_sell_preset("version1", adapter.params, ctx)
    assert should_sell is expected.should_sell


@pytest.mark.parametrize(
    ("env_val", "explicit", "expected"),
    [
        ("1", None, True),
        ("true", None, True),
        ("0", None, False),
        (None, True, True),
        (None, False, False),
    ],
)
def test_resolve_use_preset_sell_adapter(
    monkeypatch: pytest.MonkeyPatch,
    env_val: str | None,
    explicit: bool | None,
    expected: bool,
) -> None:
    if env_val is None:
        monkeypatch.delenv("BACKTEST_USE_PRESET_SELL_ADAPTER", raising=False)
    else:
        monkeypatch.setenv("BACKTEST_USE_PRESET_SELL_ADAPTER", env_val)
    assert resolve_use_preset_sell_adapter(explicit) is expected


def test_adapter_should_buy_delegates_to_legacy_not_allow_buy_by_preset() -> None:
    """F1: adapter should_buy 委托 legacy 实例（Phase 1 只卖侧单源），不切 allow_buy_by_preset。

    legacy: version1/2/3/5 should_buy 总 True（买由选股池控制）；version4 依赖 MA 指标。
    """
    status = SimpleNamespace(stock_code="000001.SZ")
    dt = datetime(2026, 6, 18, 10, 0, 0)

    # version1 legacy should_buy 总 True（ProfitStrategy.py:139-141）
    adapter_v1 = PresetStrategyAdapter("version1")
    buy1, _ = adapter_v1.should_buy(status, dt, 10.0)
    assert buy1 is True

    # version4 legacy should_buy: 无 indicators → False（Strategy4 :282-283）
    adapter_v4 = PresetStrategyAdapter("version4")
    buy4_no_ind, _ = adapter_v4.should_buy(status, dt, 10.0, indicators=None)
    assert buy4_no_ind is False
