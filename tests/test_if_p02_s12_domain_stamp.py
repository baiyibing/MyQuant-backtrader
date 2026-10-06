from __future__ import annotations

import pytest

from backtest.research import csv_daily_backtest as daily
from scripts.research.audit_s12_price_domain import fixture, replay
from tests.test_strategy12_engine import bars_for


PROFILE_STATS = {
    "rule_profile",
    "rule_profile_revision",
    "valuation_price_domain",
    "buy_cost_rate",
    "sell_cost_rate",
    "min_cost",
    "stamp_duty_total",
    "transfer_fee_total",
}


def _assert_profile_stamp_only(omitted, legacy, industry, expected_domain: str) -> None:
    assert omitted.stats == legacy.stats
    assert "valuation_price_domain" not in omitted.stats
    assert "valuation_price_domain" not in legacy.stats
    assert industry.stats["valuation_price_domain"] == expected_domain
    assert {
        key: value for key, value in industry.stats.items() if key not in PROFILE_STATS
    } == {key: value for key, value in legacy.stats.items() if key not in PROFILE_STATS}
    assert omitted.trades == legacy.trades
    assert omitted.equity_curve == legacy.equity_curve


def test_daily_s12_industry_stamps_front_valuation_without_legacy_stats_change():
    _minutes, front_daily, _days = bars_for([[(895, 10.0)]])
    args = (
        front_daily,
        {"20251103": [next(iter(front_daily))]},
        "20251103",
        "20251103",
    )
    omitted = daily.simulate(*args, strategy="version12")
    legacy = daily.simulate(*args, strategy="version12", rule_profile="legacy")
    industry = daily.simulate(*args, strategy="version12", rule_profile="industry")

    _assert_profile_stamp_only(omitted, legacy, industry, "front")


@pytest.mark.parametrize(
    ("x01_enabled", "expected_domain"),
    [(False, "front"), (True, "none")],
    ids=["minute-x01-off", "minute-x01-on"],
)
def test_minute_s12_industry_stamps_actual_valuation_domain_only(
    x01_enabled: bool, expected_domain: str
):
    data = fixture()
    omitted, _ = replay(*data, enabled=x01_enabled)
    legacy, _ = replay(*data, enabled=x01_enabled, rule_profile="legacy")
    industry, _ = replay(*data, enabled=x01_enabled, rule_profile="industry")

    _assert_profile_stamp_only(omitted, legacy, industry, expected_domain)
