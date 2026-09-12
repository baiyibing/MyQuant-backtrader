"""Lake-free contract coverage for the R2 prediction-pool to R5 loop.

R2 export artifacts are deliberately represented by tiny temporary files.
Their filename is the buy day, while H0 may omit the first prediction day.
Consequently the daily-backtest window must be derived from written files.
R5 must consume an R2 prediction export, never an R0 holdings export.
The real engine run remains an environment check because CI has no data lake.
"""

from pathlib import Path

import pytest

from backtest.research.csv_pool import validate_pool_dir


def _daily_window_from_pool_files(pool_dir: Path) -> tuple[str, str]:
    stems = sorted(path.stem for path in pool_dir.glob("*.csv"))
    if not stems:
        raise ValueError("R5 pool directory contains no CSV files")
    return stems[0], stems[-1]


def _require_r5_pool_path(pool_dir: Path) -> Path:
    parts = pool_dir.parts
    if any(
        part == "exports" and parts[index + 1].startswith("r0_")
        for index, part in enumerate(parts[:-1])
    ):
        raise ValueError("R5 refuses exports/r0_* holdings input")
    return pool_dir


def test_r2_export_contract_and_filename_derived_r5_window(tmp_path: Path):
    pool_dir = tmp_path / "r2_pred_topn_fixture"
    pool_dir.mkdir()
    pools = {
        "20260303.csv": ["600000", "000001", "920014"],
        "20260304.csv": ["300190", "688001", "920014"],
        "20260305.csv": ["920014", "000001", "600000"],
    }
    for filename, codes in pools.items():
        (pool_dir / filename).write_text(
            "".join(f"{code}\n" for code in codes),
            encoding="utf-8",
            newline="\n",
        )

    assert not pool_dir.name.startswith("r0_")
    assert validate_pool_dir(_require_r5_pool_path(pool_dir)) == []
    assert _daily_window_from_pool_files(pool_dir) == ("20260303", "20260305")
    for path in pool_dir.glob("*.csv"):
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert all(line.isdigit() and len(line) == 6 for line in raw.splitlines())


def test_r5_refuses_r0_holdings_export():
    with pytest.raises(ValueError, match=r"exports/r0_\*"):
        _require_r5_pool_path(Path("exports/r0_positions_20260302_20260323"))
