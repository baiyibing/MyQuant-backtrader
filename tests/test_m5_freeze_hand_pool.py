# -*- coding: utf-8 -*-
"""Handmade pool freeze (M5R2-4): byte copy, window filter, never stock_pool/."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.data.m5_freeze_hand_pool import (
    REPO_ROOT,
    freeze_hand_pool,
    main,
    stems_missing,
)
from scripts.data.m5_hand_topn import refuses_stock_pool


def test_freeze_copies_two_window_files_byte_identical(tmp_path: Path):
    pool_dir = tmp_path / "pool"
    out_dir = tmp_path / "exports" / "m5r2_hand_snap_20260303_20260323"
    pool_dir.mkdir()
    a = b"600000\n600001\n"
    b_bytes = b"\xef\xbb\xbf300190\r\n"
    (pool_dir / "20260303.csv").write_bytes(a)
    (pool_dir / "20260304.csv").write_bytes(b_bytes)
    (pool_dir / "outside.csv").write_bytes(b"600000\n")
    (pool_dir / "20260324.csv").write_bytes(b"600000\n")

    written = freeze_hand_pool(
        pool_dir,
        out_dir,
        start="20260303",
        end="20260323",
    )

    assert [path.name for path in written] == ["20260303.csv", "20260304.csv"]
    assert (out_dir / "20260303.csv").read_bytes() == a
    assert (out_dir / "20260304.csv").read_bytes() == b_bytes
    assert not (out_dir / "outside.csv").exists()
    assert not (out_dir / "20260324.csv").exists()


def test_stems_missing_counts_expected_not_copied():
    written = [Path("20260303.csv")]
    assert stems_missing(written, ["20260303", "20260525"]) == ["20260525"]


def test_cli_refuses_to_write_into_stock_pool(tmp_path: Path):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    (pool_dir / "20260303.csv").write_bytes(b"600000\n")
    stock_pool = REPO_ROOT / "stock_pool"
    with pytest.raises(SystemExit, match="stock_pool"):
        main(
            [
                "--pool-dir",
                str(pool_dir),
                "--out-dir",
                str(stock_pool),
                "--start",
                "20260303",
                "--end",
                "20260323",
            ]
        )
    assert refuses_stock_pool(stock_pool / "nested")
