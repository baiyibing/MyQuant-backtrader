"""X-01 source, reconstruction and pre-trade failure boundaries."""

import json
from copy import deepcopy
from decimal import Decimal

import pandas as pd
import pytest
from backtest.research import signal_price_domain as domain

CODE = "000001.SZ"
START = "20250106"
PROVENANCE = {"kind": "observed_constant_proportional",
              "algorithm": "constant_paired_ohlc", "anchor_version": "test-v1"}


def transformed(raw, factor=.5, offset=0):
    a, b = Decimal(str(factor)), Decimal(str(offset))
    result = {}
    for code, frame in raw.items():
        out = frame.copy(deep=True)
        for column in domain.OHLC:
            out[column] = [float(a * Decimal(str(value)) + b) for value in frame[column]]
        result[code] = out
    return result


def inputs(*, flat=False):
    days = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    raw = {CODE: pd.DataFrame({"open": [10., 10., 10.],
                               "high": [10. if flat else 11., 10., 10.],
                               "low": [10. if flat else 9., 10., 10.],
                               "close": [10., 10., 10.]}, index=days)}
    minute = {CODE: pd.DataFrame({key: [10., 10.] for key in domain.OHLC},
                                index=pd.to_datetime(["2025-01-06 09:30", "2025-01-06 14:55"]))}
    return transformed(raw), raw, minute


def metadata(front, raw, minute, provenance=None):
    return domain.build_source_metadata(front, raw, minute, source_snapshot_id="snapshot-test",
                                         provenance=provenance or PROVENANCE)


def build(front, raw, minute, **kwargs):
    return domain.build_s12_price_context(front, raw, minute_bars=minute,
                                          metadata=metadata(front, raw, minute), start=START, **kwargs)


def pit_certificate(front, raw):
    transforms, views = {}, []
    for day in raw[CODE].index:
        session = day.strftime("%Y%m%d")
        transforms[(CODE, session)] = {"A": ".5", "B": "0"}
        history = [{"date": previous.strftime("%Y%m%d"), "close": float(value * 2)}
                   for previous, value in front[CODE].loc[front[CODE].index < day, "close"].items()]
        views.append({"code": CODE, "session": session,
                      "reference_available_at": day.isoformat() + "+08:00",
                      "source": "independent-frozen-vendor-view", "history": history})
    provenance = {"kind": "pit", "algorithm": "independent_daily_view", "anchor_version": "v1"}
    evidence = {"kind": "pit", "source_snapshot_id": "snapshot-test", "views": views}
    return transforms, provenance, evidence


def certified_build(front, raw, minute, transforms, provenance, evidence):
    return domain.build_s12_price_context(
        front, raw, minute_bars=minute, metadata=metadata(front, raw, minute, provenance),
        transforms=transforms, start=START, evidence=evidence)


def test_automatic_proportional_path_requires_informative_prior_and_validates_all_ohlc():
    front, raw, minute = inputs()
    ctx = build(front, raw, minute)
    view = ctx.day_signal_view(CODE, START)
    assert view.previous_signal_closes_in_raw_domain == (10., 10.)
    assert view.prev_ref_unrounded == Decimal(10) and view.prev_ref_raw == 10.
    ctx.validate_simulation(minute, raw, {START: [CODE]}, START, START)
    assert ctx.metadata["pit_anchor_validation"] == "common_transform_only_full_pit_unverified"


@pytest.mark.parametrize("corruption", ["flat", "changing", "affine", "field_mismatch"])
def test_automatic_path_rejects_underdetermined_or_nonconstant_transform(corruption):
    front, raw, minute = inputs(flat=corruption == "flat")
    if corruption == "changing":
        front[CODE].iloc[-1] *= 1.01
    if corruption == "affine":
        front = transformed(raw, 1, -1)
    if corruption == "field_mismatch":
        front[CODE].iloc[0, front[CODE].columns.get_loc("high")] += .1
    with pytest.raises(domain.PriceDomainError):
        build(front, raw, minute)


def test_explicit_affine_coefficients_cannot_bypass_automatic_evidence():
    front, raw, minute = inputs(flat=True)
    front = transformed(raw, 1, -1)
    transforms = {(CODE, day.strftime("%Y%m%d")): {"A": 1, "B": -1}
                  for day in raw[CODE].index}
    with pytest.raises(domain.PriceDomainError, match="B=0 not identifiable"):
        build(front, raw, minute, transforms=transforms)


@pytest.mark.parametrize("mutation", ["missing_code", "missing_date", "duplicate_date", "nan", "zero",
                                    "missing_open", "wrong_hash", "missing_domain", "snapshot"])
def test_pair_and_identity_failures_happen_before_context_is_returned(mutation):
    front, raw, minute = inputs()
    declared = metadata(front, raw, minute)
    if mutation == "missing_code":
        front = {}
    elif mutation == "missing_date":
        front[CODE] = front[CODE].iloc[1:]
    elif mutation == "duplicate_date":
        front[CODE] = pd.concat([front[CODE].iloc[:1], front[CODE]])
    elif mutation == "nan":
        raw[CODE].iloc[-1, 0] = float("nan")
    elif mutation == "zero":
        raw[CODE].iloc[-1, 0] = 0
    elif mutation == "missing_open":
        front[CODE] = front[CODE].drop(columns="open")
    elif mutation == "wrong_hash":
        declared["source_hashes"]["front"][CODE] = "wrong"
    elif mutation == "missing_domain":
        declared.pop("raw_daily_domain")
    else:
        declared["source_snapshot_id"] = ""
    # Rebind identities for structural checks; wrong hashes remain deliberately wrong.
    if mutation in {"missing_date", "duplicate_date", "nan", "zero", "missing_open"}:
        declared = metadata(front, raw, minute)
    with pytest.raises(domain.PriceDomainError):
        domain.build_s12_price_context(front, raw, minute_bars=minute, metadata=declared, start=START)


@pytest.mark.parametrize("annotation,value", [("ymd", "20250107"), ("hm", 900)])
def test_caller_cannot_relabel_raw_minute_decision_time(annotation, value):
    front, raw, minute = inputs()
    minute[CODE][annotation] = value
    with pytest.raises(domain.PriceDomainError, match="disagrees with timestamp"):
        build(front, raw, minute)


def test_constructor_is_not_an_unvalidated_public_escape_hatch():
    front, raw, minute = inputs()
    with pytest.raises(domain.PriceDomainError, match="build_s12_price_context"):
        domain.S12PriceContext(front, raw, minute, {}, metadata(front, raw, minute))


def test_context_owns_inputs_and_metadata_and_returns_independent_raw_views():
    front, raw, minute = inputs()
    declared = metadata(front, raw, minute)
    ctx = domain.build_s12_price_context(front, raw, minute_bars=minute, metadata=declared, start=START)
    before = ctx.day_signal_view(CODE, START)
    front[CODE].iloc[:, :] = 99.
    raw[CODE].iloc[:, :] = 99.
    declared["source_hashes"]["raw"][CODE] = "mutated"
    exposed_raw = ctx.raw_daily
    exposed_raw[CODE].iloc[:, :] = 99.
    ctx.metadata["source_hashes"]["raw"][CODE] = "mutated-copy"
    assert ctx.day_signal_view(CODE, START) == before
    assert ctx.raw_daily[CODE].iloc[-1]["close"] == 10.
    ctx.validate_simulation(minute, ctx.raw_daily, {}, START, START)
    with pytest.raises(domain.PriceDomainError, match="hash mismatch"):
        ctx.validate_simulation(minute, raw, {}, START, START)


def test_simulation_rejects_front_in_raw_argument_and_unknown_pool_code():
    front, raw, minute = inputs()
    ctx = build(front, raw, minute)
    with pytest.raises(domain.PriceDomainError, match="domain=raw.*hash mismatch"):
        ctx.validate_simulation(minute, front, {}, START, START)
    with pytest.raises(domain.PriceDomainError, match="pool codes absent"):
        ctx.validate_simulation(minute, raw, {START: ["600000.SH"]}, START, START)


def test_missing_minute_session_cannot_be_hidden_by_a_valid_input_hash():
    front, raw, minute = inputs()
    minute[CODE].index -= pd.Timedelta(days=3)
    ctx = build(front, raw, minute)
    with pytest.raises(domain.PriceDomainError, match="missing raw minute session"):
        ctx.validate_simulation(minute, raw, {}, START, START)


@pytest.mark.parametrize("reference,expected", [("1.005", "1.01"), ("1.014", "1.01"),
                                              ("1.015", "1.02")])
def test_reference_uses_decimal_half_up_without_rounding_history(reference, expected):
    front, raw, minute = inputs(flat=True)
    raw[CODE].iloc[:, :] = float(reference)
    front = transformed(raw)
    transforms, provenance, evidence = pit_certificate(front, raw)
    ctx = certified_build(front, raw, minute, transforms, provenance, evidence)
    view = ctx.day_signal_view(CODE, START)
    assert view.prev_ref_unrounded == Decimal(reference)
    assert Decimal(str(view.prev_ref_raw)) == Decimal(expected)
    assert view.previous_signal_closes_in_raw_domain == (float(reference),) * 2


@pytest.mark.parametrize("event", [False, True])
def test_sub_tolerance_front_error_must_not_cross_reference_half_cent(event):
    front, raw, minute = inputs(flat=True)
    raw[CODE].iloc[:, :] = 2.01 if event else 1.005
    front = transformed(raw)
    front[CODE].iloc[1, front[CODE].columns.get_loc("close")] -= 1e-15
    transforms, provenance, evidence = pit_certificate(front, raw)
    if event:
        # Prior A=.5, D A=1: the rounding check must use the D inverse.
        front[CODE].iloc[-1] = raw[CODE].iloc[-1]
        transforms[(CODE, START)]["A"] = "1"
        for row in evidence["views"][-1]["history"]:
            row["close"] /= 2
    with pytest.raises(domain.PriceDomainError, match="precision changes rounded session reference"):
        certified_build(front, raw, minute, transforms, provenance, evidence)


def test_sub_tolerance_error_must_not_flip_equal_ma_into_reduce_signal():
    front, raw, minute = inputs()
    index = pd.bdate_range(end=raw[CODE].index[-1], periods=12)
    raw[CODE] = pd.DataFrame({key: [10.] * len(index) for key in domain.OHLC}, index=index)
    raw[CODE].loc[index[0], ["high", "low"]] = [11., 9.]
    front = transformed(raw)
    front[CODE].loc[index[-6:-1], ["high", "close"]] += 1e-11
    with pytest.raises(domain.PriceDomainError, match="precision crosses MA/stop decision boundary"):
        build(front, raw, minute)


@pytest.mark.parametrize("corruption", [None, "late", "naive", "missing_source", "wrong_snapshot",
                                      "wrong_history", "duplicate", "missing_coefficients"])
def test_pit_certificate_requires_independent_complete_timely_view(corruption):
    front, raw, minute = inputs(flat=True)
    transforms, provenance, evidence = pit_certificate(front, raw)
    row = evidence["views"][-1]
    if corruption == "late":
        row["reference_available_at"] = "2025-01-06T09:30:01+08:00"
    elif corruption == "naive":
        row["reference_available_at"] = "2025-01-06T09:29:00"
    elif corruption == "missing_source":
        row.pop("source")
    elif corruption == "wrong_snapshot":
        evidence["source_snapshot_id"] = "other-snapshot"
    elif corruption == "wrong_history":
        row["history"][0]["close"] = 11
    elif corruption == "duplicate":
        evidence["views"].append(deepcopy(row))
    elif corruption == "missing_coefficients":
        transforms.pop((CODE, START))
    if corruption is None:
        ctx = certified_build(front, raw, minute, transforms, provenance, evidence)
        assert ctx.metadata["pit_anchor_validation"] == "hash_bound_independent_pit_views"
    else:
        with pytest.raises(domain.PriceDomainError):
            certified_build(front, raw, minute, transforms, provenance, evidence)


def exact_certificate(raw):
    base = transformed(raw)
    front = transformed(raw, .4, .3)
    transforms, base_transforms, base_front = [], [], []
    for day in raw[CODE].index:
        session = day.strftime("%Y%m%d")
        transforms.append({"code": CODE, "session": session, "A": ".4", "B": ".3",
                           "reconstructed_asof": session})
        base_transforms.append({"code": CODE, "session": session, "A": ".5", "B": "0"})
        base_front.append({"code": CODE, "session": session,
                           **{key: float(base[CODE].loc[day, key]) for key in domain.OHLC}})
    provenance = {"kind": "exact_asof_reconstruction", "algorithm": "frozen-common-affine",
                  "anchor_version": "v2", "generated_at": "2025-02-01T12:00:00+08:00"}
    evidence = {"kind": provenance["kind"], "source_snapshot_id": "snapshot-test",
                "common_anchor": {"scale": ".8", "shift": ".3"},
                "base_transforms": base_transforms, "base_front": base_front}
    return front, transforms, provenance, evidence


@pytest.mark.parametrize("corruption", [None, "asof", "generated_at", "anchor", "base_front",
                                      "duplicate_base", "missing_event"])
def test_exact_reconstruction_proves_common_anchor_and_requires_transition_evidence(corruption):
    _, raw, minute = inputs()
    front, transforms, provenance, evidence = exact_certificate(raw)
    if corruption == "asof":
        transforms[-1]["reconstructed_asof"] = "20250107"
    elif corruption == "generated_at":
        provenance.pop("generated_at")
    elif corruption == "anchor":
        evidence["common_anchor"]["shift"] = ".4"
    elif corruption == "base_front":
        evidence["base_front"][-1]["close"] = 6.
    elif corruption == "duplicate_base":
        evidence["base_front"].append(deepcopy(evidence["base_front"][-1]))
    elif corruption == "missing_event":
        transforms[-1]["A"] = ".8"
        evidence["base_transforms"][-1]["A"] = "1"
        for key in domain.OHLC:
            front[CODE].loc[raw[CODE].index[-1], key] = 8.3
            evidence["base_front"][-1][key] = 10.
    if corruption is None:
        ctx = certified_build(front, raw, minute, transforms, provenance, evidence)
        assert ctx.previous_signal_closes_in_raw_domain(CODE, START) == [10., 10.]
        assert ctx.metadata["pit_anchor_validation"] == "common_affine_certificate_full_pit_unverified"
    else:
        with pytest.raises(domain.PriceDomainError):
            certified_build(front, raw, minute, transforms, provenance, evidence)


def lake(tmp_path, monkeypatch, *, mutate=None):
    front, raw, minute = inputs()
    frames = {"front": front[CODE], "raw": raw[CODE], "minute": minute[CODE]}
    paths = {}
    for kind, frame in frames.items():
        frame = frame.copy()
        frame["volume"] = 100.
        if mutate:
            frame = mutate(kind, frame)
        root = tmp_path / ("1m" if kind == "minute" else "1d")
        path = root / ("dividend_type=front" if kind == "front" else "dividend_type=none")
        path = path / "symbol=000001_SZ" / "data.parquet"
        path.parent.mkdir(parents=True)
        frame.insert(0, "time", [int(day.timestamp() * 1000) for day in frame.index])
        frame.to_parquet(path, index=False)
        paths[kind] = path
    monkeypatch.setattr(domain, "resolve_period_root", lambda period: tmp_path / period)
    monkeypatch.setattr(domain, "resolve_source_parquet", lambda name: tmp_path / name)
    return paths


def load_lake():
    return domain.load_s12_price_context({CODE}, START, START, load_start="20250102")


def test_strict_lake_reader_uses_paired_sources_without_legacy_cache(tmp_path, monkeypatch):
    paths = lake(tmp_path, monkeypatch)
    ctx, minute = load_lake()
    assert ctx.reference_price_for(CODE, START) == 10.
    assert minute[CODE]["hm"].tolist() == [570, 895]
    assert ctx.metadata["source_file_hashes"]["raw"][CODE] == domain.file_sha256(paths["raw"])
    assert ctx.metadata["cache_policy"] == "bypass_legacy_window_cache"


def test_null_parquet_timestamp_cannot_disappear_in_window_filter(tmp_path, monkeypatch):
    paths = lake(tmp_path, monkeypatch)
    frame = pd.read_parquet(paths["raw"])
    frame["time"] = frame["time"].astype("Int64")
    frame.loc[0, "time"] = pd.NA
    frame.to_parquet(paths["raw"], index=False)
    with pytest.raises(domain.PriceDomainError, match="null parquet time"):
        load_lake()


@pytest.mark.parametrize("corruption", ["missing_file", "missing_date", "duplicate", "zero_volume_bad_ohlc",
                                      "lunch_bad_ohlc", "volume_disagreement", "missing_open"])
def test_raw_parquet_fails_before_deduplication_and_filtering(tmp_path, monkeypatch, corruption):
    def mutate(kind, frame):
        if corruption == "missing_date" and kind == "front":
            return frame.iloc[1:]
        if corruption == "duplicate" and kind == "raw":
            return pd.concat([frame, frame.iloc[-1:]])
        if corruption == "zero_volume_bad_ohlc" and kind in ("front", "raw"):
            frame.loc[frame.index[0], [*domain.OHLC, "volume"]] = 0.
        if corruption == "lunch_bad_ohlc" and kind == "minute":
            frame.loc[pd.Timestamp("2025-01-06 12:00")] = 0.
        if corruption == "volume_disagreement" and kind == "front":
            frame.loc[frame.index[0], "volume"] = 0.
        if corruption == "missing_open" and kind == "raw":
            return frame.drop(columns="open")
        return frame

    paths = lake(tmp_path, monkeypatch, mutate=mutate)
    if corruption == "missing_file":
        paths["front"].unlink()
    with pytest.raises(domain.PriceDomainError, match=CODE):
        load_lake()


@pytest.mark.parametrize("corruption", ["mismatch", "nan", "duplicate"])
def test_optional_factor_is_checked_against_real_pairs(tmp_path, monkeypatch, corruption):
    lake(tmp_path, monkeypatch)
    rows = pd.DataFrame({"date": [20250106], "stock_code": [CODE], "close_front": [5.],
                         "close_none": [10.], "cumulative_adj_factor": [.5]})
    if corruption == "mismatch":
        rows["close_none"] = 11.
    elif corruption == "nan":
        rows["cumulative_adj_factor"] = float("nan")
    else:
        rows = pd.concat([rows, rows])
    rows.to_parquet(tmp_path / "adj_factor.parquet", index=False)
    with pytest.raises(domain.PriceDomainError):
        load_lake()


@pytest.mark.parametrize("corruption", [None, "source_hash", "evidence_hash", "kind"])
def test_transform_manifest_binds_sources_and_independent_evidence(tmp_path, monkeypatch, corruption):
    paths = lake(tmp_path, monkeypatch)
    front, raw, _ = inputs()
    transforms, provenance, evidence = pit_certificate(front, raw)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    provenance["evidence_file"] = {"path": "evidence.json", "sha256": domain.file_sha256(evidence_path)}
    document = {"schema_version": 1, "source_snapshot_id": "snapshot-test", "provenance": provenance,
                "sources": {kind: {CODE: {"path": str(path), "sha256": domain.file_sha256(path)}}
                            for kind, path in paths.items()},
                "transforms": [{"code": code, "session": day, **row}
                               for (code, day), row in transforms.items()]}
    if corruption == "source_hash":
        document["sources"]["raw"][CODE]["sha256"] = "wrong"
    elif corruption == "evidence_hash":
        provenance["evidence_file"]["sha256"] = "wrong"
    elif corruption == "kind":
        provenance["kind"] = "synthetic_fixture"
    manifest = tmp_path / "transforms.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    if corruption is None:
        ctx, _ = domain.load_s12_price_context({CODE}, START, START, load_start="20250102",
                                              transform_file=manifest)
        assert ctx.metadata["transform_metadata_sha256"] == domain.file_sha256(manifest)
        assert ctx.metadata["transform_evidence_sha256"] == domain.file_sha256(evidence_path)
    else:
        with pytest.raises(domain.PriceDomainError):
            domain.load_s12_price_context({CODE}, START, START, load_start="20250102", transform_file=manifest)
