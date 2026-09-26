"""Cent-quantized lake prices must not relax coefficient or OHLC checks."""

from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
import pytest

from backtest.research import signal_price_domain as domain
from tests.test_signal_price_domain import (
    CODE,
    START,
    build,
    certified_build,
    exact_certificate,
    inputs,
)


@pytest.mark.parametrize("raw,factor,front", [
    ("10.00", "0.2003", "2.00"),
    ("5.00", "0.3010", "1.51"),
    ("2.00", "0.1234", "0.25"),
    ("1000.00", "1.000004", "1000.00"),
])
def test_price_comparison_accepts_unrounded_model_against_stored_cents(raw, factor, front):
    assert domain._same_price(Decimal(raw) * Decimal(factor), Decimal(front))


@pytest.mark.parametrize("price", ["2.00", "10.00", "1000.00"])
@pytest.mark.parametrize("gap", ["0.01", "-0.01", "0.99", "-0.99"])
def test_one_cent_or_more_is_rejected_at_every_price_level(price, gap):
    assert not domain._same_price(Decimal(price), Decimal(price) + Decimal(gap))


def test_price_comparison_has_only_tiny_float_storage_slack():
    assert domain._same_price("1.505", 1.5100000000000002)
    assert not domain._same_price("1.505", "1.51000001")


def _rounded_front(raw, factor):
    result = raw.copy(deep=True)
    for field in domain.OHLC:
        result[field] = [float((Decimal(str(value)) * Decimal(factor)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)) for value in raw[field]]
    return result


def test_automatic_transform_intersects_all_days_and_fields_for_rounded_low_prices():
    dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    raw = pd.DataFrame({"open": [5., 5.1, 4.9], "high": [8., 7., 7.9],
                        "low": [3., 2.99, 3.1], "close": [6., 6.2, 6.1]}, index=dates)
    front = _rounded_front(raw, "0.3010")
    transforms = domain._automatic_transforms({CODE: front}, {CODE: raw}, START)
    assert len({row["A"] for row in transforms.values()}) == 1
    domain._validate_pair_math({CODE: front}, {CODE: raw}, transforms)
    # The first rounded open's own ratio cannot explain its high within half a tick.
    own_open_ratio = Decimal(str(front.iloc[0]["open"])) / Decimal(str(raw.iloc[0]["open"]))
    assert not domain._same_price(own_open_ratio * Decimal("8"), front.iloc[0]["high"])


@pytest.mark.parametrize("price,last_front", [(2., 1.98), (1000., 999.97)])
def test_automatic_transform_rejects_real_ratio_changes_even_at_high_prices(price, last_front):
    dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    raw = pd.DataFrame({field: [price] * 3 for field in domain.OHLC}, index=dates)
    raw.loc[dates[0], ["high", "low"]] = [price + .02, price - .02]
    front = raw.copy(deep=True)
    front.loc[dates[-1], :] = last_front
    with pytest.raises(domain.PriceDomainError, match="changing ratio requires an explicit price transform file"):
        domain._automatic_transforms({CODE: front}, {CODE: raw}, START)


def test_automatic_transform_preserves_an_exact_common_ratio():
    front, raw, _ = inputs()
    transforms = domain._automatic_transforms(front, raw, START)
    assert {row["A"] for row in transforms.values()} == {Decimal("0.5")}


@pytest.mark.parametrize("field,value,message", [
    ("high", 9.999, "high below open/close"),
    ("low", 10.001, "low above open/close"),
])
def test_intra_bar_range_errors_are_not_excused_by_price_rounding(field, value, message):
    _, raw, _ = inputs(flat=True)
    raw[CODE].loc[raw[CODE].index[0], field] = value
    with pytest.raises(domain.PriceDomainError, match=message):
        domain._validate_frame(raw[CODE], code=CODE, domain="raw")


def test_informative_range_uses_strict_ohlc_tolerance():
    _, raw, _ = inputs(flat=True)
    raw[CODE].loc[raw[CODE].index[0], "high"] = 10.001
    front = {CODE: raw[CODE] * .5}
    transforms = domain._automatic_transforms(front, raw, START)
    domain._validate_pair_math(front, raw, transforms)


@pytest.mark.parametrize("field", ["A", "B"])
def test_common_anchor_coefficients_reject_a_one_millionth_mismatch(field):
    _, raw, minute = inputs()
    front, transforms, provenance, evidence = exact_certificate(raw)
    transforms[-1][field] = str(Decimal(transforms[-1][field]) + Decimal("0.000001"))
    with pytest.raises(domain.PriceDomainError, match="common anchor coefficients do not cancel"):
        certified_build(front, raw, minute, transforms, provenance, evidence)


@pytest.mark.parametrize("field", [None, "from_A", "from_B", "to_A", "to_B", "reference_raw"])
def test_event_coefficients_are_strict_and_event_reference_uses_price_space(field):
    _, raw, minute = inputs()
    front, transforms, provenance, evidence = exact_certificate(raw)
    transforms[-1]["A"] = ".8"
    evidence["base_transforms"][-1]["A"] = "1"
    for column in domain.OHLC:
        front[CODE].loc[raw[CODE].index[-1], column] = 8.3
        evidence["base_front"][-1][column] = 10.
    event = {"code": CODE, "session": START, "source": "confirmed-vendor-event",
             "confirmed": True, "from_A": ".5", "from_B": "0", "to_A": "1",
             "to_B": "0", "reference_raw": "5"}
    evidence["events"] = [event]
    if field is None:
        certified_build(front, raw, minute, transforms, provenance, evidence)
    else:
        delta = Decimal(".01") if field == "reference_raw" else Decimal(".000001")
        event[field] = str(Decimal(event[field]) + delta)
        message = ("confirmed event reference differs" if field == "reference_raw"
                   else "event transition coefficients differ")
        with pytest.raises(domain.PriceDomainError, match=message):
            certified_build(front, raw, minute, transforms, provenance, evidence)


@pytest.mark.parametrize("reference,valid", [("5.00", True), ("5.01", True), ("5.02", False)])
def test_event_reference_compares_unrounded_model_at_a_half_cent_boundary(reference, valid):
    _, raw, _ = inputs()
    front, transforms, provenance, evidence = exact_certificate(raw)
    # Both stored front domains remain cent-quantized. The active inverse is
    # (4.30 - .296) / .8 = 5.005, so either adjacent cent is within half a tick.
    evidence["common_anchor"]["shift"] = ".296"
    for transform in transforms:
        transform["B"] = ".296"
    transforms[-1]["A"] = ".8"
    evidence["base_transforms"][-1]["A"] = "1"
    for field in domain.OHLC:
        front[CODE].loc[raw[CODE].index[-1], field] = 8.3
        evidence["base_front"][-1][field] = 10.
    evidence["events"] = [{"code": CODE, "session": START, "source": "confirmed-vendor-event",
                           "confirmed": True, "from_A": ".5", "from_B": "0", "to_A": "1",
                           "to_B": "0", "reference_raw": reference}]
    args = (front, raw, domain._transform_map(transforms), provenance, evidence, "snapshot-test")
    if valid:
        domain._validate_certificate(*args)
    else:
        with pytest.raises(domain.PriceDomainError, match="confirmed event reference differs"):
            domain._validate_certificate(*args)


@pytest.mark.parametrize("target", ["front", "base"])
@pytest.mark.parametrize("gap,valid", [(".004", True), (".01", False)])
def test_common_anchor_price_checks_allow_only_half_a_tick(target, gap, valid):
    _, raw, _ = inputs()
    front, transforms, provenance, evidence = exact_certificate(raw)
    gap = Decimal(gap)
    if target == "base":
        evidence["base_front"][-1]["close"] = float(Decimal("5") + gap)
        front[CODE].loc[raw[CODE].index[-1], "close"] = float(Decimal("4.3") + gap * Decimal(".8"))
    else:
        front[CODE].loc[raw[CODE].index[-1], "close"] = float(Decimal("4.3") + gap)
    # Isolate certificate price checks from the separate paired-bar/decision checks.
    args = (front, raw, domain._transform_map(transforms), provenance, evidence, "snapshot-test")
    if valid:
        domain._validate_certificate(*args)
    else:
        message = ("base transform does not explain raw bars" if target == "base"
                   else "front history is not a common affine anchor transform")
        with pytest.raises(domain.PriceDomainError, match=message):
            domain._validate_certificate(*args)


@pytest.mark.parametrize("factor,front_close,pit_close,valid", [
    (".2", "2.00", "10.02", True),
    ("2", "20.01", "10.00", False),
])
def test_pit_reconstruction_checks_front_space_so_inverse_error_scales_correctly(
        factor, front_close, pit_close, valid):
    dates = pd.to_datetime(["2025-01-03", "2025-01-06"])
    front = {CODE: pd.DataFrame({field: [float(front_close)] * 2 for field in domain.OHLC}, index=dates)}
    transforms = {(CODE, day.strftime("%Y%m%d")): {"A": Decimal(factor), "B": Decimal(0)}
                  for day in dates}
    views = [{"code": CODE, "session": day.strftime("%Y%m%d"),
              "reference_available_at": day.isoformat() + "+08:00", "source": "vendor-PIT",
              "history": [] if i == 0 else [{"date": "20250103", "close": pit_close}]}
             for i, day in enumerate(dates)]
    provenance = {"kind": "pit", "algorithm": "independent_daily_view", "anchor_version": "v1"}
    evidence = {"kind": "pit", "source_snapshot_id": "test", "views": views}
    args = (front, {}, transforms, provenance, evidence, "test")
    if valid:
        assert domain._validate_certificate(*args) == "hash_bound_independent_pit_views"
    else:
        with pytest.raises(domain.PriceDomainError, match="independent PIT reconstruction differs"):
            domain._validate_certificate(*args)


@pytest.mark.parametrize("raw_close,front_close,factor,valid", [
    (5., 1.51, .3010, True),
    (10., 2., .2003, True),
    (1000., 1000., 1.000004, True),
    (1000., 1000., 1.00001, False),
])
def test_factor_comparison_uses_unrounded_factor_times_raw_in_price_space(
        tmp_path, monkeypatch, raw_close, front_close, factor, valid):
    dates = pd.to_datetime(["2025-01-06"])
    raw = {CODE: pd.DataFrame({"close": [raw_close]}, index=dates)}
    front = {CODE: pd.DataFrame({"close": [front_close]}, index=dates)}
    path = tmp_path / "adj_factor.parquet"
    pd.DataFrame({"date": [20250106], "stock_code": [CODE], "close_none": [raw_close],
                  "close_front": [front_close], "cumulative_adj_factor": [factor]}).to_parquet(path, index=False)
    monkeypatch.setattr(domain, "resolve_source_parquet", lambda name: tmp_path / name)
    recheck = {}
    if valid:
        assert domain._validate_optional_factor(front, raw, recheck)["sha256"] == domain.file_sha256(path)
        assert path in recheck
    else:
        with pytest.raises(domain.PriceDomainError, match="factor file does not match real paired closes"):
            domain._validate_optional_factor(front, raw, recheck)


@pytest.mark.parametrize("field", ["close_none", "close_front"])
def test_factor_stored_close_rejects_a_one_cent_gap_at_high_prices(tmp_path, monkeypatch, field):
    dates = pd.to_datetime(["2025-01-06"])
    frames = {CODE: pd.DataFrame({"close": [1000.]}, index=dates)}
    row = {"date": [20250106], "stock_code": [CODE], "close_none": [1000.],
           "close_front": [1000.], "cumulative_adj_factor": [1.]}
    row[field] = [1000.01]
    pd.DataFrame(row).to_parquet(tmp_path / "adj_factor.parquet", index=False)
    monkeypatch.setattr(domain, "resolve_source_parquet", lambda name: tmp_path / name)
    with pytest.raises(domain.PriceDomainError, match="factor file does not match real paired closes"):
        domain._validate_optional_factor(frames, frames, {})


def test_metadata_describes_price_and_coefficient_tolerances_separately():
    front, raw, minute = inputs()
    metadata = build(front, raw, minute).metadata
    assert metadata["validation_version"] == "s12-price-domain-v3"
    assert metadata["input_price_tolerance"] == "0.005+1e-9"
    assert metadata["input_price_tolerance_mode"] == "absolute_half_tick_price_space"
    assert metadata["input_coefficient_tolerance"] == "1e-10"
    assert "input_absolute_tolerance" not in metadata
    assert "input_tolerance_mode" not in metadata
