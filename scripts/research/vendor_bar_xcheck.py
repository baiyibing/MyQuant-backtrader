"""BT entry for infra's read-only vendor comparison; sample PASS is not delta5/R4."""
from pathlib import Path

from myquant_infra.adapters.vendor_bars import compare as _shared
from myquant_infra.adapters.vendor_bars.compare import (
    FIELDS, KEYS, compare, parser, read_bars,
)

_BT_REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    return _shared.main(argv, repo_root=_BT_REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
