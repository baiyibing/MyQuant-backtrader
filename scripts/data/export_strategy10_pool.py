#!/usr/bin/env python3
"""Strategy 10 CLI: same exporter as ``export_ta_pool.py`` (source B)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data.export_ta_pool import main  # noqa: E402

__all__ = ["REPO_ROOT", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
