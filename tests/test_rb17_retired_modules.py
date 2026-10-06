"""RB-17 guards for retired paths and compatibility re-export identity."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# RB-17 found no candidate that was both unreferenced and safe to remove.
# Keep the machinery explicit so a later one-item retirement must add its path
# and immediately gains both absence and textual-reference guards.
RETIRED_PATH_PARTS: tuple[tuple[str, ...], ...] = ()


def test_retired_paths_stay_absent_and_unreferenced() -> None:
    ignored = {
        REPO / "tests" / "test_rb17_retired_modules.py",
        REPO / "docs" / "backtest" / "rb17-dead-code-inventory-2026-10-06.md",
    }
    retired = tuple("/".join(parts) for parts in RETIRED_PATH_PARTS)
    for relative in retired:
        assert not (REPO / relative).exists(), relative

    hits: dict[str, list[str]] = {relative: [] for relative in retired}
    text_suffixes = {
        ".ini", ".json", ".md", ".mdc", ".py", ".toml", ".txt", ".yaml", ".yml",
    }
    for path in REPO.rglob("*"):
        if (
            not retired
            or not path.is_file()
            or path in ignored
            or ".git" in path.parts
            or path.suffix.lower() not in text_suffixes
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for relative in retired:
            dotted = relative.removesuffix(".py").replace("/", ".")
            if relative in text or dotted in text:
                hits[relative].append(path.relative_to(REPO).as_posix())
    assert not any(hits.values()), hits


def test_turnover_resist_compat_reexports_keep_identity() -> None:
    import oskh_core.turnover_resist_bridge as compat
    import oskh_factors.bridge.turnover_resist as target

    for name in compat.__all__:
        assert getattr(compat, name) is getattr(target, name)


def test_strategy10_cli_alias_keeps_main_identity() -> None:
    import scripts.data.export_strategy10_pool as compat
    import scripts.data.export_ta_pool as target

    assert compat.main is target.main


def test_ashare_fee_reexport_keeps_identity() -> None:
    import backtest.research.ashare_fees as compat
    import backtest.research.ledger_math as target

    assert compat.trade_commission is target.trade_commission


def test_chip_algorithm_reexports_keep_identity() -> None:
    import backtest.chip_algorithm as compat
    from oskh_factors import price_bb
    from oskh_factors.chip import adj_factor, core, shares
    from qlib_cost import cyq

    targets = {
        "adj_minute_prices": adj_factor,
        "get_adj_factor": adj_factor,
        "adapt_columns": core,
        "adj_minute_chip_distribution": core,
        "compute_chip_factors": core,
        "compute_crossday_turnover_resistance": core,
        "compute_equal_weight_cyqk": core,
        "daily_chip_distribution": core,
        "derived_chip_factors": core,
        "hybrid_chip_distribution": core,
        "minute_chip_distribution": core,
        "turnover_chip_factors": core,
        "_estimate_turnover": shares,
        "_get_float_shares": shares,
        "_get_free_float_shares": shares,
        "_load_float_shares_map": shares,
        "_load_free_float_shares": shares,
        "bb_position": price_bb,
    }
    for name, target in targets.items():
        assert getattr(compat, name) is getattr(target, name)
    assert compat.cyq is cyq
    assert set(compat.__all__) == set(targets) | {"cyq"}


def test_v7_facade_reexports_keep_identity() -> None:
    import backtest.research.ashare_session as session
    import backtest.research.csv_minute_backtest_v7 as compat
    import backtest.research.strategy7_engine as engine
    import backtest.research.strategy7_rules as rules

    engine_names = (
        "NAME_BUDGET", "Lot", "Position", "SimResult", "_record_stamp",
        "_record_dict", "_minute_records", "_iter_records", "_daily_closes",
        "_pool", "_rescale_position", "_apply_exdiv_economics", "_event",
        "_buy", "_sell_lots", "_buy_tail_slice", "_is_frame_map",
        "_day_frame_records", "MinuteSession", "AccountingPolicy",
        "prepare_calendar",
    )
    rule_names = (
        "EIGHT", "FOUR", "FULL", "SIX", "TRIAL", "TRIAL_FRACTION",
        "build_index_gate", "in_add_window", "ladder_decision",
        "stop_decision", "timer_due", "validate_index_symbol",
    )
    session_names = (
        "asof_pool_name", "defer_sell_at_limit", "k_for",
        "load_limit_context", "session_limit_prices", "session_prev_close",
        "skip_buy_at_limit", "t1_sellable",
    )
    for target, names in (
        (engine, engine_names),
        (rules, rule_names),
        (session, session_names),
    ):
        for name in names:
            assert getattr(compat, name) is getattr(target, name)
