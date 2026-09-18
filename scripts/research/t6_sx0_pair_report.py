"""Pair C/X locked-cost result for T6-SX0. Does not rerun fills."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SX0_REASON = "model_exit:nonpositive"
BOOTSTRAP_SEED = 20260917
BOOTSTRAP_BLOCK = 5
BOOTSTRAP_N = 10_000
INITIAL = 100_000_000.0


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_equity(out_dir: Path) -> pd.Series:
    eq = pd.read_csv(Path(out_dir) / "daily_equity.csv")
    eq["date"] = pd.to_datetime(eq["date"].astype(str), format="%Y%m%d")
    return eq.set_index("date")["equity"].astype(float)


def _load_trades(out_dir: Path) -> pd.DataFrame:
    path = Path(out_dir) / "trades.csv"
    if not path.is_file():
        return pd.DataFrame()
    tr = pd.read_csv(path)
    if tr.empty:
        return tr
    tr["date"] = pd.to_datetime(tr["date"].astype(str), format="%Y%m%d")
    return tr


def _net_return(eq: pd.Series, initial: float = INITIAL) -> float:
    if eq.empty:
        return float("nan")
    return float(eq.iloc[-1] / initial - 1.0)


def _max_dd(eq: pd.Series) -> float:
    if eq.empty:
        return float("nan")
    peak = eq.cummax()
    return float((eq / peak - 1.0).min())


def _ann(net: float, n_days: int) -> float:
    if n_days <= 0 or not np.isfinite(net):
        return float("nan")
    return float((1.0 + net) ** (252.0 / n_days) - 1.0)


def _gross_equity(eq: pd.Series, trades: pd.DataFrame) -> pd.Series:
    if trades is None or trades.empty:
        return eq.copy()
    fees = trades.groupby("date")["commission"].sum()
    cum = fees.reindex(eq.index).fillna(0.0).cumsum()
    return eq + cum


def _daily_ret(eq: pd.Series, initial: float = INITIAL) -> pd.Series:
    prev = eq.shift(1)
    prev.iloc[0] = initial
    return eq / prev - 1.0


def moving_block_bootstrap_delta(
    r_x: pd.Series,
    r_c: pd.Series,
    *,
    block: int = BOOTSTRAP_BLOCK,
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    aligned = pd.concat({"x": r_x, "c": r_c}, axis=1).dropna()
    x = aligned["x"].to_numpy(dtype=float)
    c = aligned["c"].to_numpy(dtype=float)
    n = len(x)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.RandomState(seed)
    starts = np.arange(0, n - block + 1)
    if len(starts) == 0:
        starts = np.array([0])
        block = n
    n_blocks = int(np.ceil(n / block))
    stats = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        picks = rng.choice(starts, size=n_blocks, replace=True)
        xb = np.concatenate([x[s : s + block] for s in picks])[:n]
        cb = np.concatenate([c[s : s + block] for s in picks])[:n]
        stats[i] = float(np.prod(1.0 + xb) - np.prod(1.0 + cb))
    lo, hi = np.quantile(stats, [0.025, 0.975])
    return float(np.mean(stats)), float(lo), float(hi)


def _quarter_net(eq: pd.Series, initial: float = INITIAL) -> pd.Series:
    q = eq.index.to_period("Q")
    rows = []
    prev_end = initial
    for label, sub in eq.groupby(q, sort=True):
        end = float(sub.iloc[-1])
        rows.append((str(label), end / prev_end - 1.0))
        prev_end = end
    return pd.Series({k: v for k, v in rows})


def _load_benchmark(qlib_root: Path, start: str, end: str) -> pd.Series:
    from backtest.research.qlib_bin_daily import load_qlib_bin_daily_bars

    bars = load_qlib_bin_daily_bars(
        ["SH000300"], start, end, qlib_root=qlib_root, workers=1
    )
    if "000300.SH" in bars:
        df = bars["000300.SH"]
    elif "SH000300" in bars:
        df = bars["SH000300"]
    else:
        key = next(iter(bars))
        df = bars[key]
    close = df["close"].astype(float)
    close.index = pd.to_datetime(close.index)
    return close


def summarize_arm(out_dir: Path, initial: float = INITIAL) -> dict:
    eq = _load_equity(out_dir)
    tr = _load_trades(out_dir)
    n_days = int(len(eq))
    net = _net_return(eq, initial)
    gross_eq = _gross_equity(eq, tr)
    buys = tr[tr["side"] == "BUY"] if not tr.empty else tr
    sells = tr[tr["side"] == "SELL"] if not tr.empty else tr
    sx0 = sells[sells["reason"] == SX0_REASON] if not sells.empty else sells
    fees = float(tr["commission"].sum()) if not tr.empty else 0.0
    notional = float(tr["notional"].sum()) if not tr.empty else 0.0
    return {
        "out_dir": str(out_dir),
        "n_days": n_days,
        "final": float(eq.iloc[-1]) if n_days else initial,
        "net_return": net,
        "gross_net_return": _net_return(gross_eq, initial),
        "max_dd": _max_dd(eq),
        "ann": _ann(net, n_days),
        "buys": int(len(buys)),
        "sells": int(len(sells)),
        "fees": fees,
        "turnover_vs_initial": notional / initial if initial else float("nan"),
        "sx0_sells": int(len(sx0)),
        "sx0_days": int(sx0["date"].nunique()) if not sx0.empty else 0,
        "equity": eq,
        "gross_equity": gross_eq,
        "trades": tr,
    }


def pair_window(
    *,
    name: str,
    control_dir: Path,
    cand_dir: Path,
    pred_path: Path,
    qlib_root: Path | None,
    start: str,
    end: str,
    bootstrap: bool,
) -> dict:
    c = summarize_arm(control_dir)
    x = summarize_arm(cand_dir)
    delta = x["net_return"] - c["net_return"]
    delta_gross = x["gross_net_return"] - c["gross_net_return"]
    delta_ann_excess = None
    bench_ann = None
    if qlib_root is not None:
        bench = _load_benchmark(qlib_root, start, end)
        idx = c["equity"].index.intersection(x["equity"].index)
        b = bench.reindex(idx).ffill()
        if len(b.dropna()) >= 2:
            b0 = float(b.dropna().iloc[0])
            b1 = float(b.dropna().iloc[-1])
            bench_net = b1 / b0 - 1.0
            n = len(idx)
            bench_ann = _ann(bench_net, n)
            c["ann_excess"] = c["ann"] - bench_ann
            x["ann_excess"] = x["ann"] - bench_ann
            delta_ann_excess = x["ann_excess"] - c["ann_excess"]
    qx = _quarter_net(x["equity"])
    qc = _quarter_net(c["equity"])
    qdelta = (qx - qc).reindex(qx.index.union(qc.index)).sort_index()
    qvals = [float(v) for v in qdelta.values if np.isfinite(v)]
    n_q = len(qvals)
    n_neg = sum(1 for v in qvals if v < 0)
    n_pos = sum(1 for v in qvals if v > 0)
    majority_negative = (n_q > 0) and (n_neg / n_q > 0.5)
    single_quarter_driven = (n_q >= 2) and (delta > 0) and (n_pos <= 1)
    boot = None
    if bootstrap:
        mean, lo, hi = moving_block_bootstrap_delta(
            _daily_ret(x["equity"]), _daily_ret(c["equity"])
        )
        boot = {"mean": mean, "ci95_lo": lo, "ci95_hi": hi}
    # Reconstruct SX0 also_bottom from candidate sells vs that day's bottom reason overlap is
    # not C's book. Report executed SX0 plus also_bottom if encoded; else leave to trades.
    sx0 = x["trades"]
    sx0 = (
        sx0[(sx0["side"] == "SELL") & (sx0["reason"] == SX0_REASON)]
        if not sx0.empty
        else sx0
    )
    bottom_x = (
        x["trades"][
            (x["trades"]["side"] == "SELL")
            & (x["trades"]["reason"].astype(str).str.startswith("topk_drop"))
        ]
        if not x["trades"].empty
        else x["trades"]
    )
    c_summary = (Path(control_dir) / "summary.txt").read_text(encoding="utf-8")
    x_summary = (Path(cand_dir) / "summary.txt").read_text(encoding="utf-8")
    return {
        "window": name,
        "pred_path": str(pred_path),
        "pred_md5": _md5(pred_path) if pred_path.is_file() else None,
        "start": start,
        "end": end,
        "control": {k: v for k, v in c.items() if k not in {"equity", "gross_equity", "trades"}},
        "candidate": {k: v for k, v in x.items() if k not in {"equity", "gross_equity", "trades"}},
        "delta_net_return": delta,
        "delta_gross_net_return": delta_gross,
        "delta_ann_excess": delta_ann_excess,
        "bench_ann": bench_ann,
        "quarter_delta": {str(k): float(v) for k, v in qdelta.items()},
        "majority_negative": majority_negative,
        "single_quarter_driven": single_quarter_driven,
        "bootstrap": boot,
        "sx0_sells": int(len(sx0)) if sx0 is not None and not getattr(sx0, "empty", True) else 0,
        "sx0_days": int(sx0["date"].nunique()) if sx0 is not None and not getattr(sx0, "empty", True) else 0,
        "control_summary_head": c_summary.splitlines()[:8],
        "candidate_summary_head": x_summary.splitlines()[:8],
        "x_bottom_sells": int(len(bottom_x)) if bottom_x is not None and not getattr(bottom_x, "empty", True) else 0,
    }


def verdict(w2025: dict, w2026: dict) -> str:
    d25 = w2025["delta_net_return"]
    d26 = w2026["delta_net_return"]
    s1 = (d25 > 0) and (d26 > 0)
    if w2025.get("control") and w2025["candidate"].get("ann_excess") is not None:
        s1 = s1 and (
            w2025["candidate"]["ann_excess"] > w2025["control"]["ann_excess"]
            and w2026["candidate"]["ann_excess"] > w2026["control"]["ann_excess"]
        )
    s2 = False
    if w2026.get("bootstrap"):
        s2 = w2026["bootstrap"]["ci95_lo"] > 0
    s3 = (not w2026["majority_negative"]) and (not w2026["single_quarter_driven"])
    sx0_days = w2025["sx0_days"] + w2026["sx0_days"]
    flip = (d25 * d26 < 0) or bool(w2026["majority_negative"])
    if flip:
        return "SCORE_EXIT_FLIP"
    gross_both_pos = (
        w2025["delta_gross_net_return"] > 0 and w2026["delta_gross_net_return"] > 0
    )
    if (not flip) and gross_both_pos and (not s1):
        return "SCORE_EXIT_COST_ERASED"
    if sx0_days == 0 or (not s1) or (not s2) or w2026["single_quarter_driven"]:
        return "SCORE_EXIT_NO_EDGE"
    if s1 and s2 and s3:
        return "SCORE_EXIT_CANDIDATE"
    return "SCORE_EXIT_NO_EDGE"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-2025", type=Path, required=True)
    ap.add_argument("--candidate-2025", type=Path, required=True)
    ap.add_argument("--control-2026", type=Path, required=True)
    ap.add_argument("--candidate-2026", type=Path, required=True)
    ap.add_argument("--pred-2025", type=Path, required=True)
    ap.add_argument("--pred-2026", type=Path, required=True)
    ap.add_argument("--qlib-data-root", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    w2025 = pair_window(
        name="2025",
        control_dir=args.control_2025,
        cand_dir=args.candidate_2025,
        pred_path=args.pred_2025,
        qlib_root=args.qlib_data_root,
        start="20250103",
        end="20251231",
        bootstrap=False,
    )
    w2026 = pair_window(
        name="2026",
        control_dir=args.control_2026,
        cand_dir=args.candidate_2026,
        pred_path=args.pred_2026,
        qlib_root=args.qlib_data_root,
        start="20260106",
        end="20260914",
        bootstrap=True,
    )
    lab = verdict(w2025, w2026)
    payload = {
        "verdict": lab,
        "s0_same_pred_hash_2025": w2025["pred_md5"],
        "s0_same_pred_hash_2026": w2026["pred_md5"],
        "2025": w2025,
        "2026": w2026,
        "gates": {
            "S1": (w2025["delta_net_return"] > 0) and (w2026["delta_net_return"] > 0),
            "S2": bool(w2026.get("bootstrap") and w2026["bootstrap"]["ci95_lo"] > 0),
            "S3": (not w2026["majority_negative"]) and (not w2026["single_quarter_driven"]),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md = args.out.with_suffix(".md")
    boot = w2026.get("bootstrap") or {}
    lines = [
        "# T6-SX0 pair report",
        "",
        f"**verdict**: `{lab}`",
        "",
        f"- 2025 ΔNetReturn = {w2025['delta_net_return']:+.6%} (X {w2025['candidate']['net_return']:+.6%} vs C {w2025['control']['net_return']:+.6%})",
        f"- 2026 ΔNetReturn = {w2026['delta_net_return']:+.6%} (X {w2026['candidate']['net_return']:+.6%} vs C {w2026['control']['net_return']:+.6%})",
        f"- 2026 bootstrap 95% CI = [{boot.get('ci95_lo')}, {boot.get('ci95_hi')}]",
        f"- 2026 majority_negative={w2026['majority_negative']} single_quarter_driven={w2026['single_quarter_driven']}",
        f"- 2026 quarter ΔNetReturn: {w2026['quarter_delta']}",
        f"- SX0 sells/days: 2025 {w2025['sx0_sells']}/{w2025['sx0_days']}; 2026 {w2026['sx0_sells']}/{w2026['sx0_days']}",
        f"- pred md5 2025 `{w2025['pred_md5']}` / 2026 `{w2026['pred_md5']}`",
        f"- control 2025 `{w2025['control']['out_dir']}`",
        f"- candidate 2025 `{w2025['candidate']['out_dir']}`",
        f"- control 2026 `{w2026['control']['out_dir']}`",
        f"- candidate 2026 `{w2026['candidate']['out_dir']}`",
        "",
        "Gates: S0 semantic isolation by construction (same pred, X only adds SX0).",
        f"S1 two-window ΔNetReturn>0: {payload['gates']['S1']}; "
        f"S2 CI lower>0: {payload['gates']['S2']}; "
        f"S3: {payload['gates']['S3']}.",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(lab, flush=True)
    print(md, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
