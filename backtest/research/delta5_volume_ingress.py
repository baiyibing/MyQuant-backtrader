"""Synthetic-only δ5 ingress v1. No lake reader, certification, or disk cache.

The explicit fixture evidence below describes an invented source, never a vendor
attestation. Real sources need a separately authorized reader and certification.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType

import pandas as pd

from backtest.research.ashare_volume_cap import BucketVolume

UNIT = "raw_shares_incremental"
MAPPING_VERSION = "d5_synthetic_mapping_v1"
CLOSE_MINUTES = (*range(571, 691), *range(781, 901))


class IngressError(ValueError):
    """Propagates through VolumeCap (which only catches LookupError)."""

    def __init__(self, stage, detail):
        self.stage, self.detail = stage, detail
        super().__init__(f"{stage}: {detail}")


def require(condition, stage, detail):
    if not condition:
        raise IngressError(stage, detail)


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def session(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{8}", value), "calendar", value)
    try:
        return pd.to_datetime(value, format="%Y%m%d")
    except ValueError as exc:
        raise IngressError("calendar", value) from exc


def decode_time(value, encoding):
    require(isinstance(value, str), "time", "explicit timestamp string required")
    try:
        ts = pd.Timestamp(value)
        require(not pd.isna(ts), "time", "NaT")
        if encoding == "local_wall":
            require(ts.tzinfo is None, "time", "local_wall must be naive")
        else:
            require(ts.tzinfo is not None and ts.utcoffset().total_seconds() == 0,
                    "time", "UTC container requires explicit UTC offset")
            ts = (ts.tz_convert("Asia/Shanghai").tz_localize(None)
                  if encoding == "utc_instant" else ts.tz_localize(None))
        return ts
    except (ValueError, TypeError) as exc:
        raise IngressError("time", str(exc)) from exc


def shares(value, float_exact):
    # Even a losslessly represented integral float must be converted to int.
    require(type(value) in (int, float), "volume", "non-bool number required")
    if type(value) is float:
        require(float_exact is True and math.isfinite(value) and value.is_integer()
                and abs(value) <= 2**53 - 1, "volume", "no lossless integer-share proof")
    require(value >= 0, "volume", "negative shares")
    return int(value)


def prices(row):
    values = [row.get(k) for k in ("open", "high", "low", "close")]
    require(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values),
            "prices", "OHLC must be finite positive raw prices")
    o, h, l, c = values
    require(l <= min(o, c) <= max(o, c) <= h, "prices", "inconsistent OHLC")
    return dict(zip(("open", "high", "low", "close"), map(float, values)))


def frame_payload(frames):
    return {code: {"index": [t.isoformat() for t in frame.index],
                   "columns": list(frame.columns),
                   "dtypes": [str(t) for t in frame.dtypes],
                   "data": frame.to_numpy().tolist()}
            for code, frame in sorted(frames.items())}


def map_payload(samples):
    return [[*key, None if value is None else
             [value.shares, value.available_at, value.unit]]
            for key, value in sorted(samples.items())]


class FrozenProvider:
    def __init__(self, samples, *, forbidden=False):
        self.samples = MappingProxyType(dict(samples))
        self.calls = []
        self.forbidden = forbidden

    def __call__(self, symbol, day, hm):
        key = (symbol, day, hm)
        self.calls.append(key)
        if self.forbidden:
            raise IngressError("provider", "cap-off queried provider")
        if key not in self.samples:
            raise IngressError("provider", f"unregistered key {key}")
        return self.samples[key]


@dataclass
class Inputs:
    minute: dict
    daily: dict
    pool: dict
    names: dict
    samples: dict
    start: str
    end: str
    audit: dict

    def canonical(self):
        return {"minute": frame_payload(self.minute), "daily": frame_payload(self.daily),
                "pool": self.pool, "names": self.names, "samples": map_payload(self.samples),
                "start": self.start, "end": self.end}


def normalize(source):
    """Preflight raw fixture records before any deduplication or API invocation."""
    try:
        return _normalize(source)
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise IngressError("schema", str(exc)) from exc


def _normalize(s):
    require(s["kind"] == "synthetic", "source", "certified-real is NOT_RUN / unsupported")
    require(s["schema"] == "d5_synthetic_source_v1" and s["publisher"] and s["snapshot_id"],
            "source", "missing source identity")
    require(s["unit"] == UNIT and s["price_domain"] == "raw"
            and s["incremental"] is True, "source", "raw incremental shares required")
    require(s["label"] in ("START", "END"), "time", "unknown label")
    require(s["time_encoding"] in ("local_wall", "utc_instant", "utc_wall"),
            "time", "unknown encoding")
    require(s["interval_policy"] == "physical_one_minute_no_auction_duplication",
            "time", "special/auction interval proof required")
    require(s["availability_rule"] == "explicit_record_publication_time",
            "time", "availability proof required; close/mtime alone is insufficient")
    require(bool(s["evidence_id"]), "source", "synthetic evidence id required")
    start, end, reference = s["start"], s["end"], s["reference_day"]
    for day in (start, end, reference, *s["calendar"]):
        session(day)
    calendar = s["calendar"]
    require(calendar == sorted(set(calendar)) and calendar == [reference, *s["sessions"]]
            and reference < start <= end and s["sessions"][0] == start
            and s["sessions"][-1] == end, "coverage", "calendar/window/reference mismatch")
    require(s["no_events"] == {"start": reference, "end": end, "events": [],
                                "evidence_id": s["evidence_id"]},
            "coverage", "no-event evidence must cover reference through end")
    instruments = s["instruments"]
    codes = [v["engine_symbol"] for v in instruments.values()]
    require(codes and len(codes) == len(set(codes)), "symbols", "empty/colliding mapping")
    names = {}
    for instrument in instruments.values():
        code = instrument["engine_symbol"]
        session(instrument["listed_from"])
        session(instrument["listed_through"])
        require(re.fullmatch(r"(?:60\d{4}\.SH|00\d{4}\.SZ)", code)
                and instrument["board"] == "mainboard" and instrument["ordinary"] is True
                and instrument["is_st"] is False and instrument["name"]
                and "ST" not in instrument["name"].upper()
                and instrument["listed_from"] <= reference
                and instrument["listed_through"] >= end,
                "symbols", f"inapplicable or unproved instrument {code}")
        names[code] = instrument["name"]
    status = s["status"]
    require(set(status) == set(instruments), "coverage", "status universe mismatch")
    for symbol in instruments:
        require(set(status[symbol]) == set(s["sessions"])
                and set(status[symbol].values()) <= {"active", "suspended"},
                "coverage", f"missing lifecycle/suspension evidence {symbol}")

    samples, rows, timestamps, previous, projections = {}, {}, {}, {}, []
    for row in s["minute"]:
        symbol = row["symbol"]
        require(symbol in instruments, "symbols", f"unknown symbol {symbol}")
        code = instruments[symbol]["engine_symbol"]
        begin, close, label, publication = [decode_time(row[k], s["time_encoding"])
                                            for k in ("begin", "end", "timestamp", "available_at")]
        require(begin == begin.floor("min") and close == close.floor("min")
                and close - begin == pd.Timedelta(minutes=1), "time", "not a physical minute")
        hm, day = close.hour * 60 + close.minute, close.strftime("%Y%m%d")
        require(begin.date() == close.date() and hm in CLOSE_MINUTES,
                "time", f"outside session physical interval {begin}/{close}")
        require(label == (begin if s["label"] == "START" else close),
                "time", "label does not identify physical interval")
        require(day in s["sessions"], "coverage", f"outside frozen window {day}")
        require(publication >= close, "availability", "publication before close")
        projected = publication.ceil("min")
        require(projected.date() == close.date(), "availability", "cross-session publication")
        available = projected.hour * 60 + projected.minute
        key = code, day, hm
        require(key not in samples, "coverage", f"duplicate bucket {key}")
        require(code not in previous or close > previous[code], "coverage", f"unordered/overlap {key}")
        previous[code] = close
        quantity = shares(row["volume"], s["float_exact"])
        require(row["volume_state"] == ("zero" if quantity == 0 else "positive"),
                "volume", f"missing/contradictory zero status {key}")
        require(status[symbol][day] != "suspended" or quantity == 0,
                "coverage", f"suspended with positive volume {key}")
        rows.setdefault(code, []).append({**prices(row), "ymd": day, "hm": hm})
        timestamps.setdefault(code, []).append(close)
        samples[key] = BucketVolume(int(quantity), available, UNIT)
        projections.append({"key": list(key), "original": row["available_at"],
                            "available_at": available})

    gaps, suspensions = [], []
    for symbol, instrument in instruments.items():
        code = instrument["engine_symbol"]
        for day in s["sessions"]:
            missing = [(code, day, hm) for hm in CLOSE_MINUTES if (code, day, hm) not in samples]
            if status[symbol][day] == "suspended":
                suspensions.append({"code": code, "date": day, "absent_buckets": len(missing),
                                    "evidence_id": s["evidence_id"]})
                samples.update({key: None for key in missing})
            else:
                gaps.extend(missing)
    require(not gaps, "coverage", {"missing_buckets": gaps})
    minute = {code: pd.DataFrame(rows[code], index=pd.DatetimeIndex(timestamps[code]))
              for code in rows}  # No fabricated bars for suspended sessions.

    daily_rows, daily_dates = {}, {}
    for row in s["daily"]:
        require(row["symbol"] in instruments, "symbols", "unknown daily symbol")
        code = instruments[row["symbol"]]["engine_symbol"]
        day = row["day"]
        require(day in calendar and (code not in daily_dates or day > daily_dates[code][-1]),
                "coverage", f"unexpected/duplicate/unordered daily {code}/{day}")
        daily_rows.setdefault(code, []).append(prices(row))
        daily_dates.setdefault(code, []).append(day)
    daily_gaps = [(code, day) for code in codes for day in calendar
                  if day not in daily_dates.get(code, [])]
    require(not daily_gaps, "coverage", {"missing_reference_or_mark": daily_gaps})
    daily = {code: pd.DataFrame(daily_rows[code], index=pd.to_datetime(daily_dates[code]))
             for code in codes}
    pool = s["pool"]
    require(set(pool) <= set(s["sessions"]), "pool", "signal outside window")
    require(all(len(values) == len(set(values)) and set(values) <= set(codes)
                for values in pool.values()), "pool", "duplicate/unknown pool symbols")
    audit = {"mapping_version": MAPPING_VERSION, "source_kind": "synthetic",
             "source_certification": "NOT_RUN", "resolver": "not_applicable_synthetic",
             "source_identity": {k: s[k] for k in ("schema", "publisher", "snapshot_id", "evidence_id")},
             "evidence_origin": "explicit synthetic fixture assertions; no real-source certifier",
             "no_events": s["no_events"], "status_evidence": status,
             "requested_window": [start, end], "actual_window": [start, end],
             "reference_day": reference, "calendar": calendar,
             "expected_buckets": len(codes) * len(s["sessions"]) * len(CLOSE_MINUTES),
             "actual_buckets": len(s["minute"]), "gaps": [], "suspensions": suspensions,
             "zero_keys": [list(k) for k, v in samples.items() if v is not None and v.shares == 0],
             "availability_projection": projections, "symbol_mapping": instruments,
             "time_encoding": s["time_encoding"], "label": s["label"],
             "unit": s["unit"], "float_exact": s["float_exact"],
             "interval_policy": s["interval_policy"], "availability_rule": s["availability_rule"],
             "evidence_hash": digest({k: s[k] for k in
                                      ("evidence_id", "no_events", "status", "calendar", "instruments")}),
             "pool_hash": digest(pool), "names_hash": digest(names),
             "price_domain": "raw", "reference_and_mark": "same snapshot raw daily close",
             "limits": "existing book_limit_prices; qlib_limit_pct=None; names as registered"}
    result = Inputs(minute, daily, pool, names, samples, start, end, audit)
    result.audit["canonical_hash"] = digest(result.canonical())
    result.audit["frame_hash"] = digest(frame_payload(minute))
    result.audit["bucket_map_hash"] = digest(map_payload(samples))
    return result
