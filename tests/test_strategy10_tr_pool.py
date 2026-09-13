# -*- coding: utf-8 -*-
"""策略 10 / 源 B：注入截面、无未来日期、契约字节、拒绝 stock_pool。"""

from __future__ import annotations

import pandas as pd
import pytest

import backtest.research.csv_daily_backtest as sim
from backtest.research.csv_pool import validate_pool_dir
from backtest.research.csv_strategy_books import (
    apply_csv_strategy,
    resolve_research_pool_dir,
)
from backtest.research.source_b_tr_pool import (
    assert_section_asof,
    filter_day,
    scan_tr_days,
    write_tr_pool,
)
from scripts.data.export_ta_pool import REPO_ROOT, main as export_main
from strategies.tr_filter import ConfigurationError


def _row(
    code: str,
    *,
    ymd: str = "20260303",
    tr: float = 25.0,
    bb_position: float = 0.6,
    tr_bb_position: float = 0.7,
) -> dict[str, object]:
    return {
        "stock_code": code,
        "trade_date": ymd,
        "turnover_resistance": tr,
        "bb_position": bb_position,
        "tr_bb_position": tr_bb_position,
        "tr_bb_middle": 3.0,
        "tr_bb_upper": 4.0,
        "tr_bb_lower": 2.0,
        "bands_computed_at": 1.0,
        "window": 1000,
    }


def test_filter_keeps_pass_and_drops_fail():
    section = pd.DataFrame(
        [
            _row("600000.SH"),
            _row("600001.SH", tr=5.0),
        ]
    )
    assert filter_day(["600000.SH", "600001.SH"], section) == ["600000.SH"]


def test_bare_code_normalizes_to_canonical():
    section = pd.DataFrame([_row("600000.SH")])
    assert filter_day(["600000"], section) == ["600000.SH"]


def test_empty_section_fail_closed():
    with pytest.raises(ConfigurationError, match="empty"):
        filter_day(["600000.SH"], pd.DataFrame())


def test_missing_row_fail_closed():
    section = pd.DataFrame([_row("600000.SH")])
    with pytest.raises(ConfigurationError, match="missing"):
        filter_day(["600000.SH", "600001.SH"], section)


def test_rejects_section_rows_after_t():
    section = pd.DataFrame(
        [_row("600000.SH", ymd="20260303"), _row("600001.SH", ymd="20260304")]
    )
    with pytest.raises(ValueError, match="after T"):
        assert_section_asof(section, "20260303")

    def load(_ymd: str) -> pd.DataFrame:
        return pd.DataFrame([_row("600000.SH", ymd="20260304")])

    with pytest.raises(ValueError, match="after T"):
        scan_tr_days(
            ["20260303"],
            load_cross_section=load,
            universe_for=lambda _ymd: ["600000.SH"],
        )


def test_scan_injects_asof_and_writes_contract(tmp_path):
    table = {
        "20260303": pd.DataFrame([_row("600000.SH"), _row("000001.SZ", tr=5.0)]),
        "20260304": pd.DataFrame([_row("000001.SZ", ymd="20260304")]),
    }

    def load(ymd: str) -> pd.DataFrame:
        return table[ymd]

    days = scan_tr_days(
        ["20260303", "20260304"],
        load_cross_section=load,
        universe_for=lambda ymd: (
            ["600000.SH", "000001.SZ"] if ymd == "20260303" else ["000001.SZ"]
        ),
    )
    assert days == {"20260303": ["600000.SH"], "20260304": ["000001.SZ"]}
    written = write_tr_pool(days, tmp_path / "s10", repo=tmp_path)
    raw = (tmp_path / "s10" / "20260303.csv").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.decode("utf-8").splitlines() == ["600000"]
    assert (tmp_path / "s10" / "20260304.csv").read_text(
        encoding="utf-8"
    ).splitlines() == ["000001"]
    assert written
    assert validate_pool_dir(tmp_path / "s10") == []


def test_scan_skips_empty_day():
    def load(ymd: str) -> pd.DataFrame:
        if ymd == "20260303":
            return pd.DataFrame([_row("600000.SH")])
        return pd.DataFrame()

    days = scan_tr_days(
        ["20260303", "20260304"],
        load_cross_section=load,
        universe_for=lambda ymd: ["600000.SH"] if ymd == "20260303" else [],
    )
    assert list(days) == ["20260303"]


def test_write_refuses_stock_pool(tmp_path):
    stock = tmp_path / "stock_pool"
    stock.mkdir()
    with pytest.raises(SystemExit, match="stock_pool"):
        write_tr_pool({"20260303": ["600000.SH"]}, stock, repo=tmp_path)


def test_export_cli_refuses_repo_stock_pool():
    with pytest.raises(SystemExit, match="stock_pool"):
        export_main(
            [
                "--start",
                "20260303",
                "--end",
                "20260323",
                "--out-dir",
                str(REPO_ROOT / "stock_pool"),
            ]
        )


def test_export_cli_inject_writes_files(tmp_path):
    src = tmp_path / "section.csv"
    pd.DataFrame([_row("600000.SH"), _row("600001.SH", tr=1.0)]).to_csv(
        src, index=False, encoding="utf-8", lineterminator="\n"
    )
    dest = tmp_path / "exports" / "s10"
    uni = tmp_path / "universe.txt"
    uni.write_text("600000\n600001\n", encoding="utf-8", newline="\n")
    rc = export_main(
        [
            "--start",
            "20260303",
            "--end",
            "20260303",
            "--out-dir",
            str(dest),
            "--inject-cross-section",
            str(src),
            "--universe-file",
            str(uni),
        ]
    )
    assert rc == 0
    assert (dest / "20260303.csv").read_text(encoding="utf-8").splitlines() == [
        "600000"
    ]
    assert validate_pool_dir(dest) == []


def test_version10_reuses_version6_sells_and_refuses_stock_pool(tmp_path):
    hooks6 = apply_csv_strategy("version6")
    hooks10 = apply_csv_strategy("version10")
    assert hooks10["name"] == "version10"
    assert hooks10["book"] == "v10"
    assert hooks10["stop_pct"] == hooks6["stop_pct"]
    assert hooks10["allow_add"] is False
    assert hooks10["peak_gap_min"] == hooks6["peak_gap_min"]
    assert hooks10["take_profit"](10.218, 10.0, 10.50, 1) == hooks6["take_profit"](
        10.218, 10.0, 10.50, 1
    )
    repo = tmp_path / "repo"
    (repo / "stock_pool").mkdir(parents=True)
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version10", None, repo=repo)
    dest = repo / "exports" / "s10"
    dest.mkdir(parents=True)
    assert resolve_research_pool_dir("version10", dest, repo=repo) == dest


def test_daily_cli_version10_refuses_stock_pool(monkeypatch):
    monkeypatch.setattr(
        sim, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("run"))
    )
    with pytest.raises(SystemExit, match="stock_pool"):
        sim.main(
            ["--strategy", "version10", "--start", "20260303", "--end", "20260323"]
        )
