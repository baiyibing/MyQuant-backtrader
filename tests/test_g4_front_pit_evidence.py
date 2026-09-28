"""G4 synthetic evidence knife; real s11 signals, explicitly NOT real CYQK/PIT.

Run with pytest -q -s to print the two-anchor report. Frozen CSVs and report.json
are written only under tmp_path; A/B are local fixture labels, not vendor IDs.
"""

from hashlib import sha256
import json

import numpy as np
import pandas as pd
import pytest

from scripts.data import export_strategy11_pool as exporter
from common.infra import data_root


PRICE = ["open", "high", "low", "close"]
BUCKETS = dict(zip(
    ("600001.SH", "600002.SH", "600003.SH", "600004.SH", "600005.SH", "600006.SH"),
    ("positive_scale", "common_affine", "rounding", "non_common_revision",
     "fixed_grid_guard", "future_only_revision"), strict=True,
))
CALENDAR = pd.bdate_range("2023-04-03", periods=240)
ANCHORS = CALENDAR[[217, 237]]  # both Wednesday: incomplete current week
FROZEN_DIGESTS = {
    "A": "69da5b4f12eb40d6234b58455be862fd648498b531f966c5707fe0e5965233ac",
    "B": "5f0689fade0ed63d9b156f5bd97e00e46979de66543a7a7daf838c2b3fea1dfa",
}


def frozen_snapshots():
    """Deterministic A/B with the same six symbols and 240-session calendar."""
    close = np.full(240, 10.0)
    close[[210, 230]] = 11.0
    base = pd.DataFrame({"open": 10.0, "high": close + .125, "low": 9.875,
                         "close": close, "volume": 1000.0}, index=CALENDAR)
    a = {symbol: base.copy(deep=True) for symbol in BUCKETS}
    # Near equality: the 0.004 uplift disappears on a cent grid.
    a["600003.SH"].loc[CALENDAR[[210, 230]], "close"] = 10.004
    a["600003.SH"]["high"] = a["600003.SH"]["close"] + .125
    # Actual exporter guard, not an emulation of the Rust price histogram.
    a["600005.SH"].loc[CALENDAR[205], "high"] = 9.875 + 250000 * .01
    b = {symbol: frame.copy(deep=True) for symbol, frame in a.items()}
    b["600001.SH"][PRICE] *= 2
    b["600002.SH"][PRICE] = b["600002.SH"][PRICE] * 2 + 3
    b["600003.SH"][PRICE] = b["600003.SH"][PRICE].round(2)
    b["600004.SH"].loc[CALENDAR[210], "close"] = 10.0
    boundary = b["600005.SH"].loc[CALENDAR[205], "high"]
    b["600005.SH"].loc[CALENDAR[205], "high"] = np.nextafter(boundary, np.inf)
    b["600006.SH"].loc[CALENDAR[230], "close"] = 10.0
    return {"A": a, "B": b}


def controlled_cyqk(close, high, low, volume, shares, *, window, start_i, step):
    """Constant 0.8 after warmup; isolates price comparisons, NOT CYQK math."""
    assert (window, start_i, step) == (200, 199, .01)
    assert len({len(x) for x in (close, high, low, volume, shares)}) == 1
    span = pd.Series(high).rolling(window).max() - pd.Series(low).rolling(window).min()
    assert (span.dropna() / step <= exporter.MAX_GRID_POINTS).all()
    values = np.full(len(close), np.nan)
    values[start_i:] = .8
    return values


def signal_prefix(frame, cutoff):
    """Pure frame adapter: use production truncation and signal computation."""
    prepared, dropped = exporter.prepare_frame(frame, cutoff)
    assert dropped == 0
    edges, cyqk, grid, finite = exporter.compute_signals(
        prepared, np.full(len(prepared), 1e8), controlled_cyqk,
    )
    return pd.DataFrame({"signal": edges, "cyqk": cyqk, "grid": grid,
                         "finite": finite}, index=prepared.index)


def differences(left, right, column):
    assert left.index.equals(right.index)
    return left.index[left[column] != right[column]].strftime("%Y-%m-%d").tolist()


@pytest.fixture(autouse=True)
def no_lake(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("G4 evidence must not resolve or read a market lake")

    for module in (exporter, data_root):
        monkeypatch.setattr(module, "resolve_period_root", forbidden)
        monkeypatch.setattr(module, "resolve_source_parquet", forbidden)
    monkeypatch.setattr(exporter.pq, "read_table", forbidden)
    monkeypatch.setattr(pd, "read_parquet", forbidden)


def test_two_frozen_snapshots_two_anchor_report(tmp_path):
    snapshots = frozen_snapshots()
    hashes = {}
    for label, frames in snapshots.items():
        hashes[label] = {}
        for symbol, frame in frames.items():
            # 17 significant digits retain the one-ULP grid-boundary edit.
            payload = frame.to_csv(date_format="%Y-%m-%d", float_format="%.17g",
                                   lineterminator="\n", index_label="date").encode()
            path = tmp_path / label / f"{symbol}.csv"
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(payload)
            hashes[label][symbol] = sha256(payload).hexdigest()
            restored = pd.read_csv(path, index_col="date", parse_dates=True,
                                   float_precision="round_trip").astype(float)
            pd.testing.assert_frame_equal(frame, restored, check_freq=False,
                                          check_names=False, check_exact=True)
            frames[symbol] = restored  # run the frozen bytes, not the generator

    digests = {label: sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
               for label, items in hashes.items()}
    assert digests == FROZEN_DIGESTS  # fixture edits require explicit re-freezing
    rows = []
    for symbol, bucket in BUCKETS.items():
        runs = {label: [signal_prefix(frames[symbol], day) for day in ANCHORS]
                for label, frames in snapshots.items()}
        for label, (early, late) in runs.items():
            pd.testing.assert_frame_equal(early, late.loc[:ANCHORS[0]], check_exact=True)
            # Independent already-truncated call pins the as-of adapter itself.
            for day, actual in zip(ANCHORS, (early, late), strict=True):
                pd.testing.assert_frame_equal(actual, signal_prefix(
                    snapshots[label][symbol].loc[:day], day), check_exact=True)

        for i, day in enumerate(ANCHORS):
            left, right = runs["A"][i], runs["B"][i]
            changed = differences(left, right, "signal")
            expected_positions = {
                "positive_scale": [], "common_affine": [],
                "rounding": [210] if i == 0 else [210, 230],
                "non_common_revision": [210],
                "fixed_grid_guard": [210] if i == 0 else [210, 230],
                "future_only_revision": [] if i == 0 else [230],
            }[bucket]
            assert changed == CALENDAR[expected_positions].strftime("%Y-%m-%d").tolist()
            assert left.index[left.signal].tolist() == list(CALENDAR[[210] if i == 0 else [210, 230]])
            assert left.finite.sum() > 0  # never pass on empty/all-warmup prefixes
            if bucket != "fixed_grid_guard":
                pd.testing.assert_frame_equal(left.drop(columns="signal"),
                                              right.drop(columns="signal"), check_exact=True)
            else:
                assert differences(left, right, "grid") == CALENDAR[205:218 if i == 0 else 238].strftime("%Y-%m-%d").tolist()
                assert not right.loc[CALENDAR[205]:, "finite"].any()
                assert right.loc[CALENDAR[205]:, "cyqk"].isna().all()
            rows.append({"symbol": symbol, "bucket": bucket, "cutoff": str(day.date()),
                         "result": "differed" if changed else "same-prefix",
                         "signal_diff_days": changed,
                         "grid_diff_count": len(differences(left, right, "grid")),
                         "within_snapshot_shared_prefix": "same-prefix"})

    report = {"provenance": "synthetic_fixture", "upstream_version_id": None,
              "pit_status": "common_affine_certificate_full_pit_unverified",
              "cyqk_backend": "controlled_constant_0.8_NOT_Rust",
              "verdict": "PASS-for-method", "snapshot_sha256": hashes,
              "snapshot_digest": digests, "rows": rows}
    (tmp_path / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


@pytest.mark.parametrize("label", ["A", "B"])
def test_future_changes_do_not_rewrite_shared_prefix(label):
    for frame in frozen_snapshots()[label].values():
        changed = frame.copy(deep=True)
        changed.loc[changed.index > ANCHORS[0], PRICE] *= 3
        original = signal_prefix(frame, ANCHORS[0])
        pd.testing.assert_frame_equal(original, signal_prefix(changed, ANCHORS[1]).loc[:ANCHORS[0]],
                                      check_exact=True)
