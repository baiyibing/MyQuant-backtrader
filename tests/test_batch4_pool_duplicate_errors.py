"""Batch4 must abort on invalid duplicate pools while retaining other notes."""

from unittest.mock import Mock

import pandas as pd
import pytest

from backtest.research import csv_pool, fullstrat_research_hooks, qlib_bin_1min
from scripts.research import run_minute_sensitivity_b_batch4_fullstrat as harness


@pytest.fixture
def modeb_inputs(tmp_path, monkeypatch):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    (pool_dir / "20260901.csv").write_text("000001,first\n", encoding="utf-8")
    qlib_root = tmp_path / "qlib"
    qlib_root.mkdir()
    compact = {
        "000001.SZ": pd.DataFrame(
            [{"ymd": "20260901", "hm": 570, "open": 10.0, "close": 10.0}]
        )
    }
    monkeypatch.setattr(qlib_bin_1min, "load_qlib_bin_1min_bars", Mock(return_value=compact))
    return dict(
        start="20260901",
        end="20260901",
        pool_dir=pool_dir,
        qlib_root=qlib_root,
        work_root=tmp_path / "work",
    )


def test_pool_load_duplicate_aborts_batch4(modeb_inputs, monkeypatch):
    path = modeb_inputs["pool_dir"] / "20260901.csv"
    path.write_text("000001,first\n000001.SZ,second\n", encoding="utf-8")
    run_modeb = Mock()
    monkeypatch.setattr(fullstrat_research_hooks, "run_modeb", run_modeb)

    with pytest.raises(csv_pool.PoolDuplicateCodeError) as caught:
        harness.run_modeb_library(**modeb_inputs)

    assert caught.value.path == path
    assert caught.value.code == "000001.SZ"
    assert (caught.value.first_line, caught.value.second_line) == (1, 2)
    run_modeb.assert_not_called()


def test_modeb_duplicate_aborts_batch4(modeb_inputs, monkeypatch):
    path = modeb_inputs["pool_dir"] / "20260901.csv"
    duplicate = csv_pool.PoolDuplicateCodeError(path, "000001.SZ", 1, 2)
    run_modeb = Mock(side_effect=duplicate)
    monkeypatch.setattr(fullstrat_research_hooks, "run_modeb", run_modeb)

    with pytest.raises(csv_pool.PoolDuplicateCodeError) as caught:
        harness.run_modeb_library(**modeb_inputs)

    assert caught.value is duplicate
    run_modeb.assert_called_once()


@pytest.mark.parametrize(
    "module,function,note_prefix",
    [
        (csv_pool, "load_pool_day_map", "pool_load_failed"),
        (fullstrat_research_hooks, "run_modeb", "run_modeb_failed"),
    ],
)
def test_batch4_retains_other_failure_notes(
    modeb_inputs, monkeypatch, module, function, note_prefix
):
    failing_call = Mock(side_effect=RuntimeError("ordinary failure"))
    monkeypatch.setattr(module, function, failing_call)

    row = harness.run_modeb_library(**modeb_inputs)

    failing_call.assert_called_once()
    assert row["status"] == "DATA_GAP"
    assert row["note"] == f"{note_prefix}:ordinary failure"
