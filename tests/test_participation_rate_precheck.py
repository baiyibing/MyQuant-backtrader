"""P2-B shell precheck: unit + completed-bucket; ≠δ5 certified ≠R4.

Data-free. Does not certify capacity. Does not change VolumeCap / simulate.
"""

from __future__ import annotations

import pytest

from backtest.research.ashare_volume_cap import BucketVolume
from backtest.research.csv_minute_volume import UNIT
from backtest.research.participation_rate_precheck import (
    precheck_cli_participation_rate,
    precheck_completed_bucket_samples,
    precheck_source_pin_unit,
)


def test_cli_none_is_noop():
    # Omitted / None arm: no raise, no domain inspection required.
    precheck_cli_participation_rate(None)
    precheck_cli_participation_rate(
        None, minute_source="qlib_1min", dividend_type="front",
        tail_window_buy=True, tail_volume_unit="lots",
    )


def test_cli_rate_requires_raw_lake_shares():
    precheck_cli_participation_rate(0.1)
    with pytest.raises(ValueError, match="raw lake minute volume in shares"):
        precheck_cli_participation_rate(0.1, minute_source="qlib_1min")
    with pytest.raises(ValueError, match="raw lake minute volume in shares"):
        precheck_cli_participation_rate(0.1, dividend_type="front")
    with pytest.raises(ValueError, match="shares, not tail volume lots"):
        precheck_cli_participation_rate(
            0.1, tail_window_buy=True, tail_volume_unit="lots",
        )


def test_cli_invalid_rate_fail_closed():
    with pytest.raises(ValueError, match="finite and in"):
        precheck_cli_participation_rate(1.5)
    with pytest.raises(ValueError, match="finite and in"):
        precheck_cli_participation_rate(float("nan"))


def test_source_pin_unit():
    precheck_source_pin_unit({"unit": UNIT, "transformations": []})
    with pytest.raises(ValueError, match="raw shares"):
        precheck_source_pin_unit({"unit": "lots", "transformations": []})
    with pytest.raises(ValueError, match="raw shares"):
        precheck_source_pin_unit({"unit": UNIT, "transformations": ["x100"]})


def test_completed_bucket_samples_ok_and_rejects_auction():
    ok = {
        ("600000.SH", "20251024", 571): BucketVolume(1000, 571, UNIT),
        ("600000.SH", "20251024", 900): BucketVolume(2000, 900, UNIT),
    }
    precheck_completed_bucket_samples(ok)
    bad_auction = {
        ("600000.SH", "20251024", 570): BucketVolume(1000, 570, UNIT),
    }
    with pytest.raises(ValueError, match="auction/open hm provides no capacity"):
        precheck_completed_bucket_samples(bad_auction)
    bad_unit = {
        ("600000.SH", "20251024", 571): BucketVolume(1000, 571, "lots"),
    }
    with pytest.raises(ValueError, match="BucketVolume.unit must be"):
        precheck_completed_bucket_samples(bad_unit)
    bad_hm = {
        ("600000.SH", "20251024", 700): BucketVolume(1000, 700, UNIT),
    }
    with pytest.raises(ValueError, match="out-of-session"):
        precheck_completed_bucket_samples(bad_hm)
