"""Explicit Shanghai replay clock; no fee, price trigger or account arithmetic."""

from datetime import date, datetime, time, timedelta

from .types import (
    CalendarFacts, CancelOrder, ClockEvent, CompletedBucket, InstrumentFacts,
    LotPosition, MarkEvent, MarkPrice, Phase, RunContractError, RunInput,
    SessionBucket, Side, SubmitOrder, _require_id, _require_int,
)


def require_shanghai(value: datetime, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.utcoffset() is None
        or getattr(value.tzinfo, "key", getattr(value.tzinfo, "zone", None)) != "Asia/Shanghai"
    ):
        raise RunContractError(f"{name} must use the named Asia/Shanghai timezone")


def eligible(order: SubmitOrder, bucket: CompletedBucket, at: datetime) -> bool:
    """Only the completed bucket can match; expiry is right-open."""
    return (
        at == bucket.end
        and order.symbol == bucket.symbol
        and order.available_at <= order.submitted_at < bucket.start
        and order.effective_at <= bucket.start
        and at < order.expires_at
    )


def _tuple_of(values: tuple, kinds: tuple[type, ...], name: str) -> None:
    if type(values) is not tuple or any(type(v) not in kinds for v in values):
        raise RunContractError(f"{name} must be an explicit tuple of the declared values")


class Clock:
    """Validate calendar/identity/visibility and build a finite, stable schedule.

    Matching events are scheduled from timestamps only. A bucket's prices and
    volume reach the broker at its BUCKET event, never at order submission.
    The caller supplies the exact replay sessions; no dates/bars are invented.
    """

    def __init__(self, run: RunInput) -> None:
        self._validate(run)
        self.events = self._events(run)

    @staticmethod
    def _validate(run: RunInput) -> None:
        if type(run) is not RunInput or type(run.calendar) is not CalendarFacts:
            raise RunContractError("explicit RunInput and CalendarFacts required")
        for name in ("start_at", "end_at"):
            require_shanghai(getattr(run, name), name)
        if run.start_at >= run.end_at:
            raise RunContractError("run start_at must precede end_at")
        for name, kinds in (
            ("commands", (SubmitOrder, CancelOrder)), ("buckets", (CompletedBucket,)),
            ("instruments", (InstrumentFacts,)), ("initial_lots", (LotPosition,)),
            ("marks", (MarkEvent,)),
        ):
            _tuple_of(getattr(run, name), kinds, name)
        calendar = run.calendar
        dates = calendar.trading_dates
        _tuple_of(dates, (date,), "trading_dates")
        if not dates or any(a >= b for a, b in zip(dates, dates[1:])):
            raise RunContractError("trading_dates must be nonempty, ordered and unique")
        if calendar.company_actions_covered is not True:
            raise RunContractError("company actions coverage attestation required")
        if type(calendar.company_actions) is not tuple or calendar.company_actions:
            raise RunContractError("nonempty company actions are unsupported")
        if type(run.requires_marks) is not bool or (run.requires_marks and not run.marks):
            raise RunContractError("required marks are missing or policy is invalid")
        sessions = calendar.session_buckets
        _tuple_of(sessions, (SessionBucket,), "session_buckets")
        by_id = {}
        previous = None
        for session in sessions:
            _require_id(session.bucket_id, "bucket_id")
            require_shanghai(session.start, "session start")
            require_shanghai(session.end, "session end")
            if session.bucket_id in by_id:
                raise RunContractError("duplicate calendar bucket_id")
            if (
                session.session != "continuous"
                or session.start.date() not in dates
                or session.start.date() != session.end.date()
                or session.end - session.start != timedelta(minutes=1)
                or session.start.second or session.start.microsecond
                or not run.start_at <= session.start < session.end <= run.end_at
            ):
                raise RunContractError("invalid continuous minute session bucket")
            start, end = session.start.time(), session.end.time()
            if not (
                time(9, 30) <= start < end <= time(11, 30)
                or time(13) <= start < end <= time(14, 57)
            ):
                raise RunContractError("bucket crosses lunch or continuous session endpoints")
            if previous is not None:
                if previous.end > session.start:
                    raise RunContractError("unordered or overlapping calendar buckets")
                same_session = (
                    previous.start.date() == session.start.date()
                    and (previous.start.hour < 12) == (session.start.hour < 12)
                )
                if same_session and previous.end != session.start:
                    raise RunContractError("session gap must be covered by explicit missing buckets")
            by_id[session.bucket_id] = session
            previous = session

        for facts in run.instruments:
            _require_id(facts.symbol, "instrument symbol")
            if type(facts.trade_date) is not date:
                raise RunContractError("instrument trade_date must be an explicit date")
        symbols = {f.symbol for f in run.instruments}
        if not symbols:
            raise RunContractError("explicit instrument universe required")
        seen = set()
        previous_key = None
        for bucket in run.buckets:
            _require_id(bucket.symbol, "symbol")
            _require_id(bucket.bucket_id, "bucket_id")
            require_shanghai(bucket.start, "bucket start")
            require_shanghai(bucket.end, "bucket end")
            session = by_id.get(bucket.bucket_id)
            if session is None or (bucket.start, bucket.end) != (session.start, session.end):
                raise RunContractError("bucket lacks matching calendar coverage")
            key = (bucket.start, bucket.symbol)
            identity = (bucket.symbol, bucket.bucket_id)
            if identity in seen or (previous_key is not None and key <= previous_key):
                raise RunContractError("unordered or duplicate completed buckets")
            if type(bucket.missing) is not bool or type(bucket.halted) is not bool:
                raise RunContractError("explicit missing/halt coverage required")
            seen.add(identity)
            previous_key = key
        expected = {(symbol, s.bucket_id) for symbol in symbols for s in sessions}
        if seen != expected:
            raise RunContractError("every symbol/session needs explicit bucket or missing coverage")

        command_ids = set()
        orders = {}
        for command in run.commands:
            _require_id(command.command_id, "command_id")
            _require_id(command.order_id, "order_id")
            _require_int(command.sequence, "sequence")
            if command.command_id in command_ids:
                raise RunContractError("duplicate command_id")
            command_ids.add(command.command_id)
            for name in ("available_at", "submitted_at", "effective_at"):
                require_shanghai(getattr(command, name), name)
            if not command.available_at <= command.submitted_at <= command.effective_at:
                raise RunContractError("require available_at <= submitted_at <= effective_at")
            if not run.start_at <= command.submitted_at <= run.end_at:
                raise RunContractError("command submission outside run interval")
            if command.submitted_at.date() not in dates:
                raise RunContractError("command submission lacks trading date coverage")
            if type(command) is SubmitOrder:
                _require_id(command.symbol, "order symbol")
                if command.order_id in orders:
                    raise RunContractError("duplicate order_id; new submit requires new identity")
                if command.symbol not in symbols or not isinstance(command.side, Side):
                    raise RunContractError("unknown order symbol or side")
                require_shanghai(command.expires_at, "expires_at")
                if command.expires_at <= command.effective_at:
                    raise RunContractError("expiry must follow effective_at")
                orders[command.order_id] = command
        for command in run.commands:
            if type(command) is CancelOrder:
                order = orders.get(command.order_id)
                if order is None:
                    raise RunContractError("cancel targets unknown order")
                if (
                    command.submitted_at < order.submitted_at
                    or command.effective_at <= order.submitted_at
                ):
                    raise RunContractError("cancel must take effect after order submission")

        mark_ids = set()
        for mark in run.marks:
            _require_id(mark.mark_id, "mark_id")
            _require_id(mark.source, "mark source")
            if mark.mark_id in mark_ids:
                raise RunContractError("duplicate mark_id")
            mark_ids.add(mark.mark_id)
            require_shanghai(mark.event_time, "mark event_time")
            require_shanghai(mark.available_at, "mark available_at")
            if (
                mark.available_at != mark.event_time
                or not run.start_at <= mark.event_time <= run.end_at
                or mark.event_time.date() not in dates
                or mark.price_domain != "raw"
            ):
                raise RunContractError("mark must be contemporaneous, in-range and raw")
            _tuple_of(mark.prices, (MarkPrice,), "mark prices")
            for item in mark.prices:
                _require_id(item.symbol, "mark symbol")
            mark_symbols = [p.symbol for p in mark.prices]
            if len(set(mark_symbols)) != len(mark_symbols) or not set(mark_symbols) <= symbols:
                raise RunContractError("duplicate or unknown mark symbol")

    @staticmethod
    def _events(run: RunInput) -> tuple[ClockEvent, ...]:
        orders = {c.order_id: c for c in run.commands if type(c) is SubmitOrder}
        events = []

        def order_event(at, phase, order, payload, submitted_at=None, sequence=None):
            events.append(ClockEvent(
                at, phase, int(order.side is Side.BUY),
                order.submitted_at if submitted_at is None else submitted_at,
                order.sequence if sequence is None else sequence, order.order_id, payload,
            ))

        for command in run.commands:
            order = orders[command.order_id]
            if type(command) is SubmitOrder:
                order_event(command.submitted_at, Phase.SUBMIT, order, command)
                if command.expires_at <= run.end_at:
                    order_event(command.expires_at, Phase.EXPIRY, order, command)
            elif command.effective_at <= run.end_at:
                order_event(command.effective_at, Phase.CANCEL, order, command,
                            command.submitted_at, command.sequence)
        for bucket in run.buckets:
            # No order identity for visibility events; symbol gives a stable tie-break.
            events.append(ClockEvent(
                bucket.end, Phase.BUCKET, 0, bucket.end, 0, bucket.symbol, bucket,
            ))
            for order in orders.values():
                if eligible(order, bucket, bucket.end):
                    order_event(bucket.end, Phase.MATCH, order, bucket)
        for mark in run.marks:
            events.append(ClockEvent(
                mark.event_time, Phase.MARK, 0, mark.event_time, 0, mark.mark_id, mark,
            ))
        events.sort(key=lambda event: event.key)
        if any(a.key == b.key for a, b in zip(events, events[1:])):
            raise RunContractError("conflicting event ordering keys")
        # Detect conflicts even when a cancel's effective time is beyond this run.
        command_keys = set()
        for c in run.commands:
            order = orders[c.order_id]
            key = (
                c.submitted_at if type(c) is SubmitOrder else c.effective_at,
                Phase.SUBMIT if type(c) is SubmitOrder else Phase.CANCEL,
                int(order.side is Side.BUY), c.submitted_at, c.sequence, c.order_id,
            )
            if key in command_keys:
                raise RunContractError("conflicting command ordering keys")
            command_keys.add(key)
        return tuple(events)
