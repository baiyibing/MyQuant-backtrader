# -*- coding: utf-8 -*-
"""Source B A–C: write bytes, inject filter, CLI without live store."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backtest.research.csv_pool import validate_pool_dir
from backtest.research.source_b_tr_pool import scan_tr_days, write_tr_pool
from oskh_data.symbol_format import to_partition_key
from scripts.data.export_ta_pool import (
    REPO_ROOT,
    has_bar_on_day,
    lake_universe_on_day,
    main,
)


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


def _time_ms(*dates: str) -> list[int]:
    return [int(pd.Timestamp(date, tz="UTC").timestamp() * 1000) for date in dates]


def _write_lake(root: Path, code: str, dates: list[str], volumes: list[float]) -> None:
    part = root / f"symbol={to_partition_key(code)}"
    part.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "time": _time_ms(*dates),
            "open": [10.0] * len(dates),
            "high": [10.1] * len(dates),
            "low": [9.9] * len(dates),
            "close": [10.0] * len(dates),
            "volume": volumes,
        }
    ).to_parquet(part / "data.parquet", index=False)


def test_a_writes_two_days_and_skips_empty(tmp_path):
    days = {"20260303": ["600002.SH", "600000.SH"], "20260305": ["000001.SZ"]}
    written = write_tr_pool(days, tmp_path / "src_b", repo=tmp_path)
    assert [path.name for path in written] == ["20260303.csv", "20260305.csv"]
    raw = (tmp_path / "src_b" / "20260303.csv").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.decode("utf-8").splitlines() == ["600002", "600000"]
    assert not (tmp_path / "src_b" / "20260304.csv").exists()
    assert validate_pool_dir(tmp_path / "src_b") == []


def test_b_filter_preserves_universe_order():
    section = pd.DataFrame([_row("600000.SH"), _row("600002.SH")])

    def load(_ymd: str) -> pd.DataFrame:
        return section

    def universe(_ymd: str) -> list[str]:
        return ["600002.SH", "600000.SH"]

    days = scan_tr_days(["20260303"], load_cross_section=load, universe_for=universe)
    assert days["20260303"] == ["600002.SH", "600000.SH"]


def test_b_fail_closed_empty_and_missing():
    from strategies.tr_filter import ConfigurationError

    def load(_ymd: str) -> pd.DataFrame:
        return pd.DataFrame()

    with pytest.raises((ConfigurationError, ValueError)):
        scan_tr_days(
            ["20260303"],
            load_cross_section=load,
            universe_for=lambda _ymd: ["600000.SH"],
        )


def test_c_cli_inject_needs_universe_file(tmp_path):
    src = tmp_path / "section.csv"
    pd.DataFrame([_row("600000.SH")]).to_csv(
        src, index=False, encoding="utf-8", lineterminator="\n"
    )
    with pytest.raises(SystemExit, match="universe-file"):
        main(
            [
                "--start",
                "20260303",
                "--end",
                "20260303",
                "--out-dir",
                str(tmp_path / "out"),
                "--inject-cross-section",
                str(src),
            ]
        )


def test_c_cli_universe_file_without_store(tmp_path):
    src = tmp_path / "section.csv"
    pd.DataFrame(
        [_row("600000.SH"), _row("600001.SH", tr=1.0), _row("000001.SZ")]
    ).to_csv(src, index=False, encoding="utf-8", lineterminator="\n")
    uni = tmp_path / "universe.txt"
    uni.write_text("000001\n600000\n", encoding="utf-8", newline="\n")
    dest = tmp_path / "exports" / "src_b"
    rc = main(
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
        "000001",
        "600000",
    ]
    assert (dest / "widths.txt").read_text(encoding="utf-8") == "20260303 2\n"
    assert validate_pool_dir(dest) == []


def test_c_refuses_topk_flag():
    with pytest.raises(SystemExit):
        main(
            [
                "--start",
                "20260303",
                "--end",
                "20260303",
                "--topk",
                "10",
            ]
        )


def test_c_refuses_stock_pool_out_and_universe():
    with pytest.raises(SystemExit, match="stock_pool"):
        main(
            [
                "--start",
                "20260303",
                "--end",
                "20260303",
                "--out-dir",
                str(REPO_ROOT / "stock_pool"),
            ]
        )
    with pytest.raises(SystemExit, match="stock_pool"):
        main(
            [
                "--start",
                "20260303",
                "--end",
                "20260303",
                "--out-dir",
                str(REPO_ROOT / "exports" / "x"),
                "--universe-file",
                str(REPO_ROOT / "stock_pool" / "20260303.csv"),
            ]
        )


def test_br4_lake_only_counts_bar_on_t(tmp_path):
    root = tmp_path / "dividend_type=none"
    _write_lake(root, "600000.SH", ["2026-03-03"], [1000.0])
    _write_lake(root, "600001.SH", ["2026-03-04"], [1000.0])
    _write_lake(root, "000001.SZ", ["2026-03-03"], [0.0])
    assert has_bar_on_day("600000.SH", root, "20260303") is True
    assert has_bar_on_day("600001.SH", root, "20260303") is False
    assert has_bar_on_day("000001.SZ", root, "20260303") is False
    assert lake_universe_on_day(root, "20260303") == ["600000.SH"]


def test_br4_scan_uses_lake_not_section_extras(tmp_path):
    root = tmp_path / "dividend_type=none"
    _write_lake(root, "600000.SH", ["2026-03-03"], [1000.0])
    section = pd.DataFrame([_row("600000.SH"), _row("600001.SH")])

    days = scan_tr_days(
        ["20260303"],
        load_cross_section=lambda _ymd: section,
        universe_for=lambda ymd: lake_universe_on_day(root, ymd),
    )
    assert days == {"20260303": ["600000.SH"]}


def test_c_cli_lake_universe_plus_inject(tmp_path):
    root = tmp_path / "dividend_type=none"
    _write_lake(root, "600000.SH", ["2026-03-03"], [1000.0])
    _write_lake(root, "600001.SH", ["2026-03-03"], [1000.0])
    src = tmp_path / "section.csv"
    pd.DataFrame([_row("600000.SH"), _row("600001.SH", tr=1.0)]).to_csv(
        src, index=False, encoding="utf-8", lineterminator="\n"
    )
    dest = tmp_path / "out"
    # inject + lake-root still requires universe-file (CI must not silently
    # use the section). Use lake listing as the file.
    uni = tmp_path / "uni.txt"
    uni.write_text("600000\n600001\n", encoding="utf-8", newline="\n")
    rc = main(
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
            "--lake-root",
            str(root),
        ]
    )
    assert rc == 0
    assert (dest / "20260303.csv").read_text(encoding="utf-8").splitlines() == [
        "600000"
    ]
