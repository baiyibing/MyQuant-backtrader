"""Lock MyQuant-backtrader trade_decision.presets against OSkhQuant1.3.

MyQuant-backtrader keeps a **research copy** of ``trade_decision/presets.py``.
It must not silently drift from the trading-stack SSOT in sibling OSkhQuant1.3
(or ``OSKH_TRADING_REPO``). When the sibling tree is absent, the test skips.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LOCAL_PRESETS = REPO / "trade_decision" / "presets.py"


def _sibling_presets() -> Path | None:
    env = os.environ.get("OSKH_TRADING_REPO", "").strip()
    if env:
        p = Path(env) / "trade_decision" / "presets.py"
        return p if p.is_file() else None
    default = Path("/workspace/OSkhQuant1.3/trade_decision/presets.py")
    if default.is_file():
        return default
    # common sibling checkout next to this repo
    alt = REPO.parent / "OSkhQuant1.3" / "trade_decision" / "presets.py"
    return alt if alt.is_file() else None


def test_presets_bytes_match_trading_repo_when_present():
    """Assert research copy bytes == 1.3 presets when sibling exists."""
    sibling = _sibling_presets()
    if sibling is None:
        pytest.skip(
            "sibling trading repo presets.py not found "
            "(set OSKH_TRADING_REPO or place OSkhQuant1.3 at /workspace/OSkhQuant1.3)"
        )
    local = LOCAL_PRESETS.read_bytes()
    remote = sibling.read_bytes()
    if local == remote:
        return
    local_h = hashlib.sha256(local).hexdigest()[:16]
    remote_h = hashlib.sha256(remote).hexdigest()[:16]
    pytest.fail(
        "trade_decision/presets.py drifted from trading-stack copy.\n"
        f"  local={LOCAL_PRESETS} sha256={local_h}\n"
        f"  sibling={sibling} sha256={remote_h}\n"
        "Research copy must stay in sync with OSkhQuant1.3 (or update both)."
    )
