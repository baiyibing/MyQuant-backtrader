# -*- coding: utf-8 -*-
"""策略 9 书：止损 / 满持有 / 拒绝默认 stock_pool。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_daily_backtest as sim
from backtest.research.csv_strategy_books import (
    apply_csv_strategy,
    get_book,
    resolve_research_pool_dir,
)
from backtest.research.strategy9_rules import MAX_HOLD, STOP_PCT, take_profit_reason


def test_version9_hooks_and_max_hold():
    hooks = apply_csv_strategy("version9")
    assert hooks["name"] == "version9"
    assert hooks["book"] == "v9"
    assert hooks["allow_add"] is False
    assert hooks["peak_gap_min"] == 0
    assert hooks["stop_pct"] == pytest.approx(STOP_PCT)
    assert hooks["take_profit"](10.0, 10.0, 10.0, MAX_HOLD - 1) is None
    assert hooks["take_profit"](10.0, 10.0, 10.0, MAX_HOLD) == "force_sell:max_hold"
    assert take_profit_reason(1, 1, 1, MAX_HOLD) == "force_sell:max_hold"
    assert get_book("9").tag == "v9"
    assert get_book("v9").name == "version9"


def test_version9_refuses_default_and_repo_stock_pool(tmp_path):
    repo = tmp_path / "repo"
    (repo / "stock_pool").mkdir(parents=True)
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version9", None, repo=repo)
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version9", repo / "stock_pool", repo=repo)
    dest = repo / "exports" / "s9"
    dest.mkdir(parents=True)
    assert resolve_research_pool_dir("version9", dest, repo=repo) == dest
    default = resolve_research_pool_dir("version6", None, repo=repo)
    assert default == repo / "stock_pool"


def test_daily_cli_version9_refuses_stock_pool(monkeypatch):
    monkeypatch.setattr(
        sim, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("run"))
    )
    with pytest.raises(SystemExit, match="stock_pool"):
        sim.main(["--strategy", "version9", "--start", "20260303", "--end", "20260323"])


def test_daily_cli_version9_accepts_explicit_pool(tmp_path, monkeypatch):
    seen = {}

    def _run(*_a, **kwargs):
        seen.update(kwargs)
        st = sim.SimState(cash=21_000_000.0)
        st.equity_curve = [("20260303", 21_000_000.0)]
        st.stats["sell_book"] = "v9"
        st.stats["stop_pct"] = STOP_PCT
        return st

    monkeypatch.setattr(sim, "run", _run)
    dest = tmp_path / "s9"
    dest.mkdir()
    (dest / "20260303.csv").write_text("600000\n", encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    rc = sim.main(
        [
            "--strategy",
            "version9",
            "--start",
            "20260303",
            "--end",
            "20260323",
            "--pool-dir",
            str(dest),
            "--out-dir",
            str(out),
        ]
    )
    assert rc == 0
    assert Path(seen["pool_dir"]) == dest
    assert (out / "summary.txt").is_file()


def test_version9_force_sells_after_max_hold():
    idx = pd.bdate_range("2025-11-03", periods=26)
    pre = pd.DatetimeIndex([idx[0] - pd.Timedelta(days=3)])
    full = pre.append(idx)
    px = {
        "open": np.full(len(full), 10.0),
        "high": np.full(len(full), 10.1),
        "low": np.full(len(full), 9.9),
        "close": np.full(len(full), 10.0),
    }
    bars = {"600000.SH": pd.DataFrame(px, index=full).astype(np.float64)}
    start = idx[0].strftime("%Y%m%d")
    end = idx[-1].strftime("%Y%m%d")
    st = sim.simulate(
        bars,
        {start: ["600000.SH"]},
        start,
        end,
        strategy="version9",
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["buys"] == 1
    assert st.stats["sell_force"] == 1
    assert sells[0]["reason"] == "force_sell:max_hold"
    assert sells[0]["date"] == idx[MAX_HOLD + 1].strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(10.0)
