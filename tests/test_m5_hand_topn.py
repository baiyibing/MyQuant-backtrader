# -*- coding: utf-8 -*-
"""Handmade TopN truncator (M5-R5): 15 rows → 10, preserve order, never stock_pool/."""

from __future__ import annotations

from pathlib import Path

import pytest

from backtest.research.csv_pool import parse_pool_csv, validate_pool_dir
from scripts.data.m5_hand_topn import (
    REPO_ROOT,
    main,
    refuses_stock_pool,
    truncate_pool_file,
    write_truncated_pools,
)


def _write_pool(path: Path, codes: list[str]) -> None:
    path.write_text(
        "代码,名称\n" + "".join(f"{code},name{i}\n" for i, code in enumerate(codes)),
        encoding="utf-8",
        newline="\n",
    )


def test_truncate_15_rows_to_first_10_preserving_order(tmp_path: Path):
    codes = [f"{600000 + i:06d}" for i in range(15)]
    src = tmp_path / "20260303.csv"
    _write_pool(src, codes)
    assert parse_pool_csv(src) == [f"{c}.SH" for c in codes]
    assert truncate_pool_file(src, 10) == codes[:10]


def test_write_topn_does_not_touch_stock_pool(tmp_path: Path):
    pool_dir = tmp_path / "pool"
    out_dir = tmp_path / "exports" / "m5_hand_top10_20260303_20260323"
    pool_dir.mkdir()
    codes = [f"{600000 + i:06d}" for i in range(15)]
    _write_pool(pool_dir / "20260303.csv", codes)
    _write_pool(pool_dir / "20260304.csv", [f"{i + 1:06d}" for i in range(4)])
    (pool_dir / "outside.csv").write_text("600000\n", encoding="utf-8")
    (pool_dir / "20260324.csv").write_text("600000\n", encoding="utf-8")

    stock_pool = REPO_ROOT / "stock_pool"
    before = {
        path.name: (path.stat().st_mtime_ns, path.read_bytes())
        for path in stock_pool.glob("202603*.csv")
    }

    written = write_truncated_pools(
        pool_dir,
        out_dir,
        start="20260303",
        end="20260323",
        k=10,
    )

    assert [path.name for path in written] == ["20260303.csv", "20260304.csv"]
    raw = (out_dir / "20260303.csv").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert lines == codes[:10]
    assert all(line.isdigit() and len(line) == 6 for line in lines)
    assert validate_pool_dir(out_dir) == []
    assert (out_dir / "20260304.csv").read_text(encoding="utf-8").splitlines() == [
        f"{i:06d}" for i in range(1, 5)
    ]
    assert not (out_dir / "outside.csv").exists()
    assert not (out_dir / "20260324.csv").exists()

    after = {
        path.name: (path.stat().st_mtime_ns, path.read_bytes())
        for path in stock_pool.glob("202603*.csv")
    }
    assert after == before
    assert not refuses_stock_pool(out_dir)


def test_cli_refuses_to_write_into_stock_pool(tmp_path: Path):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    _write_pool(pool_dir / "20260303.csv", [f"{600000 + i:06d}" for i in range(15)])
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
    with pytest.raises(SystemExit, match="stock_pool"):
        write_truncated_pools(
            pool_dir,
            stock_pool / "nested",
            start="20260303",
            end="20260323",
        )
