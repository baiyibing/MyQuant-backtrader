"""LIMIT lifecycle and orchestration; Ledger remains the sole resource owner."""

from dataclasses import replace
from decimal import Decimal

from .clock import Clock, eligible
from .fees import FeeModel, from_cents, money_cents
from .ledger import Ledger
from .match import compute_bucket_capacity, match_candidates
from .types import (
    BucketQuote, CandidateMatch, ClockEvent, CompletedBucket, FillProposal,
    InstrumentFacts, LimitOrderMatchInput, MarkObservation, OrderState,
    OrderStatus, OrderTransition, Phase, ReservationRejected, RunContractError,
    RunInput, RunResult, Side, SubmitOrder, _require_id, _require_int,
)

_ACTIVE = frozenset({OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED})


def _price(price: Decimal, facts: InstrumentFacts, name: str) -> None:
    cents = money_cents(price, name)
    tick = money_cents(facts.tick_size, "tick_size")
    if not cents or not tick or cents % tick:
        raise RunContractError(f"{name} must be positive and tick-aligned")
    if not facts.limit_down <= price <= facts.limit_up:
        raise RunContractError(f"{name} outside explicit daily price limits")


class BrokerCore:
    """A single-use, finite synthetic replay; no online submit/StrategyPort API."""

    def __init__(self, run: RunInput) -> None:
        self.clock = Clock(run)
        self._run = run
        self._facts = {}
        self._validate_market()
        self._fees = FeeModel(run.buy_fees, run.sell_fees)
        self.ledger = Ledger(run.initial_cash, run.initial_lots, fee_model=self._fees)
        for lot in run.initial_lots:
            if lot.acquire_date > run.start_at.date():
                raise RunContractError("initial lot cannot be acquired in the future")
            if self._next_date(lot.acquire_date) != lot.sellable_date:
                raise RunContractError("initial lot sellable_date must be next explicit trading date")
            if lot.lot_size != self._instrument(lot.symbol, run.start_at.date()).lot_size:
                raise RunContractError("initial lot differs from instrument lot_size")
        self._orders = {}
        self._transitions = []
        self._marks = []
        self._visible = {}
        self._started = False

    def _instrument(self, symbol, day) -> InstrumentFacts:
        try:
            return self._facts[symbol, day]
        except KeyError as exc:
            raise RunContractError(f"missing instrument facts for {symbol} on {day}") from exc

    def _next_date(self, day):
        dates = self._run.calendar.trading_dates
        if day not in dates or dates.index(day) + 1 == len(dates):
            raise RunContractError("next explicit trading date missing")
        return dates[dates.index(day) + 1]

    def _validate_market(self) -> None:
        run = self._run
        lot_sizes = {}
        for facts in run.instruments:
            _require_id(facts.symbol, "instrument symbol")
            if facts.trade_date not in run.calendar.trading_dates:
                raise RunContractError("instrument lacks trading date coverage")
            if facts.board != "main" or facts.price_domain != "raw":
                raise RunContractError("only explicit main-board/raw facts supported")
            _require_int(facts.lot_size, "lot_size", minimum=1)
            tick = money_cents(facts.tick_size, "tick_size")
            lower = money_cents(facts.limit_down, "limit_down")
            upper = money_cents(facts.limit_up, "limit_up")
            if not tick or not 0 < lower < upper:
                raise RunContractError("invalid tick or daily limit facts")
            for name in ("reference_price", "limit_down", "limit_up"):
                _price(getattr(facts, name), facts, name)
            key = (facts.symbol, facts.trade_date)
            if key in self._facts:
                raise RunContractError("duplicate instrument facts")
            if lot_sizes.setdefault(facts.symbol, facts.lot_size) != facts.lot_size:
                raise RunContractError("changing instrument lot_size unsupported")
            self._facts[key] = facts
        # Validate participation even for an empty replay.
        compute_bucket_capacity(1, 0, run.participation_rate)
        for bucket in run.buckets:
            facts = self._instrument(bucket.symbol, bucket.start.date())
            if bucket.missing:
                if bucket.close is not None or bucket.volume_shares is not None:
                    raise RunContractError("missing bucket cannot carry a quote or volume")
            else:
                _price(bucket.close, facts, "bucket close")
                _require_int(bucket.volume_shares, "volume_shares")
        for command in run.commands:
            if type(command) is SubmitOrder:
                facts = self._instrument(command.symbol, command.submitted_at.date())
                LimitOrderMatchInput(
                    command.order_id, command.symbol, command.side, command.limit,
                    command.qty, facts.lot_size, command.order_type,
                )
                _require_int(command.qty, "order qty", minimum=1)
                _price(command.limit, facts, "order limit")
        for mark in run.marks:
            for item in mark.prices:
                _price(item.price, self._instrument(item.symbol, mark.event_time.date()), "mark")

    def _record(self, event: ClockEvent, state: OrderState) -> None:
        self._orders[state.order.order_id] = state
        self._transitions.append(OrderTransition(event, state))

    def _submit(self, event: ClockEvent) -> None:
        order = event.payload
        facts = self._instrument(order.symbol, order.submitted_at.date())
        state = OrderState(order, OrderStatus.SUBMITTED, 0, order.qty)
        self._record(event, state)
        if order.side is Side.BUY:
            reservation = self.ledger.reserve_buy(
                order.order_id, symbol=order.symbol, limit=order.limit,
                remaining_qty=order.qty, lot_size=facts.lot_size,
                fee_upper=self._fees.buy_fee_upper_bound(Decimal("0.00"), order.limit, order.qty),
            )
        else:
            reservation = self.ledger.reserve_sell(
                order.order_id, symbol=order.symbol, limit=order.limit,
                qty=order.qty, lot_size=facts.lot_size, trade_date=order.submitted_at.date(),
            )
        if isinstance(reservation, ReservationRejected):
            state = replace(state, status=OrderStatus.REJECTED, rejection=reservation)
        else:
            state = replace(state, status=OrderStatus.ACCEPTED)
        self._record(event, state)

    def _release(self, event: ClockEvent) -> None:
        state = self._orders[event.order_id]
        # Distinct cancels after a terminal state are acknowledged no-ops.
        # EXPIRY sorts before CANCEL, so B3 records only Expired and releases once.
        if state.status not in _ACTIVE:
            return
        if state.order.side is Side.BUY:
            self.ledger.release_buy(event.order_id)
        else:
            self.ledger.release_sell(event.order_id)
        status = OrderStatus.EXPIRED if event.phase is Phase.EXPIRY else OrderStatus.CANCELLED
        self._record(event, replace(state, status=status))

    def _register(self, event: ClockEvent) -> None:
        bucket = event.payload
        facts = self._instrument(bucket.symbol, bucket.start.date())
        capacity = 0 if bucket.missing or bucket.halted else compute_bucket_capacity(
            facts.lot_size, bucket.volume_shares, self._run.participation_rate,
        )
        self.ledger.register_bucket(
            symbol=bucket.symbol, bucket_id=bucket.bucket_id,
            trade_date=bucket.start.date(), lot_size=facts.lot_size, capacity=capacity,
        )
        self._visible[bucket.symbol, bucket.bucket_id] = bucket

    def _match(self, event: ClockEvent) -> None:
        state = self._orders[event.order_id]
        bucket: CompletedBucket = event.payload
        if state.status not in _ACTIVE or not eligible(state.order, bucket, event.event_time):
            return
        if self._visible.get((bucket.symbol, bucket.bucket_id)) != bucket:
            raise RunContractError("bucket not yet visible")
        if bucket.missing or bucket.halted:
            return
        order = state.order
        facts = self._instrument(bucket.symbol, bucket.start.date())
        if (order.side is Side.BUY and bucket.close == facts.limit_up) or (
            order.side is Side.SELL and bucket.close == facts.limit_down
        ):
            return
        snapshot = self.ledger.snapshot()
        capacity = next(b.remaining for b in snapshot.buckets
                        if (b.symbol, b.bucket_id) == (bucket.symbol, bucket.bucket_id))
        action = match_candidates(
            LimitOrderMatchInput(order.order_id, order.symbol, order.side, order.limit,
                                 state.remaining_qty, facts.lot_size),
            BucketQuote(bucket.symbol, bucket.bucket_id, bucket.start, bucket.end, bucket.close),
            capacity_remaining=capacity,
        )
        if not isinstance(action, CandidateMatch):
            return
        totals = next(t for t in snapshot.order_totals if t.order_id == order.order_id)
        after = from_cents(money_cents(totals.notional, "notional")
                           + money_cents(action.candidate_price, "price") * action.proposed_qty)
        # Length-prefixed identities avoid ambiguous concatenation and are replay-stable.
        fill_id = f"{len(order.order_id)}:{order.order_id}:{len(bucket.bucket_id)}:{bucket.bucket_id}"
        proposal = FillProposal(
            fill_id=fill_id, order_id=order.order_id, symbol=order.symbol, side=order.side,
            qty=action.proposed_qty, price=action.candidate_price,
            fee_delta=self._fees.fee_delta(order.side, totals.notional, after),
            bucket_id=bucket.bucket_id, capacity_consumed=action.proposed_qty,
            lot_size=facts.lot_size, trade_date=bucket.start.date(),
            sellable_date=self._next_date(bucket.start.date()) if order.side is Side.BUY else None,
            expected_version=snapshot.ledger_version,
        )
        self.ledger.apply_fill(proposal)
        remaining = state.remaining_qty - proposal.qty
        self._record(event, replace(
            state, filled_qty=state.filled_qty + proposal.qty, remaining_qty=remaining,
            status=OrderStatus.PARTIALLY_FILLED if remaining else OrderStatus.FILLED,
        ))

    def _mark(self, event: ClockEvent) -> None:
        mark = event.payload
        snapshot = self.ledger.snapshot()
        held = {lot.symbol for lot in snapshot.lots}
        if not held <= {item.symbol for item in mark.prices}:
            raise RunContractError("mark missing price for a held symbol")
        self._marks.append(MarkObservation(mark, snapshot))

    def run(self) -> RunResult:
        if self._started:
            raise RunContractError("BrokerCore is single-use; construct a new run")
        self._started = True
        handlers = {
            Phase.EXPIRY: self._release, Phase.CANCEL: self._release,
            Phase.BUCKET: self._register, Phase.MATCH: self._match,
            Phase.SUBMIT: self._submit, Phase.MARK: self._mark,
        }
        for event in self.clock.events:
            handlers[event.phase](event)
        snapshot = self.ledger.snapshot()
        return RunResult(
            tuple(self._orders[key] for key in sorted(self._orders)), snapshot.applied_fills,
            snapshot, tuple(self._transitions), tuple(self._marks),
        )
