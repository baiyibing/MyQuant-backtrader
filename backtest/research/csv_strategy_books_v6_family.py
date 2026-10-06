"""Version6.x apply and run-kwargs helpers; registration stays in csv_strategy_books."""

from __future__ import annotations

from typing import Optional

from backtest.research import (
    strategy6_1_rules,
    strategy6_2_rules,
    strategy6_3_rules,
    strategy6_4_rules,
    strategy6_5_rules,
    strategy6_6_rules,
    strategy6_7_rules,
    strategy6_8_rules,
    strategy6_9_rules,
    strategy6_10_rules,
    strategy6_11_rules,
    strategy6_12_rules,
    strategy6_13_rules,
    strategy6_14_rules,
    strategy6_15_rules,
    strategy6_16_rules,
    strategy6_17_rules,
    strategy6_18_rules,
    strategy6_19_rules,
    strategy6_20_rules,
    strategy6_21_rules,
    strategy6_22_rules,
    strategy6_23_rules,
    strategy6_24_rules,
    strategy6_25_rules,
    strategy6_26_rules,
    strategy6_27_rules,
    strategy6_28_rules,
    strategy6_29_rules,
    strategy6_30_rules,
    strategy6_31_rules,
    strategy6_32_rules,
    strategy6_33_rules,
    strategy6_34_rules,
    strategy6_35_rules,
    strategy6_36_rules,
    strategy6_37_rules,
    strategy6_38_rules,
    strategy6_39_rules,
    strategy6_40_rules,
    strategy6_41_rules,
    strategy6_42_rules,
    strategy6_43_rules,
    strategy6_44_rules,
    strategy6_45_rules,
    strategy6_46_rules,
    strategy6_47_rules,
)


def _apply_version6_1(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_1_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_1_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_1_rules.record_strategy6_1_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_1_rules.lot_budget,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_1(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_1", "stop_pct": stop}


def _apply_version6_2(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_2_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_2_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_2_rules.record_strategy6_2_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_2_rules.lot_budget,
        "cost_anchor": "first_lot",
        "add_step": strategy6_2_rules.ADD_STEP,
        "step_frac": strategy6_2_rules.STEP_FRAC,
    }


def _run_kwargs_version6_2(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_2", "stop_pct": stop}


def _apply_version6_3(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_3_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_3_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_3_rules.record_strategy6_3_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_3_rules.lot_budget,
        "cost_anchor": "first_lot",
        "add_step": strategy6_3_rules.ADD_STEP,
        "step_frac": strategy6_3_rules.STEP_FRAC,
    }


def _run_kwargs_version6_3(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_3", "stop_pct": stop}


def _apply_version6_4(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_4_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_4_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_4_rules.record_strategy6_4_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_4_rules.lot_budget,
        "add_step": strategy6_4_rules.ADD_STEP,
        "step_frac": strategy6_4_rules.STEP_FRAC,
        "step_cap": strategy6_4_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_4(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_4", "stop_pct": stop}


def _apply_version6_5(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_5_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_5_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_5_rules.record_strategy6_5_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_5_rules.lot_budget,
        "add_step": strategy6_5_rules.ADD_STEP,
        "step_frac": strategy6_5_rules.STEP_FRAC,
        "step_cap": strategy6_5_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_5(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_5", "stop_pct": stop}


def _apply_version6_6(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_6_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_6_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_6_rules.record_strategy6_6_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_6_rules.lot_budget,
        "add_step": strategy6_6_rules.ADD_STEP,
        "step_frac": strategy6_6_rules.STEP_FRAC,
        "step_cap": strategy6_6_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_6(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_6", "stop_pct": stop}


def _apply_version6_7(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_7_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_7_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_7_rules.record_strategy6_7_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_7_rules.lot_budget,
        "add_step": strategy6_7_rules.ADD_STEP,
        "step_frac": strategy6_7_rules.STEP_FRAC,
        "step_cap": strategy6_7_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_7(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_7", "stop_pct": stop}


def _apply_version6_8(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_8_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_8_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_8_rules.record_strategy6_8_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_8_rules.lot_budget,
        "add_step": strategy6_8_rules.ADD_STEP,
        "step_frac": strategy6_8_rules.STEP_FRAC,
        "step_cap": strategy6_8_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_8_rules.STEP_STOP_PCT,
    }


def _run_kwargs_version6_8(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_8", "stop_pct": stop}


def _apply_version6_9(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_9_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_9_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_9_rules.record_strategy6_9_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_9_rules.lot_budget,
        "add_step": strategy6_9_rules.ADD_STEP,
        "step_frac": strategy6_9_rules.STEP_FRAC,
        "add_step2": strategy6_9_rules.ADD_STEP2,
        "step_frac2": strategy6_9_rules.STEP_FRAC2,
        "tranche_max": strategy6_9_rules.TRANCHE_MAX,
        "base_zone_caps": strategy6_9_rules.BASE_ZONE_CAPS,
        "step_cap": strategy6_9_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_9(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_9", "stop_pct": stop}


def _apply_version6_10(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_10_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_10_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_10_rules.record_strategy6_10_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_10_rules.lot_budget,
        "add_step": strategy6_10_rules.ADD_STEP,
        "step_frac": strategy6_10_rules.STEP_FRAC,
        "add_step2": strategy6_10_rules.ADD_STEP2,
        "step_frac2": strategy6_10_rules.STEP_FRAC2,
        "tranche_max": strategy6_10_rules.TRANCHE_MAX,
        "base_zone_caps": strategy6_10_rules.BASE_ZONE_CAPS,
        "step_cap": strategy6_10_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_10_rules.STEP_STOP_PCT,
    }


def _run_kwargs_version6_10(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_10", "stop_pct": stop}


def _apply_version6_11(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    from backtest.research.csv_simulate_loop import run_breakout_day

    resolved = strategy6_11_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_11_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_11_rules.record_strategy6_11_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_11_rules.lot_budget,
        "add_step": strategy6_11_rules.ADD_STEP,
        "step_frac": strategy6_11_rules.STEP_FRAC,
        "add_offset": strategy6_11_rules.ADD_OFFSET,
        "tranche_max": strategy6_11_rules.TRANCHE_MAX,
        "step_cap": strategy6_11_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "breakout_day": run_breakout_day,
        # 突破书不在名单日成交：标准池买整日置空（买由 breakout_day 驱动）。
        "planned_for_day": lambda ds, held_codes: [],
    }


def _run_kwargs_version6_11(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_11", "stop_pct": stop}


def _apply_version6_12(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    from backtest.research.csv_simulate_loop import run_breakout_day

    resolved = strategy6_12_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_12_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_12_rules.record_strategy6_12_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_12_rules.lot_budget,
        "add_step": strategy6_12_rules.ADD_STEP,
        "step_frac": strategy6_12_rules.STEP_FRAC,
        "add_offset": strategy6_12_rules.ADD_OFFSET,
        "tranche_max": strategy6_12_rules.TRANCHE_MAX,
        "step_cap": strategy6_12_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "breakout_day": run_breakout_day,
        "planned_for_day": lambda ds, held_codes: [],
    }


def _run_kwargs_version6_12(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_12", "stop_pct": stop}


def _apply_version6_13(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_13_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_13_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_13_rules.record_strategy6_13_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_13_rules.lot_budget,
        "add_step": strategy6_13_rules.ADD_STEP,
        "step_frac": strategy6_13_rules.STEP_FRAC,
        "step_cap": strategy6_13_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_13_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_13_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_13_rules.SCALE_OUT_FRAC,
    }


def _run_kwargs_version6_13(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_13", "stop_pct": stop}


def _apply_version6_14(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_14_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_14_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_14_rules.record_strategy6_14_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_14_rules.lot_budget,
        "add_step": strategy6_14_rules.ADD_STEP,
        "step_frac": strategy6_14_rules.STEP_FRAC,
        "step_cap": strategy6_14_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_14_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_14_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_14_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_14_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_14_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_14(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_14", "stop_pct": stop}


def _apply_version6_15(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_15_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_15_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_15_rules.record_strategy6_15_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_15_rules.lot_budget,
        "add_step": strategy6_15_rules.ADD_STEP,
        "step_frac": strategy6_15_rules.STEP_FRAC,
        "step_cap": strategy6_15_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_15_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_15_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_15_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_15_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_15_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_15(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_15", "stop_pct": stop}


def _apply_version6_16(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_16_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_16_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_16_rules.record_strategy6_16_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_16_rules.lot_budget,
        "add_step": strategy6_16_rules.ADD_STEP,
        "step_frac": strategy6_16_rules.STEP_FRAC,
        "step_cap": strategy6_16_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_16_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_16_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_16_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_16_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_16_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_16(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_16", "stop_pct": stop}


def _apply_version6_17(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_17_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_17_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_17_rules.record_strategy6_17_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_17_rules.lot_budget,
        "add_step": strategy6_17_rules.ADD_STEP,
        "step_frac": strategy6_17_rules.STEP_FRAC,
        "step_cap": strategy6_17_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_17_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_17_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_17_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_17_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_17_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_17(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_17", "stop_pct": stop}


def _apply_version6_18(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_18_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_18_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_18_rules.record_strategy6_18_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_18_rules.lot_budget,
        "add_step": strategy6_18_rules.ADD_STEP,
        "step_frac": strategy6_18_rules.STEP_FRAC,
        "step_cap": strategy6_18_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_18_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_18_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_18_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_18_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_18_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_18_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_18(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_18", "stop_pct": stop}


def _apply_version6_19(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_19_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_19_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_19_rules.record_strategy6_19_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_19_rules.lot_budget,
        "add_step": strategy6_19_rules.ADD_STEP,
        "step_frac": strategy6_19_rules.STEP_FRAC,
        "step_cap": strategy6_19_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_19_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_19_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_19_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_19_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_19_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_19_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_19(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_19", "stop_pct": stop}


def _apply_version6_20(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_20_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_20_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_20_rules.record_strategy6_20_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_20_rules.lot_budget,
        "add_step": strategy6_20_rules.ADD_STEP,
        "step_frac": strategy6_20_rules.STEP_FRAC,
        "step_cap": strategy6_20_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_20_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_20_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_20_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_20_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_20_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_20_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_20(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_20", "stop_pct": stop}


def _apply_version6_21(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_21_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_21_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_21_rules.record_strategy6_21_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_21_rules.lot_budget,
        "add_step": strategy6_21_rules.ADD_STEP,
        "step_frac": strategy6_21_rules.STEP_FRAC,
        "step_cap": strategy6_21_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_21_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_21_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_21_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_21_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_21_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_21_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_21(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_21", "stop_pct": stop}


def _apply_version6_22(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_22_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_22_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_22_rules.record_strategy6_22_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_22_rules.lot_budget,
        "add_step": strategy6_22_rules.ADD_STEP,
        "step_frac": strategy6_22_rules.STEP_FRAC,
        "step_cap": strategy6_22_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_22_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_22_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_22_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_22_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_22_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_22_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_22(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_22", "stop_pct": stop}


def _apply_version6_23(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_23_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_23_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_23_rules.record_strategy6_23_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_23_rules.lot_budget,
        "add_step": strategy6_23_rules.ADD_STEP,
        "step_frac": strategy6_23_rules.STEP_FRAC,
        "step_cap": strategy6_23_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_23_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_23_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_23_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_23_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_23_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_23_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_23(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_23", "stop_pct": stop}


def _apply_version6_24(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_24_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_24_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_24_rules.record_strategy6_24_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_24_rules.lot_budget,
        "add_step": strategy6_24_rules.ADD_STEP,
        "step_frac": strategy6_24_rules.STEP_FRAC,
        "step_cap": strategy6_24_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_24_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_24_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_24_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_24_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_24_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_24_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_24(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_24", "stop_pct": stop}


def _apply_version6_25(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_25_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_25_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_25_rules.record_strategy6_25_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_25_rules.lot_budget,
        "add_step": strategy6_25_rules.ADD_STEP,
        "step_frac": strategy6_25_rules.STEP_FRAC,
        "step_cap": strategy6_25_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_25_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_25_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_25_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_25_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_25_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_25_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_25(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_25", "stop_pct": stop}


def _apply_version6_26(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_26_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_26_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_26_rules.record_strategy6_26_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_26_rules.lot_budget,
        "add_step": strategy6_26_rules.ADD_STEP,
        "step_frac": strategy6_26_rules.STEP_FRAC,
        "step_cap": strategy6_26_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_26_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_26_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_26_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_26_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_26_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_26_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_26(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_26", "stop_pct": stop}


def _apply_version6_27(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_27_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_27_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_27_rules.record_strategy6_27_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_27_rules.lot_budget,
        "add_step": strategy6_27_rules.ADD_STEP,
        "step_frac": strategy6_27_rules.STEP_FRAC,
        "step_cap": strategy6_27_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_27_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_27_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_27_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_27_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_27_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_27_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_27(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_27", "stop_pct": stop}


def _apply_version6_28(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_28_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_28_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_28_rules.record_strategy6_28_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_28_rules.lot_budget,
        "add_step": strategy6_28_rules.ADD_STEP,
        "step_frac": strategy6_28_rules.STEP_FRAC,
        "step_cap": strategy6_28_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_28_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_28_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_28_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_28_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_28_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_28_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_28(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_28", "stop_pct": stop}


def _apply_version6_29(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_29_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_29_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_29_rules.record_strategy6_29_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_29_rules.lot_budget,
        "add_step": strategy6_29_rules.ADD_STEP,
        "step_frac": strategy6_29_rules.STEP_FRAC,
        "step_cap": strategy6_29_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_29_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_29_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_29_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_29_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_29_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_29_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_29(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_29", "stop_pct": stop}


def _apply_version6_30(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_30_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_30_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_30_rules.record_strategy6_30_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_30_rules.lot_budget,
        "add_step": strategy6_30_rules.ADD_STEP,
        "step_frac": strategy6_30_rules.STEP_FRAC,
        "step_cap": strategy6_30_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_30_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_30_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_30_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_30_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_30_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_30_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_30(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_30", "stop_pct": stop}


def _apply_version6_31(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_31_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_31_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_31_rules.record_strategy6_31_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_31_rules.lot_budget,
        "add_step": strategy6_31_rules.ADD_STEP,
        "step_frac": strategy6_31_rules.STEP_FRAC,
        "step_cap": strategy6_31_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_31_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_31_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_31_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_31_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_31_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_31_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_31(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_31", "stop_pct": stop}


def _apply_version6_32(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_32_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_32_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_32_rules.record_strategy6_32_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_32_rules.lot_budget,
        "add_step": strategy6_32_rules.ADD_STEP,
        "step_frac": strategy6_32_rules.STEP_FRAC,
        "step_cap": strategy6_32_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_32_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_32_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_32_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_32_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_32_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_32_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_32(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_32", "stop_pct": stop}


def _apply_version6_33(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_33_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_33_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_33_rules.record_strategy6_33_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_33_rules.lot_budget,
        "add_step": strategy6_33_rules.ADD_STEP,
        "step_frac": strategy6_33_rules.STEP_FRAC,
        "step_cap": strategy6_33_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_33_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_33_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_33_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_33_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_33_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_33_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_33(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_33", "stop_pct": stop}


def _apply_version6_34(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_34_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_34_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_34_rules.record_strategy6_34_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_34_rules.lot_budget,
        "add_step": strategy6_34_rules.ADD_STEP,
        "step_frac": strategy6_34_rules.STEP_FRAC,
        "step_cap": strategy6_34_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_34_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_34_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_34_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_34_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_34_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_34_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_34(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_34", "stop_pct": stop}


def _apply_version6_35(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_35_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_35_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_35_rules.record_strategy6_35_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_35_rules.lot_budget,
        "add_step": strategy6_35_rules.ADD_STEP,
        "step_frac": strategy6_35_rules.STEP_FRAC,
        "step_cap": strategy6_35_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_35_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_35_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_35_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_35_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_35_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_35_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_35(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_35", "stop_pct": stop}


def _apply_version6_36(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_36_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_36_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_36_rules.record_strategy6_36_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_36_rules.lot_budget,
        "add_step": strategy6_36_rules.ADD_STEP,
        "step_frac": strategy6_36_rules.STEP_FRAC,
        "step_cap": strategy6_36_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_36_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_36_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_36_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_36_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_36_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_36_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_36(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_36", "stop_pct": stop}


def _apply_version6_37(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_37_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_37_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_37_rules.record_strategy6_37_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_37_rules.lot_budget,
        "add_step": strategy6_37_rules.ADD_STEP,
        "step_frac": strategy6_37_rules.STEP_FRAC,
        "step_cap": strategy6_37_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_37_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_37_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_37_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_37_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_37_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_37_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_37(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_37", "stop_pct": stop}


def _apply_version6_38(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_38_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_38_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_38_rules.record_strategy6_38_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_38_rules.lot_budget,
        "add_step": strategy6_38_rules.ADD_STEP,
        "step_frac": strategy6_38_rules.STEP_FRAC,
        "step_cap": strategy6_38_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_38_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_38_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_38_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_38_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_38_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_38_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_38(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_38", "stop_pct": stop}


def _apply_version6_39(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_39_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_39_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_39_rules.record_strategy6_39_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_39_rules.lot_budget,
        "add_step": strategy6_39_rules.ADD_STEP,
        "step_frac": strategy6_39_rules.STEP_FRAC,
        "step_cap": strategy6_39_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_39_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_39_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_39_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_39_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_39_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_39_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_39(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_39", "stop_pct": stop}


def _apply_version6_40(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_40_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_40_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_40_rules.record_strategy6_40_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_40_rules.lot_budget,
        "add_step": strategy6_40_rules.ADD_STEP,
        "step_frac": strategy6_40_rules.STEP_FRAC,
        "step_cap": strategy6_40_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_40_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_40_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_40_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_40_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_40_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_40_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_40(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_40", "stop_pct": stop}


def _apply_version6_41(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_41_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_41_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_41_rules.record_strategy6_41_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_41_rules.lot_budget,
        "add_step": strategy6_41_rules.ADD_STEP,
        "step_frac": strategy6_41_rules.STEP_FRAC,
        "step_cap": strategy6_41_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_41_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_41_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_41_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_41_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_41_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_41_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_41(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_41", "stop_pct": stop}


def _apply_version6_42(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_42_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_42_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_42_rules.record_strategy6_42_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_42_rules.lot_budget,
        "add_step": strategy6_42_rules.ADD_STEP,
        "step_frac": strategy6_42_rules.STEP_FRAC,
        "step_cap": strategy6_42_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_42_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_42_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_42_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_42_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_42_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_42_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_42(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_42", "stop_pct": stop}


def _apply_version6_43(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_43_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_43_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_43_rules.record_strategy6_43_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_43_rules.lot_budget,
        "add_step": strategy6_43_rules.ADD_STEP,
        "step_frac": strategy6_43_rules.STEP_FRAC,
        "step_cap": strategy6_43_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_43_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_43_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_43_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_43_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_43_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_43_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_43(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_43", "stop_pct": stop}


def _apply_version6_44(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_44_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_44_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_44_rules.record_strategy6_44_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_44_rules.lot_budget,
        "add_step": strategy6_44_rules.ADD_STEP,
        "step_frac": strategy6_44_rules.STEP_FRAC,
        "step_cap": strategy6_44_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_44_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_44_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_44_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_44_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_44_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_44_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_44(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_44", "stop_pct": stop}


def _apply_version6_45(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    index_block_new=None,
    **_,
) -> dict:
    resolved = strategy6_45_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_45_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_45_rules.record_strategy6_45_params(st, stop_pct=resolved)
        st.stats["index_gate_on"] = bool(strategy6_45_rules.INDEX_GATE_ON)
        st.stats["index_symbol"] = strategy6_45_rules.INDEX_SYMBOL
        st.stats["index_blocks_add"] = bool(strategy6_45_rules.INDEX_BLOCKS_ADD)

    # 上证闸门：allow_new_name 在 gate 为 None 时不闸（等 CLI 传入 block map）
    from backtest.research import strategy_book_helpers as _bh
    from backtest.research.strategy6_45_rules import INDEX_GATE_ON as _gate_on
    _allow = _bh.allow_new_name_from_gate(index_block_new, INDEX_GATE_ON=_gate_on)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_45_rules.lot_budget,
        "add_step": strategy6_45_rules.ADD_STEP,
        "step_frac": strategy6_45_rules.STEP_FRAC,
        "step_cap": strategy6_45_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_45_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_45_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_45_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_45_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_45_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_45_rules.ADD_SCHEDULE,
        "allow_new_name": _allow,
        "index_blocks_add": strategy6_45_rules.INDEX_BLOCKS_ADD,
    }


def _run_kwargs_version6_45(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_45", "stop_pct": stop}


def _apply_version6_46(
    *,
    stop_pct=None,
    take_profit=None,
    record_params=None,
    index_block_new=None,
    **_,
) -> dict:
    from backtest.research import strategy_book_helpers as _bh
    from backtest.research.strategy6_46_rules import INDEX_GATE_ON as _gate_on
    resolved = strategy6_46_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_46_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_46_rules.record_strategy6_46_params(st, stop_pct=resolved)
        st.stats["index_gate_on"] = bool(strategy6_46_rules.INDEX_GATE_ON)
        st.stats["parking_symbol"] = strategy6_46_rules.PARKING_SYMBOL
        st.stats["parking_frac"] = strategy6_46_rules.PARKING_FRAC
    _allow = _bh.allow_new_name_from_gate(index_block_new, INDEX_GATE_ON=_gate_on)
    base = _apply_version6_45(stop_pct=resolved, take_profit=_tp, record_params=_rec,
                                index_block_new=index_block_new)
    base["name"] = "version6_46"
    base["parking_symbol"] = strategy6_46_rules.PARKING_SYMBOL
    base["parking_frac"] = strategy6_46_rules.PARKING_FRAC
    base["parking_buffer"] = strategy6_46_rules.PARKING_BUFFER
    return base


def _run_kwargs_version6_46(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_46", "stop_pct": stop}


def _apply_version6_47(*, stop_pct=None, take_profit=None, record_params=None, index_block_new=None, **_):
    base = _apply_version6_46(stop_pct=stop_pct, take_profit=take_profit, record_params=record_params, index_block_new=index_block_new)
    base['name'] = 'version6_47'
    return base


def _run_kwargs_version6_47(args) -> dict:
    stop = getattr(args, 'stop_pct', None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f'--stop-pct must be in (0, 1), got {stop}')
    return {'strategy': 'version6_47', 'stop_pct': stop}
