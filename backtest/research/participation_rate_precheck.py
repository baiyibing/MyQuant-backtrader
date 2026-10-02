"""P2-B shell precheck for opt-in ``participation_rate`` (CLI / adapter / loader exit).

Landing only: argparse-after-parse, loader exit, thin adapter. **Does not** change
``simulate``, MatchCore, Fees, VolumeCap formula/clamp, or completed-bucket
definition in ``csv_minute_volume.completed_minute_volumes``.

Acceptance tag: **≠δ5 certified ≠R4**. Passing this precheck must **not** be read as
capacity certified, δ5 certified, or R4 authorization.

When ``participation_rate is None`` (omitted arm): every public entry is a no-op so
the old arm stays byte-identical at this layer.

Import fence: this module must stay **pandas-free** so L2 synthetic CLI
(``python -I -S``) can call the rate shell without pulling lake/pandas.
"""

from __future__ import annotations

from numbers import Integral
from typing import Mapping

from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap, VolumeKey

# Keep in lockstep with csv_minute_volume.UNIT (do not import that module here).
UNIT = "raw_shares_incremental"

# Mirrors the continuous hm filter inside completed_minute_volumes (read-only
# assertion surface). Do not treat this as a second completed-bucket definition.
COMPLETED_BUCKET_HM_RANGES: tuple[tuple[int, int], ...] = ((571, 690), (781, 900))
NO_CAPACITY_HM = frozenset({570, 780})  # 09:30 auction / 13:00 open — no capacity


def precheck_cli_participation_rate(
    participation_rate: float | None,
    *,
    minute_source: str = "lake",
    qlib_1min_root=None,
    dividend_type: str = "none",
    tail_window_buy: bool = False,
    tail_volume_unit: str | None = "shares",
) -> None:
    """Fail-closed CLI/adapter shell checks. No-op when rate is omitted/None."""
    if participation_rate is None:
        return
    # Same finite-[0,1] contract as csv_minute_volume.validate_participation_rate
    # (VolumeCap ctor), without importing pandas via csv_minute_volume.
    VolumeCap(participation_rate, None)
    if minute_source != "lake" or qlib_1min_root is not None or dividend_type != "none":
        raise ValueError("participation_rate requires raw lake minute volume in shares")
    if tail_window_buy and tail_volume_unit != "shares":
        raise ValueError("participation_rate requires shares, not tail volume lots")


def precheck_source_pin_unit(source: Mapping) -> None:
    """Loader-exit: PIN must attest raw shares with no runtime unit conversion."""
    if source.get("unit") != UNIT or source.get("transformations") != []:
        raise ValueError(
            "source PIN must declare raw shares; no runtime conversions"
        )


def precheck_completed_bucket_samples(
    samples: Mapping[VolumeKey, BucketVolume],
) -> None:
    """Loader-exit: samples only on completed continuous hm with attested unit.

    Does **not** invent missing keys (VolumeCap remains fail-closed). Does **not**
    redefine which hm ``completed_minute_volumes`` emits — only asserts the
    already-built map matches the frozen contract.
    """
    for key, sample in samples.items():
        if not (isinstance(key, tuple) and len(key) == 3):
            raise ValueError(f"invalid volume key: {key!r}")
        code, day, hm = key
        if not isinstance(hm, Integral) or isinstance(hm, bool):
            raise ValueError(f"invalid completed-bucket hm: {code} {day} {hm}")
        hm_i = int(hm)
        if hm_i in NO_CAPACITY_HM:
            raise ValueError(
                f"auction/open hm provides no capacity (completed-bucket precheck): "
                f"{code} {day} {hm_i}"
            )
        if not any(lo <= hm_i <= hi for lo, hi in COMPLETED_BUCKET_HM_RANGES):
            raise ValueError(
                f"out-of-session completed-bucket key: {code} {day} {hm_i}"
            )
        if not isinstance(sample, BucketVolume):
            raise ValueError(
                f"completed-bucket sample must be BucketVolume: {code} {day} {hm_i}"
            )
        if sample.unit != UNIT:
            raise ValueError(
                f"BucketVolume.unit must be {UNIT}: {code} {day} {hm_i}"
            )
