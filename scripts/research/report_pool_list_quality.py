#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI entry for H9/H16 pool list-quality reporter.

See ``backtest.research.pool_list_quality`` for the library API.

Usage:
    /workspace/vanna312/bin/python scripts/research/report_pool_list_quality.py \\
        --pool-dir path/to/pool
    /workspace/vanna312/bin/python scripts/research/report_pool_list_quality.py \\
        --pool-dir path/to/a --other-dir path/to/b --format json --top-n 10
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.pool_list_quality import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
