"""Lock MyQuant-backtrader trade_decision.presets against OSkhQuant1.3.

MyQuant-backtrader keeps a **research copy** of ``trade_decision/presets.py``.
It must not silently drift from the trading-stack SSOT in sibling OSkhQuant1.3
(or ``OSKH_TRADING_REPO``). The pinned fixture makes local drift detectable when
that sibling is absent; when present, the test also compares both files directly.

The fixture is only a record of one checked upstream commit, not proof that this
copy matches the latest upstream. See ``CONTRIBUTING.md`` for refresh steps.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LOCAL_PRESETS = REPO / "trade_decision" / "presets.py"
BASELINE = REPO / "tests" / "fixtures" / "presets_cross_repo_baseline.json"


def _sha256(path: Path) -> str:
    # 行尾归一（CRLF→LF）：基线按仓内 LF blob 哈希 pin（CONTRIBUTING.md 刷新口径），
    # Windows autocrlf checkout 会把工作树写成 CRLF，字节级比较必然假红。
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def test_local_presets_match_pinned_trading_repo_baseline():
    """Catch local preset drift even when the trading repository is absent.

    行尾归一后比较：内容（而非 EOL）才是契约。
    """
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    expected = baseline["presets_sha256"]
    actual = _sha256(LOCAL_PRESETS)
    assert actual == expected, (
        "trade_decision/presets.py drifted from the pinned OSkhQuant1.3 baseline.\n"
        f"  local={LOCAL_PRESETS} sha256={actual}\n"
        f"  baseline={BASELINE} sha256={expected}\n"
        f"  upstream_commit={baseline['upstream_commit']}\n"
        "Synchronize the preset contract intentionally, then refresh the baseline "
        "using CONTRIBUTING.md."
    )


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
    """Assert research copy bytes == 1.3 presets when sibling exists.

    同样按 LF 归一后比较：本地 CRLF checkout × 兄弟仓 LF（或反之）不构成漂移。
    """
    sibling = _sibling_presets()
    if sibling is None:
        pytest.skip(
            "sibling trading repo presets.py not found "
            "(set OSKH_TRADING_REPO or place OSkhQuant1.3 at /workspace/OSkhQuant1.3)"
        )
    local = LOCAL_PRESETS.read_bytes().replace(b"\r\n", b"\n")
    remote = sibling.read_bytes().replace(b"\r\n", b"\n")
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
