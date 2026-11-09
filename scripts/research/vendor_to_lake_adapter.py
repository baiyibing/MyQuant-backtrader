"""BT sample/configuration adapter over infra's sandbox vendor staging CLI."""
import os
from pathlib import Path

from myquant_infra.adapters.vendor_bars import staging as _shared
from myquant_infra.adapters.vendor_bars.staging import (
    AUCTION_POLICY, TRANSFORMATIONS, StartIntervalError, convert, json_write,
    read_daily, read_wind_start, sha, verify, xcheck,
)

_BT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SYMBOLS = ["002231.SZ", "300379.SZ", "600200.SH"]


def _configured_lake_roots():
    return {key: Path(os.environ[key]) for key in (
        "OSKH_SOURCE_PARQUET_ROOT", "OSKH_PERIOD_1D_ROOT",
        "OSKH_PERIOD_1M_ROOT", "OSKH_AUTHORITY_HINT_ROOT",
    ) if os.environ.get(key)}


def parser():
    return _shared.parser(default_symbols=DEFAULT_SYMBOLS)


def safe_output(path, sources):
    return _shared.safe_output(path, sources, protected_roots=_configured_lake_roots())


def main(argv=None):
    return _shared.main(argv, repo_root=_BT_REPO_ROOT,
                        protected_roots=_configured_lake_roots(), default_symbols=DEFAULT_SYMBOLS)


if __name__ == "__main__":
    raise SystemExit(main())
