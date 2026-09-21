"""Explicit research loader edge. Production runners remain unchanged.

Book loading mirrors csv_minute_backtest.run at 32b78b1; the only simulation
binding is the explicit research API, without replacing module globals.
"""

from __future__ import annotations

from backtest.research import csv_minute_backtest as book
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.fullstrat_research_hooks import simulate_book, simulate_v7


def run_book_data(
    start: str,
    end: str,
    *,
    total_cash: float = book.DEFAULT_TOTAL_CASH,
    daily_quota: float = book.DEFAULT_DAILY_QUOTA,
    name_budget: book.Optional[float] = None,
    ration: str = "file_order",
    ration_seed: int = 0,
    stop_pct: book.Optional[float] = None,
    profit_base: book.Optional[float] = None,
    tiers: book.Optional[dict] = None,
    tier_default: book.Optional[float] = None,
    pos_trail: float = book.POS_TRAIL,
    workers: int = 16,
    use_cache: bool = True,
    rebuild_cache: bool = False,
    pool_dir: book.Optional[book.Path] = None,
    strategy: str,
    take_profit=None,
    record_params=None,
    scores_by_day=None,
    topk=None,
    n_drop=None,
    eligible_buy=None,
    return_threshold_filter: bool = False,
    minute_source: str = "lake",
    daily_source: str = "lake",
    qlib_1min_root: book.Optional[book.Path] = None,
    qlib_day_root: book.Optional[book.Path] = None,
    clock_mode="production_default",
    slip_bp_per_side=0,
) -> book.SimState:
    book.warn_stale_period_env()
    if minute_source == "lake" and end > book.MINUTE_LAKE_END:
        print(
            f"[warn] --end {end} past minute lake {book.MINUTE_LAKE_END}; bars after that date are missing, use daily engine to reach today",
            flush=True,
        )
    t_pool = book.time.perf_counter()
    actual_pool_dir = book.resolve_research_pool_dir(strategy, pool_dir, repo=book.REPO)
    pool_days = book.load_pool_day_map(
        actual_pool_dir, start, end, key="ymd", empty_in_map=False
    )
    pool_names_by_day = book.load_pool_names_by_day(actual_pool_dir, start, end)
    t_pool = book.time.perf_counter() - t_pool
    if not pool_days:
        raise SystemExit(f"no pool CSVs in [{start}, {end}] under {actual_pool_dir}")
    all_codes = {c for codes in pool_days.values() for c in codes}
    from backtest.research.topk_dropout_scores import codes_from_scores

    all_codes |= codes_from_scores(scores_by_day)
    load_start = book.warmup_start(
        start,
        book.STRATEGY4_CALENDAR_SLACK_DAYS
        if book.normalize_csv_strategy(strategy) == "version4"
        else 20
        if return_threshold_filter
        else book.WARMUP_DAYS,
    )
    print(
        f"loading daily+minute: {len(all_codes)} codes, {load_start}..{end}; pool {min(pool_days)}..{max(pool_days)} ({len(pool_days)} days)",
        flush=True,
    )
    t_daily = book.time.perf_counter()
    daily = book.load_daily_ohlc(
        all_codes,
        load_start,
        end,
        source=daily_source,
        qlib_root=qlib_day_root,
        workers=workers,
    )
    t_daily = book.time.perf_counter() - t_daily
    cache_status: dict = {}
    t_minute = book.time.perf_counter()
    if minute_source == "qlib_1min":
        compact = book._load_minute_compact(
            all_codes,
            load_start,
            end,
            source="qlib_1min",
            qlib_root=qlib_1min_root,
            workers=workers,
        )
        minute = book.book_frames_from_compact(compact)
        cache_status["cache"] = "qlib_1min"
    else:
        minute = book.load_minute_bars(
            all_codes,
            load_start,
            end,
            workers=workers,
            use_cache=use_cache,
            rebuild_cache=rebuild_cache,
            status=cache_status,
        )
    t_minute = book.time.perf_counter() - t_minute
    if not daily or not minute:
        raise ValueError(
            "missing daily/minute bars; cannot label missing data as all-cash NAV"
        )
    print(
        f"loaded daily {len(daily)} / minute {len(minute)} / pool days {len(pool_days)}",
        flush=True,
    )
    if return_threshold_filter:
        from backtest.research.topk_dropout_eligibility import with_return_threshold

        eligible_buy = with_return_threshold(eligible_buy, daily)
    skipped: dict[str, int] = {}
    exdiv = book.load_exdiv_ratios(all_codes, start, end, skipped_out=skipped)
    index_block_new = None
    gate_book = book.normalize_csv_strategy(strategy)
    if gate_book in ("version8", "version8_3"):
        from backtest.research.strategy8_rules import (
            INDEX_GATE_ON,
            load_sse_ma10_block_new,
        )

        if INDEX_GATE_ON or gate_book == "version8_3":
            index_block_new = load_sse_ma10_block_new(start, end)
    t_sim = book.time.perf_counter()
    st = simulate_book(
        minute,
        daily,
        pool_days,
        start,
        end,
        total_cash=total_cash,
        daily_quota=daily_quota,
        stop_pct=stop_pct,
        profit_base=profit_base,
        tiers=tiers,
        tier_default=tier_default,
        pos_trail=pos_trail,
        strategy=strategy,
        take_profit=take_profit,
        record_params=record_params,
        name_budget=name_budget,
        ration=ration,
        ration_seed=ration_seed,
        pool_names_by_day=pool_names_by_day,
        exdiv=exdiv,
        scores_by_day=scores_by_day,
        topk=topk,
        n_drop=n_drop,
        eligible_buy=eligible_buy,
        index_block_new=index_block_new,
        clock_mode=clock_mode,
        slip_bp_per_side=slip_bp_per_side,
    )
    if skipped.get("exdiv_skipped_no_factor"):
        st.stats["exdiv_skipped_no_factor"] = int(skipped["exdiv_skipped_no_factor"])
    st.stats["t_pool_s"] = t_pool
    st.stats["t_daily_s"] = t_daily
    st.stats["t_minute_s"] = t_minute
    st.stats["t_sim_s"] = book.time.perf_counter() - t_sim
    st.stats["cache"] = cache_status.get("cache", "")
    st.stats["codes_missing"] = max(0, len(all_codes) - min(len(daily), len(minute)))
    return st


def run_v7_data(*, start, end, pool_dir, qlib_root, clock_mode, slip_bp_per_side):
    start, end = v7._as_date(start), v7._as_date(end)
    pools = v7.load_pool_days(pool_dir, start, end)
    if not pools:
        raise ValueError(f"no pool CSVs in {start}..{end}: {pool_dir}")
    minute, daily = v7._load_cli_bars(
        pools, start, end, minute_source="qlib_1min", qlib_1min_root=qlib_root
    )
    symbols = {s for values in pools.values() for s in values}
    if not minute or not daily:
        raise ValueError(
            "missing daily/minute bars; cannot label missing data as all-cash NAV"
        )
    exdiv, names = v7.load_limit_context(pool_dir, symbols, start, end)
    index = v7.load_index_daily(start, end)
    return simulate_v7(
        minute,
        daily,
        pools,
        index,
        start=start,
        end=end,
        exdiv=exdiv,
        names=names,
        clock_mode=clock_mode,
        slip_bp_per_side=slip_bp_per_side,
    )
