"""Read-only, fail-closed front -> session-D raw price context for s12.

This adapter changes units, never holdings or cash.  The automatic lake path is
intentionally narrow: one constant proportional transform identified by an
informative pre-session bar. Changing/affine transforms need a hash-bound
certificate. No vendor formula is inferred from a day's unfinished H/L/C.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from common.infra.data_root import resolve_period_root, resolve_source_parquet
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key

from backtest.research.ma_infra import sma_asof
from backtest.research.market_layer import as_datetime, utc_ms_range

OHLC = ("open", "high", "low", "close")
TOLERANCE = Decimal("1e-10")
VALIDATION_VERSION = "s12-price-domain-v1"
_VALIDATED_CONTEXT = object()


class PriceDomainError(ValueError):
    """An input or reconstruction certificate cannot establish the domain."""


def _fail(message, *, code="*", day="*", domain="*", path="<memory>"):
    raise PriceDomainError(
        f"s12 price domain: code={code} date={day} domain={domain} path={path}: {message}"
    )


def _decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PriceDomainError(f"invalid price/transform value {value!r}") from exc
    if not result.is_finite():
        raise PriceDomainError(f"non-finite price/transform value {value!r}")
    return result


def _same(left, right):
    return abs(_decimal(left) - _decimal(right)) <= TOLERANCE


def _day(value):
    return pd.Timestamp(value).strftime("%Y%m%d")


def _stamp(value):
    return pd.Timestamp(value).normalize()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frame_sha256(frame):
    """Stable identity without pandas' version-dependent CSV serialization."""
    rows = [[pd.Timestamp(index).isoformat(), *[str(v) for v in values]]
            for index, values in zip(frame.index, frame.itertuples(index=False, name=None))]
    payload = {"columns": list(frame.columns), "rows": rows}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def build_source_metadata(front_daily, raw_daily, minute_bars, *,
                          source_snapshot_id, provenance):
    """Declare domains and frozen identities; this does not certify A/B values."""
    return {
        "daily_signal_domain": "front", "raw_daily_domain": "none",
        "minute_fill_domain": "none", "source_snapshot_id": source_snapshot_id,
        "provenance": dict(provenance),
        "source_hashes": {
            domain: {code: frame_sha256(frame) for code, frame in frames.items()}
            for domain, frames in (("front", front_daily), ("raw", raw_daily),
                                   ("minute", minute_bars))
        },
    }


def _validate_frame(frame, *, code, domain, path="<memory>", minute=False):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        _fail("missing or empty bars", code=code, domain=domain, path=path)
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is not None:
        _fail("expected timezone-naive UTC-contract DatetimeIndex", code=code,
              domain=domain, path=path)
    if frame.index.hasnans or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        _fail("NaT, duplicate or unsorted dates", code=code, domain=domain, path=path)
    if not minute and not frame.index.equals(frame.index.normalize()):
        _fail("daily index is not normalized", code=code, domain=domain, path=path)
    required = ("open", "high", "close") if minute else OHLC
    if not set(required).issubset(frame.columns):
        _fail(f"missing OHLC columns {required}", code=code, domain=domain, path=path)
    for index, row in frame.iterrows():
        try:
            values = {key: _decimal(row[key]) for key in OHLC if key in frame.columns}
        except PriceDomainError as exc:
            _fail(str(exc), code=code, day=_day(index), domain=domain, path=path)
        if any(value <= 0 for value in values.values()):
            _fail("non-positive OHLC", code=code, day=_day(index), domain=domain, path=path)
        if values["high"] + TOLERANCE < max(values["open"], values["close"]):
            _fail("high below open/close", code=code, day=_day(index), domain=domain, path=path)
        if "low" in values and values["low"] - TOLERANCE > min(values["open"], values["close"]):
            _fail("low above open/close", code=code, day=_day(index), domain=domain, path=path)
    if minute:
        for column, expected in (("ymd", frame.index.strftime("%Y%m%d")),
                                 ("hm", frame.index.hour * 60 + frame.index.minute)):
            if column in frame and list(frame[column]) != list(expected):
                _fail(f"minute {column} disagrees with timestamp", code=code,
                      domain=domain, path=path)


def _transform_map(transforms):
    if transforms is None:
        return {}
    if isinstance(transforms, Mapping):
        items = [dict(value, code=key[0], session=key[1])
                 for key, value in transforms.items()]
    else:
        items = transforms
    result = {}
    for row in items:
        key = (str(row["code"]), _day(row["session"]))
        if key in result:
            _fail("duplicate transform", code=key[0], day=key[1])
        a, b = _decimal(row["A"]), _decimal(row["B"])
        if a <= 0:
            _fail("A must be positive", code=key[0], day=key[1])
        result[key] = {**row, "A": a, "B": b}
    return result


@dataclass(frozen=True)
class DaySignalView:
    previous_signal_closes_in_raw_domain: tuple[float, ...]
    prev_ref_unrounded: Decimal | None
    prev_ref_raw: float | None


class S12PriceContext:
    """Frozen input copies and validated session transforms, with no writes."""

    def __init__(self, front_daily, raw_daily, minute_bars, transforms, metadata, *,
                 _validation_token=None):
        if _validation_token is not _VALIDATED_CONTEXT:
            _fail("use build_s12_price_context to construct a validated context")
        self._front_daily = {code: frame.copy(deep=True) for code, frame in front_daily.items()}
        self._raw_daily = {code: frame.copy(deep=True) for code, frame in raw_daily.items()}
        self._minute_bars = {code: frame.copy(deep=True) for code, frame in minute_bars.items()}
        self._transforms = deepcopy(transforms)
        self._metadata = deepcopy(metadata)

    @property
    def raw_daily(self):
        return {code: frame.copy(deep=True) for code, frame in self._raw_daily.items()}

    @property
    def metadata(self):
        return json.loads(json.dumps(self._metadata))

    def raw_path_for(self, code):
        return self._metadata.get("source_paths", {}).get("raw", {}).get(code, "<memory:raw>")

    def day_signal_view(self, code, day):
        key = (code, _day(day))
        if key not in self._transforms:
            _fail("missing session transform", code=code, day=key[1], domain="front/raw",
                  path=self.raw_path_for(code))
        transform = self._transforms[key]
        history = self._front_daily[code].loc[
            self._front_daily[code].index < _stamp(day), "close"]
        values = tuple((_decimal(v) - transform["B"]) / transform["A"] for v in history)
        if any(value <= 0 for value in values):
            _fail("non-positive reconstructed historical close", code=code, day=key[1])
        previous = values[-1] if values else None
        reference = (float(previous.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                     if previous is not None else None)
        if reference is not None and reference <= 0:
            _fail("non-positive rounded reference", code=code, day=key[1])
        return DaySignalView(tuple(float(v) for v in values), previous, reference)

    def previous_signal_closes_in_raw_domain(self, code, day):
        return list(self.day_signal_view(code, day).previous_signal_closes_in_raw_domain)

    def reference_price_for(self, code, day):
        return self.day_signal_view(code, day).prev_ref_raw

    def _validate_decision_precision(self, code, day, view):
        """Tolerance may accept representation noise, never a changed decision.

        Reconstruct a second history from declared transforms and raw observations
        only for this check; the signal history remains the real front input.
        Applying the D inverse here also catches error magnification at an event.
        """
        active = self._transforms[(code, _day(day))]
        raw = self._raw_daily[code]
        theoretical = []
        for previous, close in raw.loc[raw.index < day, "close"].items():
            source = self._transforms[(code, _day(previous))]
            front = source["A"] * _decimal(close) + source["B"]
            theoretical.append((front - active["B"]) / active["A"])
        if not theoretical:
            return
        reference = theoretical[-1].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if reference != _decimal(view.prev_ref_raw):
            _fail("input precision changes rounded session reference", code=code,
                  day=_day(day), domain="front/raw", path=self.raw_path_for(code))
        intended = [float(value) for value in theoretical]
        observed = list(view.previous_signal_closes_in_raw_domain)
        minute = self._minute_bars[code]
        quotes = minute.loc[minute.index.normalize() == day, ["open", "close"]].to_numpy().ravel()
        for window, multiplier in ((5, 1.), (10, 1.), (10, .90)):
            actual, expected = sma_asof(observed, window), sma_asof(intended, window)
            if actual is None or expected is None:
                continue
            actual, expected = actual * multiplier, expected * multiplier
            if any((price < actual) != (price < expected) for price in quotes):
                _fail("input precision crosses MA/stop decision boundary", code=code,
                      day=_day(day), domain="front/raw", path=self.raw_path_for(code))

    def validate_simulation(self, minute_bars, daily_bars, pool_days, start, end):
        scope = {code for values in pool_days.values() for code in values}
        if not scope.issubset(self._raw_daily):
            _fail(f"pool codes absent from frozen scope: {sorted(scope - self._raw_daily.keys())}")
        for domain, frames in (("raw", daily_bars), ("minute", minute_bars)):
            expected = self._metadata["source_hashes"][domain]
            if set(frames) != set(expected):
                _fail("simulation scope differs from frozen input", domain=domain)
            for code, frame in frames.items():
                if frame_sha256(frame) != expected[code]:
                    _fail("simulation input hash mismatch", code=code, domain=domain)
        first, last = _stamp(start), _stamp(end)
        for code, raw in self._raw_daily.items():
            minute_days = set(minute_bars[code].index.normalize())
            required = set(raw.index[(raw.index >= first) & (raw.index <= last)])
            missing = required - minute_days
            if missing:
                _fail("missing raw minute session", code=code, day=_day(min(missing)),
                      domain="minute", path=self._metadata.get("source_paths", {})
                      .get("minute", {}).get(code, "<memory>"))
            if any(day not in raw.index for day in minute_days if first <= day <= last):
                _fail("minute date has no paired daily bar", code=code, domain="raw")
            for day in required:
                self.day_signal_view(code, day)


def _validate_identities(front_daily, raw_daily, minute_bars, metadata):
    for key, expected in (("daily_signal_domain", "front"), ("raw_daily_domain", "none"),
                          ("minute_fill_domain", "none")):
        if metadata.get(key) != expected:
            _fail(f"explicit {key}={expected!r} declaration required")
    if not metadata.get("source_snapshot_id"):
        _fail("source_snapshot_id required")
    if set(front_daily) != set(raw_daily) or set(raw_daily) != set(minute_bars):
        _fail("front/raw/minute code coverage differs")
    if not raw_daily:
        _fail("empty code scope")
    for domain, frames in (("front", front_daily), ("raw", raw_daily), ("minute", minute_bars)):
        expected = metadata.get("source_hashes", {}).get(domain, {})
        if set(expected) != set(frames):
            _fail("source hash coverage differs", domain=domain)
        for code, frame in frames.items():
            path = metadata.get("source_paths", {}).get(domain, {}).get(code, "<memory>")
            _validate_frame(frame, code=code, domain=domain, path=path, minute=domain == "minute")
            if expected[code] != frame_sha256(frame):
                _fail("source hash mismatch", code=code, domain=domain, path=path)
    for code, raw in raw_daily.items():
        if not raw.index.equals(front_daily[code].index):
            missing = raw.index.symmetric_difference(front_daily[code].index)
            _fail("front/raw date coverage differs", code=code, day=_day(missing[0]),
                  domain="front/raw")


def _automatic_transforms(front_daily, raw_daily, start):
    result = {}
    for code, raw in raw_daily.items():
        front = front_daily[code]
        ratios = [_decimal(front.loc[day, "open"]) / _decimal(raw.loc[day, "open"])
                  for day in raw.index]
        anchor = ratios[0]
        if any(abs(value - anchor) > TOLERANCE for value in ratios):
            _fail("changing ratio requires an explicit price transform file", code=code)
        before = raw.loc[raw.index < _stamp(start)] if start else raw.iloc[:0]
        informative = any(max(_decimal(row[key]) for key in OHLC)
                          - min(_decimal(row[key]) for key in OHLC) > TOLERANCE
                          for _, row in before.iterrows())
        if not informative:
            _fail("B=0 not identifiable before first decision; provide transform evidence", code=code)
        for day, ratio in zip(raw.index, ratios):
            result[(code, _day(day))] = {"A": ratio, "B": Decimal(0)}
    return result


def _validate_pair_math(front_daily, raw_daily, transforms):
    required = {(code, _day(day)) for code, frame in raw_daily.items() for day in frame.index}
    if set(transforms) != required:
        _fail("transform dates/codes must exactly cover paired daily inputs")
    for code, raw in raw_daily.items():
        front = front_daily[code]
        for day in raw.index:
            transform = transforms[(code, _day(day))]
            for field in OHLC:
                expected = transform["A"] * _decimal(raw.loc[day, field]) + transform["B"]
                if not _same(expected, front.loc[day, field]):
                    _fail(f"A/B do not explain paired {field}", code=code, day=_day(day),
                          domain="front/raw")


def _available_before_open(value, session):
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        _fail("reference_available_at must have an explicit timezone", day=session)
    cutoff = pd.Timestamp(session + " 09:30:00", tz="Asia/Shanghai")
    if timestamp > cutoff:
        _fail("reference evidence available after first session decision", day=session)


def _evidence_rows(rows, label):
    result = {}
    for row in rows:
        key = (row["code"], _day(row["session"]))
        if key in result:
            _fail(f"duplicate {label} evidence", code=key[0], day=key[1])
        result[key] = row
    return result


def _validate_certificate(front_daily, raw_daily, transforms, provenance, evidence, snapshot):
    kind = provenance.get("kind")
    if kind == "synthetic_fixture":
        if provenance.get("algorithm") != "known_affine_fixture" or not provenance.get("anchor_version"):
            _fail("synthetic fixture requires known_affine_fixture and anchor_version")
        return "synthetic_math_only"
    if kind == "observed_constant_proportional":
        return "common_transform_only_full_pit_unverified"
    if kind not in ("pit", "exact_asof_reconstruction"):
        _fail("unsupported or missing transform provenance")
    if not provenance.get("algorithm") or not provenance.get("anchor_version"):
        _fail("algorithm and anchor_version required")
    if not evidence or evidence.get("source_snapshot_id") != snapshot or evidence.get("kind") != kind:
        _fail("certificate evidence snapshot/kind mismatch")
    if kind == "pit":
        views = _evidence_rows(evidence.get("views", []), "PIT view")
        if set(views) != set(transforms):
            _fail("PIT evidence must cover every transform session")
        for (code, session), transform in transforms.items():
            row = views[(code, session)]
            _available_before_open(row.get("reference_available_at"), session)
            if not row.get("source"):
                _fail("independent PIT view source required", code=code, day=session)
            history = front_daily[code].loc[front_daily[code].index < _stamp(session), "close"]
            declared = row.get("history", [])
            if len(declared) != len(history):
                _fail("incomplete independent PIT history", code=code, day=session)
            for (day, value), observed in zip(history.items(), declared):
                reconstructed = (_decimal(value) - transform["B"]) / transform["A"]
                if _day(observed["date"]) != _day(day) or not _same(reconstructed, observed["close"]):
                    _fail("independent PIT reconstruction differs", code=code, day=session)
        return "hash_bound_independent_pit_views"
    if not provenance.get("generated_at"):
        _fail("exact reconstruction requires generated_at")
    pd.Timestamp(provenance["generated_at"])
    anchor = evidence.get("common_anchor", {})
    scale, shift = _decimal(anchor.get("scale")), _decimal(anchor.get("shift"))
    if scale <= 0:
        _fail("common anchor scale must be positive")
    base_transforms = _transform_map(evidence.get("base_transforms", []))
    base_rows = _evidence_rows(evidence.get("base_front", []), "base front")
    if set(base_transforms) != set(transforms) or set(base_rows) != set(transforms):
        _fail("exact reconstruction base coverage differs")
    for key, transform in transforms.items():
        code, session = key
        if _day(transform.get("reconstructed_asof", "19000101")) != session:
            _fail("reconstructed_asof must equal session", code=code, day=session)
        base = base_transforms[key]
        if not _same(transform["A"], scale * base["A"]) or not _same(
                transform["B"], scale * base["B"] + shift):
            _fail("common anchor coefficients do not cancel", code=code, day=session)
        for field in OHLC:
            old = _decimal(base_rows[key][field])
            actual = front_daily[code].loc[_stamp(session), field]
            if not _same(actual, scale * old + shift):
                _fail("front history is not a common affine anchor transform", code=code,
                      day=session, domain="front")
            if not _same(old, base["A"] * _decimal(raw_daily[code].loc[_stamp(session), field]) + base["B"]):
                _fail("base transform does not explain raw bars", code=code, day=session)
    events = _evidence_rows(evidence.get("events", []), "event")
    for code, raw in raw_daily.items():
        prior = None
        for day in raw.index:
            key = (code, _day(day))
            current = base_transforms[key]
            if prior is not None and (current["A"], current["B"]) != (prior["A"], prior["B"]):
                event = events.get(key, {})
                if not event.get("source") or event.get("confirmed") is not True:
                    _fail("transform transition lacks confirmed event evidence", code=code, day=key[1])
                for field, value in (("from_A", prior["A"]), ("from_B", prior["B"]),
                                     ("to_A", current["A"]), ("to_B", current["B"])):
                    if not _same(event.get(field), value):
                        _fail("event transition coefficients differ", code=code, day=key[1])
                previous = front_daily[code].loc[front_daily[code].index < day, "close"].iloc[-1]
                active = transforms[key]
                reference = ((_decimal(previous) - active["B"]) / active["A"]).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                if not _same(reference, event.get("reference_raw")):
                    _fail("confirmed event reference differs", code=code, day=key[1])
            prior = current
    return "common_affine_certificate_full_pit_unverified"


def build_s12_price_context(front_daily, raw_daily, *, minute_bars, metadata,
                            transforms=None, start=None, evidence=None):
    """Validate explicitly declared frozen inputs; never infer their domains."""
    _validate_identities(front_daily, raw_daily, minute_bars, metadata)
    provenance = metadata.get("provenance", {})
    if provenance.get("kind") == "observed_constant_proportional":
        # Explicit coefficients do not exempt an automatic-path caller from
        # identifying B=0 on pre-decision data and proving a constant ratio.
        parsed = _automatic_transforms(front_daily, raw_daily, start)
        if transforms is not None:
            declared = _transform_map(transforms)
            if set(declared) != set(parsed) or any(
                    declared[key][field] != value[field]
                    for key, value in parsed.items() for field in ("A", "B")):
                _fail("explicit transforms disagree with observed constant proportional evidence")
    elif transforms is None:
        _fail("missing explicit transforms")
    else:
        parsed = _transform_map(transforms)
    _validate_pair_math(front_daily, raw_daily, parsed)
    pit_status = _validate_certificate(front_daily, raw_daily, parsed, provenance,
                                       evidence, metadata["source_snapshot_id"])
    model = "affine" if any(row["B"] != 0 for row in parsed.values()) else "multiplicative"
    output = dict(metadata)
    output.update({
        "fix_s12_price_domain": True, "daily_signal_domain": "front",
        "signal_comparison_domain": "raw_at_session_D", "minute_fill_domain": "none",
        "mark_domain": "none", "reference_adjustment": "asof_front_to_raw_once",
        "transform_model": model, "implicit_exdiv_map": False,
        "nav_comparability": "raw_accounting_only", "pit_anchor_validation": pit_status,
        "validation_version": VALIDATION_VERSION,
        "input_absolute_tolerance": str(TOLERANCE), "real_lake_precision_validated": False,
        "cache_policy": "bypass_legacy_window_cache",
    })
    context = S12PriceContext(front_daily, raw_daily, minute_bars, parsed, output,
                              _validation_token=_VALIDATED_CONTEXT)
    for code, frame in raw_daily.items():
        for day in frame.index:
            view = context.day_signal_view(code, day)
            context._validate_decision_precision(code, day, view)
    return context


def _read_strict(path, code, domain, start, end, *, minute=False):
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    if not path.is_file():
        _fail("missing parquet file", code=code, domain=domain, path=path)
    initial_hash = file_sha256(path)
    schema = pq.read_schema(path).names
    columns = ["time", *OHLC]
    if not set(columns).issubset(schema):
        _fail("missing time/OHLC parquet columns", code=code, domain=domain, path=path)
    if "volume" in schema:
        columns.append("volume")
    first, last = utc_ms_range(start, end)
    table = pq.read_table(path, columns=columns)
    if table["time"].null_count:
        _fail("null parquet time before window filtering", code=code, domain=domain, path=path)
    table = table.filter((pc.field("time") >= first) & (pc.field("time") <= last))
    if not table.num_rows:
        _fail("empty parquet window", code=code, domain=domain, path=path)
    index = pd.to_datetime(table["time"].to_numpy(), unit="ms", utc=True).tz_localize(None)
    if not minute:
        index = index.normalize()
    frame = pd.DataFrame({key: table[key].to_numpy() for key in columns if key != "time"}, index=index)
    if frame.index.has_duplicates:
        _fail("duplicate raw parquet dates before loader deduplication", code=code,
              domain=domain, path=path)
    frame = frame.sort_index()
    # A zero-volume or out-of-session row is still part of the frozen input;
    # reject corrupt prices before the legacy-compatible filtering below.
    _validate_frame(frame, code=code, domain=domain, path=path, minute=minute)
    if "volume" in frame:
        for value in frame["volume"]:
            if _decimal(value) < 0:
                _fail("negative volume", code=code, domain=domain, path=path)
    if file_sha256(path) != initial_hash:
        _fail("parquet changed while reading frozen snapshot", code=code, domain=domain, path=path)
    return frame, initial_hash


def _verified_json(path, expected_hash=None):
    path = Path(path)
    actual = file_sha256(path)
    if expected_hash is not None and actual != expected_hash:
        _fail("evidence file hash mismatch", path=path)
    result = json.loads(path.read_text(encoding="utf-8"))
    if file_sha256(path) != actual:
        _fail("JSON evidence changed during read", path=path)
    return result, actual


def _load_certificate(path, paths, hashes):
    document, manifest_hash = _verified_json(path)
    if document.get("schema_version") != 1:
        _fail("transform file requires schema_version=1", path=path)
    declared = document.get("sources", {})
    for domain, by_code in paths.items():
        if set(declared.get(domain, {})) != set(by_code):
            _fail("transform source coverage differs", domain=domain, path=path)
        for code, source_path in by_code.items():
            entry = declared[domain][code]
            if Path(entry.get("path", "")).resolve() != source_path.resolve() or entry.get("sha256") != hashes[domain][code]:
                _fail("transform source file identity mismatch", code=code, domain=domain, path=source_path)
    provenance = document.get("provenance", {})
    if provenance.get("kind") not in ("pit", "exact_asof_reconstruction"):
        _fail("lake transform file requires PIT or exact reconstruction evidence", path=path)
    descriptor = provenance.get("evidence_file", {})
    if not descriptor.get("path") or not descriptor.get("sha256"):
        _fail("hash-bound evidence_file required", path=path)
    evidence_path = Path(descriptor["path"])
    if not evidence_path.is_absolute():
        evidence_path = Path(path).parent / evidence_path
    evidence, evidence_hash = _verified_json(evidence_path, descriptor["sha256"])
    return document, evidence, manifest_hash, evidence_hash


def _validate_optional_factor(front, raw, paths_to_recheck):
    path = resolve_source_parquet("adj_factor.parquet")
    if not path.is_file():
        return None
    initial_hash = file_sha256(path)
    table = pd.read_parquet(path)
    required = {"date", "stock_code", "close_front", "close_none", "cumulative_adj_factor"}
    if not required.issubset(table.columns):
        _fail("factor file missing declared columns", domain="factor", path=path)
    table = table.copy()
    table["code"] = table["stock_code"].map(to_canonical_symbol)
    table["day"] = pd.to_datetime(table["date"].map(as_datetime)).dt.normalize()
    table = table[table["code"].isin(raw)]
    if table["day"].isna().any():
        _fail("missing factor date", domain="factor", path=path)
    if table.duplicated(["code", "day"]).any():
        _fail("duplicate factor date/code", domain="factor", path=path)
    for row in table.itertuples():
        if row.day not in raw[row.code].index:
            continue
        expected_raw = raw[row.code].loc[row.day, "close"]
        expected_front = front[row.code].loc[row.day, "close"]
        if not all((_same(row.close_none, expected_raw), _same(row.close_front, expected_front),
                    _same(row.cumulative_adj_factor, _decimal(expected_front) / _decimal(expected_raw)))):
            _fail("factor file does not match real paired closes", code=row.code,
                  day=_day(row.day), domain="factor", path=path)
    paths_to_recheck[path] = initial_hash
    return {"path": str(path), "sha256": initial_hash}


def load_s12_price_context(codes, start, end, *, load_start, transform_file=None):
    """Read configured lake partitions once, validate before any account action."""
    paths = {"front": {}, "raw": {}, "minute": {}}
    hashes = {key: {} for key in paths}
    frames = {key: {} for key in paths}
    recheck = {}
    daily_root, minute_root = resolve_period_root("1d"), resolve_period_root("1m")
    roots = {"front": daily_root / "dividend_type=front",
             "raw": daily_root / "dividend_type=none",
             "minute": minute_root / "dividend_type=none"}
    for code in sorted(codes):
        if to_canonical_symbol(code) != code:
            _fail("expected canonical code", code=code)
        for domain, root in roots.items():
            path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
            frame, digest = _read_strict(path, code, domain, load_start, end,
                                         minute=domain == "minute")
            paths[domain][code], hashes[domain][code] = path, digest
            frames[domain][code] = frame
            recheck[path] = digest
        front, raw = frames["front"][code], frames["raw"][code]
        if not front.index.equals(raw.index):
            missing = front.index.symmetric_difference(raw.index)
            _fail("raw parquet front/none dates differ before zero-volume filtering", code=code,
                  day=_day(missing[0]), domain="front/raw", path=paths["raw"][code])
        front_zero = front["volume"].eq(0) if "volume" in front else pd.Series(False, index=front.index)
        raw_zero = raw["volume"].eq(0) if "volume" in raw else pd.Series(False, index=raw.index)
        if not front_zero.equals(raw_zero):
            _fail("front/raw suspended-session flags differ", code=code, domain="front/raw")
        for domain in ("front", "raw"):
            frames[domain][code] = frames[domain][code].loc[~raw_zero, list(OHLC)].astype(float)
        minute = frames["minute"][code]
        hm = minute.index.hour * 60 + minute.index.minute
        minute = minute.loc[((hm >= 570) & (hm <= 690)) | ((hm >= 780) & (hm <= 900))].copy()
        if "volume" in minute:
            active = minute.groupby(minute.index.normalize())["volume"].transform("sum").ne(0)
            minute = minute.loc[active].drop(columns="volume")
        minute = minute.astype(float)
        minute["ymd"] = minute.index.strftime("%Y%m%d")
        minute["hm"] = minute.index.hour * 60 + minute.index.minute
        frames["minute"][code] = minute
    factor = _validate_optional_factor(frames["front"], frames["raw"], recheck)
    snapshot = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    provenance = {"kind": "observed_constant_proportional", "algorithm": "constant_paired_ohlc",
                  "anchor_version": VALIDATION_VERSION}
    transforms = evidence = None
    extra = {}
    if transform_file:
        document, evidence, manifest_hash, evidence_hash = _load_certificate(transform_file, paths, hashes)
        snapshot = document.get("source_snapshot_id")
        provenance, transforms = document["provenance"], document.get("transforms")
        extra = {"transform_metadata_sha256": manifest_hash, "transform_evidence_sha256": evidence_hash}
    metadata = build_source_metadata(frames["front"], frames["raw"], frames["minute"],
                                     source_snapshot_id=snapshot, provenance=provenance)
    metadata.update(extra)
    metadata.update({"source_paths": {domain: {code: str(path) for code, path in by_code.items()}
                                      for domain, by_code in paths.items()},
                     "source_file_hashes": hashes, "optional_factor": factor})
    context = build_s12_price_context(frames["front"], frames["raw"], minute_bars=frames["minute"],
                                      metadata=metadata, transforms=transforms, start=start, evidence=evidence)
    context.validate_simulation(frames["minute"], context.raw_daily, {}, start, end)
    for path, digest in recheck.items():
        if file_sha256(path) != digest:
            _fail("source changed during multi-file snapshot validation", path=path)
    return context, frames["minute"]
