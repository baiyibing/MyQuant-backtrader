"""Strict, read-only front EOD input for the opt-in strategy 11 domain fix.

Execution bars are never replaced or adjusted here.  The legacy daily loader
remains unchanged; this path checks original parquet rows before its de-dup or
zero-volume filtering could conceal a missing signal observation.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from common.infra.data_root import resolve_period_root
from oskh_data.symbol_format import to_partition_key

OHLC = ("open", "high", "low", "close")


class S11ExitDomainError(ValueError):
    """An ON signal input cannot satisfy the daily observation contract."""


def _ymd(value) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def _error(code, domain, path, message, day=None) -> S11ExitDomainError:
    return S11ExitDomainError(
        f"s11 exit domain: code={code} date={_ymd(day) if day is not None else 'unknown'} "
        f"domain={domain} path={path}: {message}"
    )


def _checked_frame(frame, *, code, domain, path, end) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise _error(code, domain, path, "missing bars")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise _error(code, domain, path, "daily bars require DatetimeIndex")
    if frame.index.hasnans or frame.index.tz is not None:
        raise _error(code, domain, path, "invalid daily dates; expected naive UTC dates")
    # A simulation prefix does not inspect later prices or count them as history.
    frame = frame.loc[frame.index <= pd.Timestamp(end)]
    if frame.empty:
        raise _error(code, domain, path, "missing bars through requested end")
    non_daily = frame.index != frame.index.normalize()
    if non_daily.any():
        raise _error(code, domain, path, "non-normalized daily date", frame.index[non_daily][0])
    duplicate = frame.index.duplicated(keep=False)
    if duplicate.any():
        raise _error(code, domain, path, "duplicate daily date", frame.index[duplicate][0])
    if not frame.index.is_monotonic_increasing:
        raise _error(code, domain, path, "daily dates must be sorted")
    if "close" not in frame.columns:
        raise _error(code, domain, path, "missing close column")
    columns = [name for name in OHLC if name in frame.columns]
    try:
        values = frame.loc[:, columns].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise _error(code, domain, path, "nonnumeric price") from exc
    bad = (~np.isfinite(values) | (values <= 0)).any(axis=1)
    if bad.any():
        raise _error(code, domain, path, "nonfinite or nonpositive price", frame.index[bad][0])
    if all(name in frame.columns for name in OHLC):
        op, high, low, close = (frame[name].to_numpy(dtype=float) for name in OHLC)
        invalid = (high < np.maximum(op, close)) | (low > np.minimum(op, close)) | (low > high)
        if invalid.any():
            raise _error(code, domain, path, "invalid OHLC range", frame.index[invalid][0])
    return frame


def _same_dates(raw, front, *, code, raw_path, front_path) -> None:
    missing = raw.index.difference(front.index)
    extra = front.index.difference(raw.index)
    if len(missing):
        raise _error(code, "front", front_path, f"missing raw observation/history from {raw_path}", missing[0])
    if len(extra):
        raise _error(code, "none", raw_path, f"date conflict: front-only observation in {front_path}", extra[0])


def validate_signal_bars(
    raw_bars: Mapping[str, pd.DataFrame],
    signal_bars_front: Mapping[str, pd.DataFrame],
    *,
    start,
    end,
    required_codes: Iterable[str] | None = None,
) -> None:
    """Check the supplied simulation prefix, including its actual warmup rows.

    No minimum history length is manufactured: fewer than five shared rows are
    valid and keep the original FSM's insufficient-SMA behavior.  ``start`` is
    the trading or load start, not a license to discard supplied warmup history.
    """
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("s11 exit domain: start must not be after end")
    if not isinstance(signal_bars_front, Mapping):
        raise _error("<all>", "front", "<memory>", "signal_bars_front mapping is required")
    codes = set(raw_bars) | set(signal_bars_front) | set(required_codes or ())
    for code in sorted(codes):
        raw = _checked_frame(raw_bars.get(code), code=code, domain="none", path="<memory>", end=end)
        front = _checked_frame(
            signal_bars_front.get(code), code=code, domain="front", path="<memory>", end=end
        )
        _same_dates(raw, front, code=code, raw_path="<memory>", front_path="<memory>")


def _read_partition(code: str, path: Path, *, domain: str, start, end):
    if not path.is_file():
        raise FileNotFoundError(f"s11 exit domain: code={code} domain={domain} missing partition: {path}")
    try:
        # Hash the exact bytes consumed, so a concurrent atomic replacement
        # cannot result in a manifest hash from a different file version.
        payload = path.read_bytes()
        table = pq.read_table(io.BytesIO(payload))
        missing = {"time", *OHLC} - set(table.column_names)
        if missing:
            raise _error(code, domain, path, f"missing columns: {sorted(missing)}")
        stamps = pd.to_datetime(table["time"].to_numpy(), unit="ms", utc=True)
        if stamps.hasnans:
            raise _error(code, domain, path, "invalid source timestamp")
        dates = stamps.tz_localize(None).normalize()
        columns = list(OHLC) + (["volume"] if "volume" in table.column_names else [])
        frame = pd.DataFrame({key: table[key].to_numpy() for key in columns}, index=dates)
        frame = frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index <= pd.Timestamp(end))]
        # Physical parquet ordering is not a semantic date order, but repeated
        # daily observations are rejected rather than silently keep-last.
        frame = _checked_frame(frame.sort_index(), code=code, domain=domain, path=path, end=end)
        if "volume" in frame:
            volume = frame["volume"].to_numpy(dtype=float)
            bad = ~np.isfinite(volume) | (volume < 0)
            if bad.any():
                raise _error(code, domain, path, "invalid volume", frame.index[bad][0])
            effective = frame.loc[volume != 0, list(OHLC)].astype(float)
        else:
            effective = frame.loc[:, list(OHLC)].astype(float)
        source = {
            "code": code, "path": str(path), "sha256": hashlib.sha256(payload).hexdigest(),
            "rows": len(frame), "effective_rows": len(effective),
        }
        return frame, effective, source
    except S11ExitDomainError:
        raise
    except Exception as exc:
        raise _error(code, domain, path, "failed to read daily partition") from exc


def _sources_hash(sources: list[dict]) -> str:
    identity = [{"code": row["code"], "sha256": row["sha256"]} for row in sources]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()


def load_signal_bars_front(
    raw_bars: Mapping[str, pd.DataFrame],
    codes: Iterable[str],
    start,
    end,
    *,
    daily_root: Path | str | None = None,
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Load both actual source partitions and fail before any trading starts."""
    base = Path(daily_root) if daily_root is not None else resolve_period_root("1d")
    for domain in ("none", "front"):
        if not (base / f"dividend_type={domain}").is_dir():
            raise FileNotFoundError(f"s11 exit domain: missing {domain} daily directory: {base / f'dividend_type={domain}'}")
    front_bars = {}
    raw_sources, front_sources = [], []
    for code in sorted(set(codes) | set(raw_bars)):
        paths = {domain: base / f"dividend_type={domain}" / f"symbol={to_partition_key(code)}" / "data.parquet"
                 for domain in ("none", "front")}
        raw_full, raw, raw_source = _read_partition(code, paths["none"], domain="none", start=start, end=end)
        front_full, front, front_source = _read_partition(code, paths["front"], domain="front", start=start, end=end)
        _same_dates(raw_full, front_full, code=code, raw_path=paths["none"], front_path=paths["front"])
        _same_dates(raw, front, code=code, raw_path=paths["none"], front_path=paths["front"])
        consumed = _checked_frame(raw_bars.get(code), code=code, domain="none", path=paths["none"], end=end)
        _same_dates(raw, consumed, code=code, raw_path=paths["none"], front_path="<consumed raw>")
        if not all(name in consumed for name in OHLC):
            raise _error(code, "none", paths["none"], "consumed raw bars missing OHLC columns")
        if not np.array_equal(raw.loc[:, list(OHLC)].to_numpy(), consumed.loc[:, list(OHLC)].to_numpy()):
            raise _error(code, "none", paths["none"], "raw snapshot conflict: consumed prices differ from source")
        front_bars[code] = front
        raw_sources.append(raw_source)
        front_sources.append(front_source)
    validate_signal_bars(raw_bars, front_bars, start=start, end=end, required_codes=codes)
    return front_bars, {
        "daily_root": str(base), "loaded_start": _ymd(start), "loaded_end": _ymd(end),
        "raw_sources": raw_sources, "front_sources": front_sources,
        "raw_sources_sha256": _sources_hash(raw_sources),
        "front_sources_sha256": _sources_hash(front_sources),
        "snapshot_validation": "paired_dates_and_consumed_raw; upstream_version_identity_unverified",
    }


def build_run_metadata(
    *, enabled: bool, execution_domain: str, daily_source: str,
    minute_source: str | None = None, exdiv, source_metadata=None, raw_bars=None,
) -> dict:
    """Outer run/manifest metadata only; even OFF performs no extra source read."""
    reference_policy = (
        "legacy_none_reference_map"
        if exdiv is not None
        else "legacy_unmapped"
    )
    result = {
        "fix_s11_exit_domain": bool(enabled),
        "entry_signal_domain": "front",
        "entry_signal_provenance": "version11_exporter_contract; external_pool_provenance_required",
        "exit_signal_domain": "front" if enabled else "legacy_execution_bars",
        "exit_sma_includes_today": True,
        "exit_signal_clock": "EOD",
        "pending_fill_clock": "next_available_open",
        "fill_domain": execution_domain,
        "mark_domain": execution_domain,
        "daily_source": daily_source,
        "minute_source": minute_source,
        "signal_exdiv_remap": False if enabled else bool(exdiv),
        "execution_reference_policy": reference_policy,
        "execution_reference_loader_called": exdiv is not None,
        "execution_reference_map_loaded": bool(exdiv),
        "sources": source_metadata,
        "validation_scope": "framework_only; X-08_exporter_unverified; Slice_D_incomplete",
    }
    if raw_bars is not None:
        digest = hashlib.sha256()
        for code, frame in sorted(raw_bars.items()):
            digest.update(str(code).encode("utf-8"))
            digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes())
        result["consumed_execution_bars_sha256"] = digest.hexdigest()
    return result
