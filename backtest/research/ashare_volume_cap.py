"""Opt-in completed-minute capacity; no market-data reads or default rate.

Keys are (engine symbol, YYYYMMDD session, minute-of-day bucket close).
The caller attests raw-domain, incremental *share* volume via BucketVolume.unit.
available_at is the same session's minute-of-day when the completed bucket is
known. Whole-bucket use at its close is a completed-bar capacity approximation.
Open triggers cannot use that bar's completed capacity. No EOD volume fallback.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from numbers import Integral


@dataclass(frozen=True)
class BucketVolume:
    shares: int
    available_at: int
    unit: str  # must explicitly attest "raw_shares_incremental"


VolumeKey = tuple[str, str, int]
VolumeLookup = Mapping[VolumeKey, BucketVolume | None] | Callable[
    [str, str, int], BucketVolume | None
]


class VolumeCap:
    """One run's shared buy/sell budget. Clamp is read-only; book then consume.

    Samples are frozen on first lookup, including unavailable samples. Revisited
    buckets retain usage; a new bucket gets only its own budget, never carryover.
    None rate is represented by *no VolumeCap object* in production callers.
    """

    def __init__(self, participation_rate: float, volume_for_bucket: VolumeLookup | None):
        try:
            rate = Decimal(str(participation_rate))
        except InvalidOperation as exc:
            raise ValueError("participation_rate must be finite and in [0, 1]") from exc
        if not rate.is_finite() or not 0 <= rate <= 1:
            raise ValueError("participation_rate must be finite and in [0, 1]")
        # Integer ratio avoids both binary float and Decimal context rounding.
        self._numerator, self._denominator = rate.as_integer_ratio()
        self._lookup = volume_for_bucket
        self._samples: dict[VolumeKey, BucketVolume | None] = {}
        self.used: dict[VolumeKey, int] = {}

    def clamp(self, key: VolumeKey, at: int | None, wanted: int, *,
              buy: bool = False, atomic: bool = False) -> tuple[int, str]:
        """Return filled-eligible shares and a diagnostic for a zero allocation."""
        bucket = key[2]
        if (not isinstance(bucket, Integral) or isinstance(bucket, bool)
                or not 0 <= bucket < 1440 or not isinstance(at, Integral)
                or isinstance(at, bool) or not bucket <= at < 1440):
            return 0, "skip_volume_unavailable:bucket_not_completed"
        if key not in self._samples:
            try:
                sample = (self._lookup(*key) if callable(self._lookup)
                          else self._lookup.get(key) if self._lookup is not None else None)
            except LookupError:
                sample = None
            self._samples[key] = sample
        sample = self._samples[key]
        if not isinstance(sample, BucketVolume):
            return 0, "skip_volume_unavailable:missing_or_untyped"
        if sample.unit != "raw_shares_incremental":
            return 0, "skip_volume_unavailable:unit"
        if (not isinstance(sample.shares, Integral) or isinstance(sample.shares, bool)
                or sample.shares < 0):
            return 0, "skip_volume_unavailable:invalid_shares"
        if (not isinstance(sample.available_at, Integral) or isinstance(sample.available_at, bool)
                or not bucket <= sample.available_at < 1440 or sample.available_at > at):
            return 0, "skip_volume_unavailable:available_at"
        budget = self._numerator * int(sample.shares) // self._denominator
        remaining = max(0, budget - self.used.get(key, 0))
        if atomic and wanted > remaining:
            return 0, "skip_volume_cap:atomic_exit"
        filled = min(wanted, remaining)
        if buy:
            filled = filled // 100 * 100
        return filled, "" if filled else "skip_volume_cap:zero_or_exhausted"

    def consume(self, key: VolumeKey, shares: int) -> None:
        """Call only after a successful booked fill, with its actual share count."""
        if shares <= 0:
            raise ValueError("only positive booked fills consume volume")
        self.used[key] = self.used.get(key, 0) + shares
